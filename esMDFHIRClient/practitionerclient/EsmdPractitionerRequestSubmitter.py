import requests
import json
from EsmdAuthClient import EsmdAuthClient  # Import the EsmdAuthClient class
from logger import setup_logger  # Import the common logger setup function
from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility
from PractitionerMetadata import PractitionerMetadata  # Import PractitionerMetadata
from EsmdPractitionerResponse import FhirBatchResponseProcessor


class PractitionerRequestSubmitter:
    def __init__(self):
        """
        Initialize the PractitionerRequestSubmitter with the base FHIR server URL and authorization token.
        """
        # Set up the logger for this class using the common logger
        self.logger = setup_logger(self.__class__.__name__)
        # Initialize configuration utility
        self.config_util = ConfigUtility()
        # Initialize EsmdAuthClient to get the access token
        self.auth_client = EsmdAuthClient()
        self.base_url = self.config_util.get_fhir_server_url()

    def submit_practitioner(self, practitioner_json):
        """
        Submit the Practitioner resource to the FHIR server.

        :param practitioner_json: JSON body of the Practitioner resource (Esmd-Practitioner).
        :return: Response object from the FHIR server or None in case of an error.
        """
        if not practitioner_json:
            self.logger.error("Empty practitioner JSON provided, aborting submission.")
            return None

        try:
            access_token = self.auth_client.get_token()  # Get the token dynamically
            if not access_token:
                self.logger.error("No access token could be retrieved, aborting request.")
                return None

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/fhir+json',
                'Accept': 'application/fhir+json'
            }

            # Endpoint for Practitioner resource
            practitioner_endpoint = f'{self.base_url}/Practitioner'

            self.logger.info(f"Submitting Practitioner resource to {practitioner_endpoint}")

            # Sending the request to the FHIR server
            response = requests.post(practitioner_endpoint, headers=headers, data=json.dumps(practitioner_json))
            
            # Log response status and content
            self.logger.debug(f"Response Status Code: {response.status_code}")
            self.logger.debug(f"Response Content: {response.content}")

            # Raise an exception for HTTP errors
            response.raise_for_status()

            self.logger.info("Practitioner resource submitted successfully.")
            return response.json()  # Return the response as JSON

        except requests.exceptions.HTTPError as errh:
            self.logger.error(f"HTTP Error occurred: {errh}, Status Code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.ConnectionError as errc:
            self.logger.error(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            self.logger.error(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            self.logger.error(f"Request Error occurred: {err}")
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred: {e}")

        return None

    def submit_practitioner_bundle(self, bundle_practitioners_json):
        """
        Submit a list of Practitioner resources to the esMD FHIR server in a batch.

        :param bundle_practitioners_json: JSON body of the Practitioner Bundle resource.
        :return: Response object from the FHIR server or None in case of an error.
        """
        if not bundle_practitioners_json:
            self.logger.error("Empty practitioner bundle JSON provided, aborting submission.")
            return None

        try:
            access_token = self.auth_client.get_token()  # Get the token dynamically
            if not access_token:
                self.logger.error("No access token could be retrieved, aborting request.")
                return None

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/fhir+json',
                'Accept': 'application/fhir+json'
            }

            # Endpoint for Bundle resource
            bundle_endpoint = f'{self.base_url}/'

            self.logger.info(f"Submitting Practitioner Bundle resource to {bundle_endpoint}")

            # Sending the request to the FHIR server
            response = requests.post(bundle_endpoint, headers=headers, data=json.dumps(bundle_practitioners_json))
            
            # Log response status and content
            self.logger.debug(f"Response Status Code: {response.status_code}")
            self.logger.debug(f"Response Content: {response.content}")

            # Raise an exception for HTTP errors
            response.raise_for_status()

            self.logger.info("Practitioner Bundle resource submitted successfully.")
            return response.json()  # Return the response as JSON

        except requests.exceptions.HTTPError as errh:
            self.logger.error(f"HTTP Error occurred: {errh}, Status Code: {response.status_code}, Response: {response.text}")
        except requests.exceptions.ConnectionError as errc:
            self.logger.error(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            self.logger.error(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            self.logger.error(f"Request Error occurred: {err}")
        except Exception as e:
            self.logger.exception(f"An unexpected error occurred: {e}")

        return None


# Example usage
if __name__ == "__main__":
    # Initialize the PractitionerRequestSubmitter
    submitter = PractitionerRequestSubmitter()

    # Sample test data for list of practitioners
    practitioner_metadata_1 = PractitionerMetadata(
        first_name="John",
        last_name="Doe",
        gender="male",
        npi="1234567893",
        provider_number="12345678",
        provider_taxid="1234567890",
        action_requested="A",
        service_code="EEB",
        service_start_date="2024-05-01",
        service_end_date="2024-05-31"
    )

    practitioner_metadata_2 = PractitionerMetadata(
        first_name="Jane",
        last_name="Smith",
        gender="female",
        npi="9876543210",
        provider_number="87654321",
        provider_taxid="0987654321",
        action_requested="B",
        service_code="XYZ",
        service_start_date="2024-06-01",
        service_end_date="2024-06-30"
    )

    practitioner_metadata_3 = PractitionerMetadata(
        first_name="Emily",
        last_name="Johnson",
        gender="female",
        npi="1122334455",
        provider_number="66554433",
        provider_taxid="9988776655",
        action_requested="C",
        service_code="XYZ",
        service_start_date="2024-07-01",
        service_end_date="2024-07-31"
    )

    # Create a list of PractitionerMetadata objects
    practitioners_metadata_list = [practitioner_metadata_1, practitioner_metadata_2, practitioner_metadata_3]

    # Submit the practitioner bundle
    print("Submitting Practitioner Bundle...")
    bundle_response = submitter.submit_practitioner_bundle(practitioners_metadata_list)

    # Print the response
    if bundle_response:
        print("Practitioner Bundle Submission Response:")
        print(json.dumps(bundle_response, indent=2))
        processor = FhirBatchResponseProcessor(bundle_response)
        practitioner_response_list = processor.extract_practitioner_ids_with_status()
        # Print the extracted practitioner information
        print("Extracted Practitioner Information:", json.dumps(practitioner_info, indent=2))
    else:
        print("Failed to submit the practitioner bundle.")
