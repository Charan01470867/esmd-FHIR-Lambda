# BundleSubmissionHandler.py

import os
import json
import hashlib
import base64
import logging
import re
import requests
import tempfile
import boto3
from datetime import datetime
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth
from botocore.credentials import Credentials

# Utility and handler imports
from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility
from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger
from esMDFHIRClient.BundleSubmissionclient.PresignedUrlGenerator import PresignedUrlGenerator
from esMDFHIRClient.BundleSubmissionclient.PresignedUrlUploader import PresignedUrlUploader
from esMDFHIRClient.BundleSubmissionclient.PrepareEsmdBundleSubmissionData import PrepareBundleSubmission
from esMDFHIRClient.BundleSubmissionclient.EsmdBundleSubmission import BundleSubmission
from esMDFHIRClient.BundleSubmissionclient.EsmdFhirBundleSubmissionResponseProcessor import FhirResponseProcessor
from esMDFHIRProvidersProcessor.LoissS3Utils import download_file_from_s3, upload_file_to_s3, delete_file_from_s3, move_file_in_s3
from esMDFHIRProvidersProcessor.LoissS3Utils import s3_request
from esMDFHIRProvidersProcessor.LoissTransactionLogger import LoissTransactionLogger

# Extension URL for ReviewContractorOID (ValueSet: Esmd-VS-ReviewContractorOIDs)
REVIEW_CONTRACTOR_OID_URL = "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ReviewContractorOid"


def ensure_urn_oid(value):
    """Ensure an OID value has the urn:oid: prefix. If missing, add it. Return None if value is empty."""
    if value is None or not str(value).strip():
        return None
    v = str(value).strip()
    if v.lower().startswith("urn:oid:"):
        return v
    return "urn:oid:" + v


