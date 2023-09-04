import os
import yaml
import logging

# Set the logging level and format
logging.basicConfig(level=logging.INFO if os.environ.get('MODE') != 'DEV' else logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

logging.info('--------------')
logging.info('ScriptableBeat - Starting')

def read_config(config_file_path):
    logging.info('Reading configuration from "%s" ...', config_file_path)
    try:
        with open(config_file_path, 'r') as config_file:
            config_data = yaml.safe_load(config_file)
            logging.info('Configuration loaded.', config_file_path)
        return config_data
    except FileNotFoundError:
        logging.error('Config file "%s" not found.', config_file_path)
        return None
    except Exception as e:
        logging.error('Error reading config file: %s', str(e))
        return None

if __name__ == "__main__":
    # Define the path to the config file
    config_file_path = '/beats/scriptablebeat/config' if os.environ.get('MODE') != 'DEV' else '../config.dev'
    config_file_name = 'scriptablebeat.yml'
    config_file_path = os.path.join(config_file_path, config_file_name)

    # Read the configuration
    config = read_config(config_file_path)

    if config:
        # Access specific configuration values
        db_host = config.get('database', {}).get('host', 'localhost') # XXXX
        db_port = config.get('database', {}).get('port', 3306) # XXXX
        db_username = config.get('database', {}).get('username', 'myuser') # XXXX
        db_password = config.get('database', {}).get('password', 'mypassword') # XXXX

        script_language = config.get('language', 'bash')

        logging.debug('Database Configuration:')
        logging.debug('Host: %s', db_host)
        logging.debug('Port: %s', db_port)
        logging.debug('Username: %s', db_username)
        logging.debug('Password: %s', db_password)
        logging.debug('script_language: %s', script_language)
