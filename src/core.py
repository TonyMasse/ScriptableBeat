import os
import yaml
import logging
import time
import datetime
import json
import threading
from locallib.pyLogBeat import PyLogBeatClient

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
    logging.info('Shutdown requested. 🛑')
    global are_we_running
    are_we_running = False

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
            os.system('pip3 install ' + module)


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

def run_script(script):
    script_language = config.get('scriptablebeat', {}).get('language', 'bash')
    if script_language == 'python':
        os.system('python3 ' + script)

    if script_language == 'bash':
        os.system('bash ' + script)
    
    if script_language == 'powershell':
        os.system('pwsh ' + script)

def run_script_first_run(config):
    # Run the first run script only once, at the very first startup
    script__first_run = config.get('scriptablebeat', {}).get('scripts', {}).get('first_run', None)

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
            run_script(first_script_file_path)
    except Exception as e:
        logging.error('Error running first run script: %s', str(e))

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
    run_script_first_run(config)

    # script__first_run = config.get('scriptablebeat', {}).get('scripts', {}).get('first_run', None)
    # script__startup_run = config.get('scriptablebeat', {}).get('scripts', {}).get('startup_run', '')
    # script__scheduled_run = config.get('scriptablebeat', {}).get('scripts', {}).get('scheduled_run', '')

    # Do stuff
    logging.debug('Do dummy stuff for 10 seconds...') # TODO: Remove this
    time.sleep(10) # TODO: Remove this
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