class BundleSubmissionHandler:
    def __init__(self, xml_filepath, txt_filename=None, pdf_filename=None, is_s3=True, metadata=None):
        # Initialize configuration and logger
        self.logger = logging.getLogger(__name__)
        self.config = ConfigUtility()
        self.xml_filepath = xml_filepath
        self.txt_filename = txt_filename
        self.pdf_filename = pdf_filename
        self.is_s3 = is_s3
        self.metadata = metadata
        self.now = datetime.now()

        # Build metadata extensions and identifiers used in FHIR bundle
        self.extensions_data = self._build_extensions_data()
        self.identifiers_data = self._build_identifiers_data()

        # Read S3 configuration details
        self.bucket_name = self.config.get_value("LoissS3Bucket.Loiss_S3_Bucket")
        self.region = self.config.get_value("LoissS3Bucket.Region_Name")
        self.access_key = self.config.get_value("LoissS3Bucket.S3_Bucket_Aws_Access_Key_Id")
        self.secret_key = self.config.get_value("LoissS3Bucket.S3_Bucket_Aws_Secret_Access_Key")

        self.logger.debug(f"Initialized with: xml={self.xml_filepath}, txt={self.txt_filename}, pdf={self.pdf_filename}")

        self.transaction_logger = LoissTransactionLogger(
            bucket=self.bucket_name, 
            region=self.region, 
            access_key=self.access_key,
            secret_key=self.secret_key, 
            log_prefix=self.config.get_value("LoissS3Bucket.Transaction_Log")
            )

        self._processed_s3_root = (
            self.config.get_value("LoissS3Bucket.Processed_Files") or "PROCESSED"
        ).strip().strip("/")
        self._errored_s3_root = (
            self.config.get_value("LoissS3Bucket.Errored_Files") or "ERRORED"
        ).strip().strip("/")

    def _build_extensions_data(self):
        """Creates metadata extensions used in the FHIR bundle submission."""
        ext = {
            "SenderOid": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-OrganizationId",
            "SenderOidValue": self.metadata["homeCommunityId"],
            "IntendedRecipient": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-IntendedRecipient",
            "IntendedRecipientValue": self.metadata["intendedRecipient"],
            "LinesOfBusinessId": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-LinesOfBusinessId",
            "LinesOfBusinessIdValue": self.metadata["contentTypeCode"],
            "UniqueId": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-UniqueId",
            "UniqueIdValue": self.metadata["uniqueID"],
            "Npi": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-NPI",
            "NpiValue": self.metadata["NPI"],
            "CaseId": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-CaseId",
            "CaseIdValue": self.metadata["esMDCaseID"],
            "ClaimId": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ClaimId",
            "ClaimIdValue": self.metadata["esMDClaimID"],
            "AttachmentControlNumber": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-AttachmentControlNumber",
            "AttachmentControlNumberValue": self.metadata.get("attachmentControlNumber"),
        }
        # ParentUniqueID from TXT (when present) - add extension URL for submission
        parent_unique_id = self.metadata.get("ParentUniqueID") or self.metadata.get("ParentUniqueId")
        if parent_unique_id:
            ext["ParentUniqueId"] = "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-ParentUniqueId"
            ext["ParentUniqueIdValue"] = parent_unique_id
        # SplitNumber from TXT (when present) - add extension URL for submission
        split_number = self.metadata.get("SplitNumber")
        if split_number:
            ext["SplitNumber"] = "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-SplitNumber"
            ext["SplitNumberValue"] = split_number
        # ReviewContractorOID (Esmd-VS-ReviewContractorOIDs): ensure urn:oid: prefix
        rc_oid_raw = self.metadata.get("reviewContractorOID") or self.metadata.get("reviewContractorOid")
        rc_oid = ensure_urn_oid(rc_oid_raw)
        if rc_oid:
            ext["ReviewContractorOid"] = REVIEW_CONTRACTOR_OID_URL
            ext["ReviewContractorOidValue"] = rc_oid
        return ext

    def _build_identifiers_data(self):
        """Prepares identifiers used in the FHIR DocumentReference and submission bundle."""
        return {
            "UniqueIdSystem": self.extensions_data["UniqueId"],
            "UniqueIdValue": self.extensions_data["UniqueIdValue"],
            "NpiSystem": self.extensions_data["Npi"],
            "NpiValue": self.extensions_data["NpiValue"]
        }

    def _s3_file_exists(self, key):
        """Check if a file exists in S3 using signed GET request."""
        try:
            response = s3_request(
                method="GET",
                bucket=self.bucket_name,
                region=self.region,
                key=key,
                access_key=self.access_key,
                secret_key=self.secret_key
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.warning(f"Signed HEAD request failed for {key}: {str(e)}")
        return False

    def run(self):
        local_xml_path = None
        submission_succeeded = False
        failure_stage = None
        failure_detail = None

        try:
            # STEP 1: Download XML file from S3 to local temp file (streaming, low memory)
            if self.is_s3:
                self.logger.info(f"Downloading XML from S3: {self.xml_filepath}")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xml")
                local_xml_path = tmp.name
                tmp.close()
                s3 = boto3.client("s3")
                with open(local_xml_path, "wb") as out_f:
                    s3.download_fileobj(self.bucket_name, self.xml_filepath, out_f)
                file_size = os.path.getsize(local_xml_path)
                self.logger.info(f"Downloaded XML to temp file: {local_xml_path} ({file_size} bytes)")
            else:
                raise RuntimeError("S3 must be used. Local files are no longer supported.")

            self.logger.info("Starting Bundle Submission Handler execution")

            # STEP 2: Get a presigned URL from CMS for uploading the document
            url_generator = PresignedUrlGenerator()
            token = url_generator.auth_client.get_token()
            if not token:
                self.logger.error("No access token retrieved. Check AWS Secrets Manager (test/esmdfhir) and CMS auth endpoint.")
                raise RuntimeError("No access token available. Verify Secrets Manager credentials and CMS auth endpoint.")
            raw_response = url_generator.generate_presigned_url(
                token,
                self.extensions_data["UniqueIdValue"],
                self.extensions_data["SenderOidValue"],
                [(self.xml_filepath, local_xml_path)]
            )

            if isinstance(raw_response, dict):
                presigned_response = raw_response
            elif raw_response is not None:
                presigned_response = json.loads(raw_response)
            else:
                presigned_response = {}
            upload_targets = []

            for param in presigned_response.get("parameter", []):
                if param.get("name") == "presignedUrls":
                    for part in param.get("part", []):
                        if part.get("name") == "file":
                            file_params = part.get("part", [])
                            filename = next((p.get("part") or p.get("valueString") for p in file_params if p.get("name") == "filename"), None)
                            upload_url = next((p.get("part") or p.get("valueUrl") for p in file_params if p.get("name") == "uploadUrl"), None)
                            if filename and upload_url:
                                upload_targets.append((filename, upload_url))

            if not upload_targets:
                failure_stage = "presigned_url"
                failure_detail = "No presigned upload targets returned from CMS"
                self.logger.error(failure_detail)
                self.transaction_logger.update_transaction_status(
                    self.extensions_data["UniqueIdValue"], "submission_failed"
                )
                return

            # STEP 3: Upload the document to CMS via the presigned URL
            uploader = PresignedUrlUploader()
            attachments = []

            for filename, upload_url in upload_targets:
                file_size = os.path.getsize(local_xml_path)
                md5_hash = hashlib.md5()
                sha256_hash = hashlib.sha256()
                with open(local_xml_path, "rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        md5_hash.update(chunk)
                        sha256_hash.update(chunk)
                md5str = base64.b64encode(md5_hash.digest()).decode("utf-8")
                sha256str = sha256_hash.hexdigest()
                content_type = "application/xml"

                self.logger.info(f"Uploading file of size {file_size} bytes to presigned URL...")
                response = uploader.upload_file(
                    presigned_url=upload_url,
                    file_path=local_xml_path,
                    md5str=md5str,
                    content_length=file_size,
                    content_type=content_type
                )

                data = json.loads(response) if response else {}
                if data.get("status") == "SUCCESS":
                    self.logger.debug(f"Generated SHA-256 hash for {filename}: {sha256str}")
                    attachments.append({
                        "filename": filename,
                        "uploaded_url": data["s3uri"],
                        "size": file_size,
                        "content_type": content_type,
                        "sha256_hash": sha256str,
                        "md5_hash": md5str
                    })
                else:
                    self.logger.error(f"Upload failed for {filename}, skipping bundle submission.")

            if not attachments:
                failure_stage = "presigned_upload"
                failure_detail = "No files uploaded successfully to presigned URL"
                self.logger.error(failure_detail)
                self.transaction_logger.update_transaction_status(
                    self.extensions_data["UniqueIdValue"], "submission_failed"
                )
                return

            # STEP 4: Submit the full FHIR bundle
            bundle_id = "bundle-" + url_generator.generate_random_alphanumeric()
            list_id = "list-" + url_generator.generate_random_alphanumeric()
            bundle_submission = PrepareBundleSubmission(bundle_id, list_id, self.extensions_data, self.identifiers_data)
            bundle_submission.add_document_reference("doc-001", attachments)
            final_bundle = bundle_submission.build_bundle()

            submission = BundleSubmission("https://val.cpiapigateway.cms.gov/api/esmdf/ext/v1/fhir")
            fhir_result = submission.submit_bundle(final_bundle)

            if fhir_result is None:
                success_flag = False
                fhir_payload = None
            elif isinstance(fhir_result, tuple):
                success_flag, fhir_payload = fhir_result
            else:
                success_flag, fhir_payload = True, fhir_result

            # STEP 5: Save and process FHIR response (success only)
            if success_flag and fhir_payload:
                self.logger.debug(f"FHIR response content: {fhir_payload}")
                self._save_response_to_s3(fhir_payload)
                FhirResponseProcessor(fhir_payload).process_response()
                transaction_id = fhir_payload.get("identifier", {}).get("value")
                if transaction_id:
                    self.logger.info(f"Extracted transaction_id: {transaction_id}")
                    self.logger.info(f"Updating transaction status with transaction_id: {transaction_id}")
                else:
                    self.logger.warning("Transaction ID was not found in FHIR response.")
                self.transaction_logger.update_transaction_status(
                    unique_id=self.extensions_data["UniqueIdValue"],
                    new_status="submitted",
                    additional_fields={"transaction_id": transaction_id} if transaction_id else None
                )
                submission_succeeded = True
                self.logger.info("Bundle submission completed successfully")
            elif fhir_payload:
                failure_stage = "fhir_submit"
                failure_detail = json.dumps(fhir_payload, default=str)[:8000]
                self.logger.error(f"FHIR bundle submission failed: {failure_detail[:500]}...")
                self._save_fhir_error_payload_to_s3(fhir_payload)
                self.transaction_logger.update_transaction_status(
                    self.extensions_data["UniqueIdValue"], "submission_failed"
                )
            else:
                failure_stage = "fhir_submit"
                failure_detail = "Empty or null response from FHIR submit_bundle"
                self.logger.warning(failure_detail)
                self.transaction_logger.update_transaction_status(
                    self.extensions_data["UniqueIdValue"], "submission_failed"
                )

        except Exception as e:
            failure_stage = failure_stage or "exception"
            failure_detail = failure_detail or str(e)
            self.logger.exception("Unexpected error in BundleSubmissionHandler")
        finally:
            if local_xml_path and os.path.exists(local_xml_path):
                try:
                    os.remove(local_xml_path)
                except OSError:
                    self.logger.warning(f"Failed to clean temp file: {local_xml_path}")

            manifest = None
            if not submission_succeeded:
                manifest = {
                    "unique_id": self.extensions_data.get("UniqueIdValue"),
                    "failure_stage": failure_stage or "unknown",
                    "failure_detail": failure_detail,
                    "xml": self.xml_filepath,
                    "txt": self.txt_filename,
                    "pdf": self.pdf_filename,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            if submission_succeeded:
                self._relocate_submission_files(self._processed_s3_root, manifest=None)
                txn_status = "submitted"
            else:
                self._relocate_submission_files(self._errored_s3_root, manifest=manifest)
                txn_status = "submission_failed"

            transaction_entry = {
                "unique_id": self.extensions_data["UniqueIdValue"],
                "xml": self.xml_filepath,
                "txt": self.txt_filename,
                "pdf": self.pdf_filename,
                "status": txn_status,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if not submission_succeeded and failure_stage:
                transaction_entry["failure_stage"] = failure_stage
            self.transaction_logger.save_transaction(transaction_entry)
       
    def _get_actual_pdf_filename(self):
        """Get the actual PDF filename from the TXT file metadata."""
        try:
            # Construct TXT file path from XML path
            txt_key = self.xml_filepath.replace("GeneratedXML", "INFO").replace(".xml", ".TXT")
        
            # Download TXT file
            txt_content = download_file_from_s3(
                bucket=self.bucket_name,
                region=self.region,
                key=txt_key,
                access_key=self.access_key,
                secret_key=self.secret_key
            ).decode('utf-8')
        
            # Parse metadata from TXT content
            metadata = {}
            for line in txt_content.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    metadata[key.strip()] = value.strip()
        
            # Get PDF filename from metadata
            pdf_filename = metadata.get("file")
            if not pdf_filename:
                self.logger.warning("PDF filename not found in TXT metadata")
                return os.path.basename(self.xml_filepath).replace(".xml", ".PDF")
        
            return pdf_filename
        
        except Exception as e:
            self.logger.warning(f"Error getting PDF filename: {str(e)}")
        return os.path.basename(self.xml_filepath).replace(".xml", ".PDF")

    def _save_response_to_s3(self, response_json):
        """Uploads the FHIR response JSON to the response folder in S3 (config: LoissS3Bucket.Response_Prefix)."""
        try:
            response_prefix = self.config.get_value("LoissS3Bucket.Response_Prefix") or "JSONRESPONSES"
            unique_id = self.extensions_data.get("UniqueIdValue", "unknown")
            response_filename = f"{unique_id}_response.json"
            s3_key = f"{response_prefix}/{response_filename}"
            response_bytes = json.dumps(response_json, indent=2).encode('utf-8')

            upload_file_to_s3(
                bucket=self.bucket_name,
                region=self.region,
                key=s3_key,
                access_key=self.access_key,
                secret_key=self.secret_key,
                file_path=response_bytes,
                content_type="application/json"
            )
            self.logger.info(f"FHIR response uploaded to S3 at: {s3_key}")
        except Exception as e:
            self.logger.error(f"Failed to upload FHIR response to S3: {e}")

    def _save_fhir_error_payload_to_s3(self, error_payload):
        """Persist FHIR submission error details under JSONRESPONSES for troubleshooting."""
        try:
            response_prefix = self.config.get_value("LoissS3Bucket.Response_Prefix") or "JSONRESPONSES"
            unique_id = self.extensions_data.get("UniqueIdValue", "unknown")
            response_filename = f"{unique_id}_submission_error.json"
            s3_key = f"{response_prefix}/{response_filename}"
            response_bytes = json.dumps(error_payload, indent=2, default=str).encode("utf-8")
            upload_file_to_s3(
                bucket=self.bucket_name,
                region=self.region,
                key=s3_key,
                access_key=self.access_key,
                secret_key=self.secret_key,
                file_path=response_bytes,
                content_type="application/json"
            )
            self.logger.info(f"FHIR submission error payload uploaded to S3 at: {s3_key}")
        except Exception as e:
            self.logger.error(f"Failed to upload FHIR error payload to S3: {e}")

    def _upload_submission_error_manifest(self, manifest_s3_key, manifest_dict):
        try:
            body = json.dumps(manifest_dict, indent=2, default=str).encode("utf-8")
            upload_file_to_s3(
                bucket=self.bucket_name,
                region=self.region,
                key=manifest_s3_key,
                access_key=self.access_key,
                secret_key=self.secret_key,
                file_path=body,
                content_type="application/json"
            )
            self.logger.info(f"Submission error manifest written to s3://{self.bucket_name}/{manifest_s3_key}")
        except Exception as e:
            self.logger.error(f"Failed to upload submission error manifest: {e}")

    def _relocate_submission_files(self, root_prefix, manifest=None):
        """
        Move XML/TXT/PDF under root_prefix/{timestamp}_{unique_id}/.
        root_prefix is from config: Processed_Files or Errored_Files.
        If manifest is provided (failure path), uploads submission_error.json first.
        """
        try:
            unique_id = self.extensions_data.get("UniqueIdValue", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            base_prefix = f"{root_prefix}/{timestamp}_{unique_id}"

            if manifest:
                self._upload_submission_error_manifest(
                    f"{base_prefix}/submission_error.json", manifest
                )

            files_to_move = []
            if self.xml_filepath:
                files_to_move.append({
                    "type": "XML",
                    "source": self.xml_filepath,
                    "dest": f"{base_prefix}/{os.path.basename(self.xml_filepath)}",
                })
            if self.txt_filename:
                files_to_move.append({
                    "type": "TXT",
                    "source": self.txt_filename,
                    "dest": f"{base_prefix}/{os.path.basename(self.txt_filename)}",
                })
            if self.pdf_filename:
                files_to_move.append({
                    "type": "PDF",
                    "source": self.pdf_filename,
                    "dest": f"{base_prefix}/{os.path.basename(self.pdf_filename)}",
                })

            moved_files = 0
            for file_info in files_to_move:
                try:
                    if not self._s3_file_exists(file_info["source"]):
                        self.logger.warning(f"Source file not found: {file_info['source']}")
                        continue
                    move_file_in_s3(
                        bucket=self.bucket_name,
                        region=self.region,
                        source_key=file_info["source"],
                        destination_key=file_info["dest"],
                        access_key=self.access_key,
                        secret_key=self.secret_key,
                    )
                    self.logger.info(
                        f"Moved {file_info['type']} file: {file_info['source']} → {file_info['dest']}"
                    )
                    moved_files += 1
                except Exception as e:
                    self.logger.error(f"Failed to move {file_info['type']} file: {str(e)}")

            self.logger.info(
                f"File relocation to {root_prefix}/ completed. "
                f"Successfully moved {moved_files}/{len(files_to_move)} files"
            )
        except Exception as e:
            self.logger.error(f"Error during file relocation: {str(e)}", exc_info=True)

if __name__ == "__main__":
    raise RuntimeError("Please invoke BundleSubmissionHandler from a processor with valid XML S3 key.")