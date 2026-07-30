import requests
import json
from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility
from logger import setup_logger

class EsmdAuthClient:
    def __init__(self):
        # Initialize configuration utility
        self.config_util = ConfigUtility()
        # Set up the logger for this class using the common logger
        self.logger = setup_logger(self.__class__.__name__)
        # Load configurations
        self.auth_url = self.config_util.get_token_endpoint()
        self.client_id = self.config_util.get_client_id()
        self.client_secret = self.config_util.get_client_secret() 
        self.scope =  self.config_util.get_scope()
        self.token = None
        self.token_type = None
        self.expires_in = None

    def get_token(self):
        """
        Retrieve the OAuth2 token using client credentials flow.
        """
        payload = {}

        headers = {
            'clientid': self.client_id,
            'clientsecret': self.client_secret,
            'scope': self.scope
        }

        self.logger.info("Requesting token from esMD Auth API...")
        try:
            response = requests.post(self.auth_url, data=payload, headers=headers)
            response.raise_for_status()

            # Extract token and token information from the response
            token_info = response.json()
            self.token = token_info.get('access_token')
            self.token_type = token_info.get('token_type')
            self.expires_in = token_info.get('expires_in')

            self.logger.info(f"Token retrieved successfully. Expires in {self.expires_in} seconds.")
            return self.token
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"HTTP error occurred: {http_err}")
        except Exception as err:
            self.logger.error(f"An error occurred: {err}")
        return None

    def get_authorization_header(self):
        """
        Returns the authorization header with the Bearer token.
        """
        if self.token:
            return {'Authorization': f'Bearer {self.token}'}
        else:
            self.logger.warning("No token available. Please call get_token() first.")
            return None

# Example usage:
if __name__ == "__main__":
    self.logger.basicConfig(level=self.logger.INFO)
    config_util = ConfigUtility()
    # esMD Auth client details
    CLIENT_ID = config_util.get_client_id()
    CLIENT_SECRET = config_util.get_client_secret()
    AUTH_URL = config_util.get_token_endpoint()
    SCOPE = config_util.get_scope()

    # Create an instance of the EsmdAuthClient
    auth_client = EsmdAuthClient(CLIENT_ID, CLIENT_SECRET, SCOPE, AUTH_URL)

    # Retrieve the token
    token = auth_client.get_token()
    
    if token:
        print(f"Token: {token}")
        print(f"Authorization Header: {auth_client.get_authorization_header()}")