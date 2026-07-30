import json
from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger

import logging

class FhirResponseProcessor:
    def __init__(self, response_data):
        self.response_data = response_data
        self.logger = logging.getLogger(__name__)  # Setup logger

    def process_response(self):
        """
        Processes the FHIR response, either a Bundle or OperationOutcome.
        
        :return: A dictionary with the status of the validation and detailed messages.
        """
        try:
            # Check the resourceType to determine if it's a Bundle or OperationOutcome
            resource_type = self.response_data.get("resourceType", "")
            
            if resource_type == "Bundle":
                self.logger.info("Processing FHIR Bundle resource.")
                return self._process_bundle(self.response_data)
            elif resource_type == "OperationOutcome":
                self.logger.info("Processing FHIR OperationOutcome resource.")
                return self._process_operation_outcome(self.response_data)
            else:
                self.logger.error(f"Unknown resourceType: {resource_type}")
                return {
                    "valid": False,
                    "message": f"Unknown resourceType: {resource_type}"
                }
        except Exception as e:
            self.logger.exception("Failed to process the FHIR response.")
            return {
                "valid": False,
                "message": str(e)
            }

    def _process_bundle(self, bundle):
        """
        Processes a Bundle resource.
        
        :param bundle: The FHIR Bundle resource.
        :return: A dictionary with validation results.
        """
        validation_results = {
            "valid": True,
            "details": []
        }

        # Ensure 'entry' exists in the bundle
        if "entry" not in bundle:
            self.logger.error("Bundle does not contain 'entry'.")
            return {
                "valid": False,
                "message": "Bundle does not contain 'entry'."
            }

        # Iterate through each entry in the Bundle
        for entry in bundle.get("entry", []):
            try:
                response = entry.get("response", {})
                
                # Validate the status
                status = response.get("status", "")
                if status != "201 Created":
                    self._log_failure(validation_results, f"Resource did not have status '201 Created'. Found: {status}")
                    continue  # No need to check further if status is incorrect

                # Validate the outcome and code
                outcome = response.get("outcome", {})
                if outcome.get("resourceType") == "OperationOutcome":
                    result = self._process_operation_outcome(outcome)
                    validation_results["details"].extend(result["details"])
                    if not result["valid"]:
                        validation_results["valid"] = False
                else:
                    self._log_failure(validation_results, "Expected an OperationOutcome but did not find one.")
                    
            except KeyError as e:
                self.logger.warning(f"Missing expected key: {e}")
                self._log_failure(validation_results, f"Missing key in entry: {e}")
            except Exception as e:
                self.logger.exception("Unexpected error while processing bundle entry.")
                self._log_failure(validation_results, str(e))

        return validation_results

    def _process_operation_outcome(self, operation_outcome):
        """
        Processes an OperationOutcome resource.
        
        :param operation_outcome: The FHIR OperationOutcome resource.
        :return: A dictionary with validation results.
        """
        validation_results = {
            "valid": True,
            "details": []
        }

        # Ensure 'issue' exists in the OperationOutcome
        if "issue" not in operation_outcome:
            self.logger.error("OperationOutcome does not contain 'issue'.")
            return {
                "valid": False,
                "message": "OperationOutcome does not contain 'issue'."
            }

        try:
            issues = operation_outcome.get("issue", [])
            for issue in issues:
                details = issue.get("details", {})
                coding = details.get("coding", [])
                if coding and coding[0].get("code") == "SUCCESSFUL_CREATE":
                    validation_results["details"].append({
                        "status": "success",
                        "message": issue.get("diagnostics", "OperationOutcome was successful.")
                    })
                    self.logger.info("OperationOutcome success.")
                else:
                    self._log_failure(validation_results, f"OperationOutcome issue found with code: {coding[0].get('code') if coding else 'N/A'}")
        
        except KeyError as e:
            self.logger.warning(f"Missing expected key: {e}")
            self._log_failure(validation_results, f"Missing key in OperationOutcome: {e}")
        except Exception as e:
            self.logger.exception("Unexpected error while processing OperationOutcome.")
            self._log_failure(validation_results, str(e))

        return validation_results

    def _log_failure(self, validation_results, message):
        """
        Helper method to log failures and update validation results.
        
        :param validation_results: The current validation result object to update.
        :param message: The failure message to log.
        """
        self.logger.error(message)
        validation_results["valid"] = False
        validation_results["details"].append({
            "status": "failure",
            "message": message
        })
    
    def extract_esmd_transaction_id(self):
        """
        Extracts the Esmd-TransactionId from either a Bundle or OperationOutcome.
        
        :return: The extracted Esmd-TransactionId or None if not found.
        """
        try:
            resource_type = self.response_data.get("resourceType", "")
            
            if resource_type == "Bundle":
                return self._extract_from_bundle(self.response_data)
            elif resource_type == "OperationOutcome":
                return self._extract_from_operation_outcome(self.response_data)
            else:
                self.logger.warning(f"Unknown resourceType: {resource_type}")
                return None
        except Exception as e:
            self.logger.exception("Failed to extract Esmd-TransactionId.")
            return None

    def _extract_from_bundle(self, bundle):
        """
        Extracts the Esmd-TransactionId from a Bundle resource.
        
        :param bundle: The FHIR Bundle resource.
        :return: The extracted Esmd-TransactionId or None if not found.
        """
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            extensions = resource.get("extension", [])
            
            for ext in extensions:
                if ext.get("url") == "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-TransactionId":
                    transaction_id = ext.get("valueString")
                    self.logger.info(f"Found Esmd-TransactionId in Bundle: {transaction_id}")
                    return transaction_id
        
        self.logger.warning("Esmd-TransactionId not found in Bundle.")
        return None

    def _extract_from_operation_outcome(self, operation_outcome):
        """
        Extracts the Esmd-TransactionId from an OperationOutcome resource.
        
        :param operation_outcome: The FHIR OperationOutcome resource.
        :return: The extracted Esmd-TransactionId or None if not found.
        """
        issues = operation_outcome.get("issue", [])
        
        for issue in issues:
            diagnostics = issue.get("diagnostics", "")
            if "Esmd-TransactionId" in diagnostics:
                transaction_id = diagnostics.split("Esmd-TransactionId: ")[1].split()[0]
                self.logger.info(f"Found Esmd-TransactionId in OperationOutcome: {transaction_id}")
                return transaction_id
        
        self.logger.warning("Esmd-TransactionId not found in OperationOutcome.")
        return None

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)

    # Example FHIR response with Bundle
    response_data = {
            "resourceType": "Bundle",
            "id": "791ba232-ea32-4bcf-8a0e-a64123dc53e4",
            "type": "transaction-response",
            "link": [
                {
                    "relation": "self",
                    "url": "https://terminology.esmduat.cms.gov:8099/fhir"
                }
            ],
            "entry": [
                {
                    "response": {
                        "status": "201 Created",
                        "location": "List/1647/_history/1",
                        "etag": "1",
                        "lastModified": "2024-10-03T15:26:13.650-04:00",
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
                                    "diagnostics": "Successfully created resource \"List/1647/_history/1\". Took 1,834ms."
                                }
                            ]
                        }
                    }
                },
                {
                    "response": {
                        "status": "201 Created",
                        "location": "DocumentReference/1648/_history/1",
                        "etag": "1",
                        "lastModified": "2024-10-03T15:26:13.650-04:00",
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
                                    "diagnostics": "Successfully created resource \"DocumentReference/1648/_history/1\". Took 270ms."
                                }
                            ]
                        }
                    }
                }
            ]
        }

    processor = FhirResponseProcessor(response_data)
    transaction_id = processor.extract_esmd_transaction_id()

    print(f"Extracted Esmd-TransactionId: {transaction_id}")
