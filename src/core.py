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

__version__ = '0.1'
beat_name = 'ScriptableBeat'
are_we_running = True

# Set the logging level and format
logging.basicConfig(level=logging.INFO if os.environ.get('MODE') != 'DEV' else logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
# logging.getLogger('pylogbeat').setLevel(logging.DEBUG)

# Get the base directory of the script
base_script_dir = os.path.dirname(os.path.realpath(__file__))

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
            client.connect()
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

    lumberjack_client.send([message])

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
    logging.info('Shutdown initiated. 🛑')
    global are_we_running
    are_we_running = False

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

    lumberjack_client.send([message])

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
        return None

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
                            logging.info(line)
                    # elif fd is process.stderr and data_stream__monitor_sources.count('stderr') > 0:
                    elif fd is process.stderr and 'stderr' in data_stream__monitor_sources:
                        send_message_to_stream(lumberjack_client, line if data_stream__stderr__report_as_log_in_stream else None, line if data_stream__stderr__report_as_error_in_stream else None)
                        if data_stream__stderr__log_in_beats_log:
                            logging.error(line)
                else:
                    fd_set.remove(fd)

    # Wait for the command to finish
    process.wait()

    logging.info('Script run finished ("%s")', script)

def run_script_first_run(config, lumberjack_client = None):
    # Run the first run script only once, at the very first startup
    script__first_run = config.get('scriptablebeat', {}).get('scripts', {}).get('first_run', None)
    data_stream__capture__first_run = config.get('scriptablebeat', {}).get('data_stream', {}).get('capture', {}).get('first_run', False)

    state_folder_path = '/beats/scriptablebeat/state' if os.environ.get('MODE') != 'DEV' else os.path.join(base_script_dir, '..', 'state.dev')
    first_script_file_name = 'script.first_run'
    first_script_file_path = os.path.join(state_folder_path, first_script_file_name)

    try:
        if os.path.exists(first_script_file_path):
            logging.info("Not running first run script as it has already been run.")
        else:
            logging.info('Storing first_run script into local file: "%s"...', first_script_file_path)
            with open(first_script_file_path, "w") as file:
                file.write(script__first_run)

            logging.info("Running first_run script...")
            run_script(first_script_file_path, data_stream__capture__first_run, lumberjack_client)
    except Exception as e:
        logging.error('Error running first run script: %s', str(e))

def run_script_startup_run(config, lumberjack_client = None):
    # Run the startup run script at each startup
    script__startup_run = config.get('scriptablebeat', {}).get('scripts', {}).get('startup_run', None)
    data_stream__capture__startup_run = config.get('scriptablebeat', {}).get('data_stream', {}).get('capture', {}).get('startup_run', False)

    state_folder_path = '/beats/scriptablebeat/state' if os.environ.get('MODE') != 'DEV' else os.path.join(base_script_dir, '..', 'state.dev')
    startup_script_file_name = 'script.startup_run'
    startup_script_file_path = os.path.join(state_folder_path, startup_script_file_name)

    try:
        logging.info('Storing startup_run script into local file: "%s"...', startup_script_file_path)
        with open(startup_script_file_path, "w") as file:
            file.write(script__startup_run)

        logging.info("Running startup_run script...")
        run_script(startup_script_file_path, data_stream__capture__startup_run, lumberjack_client)
    except Exception as e:
        logging.error('Error running first run script: %s', str(e))

# TODO: Run the scheduled script
# TODO: Run the scheduled script at the scheduled time

if __name__ == "__main__":
    logging.info('--------------')
    logging.info('%s v%s - Starting - 🚀', beat_name, __version__)
    logging.info('--------------')

    # Read the configuration
    config = read_config()

    if config is None:
        logging.error('No configuration found. Exiting.')
        exit(1)

    # Access specific configuration values
    beatIdentifier = config.get('scriptablebeat', {}).get('beatIdentifier', '')

    logging.debug('Configuration: %s', config)

    # Connect to the Lumberjack Server
    lumberjack_client = connect_to_lumberjack_server(config)
    if lumberjack_client is None:
        logging.error('No connection to Lumberjack server could be established. Exiting.')
        exit(1)

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
    #   - [ ] Run First Run script (only once, at the very first startup)
    #   - [ ] Run Startup script (at each startup)
    #   - [ ] Run Scheduler

    # Get modules from config, then download and install them
    download_modules(config)

    # Run the first run script only once, at the very first startup
    run_script_first_run(config, lumberjack_client)

    # Run the startup script
    run_script_startup_run(config, lumberjack_client)

    # script__first_run = config.get('scriptablebeat', {}).get('scripts', {}).get('first_run', None)
    # script__startup_run = config.get('scriptablebeat', {}).get('scripts', {}).get('startup_run', '')
    # script__scheduled_run = config.get('scriptablebeat', {}).get('scripts', {}).get('scheduled_run', '')

    # Do stuff
    logging.debug('Do dummy stuff for 10 seconds...') # TODO: Remove this
    time.sleep(3) # TODO: Remove this
    initiate_shutdown() # TODO: Remove this
    logging.debug('Done doing dummy stuff') # TODO: Remove this

    # Shutting down sequence

    # Bring the threads to the yard...
    logging.info('Waiting for threads to finish...')
    heartbeat_thread.join()

    # Turn the light on our way out...
    lumberjack_client.close() # 😘

    logging.info('--------------')
    logging.info('%s v%s - Stopped - 🏁', beat_name, __version__)
    logging.info('--------------')
