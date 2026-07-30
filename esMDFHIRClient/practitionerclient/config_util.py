import yaml
import os

class ConfigUtility:
    def __init__(self, config_file='config.yaml'):
        with open(config_file, 'r') as file:
            self.config = yaml.safe_load(file)

    def get_fhir_server_url(self):
        """Get FHIR Server Base URL from config."""
        return self.config['server']['base_url']

    def get_timeout(self):
        """Get FHIR Server Timeout from config."""
        return self.config['server']['timeout']

    def get_auth_token(self):
        """Retrieve access token from environment variables (recommended for sensitive data)."""
        return os.getenv('ACCESS_TOKEN')

    def get_client_id(self):
        """Retrieve client ID from config."""
        return self.config['auth']['client_id']

    def get_client_secret(self):
        """Retrieve client Secret from config."""
        return self.config['auth']['client_secret']

    def get_token_endpoint(self):
        """Retrieve token endpoint from config."""
        return self.config['auth']['token_endpoint']

    def get_scope(self):
        """Retrieve scope from config."""
        return self.config['auth']['scope']
    
    def get_oid(self):
        """Retrieve oid from config."""
        return self.config['org']['oid']

    def get_logging_level(self):
        """Retrieve logging level from config."""
        return self.config['logging']['level']

# Usage example:
if __name__ == "__main__":
    config_util = ConfigUtility()

    # Example usage
    print("FHIR Server URL:", config_util.get_fhir_server_url())
    print("Client ID:", config_util.get_client_id())
    print("Timeout:", config_util.get_timeout())

    # Make sure to set the ACCESS_TOKEN environment variable
    print("Access Token:", config_util.get_auth_token())
