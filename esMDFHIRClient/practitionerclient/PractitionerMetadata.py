import uuid
import logging
import json
from logger import setup_logger  # Ensure this is set up in your project

class PractitionerMetadata:
    def __init__(self, first_name, last_name, gender, npi, provider_number, provider_taxid, action_requested, service_code, service_start_date, service_end_date):
        self.first_name = first_name
        self.last_name = last_name
        self.gender = gender
        self.npi = npi
        self.provider_number = provider_number
        self.provider_taxid = provider_taxid
        self.action_requested = action_requested
        self.service_code = service_code
        self.service_start_date = service_start_date
        self.service_end_date = service_end_date
        # Set up the logger for this class using the common logger
        self.logger = setup_logger(self.__class__.__name__)

    # Create a FHIR Practitioner resource using practitioner metadata
    def create_practitioner(self):
        practitioner_id = str(uuid.uuid4())

        practitioner = {
            "resourceType": "Practitioner",
            "id": practitioner_id,
            "meta": {
                "profile": [
                    "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Practitioner"
                ],
                "security": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                        "code": "R"
                    }
                ]
            },
            "identifier": [
                {
                    "use": "official",
                    "system": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-NPI",
                    "value": self.npi
                },
                {
                    "use": "official",
                    "system": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ProviderTaxId",
                    "value": self.provider_taxid
                },
                {
                    "use": "official",
                    "system": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ProviderNumber",
                    "value": self.provider_number
                }
            ],
            "telecom": [
                {
                    "system": "phone",
                    "value": "555-123-4567",
                    "use": "work"
                }
            ],
            "name": [
                {
                    "family": self.last_name,
                    "given": [self.first_name],
                    "prefix": ["Dr"]
                }
            ],
            "extension": [
                {
                    "url": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ActionRequestedCode",
                    "valueString": self.action_requested
                },
                {
                    "url": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ServiceCode",
                    "valueCode": self.service_code
                },
                {
                    "url": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ServiceStartDate",
                    "valueDate": self.service_start_date
                },
                {
                    "url": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ServiceEndDate",
                    "valueDate": self.service_end_date
                }
            ]
        }

        self.logger.info(f"Practitioner created with ID: {practitioner_id}")
        return practitioner

    # Create a Bundle with multiple Practitioner resources
    @staticmethod
    def create_practitioner_bundle(practitioners):
        bundle_id = str(uuid.uuid4())

        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "batch",  # Set the Bundle type to 'batch'
            "entry": []
        }

        for practitioner in practitioners:
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{practitioner['id']}",
                "resource": practitioner,
                "request": {
                    "method": "POST",
                    "url": "Practitioner"
                }
            })

        logging.info(f"Bundle created with ID: {bundle_id} and {len(practitioners)} practitioners")
        return bundle

if __name__ == "__main__":
  # Create individual practitioners using metadata
  practitioner1 = PractitionerMetadata("John", "Doe", "male", "1234567890", "12345", "TAXID123", "action1", "SC1", "2024-01-01", "2024-01-31").create_practitioner()
  practitioner2 = PractitionerMetadata("Jane", "Smith", "female", "9876543210", "54321", "TAXID987", "action2", "SC2", "2024-02-01", "2024-02-28").create_practitioner()

  # Prepare a list of practitioners
  practitioners = [practitioner1, practitioner2]

  # Create a FHIR bundle containing multiple practitioners
  bundle = PractitionerMetadata.create_practitioner_bundle(practitioners)

  print(json.dumps(bundle))
