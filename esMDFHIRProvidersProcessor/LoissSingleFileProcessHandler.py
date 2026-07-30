import os
import argparse
import base64
import logging
import tempfile
import boto3
from xml.sax.saxutils import escape

from esMDFHIRClient.BundleSubmissionclient.config_util import ConfigUtility
from esMDFHIRProvidersProcessor.LoissS3Utils import download_file_from_s3, upload_file_to_s3
from esMDFHIRClient.BundleSubmissionHandler import BundleSubmissionHandler

DEFAULT_WARN_THRESHOLD_MB = 50

class LoissSingleFileProcessHandler:
    def __init__(self, pdf_path):
        self.config = ConfigUtility()
        self.logger = logging.getLogger(__name__)
        #self.logger = setup_logger(self.__class__.__name__)
        self.pdf_path = pdf_path        
        self.txt_file_name = self.get_txt_filename_from_path(pdf_path)        
         # Load S3 credentials and prefixes from config.yaml
        self.bucket_name = self.config.get_value("LoissS3Bucket.Loiss_S3_Bucket")
        self.region = self.config.get_value("LoissS3Bucket.Region_Name")
        self.access_key = self.config.get_value("LoissS3Bucket.S3_Bucket_Aws_Access_Key_Id")
        self.secret_key = self.config.get_value("LoissS3Bucket.S3_Bucket_Aws_Secret_Access_Key")
        self.txt_folder_s3 = self.config.get_value("LoissS3Bucket.TXT_File")
        self.txt_path = f"{self.txt_folder_s3}/{self.txt_file_name}"
        self.pdf_folder_s3 = self.config.get_value("LoissS3Bucket.PDF_File")
        self.generated_folder_s3 = self.config.get_value("LoissS3Bucket.Generated_XMLPath")
        self.response_prefix = self.config.get_value("LoissS3Bucket.Response_Prefix")
        self.processed_prefix = self.config.get_value("LoissS3Bucket.Processed_Files")

    def _get_soft_limit_bytes(self):
        """
        Optional hard-enforce soft limit from environment:
        ESMD_PDF_SOFT_LIMIT_MB=75
        If unset/invalid, returns None (warn-only mode).
        """
        raw = os.getenv("ESMD_PDF_SOFT_LIMIT_MB")
        if not raw:
            return None
        try:
            mb = int(raw)
            if mb <= 0:
                print(f"[WARN] Ignoring invalid ESMD_PDF_SOFT_LIMIT_MB value: {raw}")
                return None
            return mb * 1024 * 1024
        except ValueError:
            print(f"[WARN] Ignoring non-numeric ESMD_PDF_SOFT_LIMIT_MB value: {raw}")
            return None
    
    def process(self):
        local_xml_path = None
        try:
            print(f"PDF File Path   : {self.pdf_path}")
            print(f"TXT File Path   : {self.txt_path}")   
            print("Calling process_txt_file function")
            local_xml_path, xml_filename, xml_s3_key, txt_s3_key, pdf_s3_key, metadata = self.process_txt_file()
            
            if not local_xml_path or not xml_filename:
                print(f"Skipping file {self.txt_path} due to previous errors.")
                return

            # Upload generated XML to S3
            uploaded_key = self.upload_xml_to_s3(local_xml_path, xml_filename)
            if not uploaded_key:
                print(f"Skipping file {self.txt_path} due to Upload errors.")
                return

            # Submit XML directly from S3
            print(f"Submitting CCD XML from S3: {uploaded_key}")
            BundleSubmissionHandler(xml_filepath=uploaded_key,
                                    txt_filename=txt_s3_key,
                                    pdf_filename=pdf_s3_key,
                                    metadata=metadata).run()

            print("All Loiss files processed")
        finally:
            if local_xml_path and os.path.exists(local_xml_path):
                try:
                    os.remove(local_xml_path)
                except OSError:
                    print(f"[WARN] Could not remove temp XML file: {local_xml_path}")
        
    def process_txt_file(self):
            print(f"Started processing txt file txt folder path is {self.txt_folder_s3}")
            print(f"txt file name is {self.txt_path}")
            """Process a single TXT file and generate corresponding XML and paths"""
            txt_path = self.txt_path  
            print(f"Fetching TXT from S3: {txt_path}")
            txt_bytes = self.fetch_file(txt_path)
            print(f"TXT fetch complete. Bytes: {len(txt_bytes) if txt_bytes else 'None'}")
            if not txt_bytes:
                return None, None, None, None, None, None

            lines = txt_bytes.decode("utf-8").splitlines()        
            metadata = self.parse_metadata(lines)
            print(f"Text File name with path is {metadata}")
            esmd_claimid = metadata.get("esMDClaimID")
            print(f"esMD Claim ID is = {esmd_claimid}")
            pdf_filename = metadata.get("file")
            print(f"PDF FIle Name is = {pdf_filename}")
            if not pdf_filename:
                print("PDF filename not found in TXT metadata.")
                return None, None, None, None, None, None

            pdf_path = f"{self.pdf_folder_s3}/{pdf_filename}"
            s3_client = boto3.client("s3")
            try:
                head = s3_client.head_object(Bucket=self.bucket_name, Key=pdf_path)
                pdf_size = head.get("ContentLength", 0)
            except Exception as e:
                print(f"[ERROR] Could not get PDF metadata for {pdf_path}: {e}")
                return None, None, None, None, None, None
            pdf_size_mb = pdf_size / (1024 * 1024)
            warn_threshold_bytes = DEFAULT_WARN_THRESHOLD_MB * 1024 * 1024
            soft_limit_bytes = self._get_soft_limit_bytes()
            print(f"[INFO] PDF size: {pdf_size} bytes ({pdf_size_mb:.2f} MB)")
            print(f"[INFO] Lambda memory-stage checkpoint: PDF bytes loaded for {pdf_filename}")
            if pdf_size >= warn_threshold_bytes:
                print(
                    f"[WARN] Large PDF detected (>= {DEFAULT_WARN_THRESHOLD_MB} MB): "
                    f"{pdf_filename} is {pdf_size_mb:.2f} MB"
                )

            # Convert PDF to base64 and generate CCD XML
            if soft_limit_bytes and pdf_size > soft_limit_bytes:
                print(
                    f"[ERROR] PDF exceeds configured ESMD_PDF_SOFT_LIMIT_MB "
                    f"({soft_limit_bytes} bytes): {pdf_size} bytes for {pdf_filename}"
                )
                return None, None, None, None, None, None
            temp_xml = tempfile.NamedTemporaryFile(delete=False, suffix=".xml")
            temp_xml_path = temp_xml.name
            temp_xml.close()
            print("[INFO] Starting streamed base64->XML generation...")
            self.generate_ccd_xml_file_streaming(metadata, pdf_path, temp_xml_path)
            xml_size = os.path.getsize(temp_xml_path)
            print(f"[INFO] Streamed CCD XML generated at {temp_xml_path} ({xml_size} bytes)")
            print(f"[INFO] Lambda memory-stage checkpoint: XML file ready for upload ({pdf_filename})")
            xml_filename = os.path.splitext(self.txt_path)[0] + ".xml"
            xml_s3_key = f"{self.generated_folder_s3}/{xml_filename}"

            return temp_xml_path, xml_filename, xml_s3_key, txt_path, pdf_path, metadata     

    def fetch_file(self, s3_key): 
        try:
            # Download a file from S3 using utility function
            content = download_file_from_s3(self.bucket_name, self.region, s3_key, self.access_key, self.secret_key)
            print(f"[INFO] Successfully downloaded: {s3_key} ({len(content)} bytes)")
            return content
        except Exception as e:
            print(f"[ERROR] Failed to download {s3_key}: {e}")       
        
         

    def upload_xml_to_s3(self, xml_source, xml_filename):
        # Upload encoded XML file to the GeneratedXML S3 folder
        s3_key = f"{self.generated_folder_s3}/{xml_filename}"
        upload_file_to_s3(
            bucket=self.bucket_name,
            region=self.region,
            key=s3_key,
            access_key=self.access_key,
            secret_key=self.secret_key,
            file_path=xml_source,
            content_type="application/xml"
        )
        print(f"Uploaded generated XML to S3 at: {s3_key}")
        return s3_key

    def _convert_to_txt_path(self, pdf_path):
            base, _ = os.path.splitext(pdf_path)
            return base + ".TXT"
    
    def get_txt_filename_from_path(self, pdf_path):
        filename = os.path.basename(pdf_path)  # file123.pdf
        base, _ = os.path.splitext(filename)
        return base + ".TXT"

    def parse_metadata(self, lines):
        # Convert lines in TXT to a metadata dictionary
        metadata = {}
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                metadata[key.strip()] = value.strip()
        return metadata

    def generate_ccd_xml(self, metadata_dict, pdf_base64):
        # Build CCD XML string directly to avoid ElementTree memory overhead for large payloads.
        title = escape(metadata_dict.get("title", "Clinical Document"))
        creation_time = escape(metadata_dict.get("creationTime", ""))
        unique_id = escape(metadata_dict.get("uniqueID", "UNKNOWN"))
        patient_id = escape(metadata_dict.get("patientID2", "UNKNOWN"))
        author = escape(metadata_dict.get("author2", "UNKNOWN"))
        return (
            '<?xml version="1.0" ?>'
            '<ClinicalDocument xmlns="urn:hl7-org:v3" classCode="DOCCLIN" moodCode="EVN">'
            '<typeId root="2.16.840.1.113883.1.3" extension="POCD_HD000040"/>'
            '<templateId root="2.16.840.1.113883.10.20.1"/>'
            f'<id root="2.16.840.1.113883.3.72" extension="{unique_id}"/>'
            '<code code="34133-9" codeSystem="2.16.840.1.113883.6.1"/>'
            f'<title>{title}</title>'
            f'<effectiveTime value="{creation_time}"/>'
            '<recordTarget><patientRole>'
            f'<id extension="{patient_id}"/>'
            '</patientRole></recordTarget>'
            '<author>'
            f'<time value="{creation_time}"/>'
            '<assignedAuthor>'
            f'<id extension="{author}"/>'
            '</assignedAuthor>'
            '</author>'
            '<custodian><assignedCustodian><representedCustodianOrganization/></assignedCustodian></custodian>'
            '<component><nonXMLBody mediaType="application/pdf">'
            f'<text>{pdf_base64}</text>'
            '</nonXMLBody></component>'
            '</ClinicalDocument>'
        )

    def generate_ccd_xml_file_streaming(self, metadata_dict, pdf_s3_key, output_file_path):
        """
        Stream PDF from S3 and write base64 directly into XML file to avoid large
        in-memory buffers in Lambda.
        """
        title = escape(metadata_dict.get("title", "Clinical Document"))
        creation_time = escape(metadata_dict.get("creationTime", ""))
        unique_id = escape(metadata_dict.get("uniqueID", "UNKNOWN"))
        patient_id = escape(metadata_dict.get("patientID2", "UNKNOWN"))
        author = escape(metadata_dict.get("author2", "UNKNOWN"))

        xml_prefix = (
            '<?xml version="1.0" ?>'
            '<ClinicalDocument xmlns="urn:hl7-org:v3" classCode="DOCCLIN" moodCode="EVN">'
            '<typeId root="2.16.840.1.113883.1.3" extension="POCD_HD000040"/>'
            '<templateId root="2.16.840.1.113883.10.20.1"/>'
            f'<id root="2.16.840.1.113883.3.72" extension="{unique_id}"/>'
            '<code code="34133-9" codeSystem="2.16.840.1.113883.6.1"/>'
            f'<title>{title}</title>'
            f'<effectiveTime value="{creation_time}"/>'
            '<recordTarget><patientRole>'
            f'<id extension="{patient_id}"/>'
            '</patientRole></recordTarget>'
            '<author>'
            f'<time value="{creation_time}"/>'
            '<assignedAuthor>'
            f'<id extension="{author}"/>'
            '</assignedAuthor>'
            '</author>'
            '<custodian><assignedCustodian><representedCustodianOrganization/></assignedCustodian></custodian>'
            '<component><nonXMLBody mediaType="application/pdf"><text>'
        )
        xml_suffix = "</text></nonXMLBody></component></ClinicalDocument>"

        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=self.bucket_name, Key=pdf_s3_key)
        body = obj["Body"]
        remainder = b""

        with open(output_file_path, "w", encoding="utf-8") as out_f:
            out_f.write(xml_prefix)
            for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                data = remainder + chunk
                usable_len = (len(data) // 3) * 3
                if usable_len:
                    out_f.write(base64.b64encode(data[:usable_len]).decode("ascii"))
                remainder = data[usable_len:]

            if remainder:
                out_f.write(base64.b64encode(remainder).decode("ascii"))
            out_f.write(xml_suffix)
    
    # Only runs when script is executed directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDF file and its corresponding TXT file.")
    parser.add_argument("pdf_path", help="Path to the PDF file")

    args = parser.parse_args()

    processor = LoissSingleFileProcessHandler(args.pdf_path)
    processor.process()


