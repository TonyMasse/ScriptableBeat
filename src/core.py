import os
import yaml
import logging
from locallib.pyLogBeat import PyLogBeatClient

__version__ = '0.1'

# Set the logging level and format
logging.basicConfig(level=logging.INFO if os.environ.get('MODE') != 'DEV' else logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
# logging.getLogger('pylogbeat').setLevel(logging.DEBUG)

logging.info('--------------')
logging.info('ScriptableBeat v%s - Starting - 🚀', __version__)
logging.info('--------------')

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

def connect_to_lumberjack_server():
    # Read the configuration
    config = read_config()

    if config:
        # Access specific configuration values
        output = config.get('output', {})
        output__logstash = output.get('logstash', {})
        logstash__hosts = output__logstash.get('hosts', ['opencollector:5044'])
        logstash__host = logstash__hosts[0].split(":")[0]
        logstash__port = int(logstash__hosts[0].split(":")[1])
        logstash__ssl_enable = output__logstash.get('ssl_enable', False)

        logging.info('Output configuration: %s', output)

        # Create the client
        client = PyLogBeatClient(
            logstash__host,
            logstash__port,
            ssl_enable=logstash__ssl_enable
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

if __name__ == "__main__":
    # Read the configuration
    config = read_config()

    if config is None:
        logging.error('No configuration found. Exiting.')
        exit(1)

    # Access specific configuration values
    script__first_run = config.get('scriptablebeat', {}).get('scripts', {}).get('first_run', None)
    script__run = config.get('scriptablebeat', {}).get('scripts', {}).get('run', '')
    script__scheduled = config.get('scriptablebeat', {}).get('scripts', {}).get('scheduled', '')
    script_language = config.get('scriptablebeat', {}).get('language', 'bash')

    logging.debug('Configuration:')
    logging.debug('script_language: %s', script_language)
    logging.debug('script__first_run: %s', script__first_run)
    logging.debug('script__run: %s', script__run)
    logging.debug('script__scheduled: %s', script__scheduled)

    # Connect to the Lumberjack Server
    lumberjack_client = connect_to_lumberjack_server()
    if lumberjack_client is None:
        logging.error('No connection to Lumberjack serve could be established. Exiting.')
        exit(1)

    # Send the Startup message
    message = {'@timestamp': '2018-01-02T01:02:03',  '@version': '1', 'message': 'hello world'} # TODO: Replace with actual message
    lumberjack_client.send([message])

    # Turn the light on our way out...
    lumberjack_client.close() # 😘
