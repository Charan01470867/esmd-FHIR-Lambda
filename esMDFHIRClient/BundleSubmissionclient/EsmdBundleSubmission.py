import json
import requests
import logging

from datetime import datetime
from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger  # Import the common logger setup function
from esMDFHIRClient.BundleSubmissionclient.EsmdAuthClient import EsmdAuthClient  # Import the EsmdAuthClient class
from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility


class BundleSubmission:
    def __init__(self, esmd_fhir_server_url):
        """
        Initialize the BundleSubmission utility class with the FHIR server URL.
        """
        self.esmd_fhir_server_url = esmd_fhir_server_url
        self.base_url = esmd_fhir_server_url
        # Set up the logger for this class using the common logger
        #self.logger = setup_logger(self.__class__.__name__)
        self.logger = logging.getLogger(__name__)
        # Initialize configuration utility
        self.config_util = ConfigUtility()

        # Initialize EsmdAuthClient to get the access token
        self.auth_client = EsmdAuthClient()
        self.base_url = self.config_util.get_fhir_server_url()


    def submit_bundle(self, bundle):
        """
        Submit the prepared Bundle to the FHIR server.

        :param bundle: The prepared FHIR Bundle JSON object.
        :return: Response from the FHIR server.
        """
        access_token = self.auth_client.get_token()  # Get the token dynamically

        if not access_token:
            print("No access token could be retrieved, aborting request.")
            return None
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/fhir+json',
            'Accept': 'application/fhir+json',
            'client_id': 'test',
            'client_secret': 'test'
        }
        
        # Ensure the FHIR server URL ends with a '/'
        if not self.esmd_fhir_server_url.endswith('/'):
            self.esmd_fhir_server_url += '/'
        
        try:
            response = requests.post(self.esmd_fhir_server_url, headers=headers, data=json.dumps(bundle))
            response.raise_for_status()
            
            # Log success and return the response
            print("Successfully submitted bundle to the FHIR server.")
            
            return True, response.json()  # Return response from server
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err} - Response: {response.text}")
            return False, {
                "error": str(http_err),
                "status_code": response.status_code,
                "response": response.text
            }

        except requests.exceptions.ConnectionError as conn_err:
            print(f"Connection error occurred: {conn_err}")
            return False, {"error": str(conn_err)}

        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout error occurred: {timeout_err}")
            return False, {"error": str(timeout_err)}

        except requests.exceptions.RequestException as req_err:
            print(f"Request exception occurred: {req_err}")
            return False, {"error": str(req_err)}

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return False, {"error": str(e)}


# # Example Usage:
# if __name__ == "__main__":

#     # Base URL of the FHIR server
#     base_url = "http://internal-esmd-dev-apps-986151145.us-east-1.elb.amazonaws.com:9012/fhir"
#     dir_path = "c:/fhir/testd/"
#     # Initialize the generator
#     generator = PresignedUrlGenerator(base_url)

#     # Example sender OID and file paths
#     sender_oid = "2.16.840.1.113883.4.1.1.1234"
#     file_paths = [
#         "c:/fhir/testd/pkpadmin.pdf",
#         "c:/fhir/testd/pkpadmin1.pdf"
#     ]

   