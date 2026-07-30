import json
from logger import setup_logger

class FhirBatchResponseProcessor:
    def __init__(self, bundle_response):
        """
        Initialize the processor with the FHIR Bundle batch-response.
        
        :param bundle_response: JSON object of the FHIR Bundle batch-response.
        """
        self.bundle_response = bundle_response
        self.logger = setup_logger(self.__class__.__name__)

    def extract_practitioner_ids_with_status(self):
        """
        Extract Practitioner IDs and their status from the 'location' and 'status' fields in the batch-response entries.
        
        :return: List of dictionaries with Practitioner ID and status.
        """
        practitioner_info_list = []
        
        try:
            # Validate that the response is a Bundle and that it has entries
            if self.bundle_response.get('resourceType') != 'Bundle' or not self.bundle_response.get('entry'):
                self.logger.error("Invalid bundle response: Missing 'resourceType' or 'entry'.")
                return practitioner_info_list
            
            # Iterate through each entry in the bundle
            for entry in self.bundle_response.get('entry', []):
                response = entry.get('response', {})
                location = response.get('location', '')
                status = response.get('status', '')

                if location.startswith("Practitioner/"):
                    # Extract the Practitioner ID from the location string (e.g., "Practitioner/3774/_history/1")
                    practitioner_id = location.split('/')[1]
                    practitioner_info_list.append({
                        "practitioner_id": practitioner_id,
                        "status": status
                    })
                    self.logger.info(f"Extracted Practitioner ID: {practitioner_id} with status: {status}")
            
            return practitioner_info_list
        
        except Exception as e:
            self.logger.exception(f"An error occurred while processing the batch response: {e}")
            return []

# Example usage:
if __name__ == "__main__":
    # Example bundle response JSON
    bundle_response = {
        "resourceType": "Bundle",
        "id": "b5b93c34-8cd7-43c4-b0cc-6e8db1ab8000",
        "type": "batch-response",
        "link": [
            {
                "relation": "self",
                "url": "http://3.16.206.148:8080/fhir"
            }
        ],
        "entry": [
            {
                "response": {
                    "status": "201 Created",
                    "location": "Practitioner/3774/_history/1",
                    "etag": "1",
                    "lastModified": "2024-10-06T00:27:17.117+00:00",
                    "outcome": {
                        "resourceType": "OperationOutcome",
                        "issue": [
                            {
                                "severity": "information",
                                "code": "informational",
                                "details": {
                                    "coding": [
                                        {
                                            "system": "https://hapifhir.io/fhir/CodeSystem/hapi-fhir-storage-response-code",
                                            "code": "SUCCESSFUL_CREATE",
                                            "display": "Create succeeded."
                                        }
                                    ]
                                },
                                "diagnostics": "Successfully created resource \"Practitioner/3774/_history/1\". Took 2ms."
                            }
                        ]
                    }
                }
            },
            {
                "response": {
                    "status": "201 Created",
                    "location": "Practitioner/3775/_history/1",
                    "etag": "1",
                    "lastModified": "2024-10-06T00:27:17.140+00:00",
                    "outcome": {
                        "resourceType": "OperationOutcome",
                        "issue": [
                            {
                                "severity": "information",
                                "code": "informational",
                                "details": {
                                    "coding": [
                                        {
                                            "system": "https://hapifhir.io/fhir/CodeSystem/hapi-fhir-storage-response-code",
                                            "code": "SUCCESSFUL_CREATE",
                                            "display": "Create succeeded."
                                        }
                                    ]
                                },
                                "diagnostics": "Successfully created resource \"Practitioner/3775/_history/1\". Took 1ms."
                            }
                        ]
                    }
                }
            }
        ]
    }

    # Initialize the processor with the bundle response
    processor = FhirBatchResponseProcessor(bundle_response)
    
    # Extract practitioner IDs and status
    practitioner_info = processor.extract_practitioner_ids_with_status()
    
    # Print the extracted practitioner information
    print("Extracted Practitioner Information:", json.dumps(practitioner_info, indent=2))
