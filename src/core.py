import signal
import os
import yaml
import logging
import time
import datetime
import json
import threading
from locallib.pyLogBeat import PyLogBeatClient
import subprocess
import select
import glob

__version__ = '1.0'
beat_name = 'ScriptableBeat'
are_we_running = True
are_we_paused = False

# Set the logging level and format
logging.basicConfig(level=logging.INFO if os.environ.get('MODE') != 'DEV' else logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Get the base directory of the script
base_script_dir = os.path.dirname(os.path.realpath(__file__))

# Set the path to the State folder
state_folder_path = '/beats/scriptablebeat/state' if os.environ.get('MODE') != 'DEV' else os.path.join(base_script_dir, '..', 'state.dev')

# File to store the file positions
file_positions_file_path = os.path.join(state_folder_path, 'file_positions.json')

# Lock for thread-safe access to file_positions_file
file_positions_file_lock = threading.Lock()

def read_config():
    # Define the path to the config file
    config_folder_path = '/beats/scriptablebeat/config' if os.environ.get('MODE') != 'DEV' else os.path.join(base_script_dir, '..', 'config.dev')
    config_file_name = 'scriptablebeat.yml'
    config_file_path = os.path.join(config_folder_path, config_file_name)

    logging.info('Reading configuration from "%s" ...', config_file_path)
    try:
        with open(config_file_path, 'r') as config_file:
            config_data = yaml.safe_load(config_file)
            logging.info('Configuration loaded.')
        return config_data
    except FileNotFoundError:
        logging.error('Config file "%s" not found.', config_file_path)
        return None
    except Exception as e:
        logging.error('Error reading config file: %s', str(e))
        return None

def pause():
    global are_we_paused
    are_we_paused = True

def unpause():
    global are_we_paused
    are_we_paused = False

def reconnect_to_lumberjack_server(lumberjack_client, exception_safe = True):
    if lumberjack_client is None:
        logging.error('No valid Lumberjack object to try to reconnect. Failing to reconnect.')
        return None

    # Have you tried turning it off and on again?

    # First Pause the scheduler
    pause()

    are_we_connected = False
    lumberjack_retry_delay = 5
    lumberjack_max_retry = 10000
    second_counter = 0
    lumberjack_retry = 0
    while are_we_running and not are_we_connected and lumberjack_max_retry > lumberjack_retry:
        second_counter += 1
        if second_counter >= lumberjack_retry_delay:
            second_counter = 0
            lumberjack_retry += 1

            try:
                lumberjack_client.close()
            except Exception as e:
                logging.error('Error closing Lumberjack connection: %s', str(e))
    
            try:
                logging.info('Connecting to Lumberjack Server (attempt %s)...', lumberjack_retry)
                are_we_connected = False
                lumberjack_client.connect()
                are_we_connected = True
            except Exception as e:
                logging.error('Error connecting to Lumberjack Server: %s. Will retry to connect in %s seconds', str(e), lumberjack_retry_delay)
                are_we_connected = False
        time.sleep(1)

    if not exception_safe and are_we_running and not are_we_connected and lumberjack_max_retry <= lumberjack_retry:
        raise Exception("Too many retries to connect to Lumberjack Server.")

    # Then unpause the scheduler
    if are_we_running:
        unpause()

    return None

def connect_to_lumberjack_server(config):
    if config:
        # Access specific configuration values
        output = config.get('output', {})
        output__logstash = output.get('logstash', {})
        logstash__hosts = output__logstash.get('hosts', ['opencollector:5044'])
        logstash__host = logstash__hosts[0].split(":")[0]
        logstash__port = int(logstash__hosts[0].split(":")[1])
        logstash__ssl_enable = output__logstash.get('ssl_enable', False)
        logstash__timeout = output__logstash.get('timeout', 30)

        logging.info('Output configuration: %s', output)

        # Create the client
        client = PyLogBeatClient(
            logstash__host,
            logstash__port,
            ssl_enable=logstash__ssl_enable,
            timeout=logstash__timeout
        )

        # Connect to the client
        logging.info('Connecting to Lumberjack Server on host "%s", port "%s"...', logstash__host, logstash__port)
        try:
            reconnect_to_lumberjack_server(client, False)
            logging.info('Connected to Lumberjack Server (%s:%s).', logstash__host, logstash__port)
            return client
        except Exception as e:
            logging.error('Error connecting to Lumberjack Server: %s', str(e))
            return None

def send_heartbeat(lumberjack_client, status_code, status_description):
    if lumberjack_client is None:
        logging.error('No connection to Lumberjack server is established. Heartbeat message cannot be sent.')
        return None

    # Time in seconds since the epoch
    now = datetime.datetime.now()
    nanoseconds_since_epoch = int(time.mktime(now.timetuple())) * 1000000000
    time_ISO8601 = now.isoformat()

    # Get the hostname
    hostname = os.uname()[1]

    # Get the beat identifier from the configuration
    beatIdentifier = config.get(beat_name.lower(), {}).get('beatIdentifier', '')

    heartbeat_message = {
        'service_name': beat_name.lower(),
        'service_version': __version__,
        'time': {
            'seconds': int(nanoseconds_since_epoch) # OC is expecting this in nanoseconds
        },
        'status': {
            'code': status_code,
            'description': status_description
        }
    }

    message = {
        '@timestamp': time_ISO8601,
        'fullyqualifiedbeatname': "_".join([beat_name.lower(), beatIdentifier]),
        '@version': '1',
        'beat': {
            'hostname': hostname,
            'version': __version__,
            'name': hostname
        },
        'host': {
            'name': hostname
        },
        'heartbeat': json.dumps(heartbeat_message)
    }

    logging.debug('Sending Heartbeat with status "%s" (%s)... ❤️', status_description, status_code)

    try:
        lumberjack_client.send([message])
    except Exception as e:
        logging.error('Error sending message to Lumberjack server: %s', str(e))


    # Results in this in LogStash:
    # {
    #                 "@timestamp" => 2018-01-02T01:02:03.000Z,
    #     "fullyqualifiedbeatname" => "scriptablebeat_478_Test_001",
    #                   "@version" => "1",
    #                       "beat" => {
    #         "hostname" => "66f91015e36b",
    #          "version" => "0.1",
    #             "name" => "66f91015e36b"
    #     },
    #                       "host" => {
    #         "name" => "66f91015e36b"
    #     },
    #                  "heartbeat" => "{\"service_name\": \"scriptablebeat\", \"service_version\": \"0.1\", \"time\": {\"seconds\": 1693950876000000000}, \"status\": {\"code\": 1, \"description\": \"Service started\"}}"
    # }

    # Model from WebhookBeat:
    # - Startup:
    # {
    #                 "@timestamp" => 2023-09-05T21:29:45.508Z,
    #     "fullyqualifiedbeatname" => "webhookbeat_170_WC_Rob_N",
    #                   "@version" => "1",
    #                       "beat" => {
    #         "hostname" => "e92561d0cd37",
    #          "version" => "6.6.0",
    #             "name" => "e92561d0cd37"
    #     },
    #                       "host" => {
    #         "name" => "e92561d0cd37"
    #     },
    #                  "heartbeat" => "{\"service_name\":\"webhook\",\"service_version\":\"\",\"time\":{\"seconds\":1693949385508335700},\"status\":{\"code\":1,\"description\":\"Service started\"}}"
    # }
    #
    # - Heartbeat:
    # {
    #               "@timestamp" => 2023-09-13T15:44:23.501Z,
    #   "fullyqualifiedbeatname" => "webhookbeat_170_WC_Rob_N",
    #                 "@version" => "1",
    #                     "beat" => {
    #         "hostname" => "e92561d0cd37",
    #         "version" => "6.6.0",
    #             "name" => "e92561d0cd37"
    #     },
    #                     "host" => {
    #         "name" => "e92561d0cd37"
    #     },
    #                "heartbeat" => "{\"service_name\":\"webhook\",\"service_version\":\"\",\"time\":{\"seconds\":1694619863501683900},\"status\":{\"code\":2,\"description\":\"Service is Running\"}}"
    # }

def heartbeat_background_job(lumberjack_client, status_code = 2, status_description = 'Service is Running'):
    # Check if the heartbeat is disabled
    heartbeatdisabled = config.get('scriptablebeat', {}).get('heartbeatdisabled', False)
    if heartbeatdisabled:
        logging.info('Heartbeat is disabled. 💔')
        return None

    # Send the Startup message
    send_heartbeat(lumberjack_client, 1, 'Service started')

    heartbeatinterval = config.get('scriptablebeat', {}).get('heartbeatinterval', 60)
    logging.info('Heartbeat interval is %s seconds.', heartbeatinterval)

    # Cycling through the heartbeat interval
    # At one second intervals, so we can check for a shutdown request
    second_counter = 0
    while are_we_running:
        second_counter += 1
        time.sleep(1)
        if second_counter >= heartbeatinterval:
            second_counter = 0
            send_heartbeat(lumberjack_client, status_code, status_description)
    send_heartbeat(lumberjack_client, 3, 'Service is Stopped')

def initiate_shutdown():
    global are_we_running
    if are_we_running:
        logging.info('Shutdown initiated. 🛑')
    are_we_running = False

# Handle SIGTERM and SIGHUP signals
def handle_signals(signum, frame):
    logging.info("Received signal %s. Shutting down gracefully...", signum)
    initiate_shutdown()

def lumberjack_safe_send(lumberjack_client, jsonPayload):
    if lumberjack_client is None:
        logging.debug('No connection to Lumberjack server is established. Message cannot be sent.')
        return None

    try:
        lumberjack_client.connect() # Trying to reconnect if we had lost the connection
        lumberjack_client.send(jsonPayload)
    except Exception as e:
        logging.error('Error sending message to Lumberjack server: %s', str(e))

        # Trying to reconnect completely
        reconnect_to_lumberjack_server(lumberjack_client)

def send_message_to_stream(lumberjack_client, log_payload = None, error_payload = None):
    if lumberjack_client is None:
        logging.debug('No connection to Lumberjack server is established. Message cannot be sent.')
        return None

    # Time in seconds since the epoch
    time_ISO8601 = datetime.datetime.now().isoformat()

    # Get the hostname
    hostname = os.uname()[1]

    # Get the beat identifier from the configuration
    beatIdentifier = config.get(beat_name.lower(), {}).get('beatIdentifier', '')

    message = {
        '@timestamp': time_ISO8601,
        'fullyqualifiedbeatname': "_".join([beat_name.lower(), beatIdentifier]),
        '@version': '1',
        'beat': {
            'hostname': hostname,
            'version': __version__,
            'name': hostname
        },
        'host': {
            'name': hostname
        }
    }

    if log_payload is not None:
        message['message'] = log_payload

    if error_payload is not None:
        message['errormessage'] = error_payload

    lumberjack_safe_send(lumberjack_client, [message])

def download_modules(config):
    # Read from the configuration the list of required packages/modules required by the script
    # Download/update each of the said packages/modules

    logging.info('Downloading required modules...')

    # Access specific configuration values
    script_language = config.get('scriptablebeat', {}).get('language', 'bash')
    script_required_modules = config.get('scriptablebeat', {}).get('required_modules', [])

    logging.debug('Language: %s', script_language)
    logging.debug('Required modules: %s', script_required_modules)

    if script_language == 'python':
        # Install the required modules
        for module in script_required_modules:
            logging.info('Installing Python module: %s ...', module)
            os.system('pip3 install --no-input --no-color --disable-pip-version-check --quiet --quiet ' + module)


    if script_language == 'bash':
        # Install the required modules
        for module in script_required_modules:
            logging.info('Installing system module or command: %s ...', module)
            os.system('apt-get install -y ' + module)
    
    if script_language == 'powershell':
        # Install the required modules
        for module in script_required_modules:
            logging.info('Installing Powertshell module: %s ...', module)
            os.system('Install-Module -Name ' + module)

def run_script(script, capture_output = False, lumberjack_client = None):
    script_language = config.get('scriptablebeat', {}).get('language', 'bash')
    data_stream__format = config.get('scriptablebeat', {}).get('data_stream', {}).get('format', 'text')
    data_stream__monitor_sources = config.get('scriptablebeat', {}).get('data_stream', {}).get('moniror_sources', [])

    data_stream__stdout__report_as_log_in_stream = config.get('scriptablebeat', {}).get('data_stream', {}).get('stdout', {}).get('report_as_log_in_stream', False)
    data_stream__stdout__report_as_error_in_stream = config.get('scriptablebeat', {}).get('data_stream', {}).get('stdout', {}).get('report_as_error_in_stream', False)
    data_stream__stdout__log_in_beats_log = config.get('scriptablebeat', {}).get('data_stream', {}).get('stdout', {}).get('log_in_beats_log', False)

    data_stream__stderr__report_as_log_in_stream = config.get('scriptablebeat', {}).get('data_stream', {}).get('stderr', {}).get('report_as_log_in_stream', False)
    data_stream__stderr__report_as_error_in_stream = config.get('scriptablebeat', {}).get('data_stream', {}).get('stderr', {}).get('report_as_error_in_stream', False)
    data_stream__stderr__log_in_beats_log = config.get('scriptablebeat', {}).get('data_stream', {}).get('stderr', {}).get('log_in_beats_log', False)

    if script_language == 'python':
        logging.info('Running Python script from local file "%s"...', script)
        process = subprocess.Popen(["python3", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if script_language == 'bash':
        logging.info('Running Bash script from local file "%s"...', script)
        process = subprocess.Popen(["bash", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if script_language == 'powershell':
        logging.info('Running PowerShell script from local file "%s"...', script)
        process = subprocess.Popen(["pwsh", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if process is None:
        logging.error('Error running script.')
        return 255 # Bad exectution (non 0)

    if capture_output:
        # Create a set to hold file descriptors for monitoring
        fd_set = [process.stdout, process.stderr]

        # Monitor the command's output in real-time
        while fd_set:
            ready_to_read, _, _ = select.select(fd_set, [], [])
            for fd in ready_to_read:
                line = fd.readline()
                if line:
                    # if fd is process.stdout and data_stream__monitor_sources.count('stdout') > 0:
                    if fd is process.stdout and 'stdout' in data_stream__monitor_sources:
                        send_message_to_stream(lumberjack_client, line if data_stream__stdout__report_as_log_in_stream else None, line if data_stream__stdout__report_as_error_in_stream else None)
                        if data_stream__stdout__log_in_beats_log:
                            logging.info("External script STDOUT: %s", line)
                    # elif fd is process.stderr and data_stream__monitor_sources.count('stderr') > 0:
                    elif fd is process.stderr and 'stderr' in data_stream__monitor_sources:
                        send_message_to_stream(lumberjack_client, line if data_stream__stderr__report_as_log_in_stream else None, line if data_stream__stderr__report_as_error_in_stream else None)
                        if data_stream__stderr__log_in_beats_log:
                            logging.error("External script STDERR: %s", line)
                else:
                    fd_set.remove(fd)

    # Wait for the command to finish and grab the return code
    exit_code = process.wait()

    logging.info('Script run finished ("%s")', script)
    return exit_code

def run_script_first_run(config, lumberjack_client = None):
    # Run the first run script only once, at the very first startup
    script__first_run = config.get('scriptablebeat', {}).get('scripts', {}).get('first_run', None)
    data_stream__capture__first_run = config.get('scriptablebeat', {}).get('data_stream', {}).get('capture', {}).get('first_run', False)

    first_script_file_name = 'script.first_run'
    first_script_file_path = os.path.join(state_folder_path, first_script_file_name)

    try:
        if os.path.exists(first_script_file_path):
            logging.info("Not running first run script as it has already been run.")
            return 0 # Success
        else:
            logging.info('Storing first_run script into local file: "%s"...', first_script_file_path)
            with open(first_script_file_path, "w") as file:
                file.write(script__first_run)

            logging.info("Running first_run script...")
            return run_script(first_script_file_path, data_stream__capture__first_run, lumberjack_client)
    except Exception as e:
        logging.error('Error running first run script: %s', str(e))
        return 255 # Bad exectution (non 0)

def run_script_startup_run(config, lumberjack_client = None):
    # Run the startup run script at each startup
    script__startup_run = config.get('scriptablebeat', {}).get('scripts', {}).get('startup_run', None)
    data_stream__capture__startup_run = config.get('scriptablebeat', {}).get('data_stream', {}).get('capture', {}).get('startup_run', False)

    startup_script_file_name = 'script.startup_run'
    startup_script_file_path = os.path.join(state_folder_path, startup_script_file_name)

    try:
        logging.info('Storing startup_run script into local file: "%s"...', startup_script_file_path)
        with open(startup_script_file_path, "w") as file:
            file.write(script__startup_run)

        logging.info("Running startup_run script...")
        return run_script(startup_script_file_path, data_stream__capture__startup_run, lumberjack_client)
    except Exception as e:
        logging.error('Error running startup run script: %s', str(e))
        return 255 # Bad exectution (non 0)

def run_script_scheduled_run(config, lumberjack_client = None):
    # Run the scheduled run script on each tick of the scheduler
    script__scheduled_run = config.get('scriptablebeat', {}).get('scripts', {}).get('scheduled_run', None)
    data_stream__capture__scheduled_run = config.get('scriptablebeat', {}).get('data_stream', {}).get('capture', {}).get('scheduled_run', False)

    scheduled_script_file_name = 'script.scheduled_run'
    scheduled_script_file_path = os.path.join(state_folder_path, scheduled_script_file_name)

    try:
        logging.info('Storing scheduled_run script into local file: "%s"...', scheduled_script_file_path)
        with open(scheduled_script_file_path, "w") as file:
            file.write(script__scheduled_run)

        logging.info("Running scheduled_run script...")
        return run_script(scheduled_script_file_path, data_stream__capture__scheduled_run, lumberjack_client)
    except Exception as e:
        logging.error('Error running scheduled run script: %s', str(e))
        return 255 # Bad exectution (non 0)

def interval_to_seconds(interval, default = 60):
    # Convert the scheduler_interval from the config into seconds
    interval_seconds = default
    if interval.endswith('s'):
        interval_seconds = int(interval[:-1])
    elif interval.endswith('m'):
        interval_seconds = int(interval[:-1]) * 60
    elif interval.endswith('h'):
        interval_seconds = int(interval[:-1]) * 60 * 60
    elif interval.endswith('d'):
        interval_seconds = int(interval[:-1]) * 60 * 60 * 24
    else:
        interval_seconds = int(interval)

    if interval_seconds is None or interval_seconds < 1:
        interval_seconds = default

    return interval_seconds

def script_scheduled_run_background_job(config, lumberjack_client):
    scheduler_interval = config.get('scriptablebeat', {}).get('scheduler', {}).get('frequency', '1m')
    scheduler_interval_seconds = interval_to_seconds(scheduler_interval, 60)
        
    logging.info('Scheduler interval is %s seconds ("%s" per the configuration). ⏱️', scheduler_interval_seconds, scheduler_interval)

    # Run the first occurence
    run_script_scheduled_run(config, lumberjack_client)

    # Cycling through the scheduler interval
    # At one second intervals, so we can check for a shutdown request
    second_counter = 0
    while are_we_running:
        second_counter += 1
        time.sleep(1)
        if second_counter >= scheduler_interval_seconds:
            second_counter = 0
            if not are_we_paused:
                run_script_scheduled_run(config, lumberjack_client)
            else:
                logging.info('Scheduler is paused.')

def persist_file_positions(file_info):
    with file_positions_file_lock:
        try:
            logging.debug('Storing file positions into local file: "%s"...', file_positions_file_path)
            with open(file_positions_file_path, "w") as file:
                json.dump(file_info, file)
        except Exception as e:
            logging.error('Error storing file positions: %s', str(e))

def read_file_positions():
    if os.path.exists(file_positions_file_path):
        with file_positions_file_lock:
            try:
                logging.debug('Reading file positions from local file: "%s"...', file_positions_file_path)
                with open(file_positions_file_path, "r") as file:
                    return json.load(file)
            except Exception as e:
                logging.error('Error reading file positions: %s', str(e))
                return {}
    else:
        logging.info('No file positions found ("%s"). Starting afresh with a blank list.', file_positions_file_path)
        return {}

def monitor_files_background_job():
    # Get the globs from the configuration
    filenameGlobs = config.get('scriptablebeat', {}).get('data_stream', {}).get('files', {}).get('paths', [])
    data_stream__monitor_sources = config.get('scriptablebeat', {}).get('data_stream', {}).get('moniror_sources', [])
    filemonitoring__report_as_log_in_stream = config.get('scriptablebeat', {}).get('data_stream', {}).get('files', {}).get('report_as_log_in_stream', True)
    filemonitoring__report_as_error_in_stream = config.get('scriptablebeat', {}).get('data_stream', {}).get('files', {}).get('report_as_error_in_stream', False)
    filemonitoring__log_in_beats_log = config.get('scriptablebeat', {}).get('data_stream', {}).get('files', {}).get('log_in_beats_log', False)
    filemonitoring__after_reading = config.get('scriptablebeat', {}).get('data_stream', {}).get('files', {}).get('after_reading', 'leave_as_is')
    filemonitoring__folder_left_empty = config.get('scriptablebeat', {}).get('data_stream', {}).get('files', {}).get('folder_left_empty', 'leave_as_is')
    filemonitoring__persist_positions_every = config.get('scriptablebeat', {}).get('data_stream', {}).get('files', {}).get('persist_positions_every', '2s')
    filemonitoring__persist_positions_every_seconds = interval_to_seconds(filemonitoring__persist_positions_every, 5)

    if 'files' not in data_stream__monitor_sources:
        logging.info('Not set to monitor file ("files" not set in scriptablebeat.data_stream.monitor_sources).')
        return None

    if filenameGlobs is None or len(filenameGlobs) == 0:
        logging.info('No files to monitor. (No path provided in scriptablebeat.data_stream.files.paths)')
        return None

    # Dictionary to store file positions and sizes
    file_info = read_file_positions()

    # To debounce the file positions saving
    last_time_file_positions_saved = time.time()

    while are_we_running:
        try:
            # Process the list of globs
            matching_files = []
            for pattern in filenameGlobs:
                matching_files.extend(glob.glob(pattern))

            for file_path in matching_files:
                # logging.debug(f"Checking file '{file_path}'...") # TODO: Remove this line
                try:
                    # Check if the file is already in the dictionary
                    if file_path not in file_info:
                        file_info[file_path] = {'position': 0, 'size': 0}

                    # Get the current file size
                    current_size = os.path.getsize(file_path)

                    # Check if the file size hasn't grown since the last read
                    if current_size == file_info[file_path]['size']:
                        if filemonitoring__after_reading == 'delete':
                            logging.debug(f"File '{file_path}' has not grown since last cycle. Deleting... 🗑️") # TODO: Remove this line
                            os.remove(file_path)
                            # Remove the file from the file_info dictionary
                            file_info.pop(file_path, None)

                            # Check if the directory is empty after deleting the file
                            if filemonitoring__folder_left_empty == 'delete':
                                dir_path = os.path.dirname(file_path)
                                if not os.listdir(dir_path):
                                    logging.debug(f"Directory '{dir_path}' is now empty. Deleting...") # TODO: Remove this line
                                    os.rmdir(dir_path)
                        elif filemonitoring__after_reading == 'flush_to_empty' and current_size > 0:
                            logging.debug(f"File '{file_path}' has not grown since last cycle. Flushing to empty...")
                            with open(file_path, 'w') as file:
                                file.truncate(0)
                            # Reset the file position
                            file_info[file_path] = {'position': 0, 'size': 0}

                    else:
                        # Check if the file has shrunk or grown
                        if current_size < file_info[file_path]['size']:
                            logging.debug(f"File '{file_path}' has shrunk. Reading from the beginning...")
                            file_info[file_path] = {'position': 0, 'size': 0}
                        else:
                            logging.debug(f"File '{file_path}' has grown. Reading from previous position...")

                        # Tail the file
                        with open(file_path, 'r') as file:
                            # Move to the last remembered position
                            file.seek(file_info[file_path]['position'])

                            line = True
                            while are_we_running and line:
                                line = file.readline()

                                if line:
                                    # Send the line to the Lumberjack Server
                                    if filemonitoring__report_as_log_in_stream or filemonitoring__report_as_error_in_stream:
                                        send_message_to_stream(lumberjack_client, line if filemonitoring__report_as_log_in_stream else None, line if filemonitoring__report_as_error_in_stream else None)

                                    # And/or to the Beats' log
                                    if filemonitoring__log_in_beats_log:
                                        logging.info("External script FILE: %s", line)

                                    # Update the current position in the file
                                    file_info[file_path]['position'] = file.tell()
                                    logging.debug(f"File '{file_path}' - New position: {file_info[file_path]['position']}") # TODO: Remove this line
                                else:
                                    time.sleep(0.1)
                                    logging.debug(f"File '{file_path}' - No more line in file.") # TODO: Remove this line

                        # Update the file size in the dictionary
                        file_info[file_path]['size'] = current_size

                except FileNotFoundError:
                    # Handle file deletion
                    file_info.pop(file_path, None)

                # Check if it's time to save the file_info to disk
                if time.time() - last_time_file_positions_saved >= filemonitoring__persist_positions_every_seconds:
                    persist_file_positions(file_info)
                    last_time_file_positions_saved = time.time()

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            time.sleep(1)

        # Hold a bit before checking again
        time.sleep(0.5)

    # Persist the file positions
    persist_file_positions(file_info)

if __name__ == "__main__":
    logging.info('--------------')
    logging.info('%s v%s - Starting - 🚀', beat_name, __version__)
    logging.info('--------------')
    logging.info('Press [CTRL] + [C] or send SIGTERM or SIGHUP to stop.')

    # Register the signal handler
    signal.signal(signal.SIGTERM, handle_signals)
    signal.signal(signal.SIGHUP, handle_signals)

    # Read the configuration
    config = read_config()

    if config is None:
        logging.error('No configuration found. Exiting.')
        exit(1)

    # Access specific configuration values
    beatIdentifier = config.get('scriptablebeat', {}).get('beatIdentifier', '')

    logging.debug('Configuration: %s', config)

    # Connect to the Lumberjack Server. It will try to connect every 10 seconds until it succeeds.
    lumberjack_client = None
    lumberjack_client_connection_retry_delay = 10
    try:
        second_counter = lumberjack_client_connection_retry_delay
        while are_we_running and lumberjack_client is None:
            second_counter += 1
            if second_counter >= lumberjack_client_connection_retry_delay:
                second_counter = 0
                lumberjack_client = connect_to_lumberjack_server(config)
                if lumberjack_client is None:
                    logging.error('No connection to Lumberjack server could be established. Retrying in %s seconds...', lumberjack_client_connection_retry_delay)
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info('Keyboard interrupt detected. Exiting.')

    if lumberjack_client is not None:
        # Set the heartbeat job in its own thread
        heartbeat_thread = threading.Thread(target=heartbeat_background_job, args=(lumberjack_client, 2, 'Service is Running'))
        heartbeat_thread.start()

        # Give a chance to the heartbeat to send the first message
        time.sleep(0.5)

        # - Start run sequence (only passing to next step on success of each step):
        #   - [x] Read the configuration file
        #   - [x] Establish comms with OC/SMA and other internal Beat required prep tasks
        #   - [x] Enable Heartbeat
        #   - [x] Read from the configuration the list of required packages/modules required by the script
        #   - [x] Download/update each of the said packages/modules
        #   - [x] Run First Run script (only once, at the very first startup)
        #   - [x] Run Startup script (at each startup)
        #   - [x] Run Scheduler

        # Get modules from config, then download and install them
        download_modules(config)

        # Create a separate thread for monitoring files in the background
        file_monitor_thread = threading.Thread(target=monitor_files_background_job)

        # Start the thread
        file_monitor_thread.start()

        # Run the first run script only once, at the very first startup
        first_run_exit_code = run_script_first_run(config, lumberjack_client)

        if first_run_exit_code == 0:
            # Run the startup script
            startup_run_exit_code = run_script_startup_run(config, lumberjack_client)

            if startup_run_exit_code == 0:
                # Set the schedulre to Not Paused
                unpause()

                # Set the scheduler job in its own thread
                scheduler_thread = threading.Thread(target=script_scheduled_run_background_job, args=(config, lumberjack_client))
                scheduler_thread.start()

                # Waiting to told to shutdown
                # At one second intervals, so we can check for a shutdown request
                try:
                    while are_we_running:
                        time.sleep(1)
                except KeyboardInterrupt:
                    logging.info('Keyboard interrupt detected. Exiting.')
            else:
                logging.error('Startup script failed with error code %s. Exiting.', startup_run_exit_code)
        else:
            logging.error('First run script failed with error code %s. Exiting.', first_run_exit_code)

    # Shutting down sequence
    initiate_shutdown()

    try:
        if scheduler_thread is not None:
            if scheduler_thread.is_alive():
                logging.info('Waiting for scheduler thread to finish...')
                scheduler_thread.join()
    except NameError:
        logging.debug('No scheduler thread to wait for.')

    try:
        if file_monitor_thread is not None:
            if file_monitor_thread.is_alive():
                logging.info('Waiting for file monitor thread to finish...')
                file_monitor_thread.join()
    except NameError:
        logging.debug('No file monitor thread to wait for.')

    try:
        if heartbeat_thread is not None:
            if heartbeat_thread.is_alive():
                logging.info('Waiting for heartbeat thread to finish...')
                heartbeat_thread.join()
    except NameError:
        logging.debug('No heartbeat thread to wait for.')

    # Turn the light on our way out...
    try:
        if lumberjack_client is not None:
            lumberjack_client.close() # 😘
    except NameError:
        logging.debug('No Lumberjack client to close.')

    logging.info('--------------')
    logging.info('%s v%s - Stopped - 🏁', beat_name, __version__)
    logging.info('--------------')
