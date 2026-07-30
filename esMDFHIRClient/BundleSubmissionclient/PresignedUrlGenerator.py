# bundlesubmissionclient/PresignedUrlGenerator.py

import json
import logging
import requests
import os
import hashlib
import base64
import random
import string
from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility
from esMDFHIRClient.BundleSubmissionclient.EsmdAuthClient import EsmdAuthClient
from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger

class PresignedUrlGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_util = ConfigUtility()
        self.auth_client = EsmdAuthClient()
        self.presigned_url = self.config_util.get_presigned_url_base()

    def generate_md5_from_bytes(self, file_bytes):
        hash_md5 = hashlib.md5()
        hash_md5.update(file_bytes)
        return base64.b64encode(hash_md5.digest()).decode('utf-8')

    def generate_sha256_from_bytes(self, file_bytes):
        hash_sha256 = hashlib.sha256()
        hash_sha256.update(file_bytes)
        return hash_sha256.hexdigest()

    def generate_md5_from_file(self, file_path):
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hash_md5.update(chunk)
        return base64.b64encode(hash_md5.digest()).decode("utf-8")

    def generate_sha256_from_file(self, file_path):
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def generate_random_alphanumeric(self, length=5):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    def generate_presigned_url(self, token, uniqueId, sender_oid, file_info_list):
        parameters = {
            "resourceType": "Parameters",
            "id": uniqueId,
            "parameter": [
                {"name": "senderoid", "valueString": sender_oid},
                {"name": "organizationid", "valueString": sender_oid}
            ]
        }

        for file_name, file_source in file_info_list:
            if isinstance(file_source, (bytes, bytearray)):
                md5_hash = self.generate_md5_from_bytes(file_source)
                sha256_hash = self.generate_sha256_from_bytes(file_source)
                file_size = len(file_source)
            elif isinstance(file_source, str):
                md5_hash = self.generate_md5_from_file(file_source)
                sha256_hash = self.generate_sha256_from_file(file_source)
                file_size = os.path.getsize(file_source)
            else:
                raise ValueError("file_info_list entries must contain bytes or file path string")

            self.logger.debug(f"[DEBUG] MD5 for presigned request: {md5_hash} -> {file_name}")

            mime_type = "application/xml" if file_name.endswith(".xml") else "application/pdf"
            file_param = {
                "name": "fileinfo",
                "part": [
                    {"name": "filename", "valueString": os.path.basename(file_name)},
                    {"name": "content-md5", "valueString": md5_hash},
                    {"name": "mimetype", "valueString": mime_type},
                    {"name": "filesize", "valueString": "1"}  # hardcoded as workaround
                ]
            }
            parameters["parameter"].append(file_param)

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/fhir+json",
                "Accept": "application/fhir+json"
            }
            self.logger.info("REQUESTING PRESIGNED URL...")
            self.logger.info(f"URL: {self.presigned_url}/DocumentReference/$generate-presigned-url")

            response = requests.post(
                f"{self.presigned_url}/DocumentReference/$generate-presigned-url",
                headers=headers,
                data=json.dumps(parameters)
            )

            self.logger.info("RESPONSE FROM PRESIGNED URL API >>>")
            self.logger.info(f"Status Code: {response.status_code}")
            self.logger.info(f"Response Text: {response.text}")

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to generate pre-signed URL. Status code: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
        except Exception as e:
            self.logger.error(f"An error occurred during presigned request: {e}")

        return None


# # Example usage
# if __name__ == "__main__":
#     # Data for extensions and identifiers
#     extensions_data = {
#         "SenderOid": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission/Esmd-Ext-SenderOid",
#         "SenderOidValue": "urn:oid:1.2.840.10008.3.1.2.1.1",
#         "IntendedRecipient": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission/Esmd-Ext-IntendedRecipient",
#         "IntendedRecipientValue": "urn:oid:2.16.840.1.113883.13.34.110.1.100.23",
#         "LinesOfBusinessId": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission/Esmd-Ext-LinesOfBunsinessId",
#         "LinesOfBusinessIdValue": "1",
#         "ClaimId": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission/Esmd-Ext-ClaimId",
#         "ClaimIdValue": "CLAIM1234567",
#         "CaseId": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission/Esmd-Ext-CaseId",
#         "CaseIdValue": "CASE1234567"
        
#     }

#     identifiers_data = {
#         "UniqueIdSystem": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission/Esmd-Ext-UniqueId",
#         "UniqueIdValue": "UNIQUE1234570",
#         "NpiSystem": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission/Esmd-Ext-NPI",
#         "NpiValue": "1234567890"
#     }

#     file_paths = [
#         "c:/fhir/testd/test-file-200.xml",
#         "c:/fhir/testd/test-file-201.xml."
#     ]

#     # Initialize the generator
#     generator = PresignedUrlGenerator()

#     # Generate the pre-signed URL
#     response = generator.entry_point("UNIQUE1234570", extensions_data, identifiers_data, file_paths)

#     # Output the response
#     if response:
#         print(json.dumps(response, indent=2))
