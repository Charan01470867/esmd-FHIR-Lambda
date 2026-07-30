# PresignedUrlUploader.py

import requests
import os
import hashlib
import base64
import logging
import xml.etree.ElementTree as ET
from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger
from esMDFHIRClient.BundleSubmissionclient.EsmdAuthClient import EsmdAuthClient
from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility

class PresignedUrlUploader:
    def __init__(self):
        """
        Initialize the PresignedUrlUploader utility class.
        """
        # Set up the logger for this class
        self.logger = logging.getLogger(__name__)
        
        # Initialize configuration utility
        self.config_util = ConfigUtility()

        # Initialize EsmdAuthClient to get the access token
        self.auth_client = EsmdAuthClient()
        self.base_url = self.config_util.get_fhir_server_url()


    def generate_md5(self, file_path):
        """Generate base64-encoded MD5 hash of file contents."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return base64.b64encode(hash_md5.digest()).decode('utf-8')
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            return None

    def generate_sha256(self, file_path):
        """Generate SHA-256 hash in hexadecimal format (64 characters) for bundle submission."""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
        return None


    def upload_file(self, presigned_url, file_bytes=None, file_path=None, md5str=None, content_length=None, content_type='application/xml'):
        """
        Upload to CMS using presigned URL, with support for both in-memory bytes or file path.
        """
        try:
            if file_bytes is None and file_path is None:
                self.logger.error("Either file_bytes or file_path must be provided.")
                return None

            access_token = self.auth_client.get_token()
            if not access_token:
                self.logger.error("No access token could be retrieved, aborting request.")
                return None

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': content_type,
                'Content-MD5': md5str,
                'Content-Length': str(content_length)
            }

            self.logger.debug(f"Uploading to CMS via POST: {presigned_url}")
            if file_bytes is not None:
                response = requests.post(presigned_url, headers=headers, data=file_bytes)
            else:
                if not os.path.exists(file_path):
                    self.logger.error(f"File not found: {file_path}")
                    return None
                with open(file_path, "rb") as f:
                    response = requests.post(presigned_url, headers=headers, data=f)

            if response.status_code == 200:
                self.logger.info(f"Upload to CMS successful")
                return response.text
            else:
                self.logger.error(
                f"Upload failed. Status: {response.status_code}. Response: {response.text[:300]}"
            )
            return None

        except Exception as e:
            self.logger.exception(f"Error during upload to CMS")
            return None
