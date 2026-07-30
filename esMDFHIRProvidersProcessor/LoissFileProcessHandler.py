# # LoissFileProcessHandler.py

import os
import json
import base64
import boto3
from xml.etree import ElementTree as ET
from xml.dom import minidom

from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger
from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility
from esMDFHIRProvidersProcessor.LoissS3Utils import download_file_from_s3, upload_file_to_s3
from esMDFHIRClient.BundleSubmissionHandler import BundleSubmissionHandler

class LoissFileProcessHandler:
    def __init__(self):
        self.config = ConfigUtility()
        self.logger = setup_logger(self.__class__.__name__)

        # Load S3 credentials and prefixes from config.yaml
        self.bucket_name = self.config.get_value("LoissS3Bucket.Loiss_S3_Bucket")
        self.region = self.config.get_value("LoissS3Bucket.Region_Name")
        self.access_key = self.config.get_value("LoissS3Bucket.S3_Bucket_Aws_Access_Key_Id")
        self.secret_key = self.config.get_value("LoissS3Bucket.S3_Bucket_Aws_Secret_Access_Key")

        self.txt_folder_s3 = self.config.get_value("LoissS3Bucket.TXT_File")
        self.pdf_folder_s3 = self.config.get_value("LoissS3Bucket.PDF_File")
        self.generated_folder_s3 = self.config.get_value("LoissS3Bucket.Generated_XMLPath")
        self.response_prefix = self.config.get_value("LoissS3Bucket.Response_Prefix")
        self.processed_prefix = self.config.get_value("LoissS3Bucket.Processed_Files")

    def run(self):
        """Main processing method"""
        self.logger.info("Starting Loiss file processing handler")

        # Get list of all TXT files in S3 folder
        txt_filenames = self.list_txt_files_in_s3()

        if not txt_filenames:
            self.logger.warning("No TXT files found in S3 folder")
            return

        self.logger.info(f"Found {len(txt_filenames)} TXT files to process")

        for txt_filename in txt_filenames:
            self.logger.info(f"Processing file: {txt_filename}")
            ccd_xml, xml_filename, xml_s3_key, txt_s3_key, pdf_s3_key, metadata = self.process_txt_file(txt_filename)
            if not ccd_xml or not xml_filename:
                self.logger.error(f"Skipping file {txt_filename} due to previous errors.")
                continue

            # Encode XML content as bytes before upload
            xml_bytes = ccd_xml.encode("utf-8")

            # Upload generated XML to S3
            uploaded_key = self.upload_xml_to_s3(xml_bytes, xml_filename)
            if not uploaded_key:
                continue

            # Submit XML directly from S3
            self.logger.info(f"Submitting CCD XML from S3: {xml_s3_key}")
            BundleSubmissionHandler(xml_filepath=xml_s3_key,
                                    txt_filename=txt_s3_key,
                                    pdf_filename=pdf_s3_key,
                                    metadata=metadata).run()

        self.logger.info("All Loiss files processed")

    def get_s3_client(self):
        # Create and return a Boto3 S3 client
        return boto3.client(
            's3',
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )

    def list_txt_files_in_s3(self):
        # List all .TXT files in the TXT folder on S3
        try:
            s3 = self.get_s3_client()
            response = s3.list_objects_v2(Bucket=self.bucket_name, Prefix=self.txt_folder_s3)
            txt_files = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.lower().endswith('.txt'):
                    txt_files.append(os.path.basename(key))
            return txt_files
        except Exception as e:
            self.logger.error(f"Failed to list TXT files from S3: {e}")
            return []

    def process_txt_file(self, txt_filename):
        """Process a single TXT file and generate corresponding XML and paths"""
        txt_path = f"{self.txt_folder_s3}/{txt_filename}"
        txt_bytes = self.fetch_file(txt_path)    
        if not txt_bytes:
            return None, None, None, None, None

        lines = txt_bytes.decode("utf-8").splitlines()        
        metadata = self.parse_metadata(lines)
        self.logger.info(f"Text File name with path is {metadata}");
        esmd_claimid = metadata.get("esMDClaimID")
        self.logger.info(f"esMD Claim ID is = {esmd_claimid}");
        pdf_filename = metadata.get("file")
        self.logger.info(f"PDF FIle Name is = {pdf_filename}");
        if not pdf_filename:
            self.logger.error("PDF filename not found in TXT metadata.")
            return None, None, None, None, None

        pdf_path = f"{self.pdf_folder_s3}/{pdf_filename}"
        pdf_bytes = self.fetch_file(pdf_path)
        if not pdf_bytes:
            return None, None, None, None, None

        # Convert PDF to base64 and generate CCD XML
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        ccd_xml = self.generate_ccd_xml(metadata, pdf_b64)
        xml_filename = os.path.splitext(txt_filename)[0] + ".xml"
        xml_s3_key = f"{self.generated_folder_s3}/{xml_filename}"

        return ccd_xml, xml_filename, xml_s3_key, txt_path, pdf_path, metadata

    def fetch_file(self, s3_key):        
        # Download a file from S3 using utility function
        return download_file_from_s3(self.bucket_name, self.region, s3_key, self.access_key, self.secret_key)

    def upload_xml_to_s3(self, xml_bytes, xml_filename):
        # Upload encoded XML file to the GeneratedXML S3 folder
        s3_key = f"{self.generated_folder_s3}/{xml_filename}"
        upload_file_to_s3(
            bucket=self.bucket_name,
            region=self.region,
            key=s3_key,
            access_key=self.access_key,
            secret_key=self.secret_key,
            file_path=xml_bytes,
            content_type="application/xml"
        )
        self.logger.info(f"Uploaded generated XML to S3 at: {s3_key}")
        return s3_key

    def parse_metadata(self, lines):
        # Convert lines in TXT to a metadata dictionary
        metadata = {}
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                metadata[key.strip()] = value.strip()
        return metadata

    def generate_ccd_xml(self, metadata_dict, pdf_base64):
        # Build CCD-compliant XML from metadata and base64-encoded PDF
        NS = "urn:hl7-org:v3"
        ET.register_namespace("", NS)

        root = ET.Element("{%s}ClinicalDocument" % NS, attrib={
            "classCode": "DOCCLIN",
            "moodCode": "EVN"
        })

        ET.SubElement(root, "{%s}typeId" % NS, {
            "root": "2.16.840.1.113883.1.3",
            "extension": "POCD_HD000040"
        })

        ET.SubElement(root, "{%s}templateId" % NS, {
            "root": "2.16.840.1.113883.10.20.1"
        })

        ET.SubElement(root, "{%s}id" % NS, {
            "root": "2.16.840.1.113883.3.72",
            "extension": metadata_dict.get("uniqueID", "UNKNOWN")
        })

        ET.SubElement(root, "{%s}code" % NS, {
            "code": "34133-9",
            "codeSystem": "2.16.840.1.113883.6.1"
        })

        ET.SubElement(root, "{%s}title" % NS).text = metadata_dict.get("title", "Clinical Document")

        ET.SubElement(root, "{%s}effectiveTime" % NS, {
            "value": metadata_dict.get("creationTime", "")
        })

        record_target = ET.SubElement(root, "{%s}recordTarget" % NS)
        patient_role = ET.SubElement(record_target, "{%s}patientRole" % NS)
        ET.SubElement(patient_role, "{%s}id" % NS, {
            "extension": metadata_dict.get("patientID2", "UNKNOWN")
        })

        author = ET.SubElement(root, "{%s}author" % NS)
        ET.SubElement(author, "{%s}time" % NS, {
            "value": metadata_dict.get("creationTime", "")
        })
        assigned_author = ET.SubElement(author, "{%s}assignedAuthor" % NS)
        ET.SubElement(assigned_author, "{%s}id" % NS, {
            "extension": metadata_dict.get("author2", "UNKNOWN")
        })

        custodian = ET.SubElement(root, "{%s}custodian" % NS)
        assigned_custodian = ET.SubElement(custodian, "{%s}assignedCustodian" % NS)
        ET.SubElement(assigned_custodian, "{%s}representedCustodianOrganization" % NS)

        component = ET.SubElement(root, "{%s}component" % NS)
        nonxml = ET.SubElement(component, "{%s}nonXMLBody" % NS, {
            "mediaType": "application/pdf"
        })
        ET.SubElement(nonxml, "{%s}text" % NS).text = pdf_base64

        rough_string = ET.tostring(root, encoding="utf-8", method="xml")

        try:
            pretty_xml = minidom.parseString(rough_string).toprettyxml(indent="  ")
            return pretty_xml
        except Exception as e:
            self.logger.warning(f"Pretty-printing failed, returning raw XML. Error: {e}")
        return rough_string.decode("utf-8")

if __name__ == "__main__":
    handler = LoissFileProcessHandler()
    handler.run()
