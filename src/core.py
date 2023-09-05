import os
import yaml
import logging
from locallib.pyLogBeat import PyLogBeatClient

# Set the logging level and format
logging.basicConfig(level=logging.INFO if os.environ.get('MODE') != 'DEV' else logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
# logging.getLogger('pylogbeat').setLevel(logging.DEBUG)

logging.info('--------------')
logging.info('ScriptableBeat - Starting')

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

if __name__ == "__main__":
    # Read the configuration
    config = read_config()

    if config:
        # Access specific configuration values
        script__first_run = config.get('scripts', {}).get('first_run', None)
        script__run = config.get('scripts', {}).get('run', '')
        script__scheduled = config.get('scripts', {}).get('scheduled', '')
        script_language = config.get('language', 'bash')

        logging.debug('Configuration:')
        logging.debug('script_language: %s', script_language)
        logging.debug('script__first_run: %s', script__first_run)
        logging.debug('script__run: %s', script__run)
        logging.debug('script__scheduled: %s', script__scheduled)
