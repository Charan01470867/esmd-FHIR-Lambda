import json
import io
import logging
from datetime import datetime
from esMDFHIRProvidersProcessor.LoissS3Utils import download_file_from_s3, upload_file_to_s3
from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger

log_key = "transaction/transaction_log.json"  # Folder inside S3 bucket

class LoissTransactionLogger:
    def __init__(self, bucket, region, access_key, secret_key, log_prefix):
        self.bucket = bucket
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.log_prefix = log_prefix
        self.log_key = f"{self.log_prefix}/transaction_log.json"
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_transactions(self):
        """Load transaction log from S3."""
        try:
            file_content = download_file_from_s3(
                self.bucket, self.region, self.log_key, self.access_key, self.secret_key
            )
            return json.loads(file_content.decode("utf-8"))
        except Exception:
            return []

    def save_transaction(self, entry):
        """Add a new entry to the transaction log."""
        data = self.load_transactions()
        data.append(entry)
        self._write_log_to_s3(data)

    def update_transaction_status(self, unique_id, new_status, additional_fields=None):
        """Update status in S3 log and optionally attach more data like transaction_id."""
        data = self.load_transactions()
        updated = False
        for txn in data:
            if txn.get("unique_id") == unique_id:
                txn["status"] = new_status
                txn["updated_at"] = datetime.utcnow().isoformat()
                if additional_fields:
                    txn.update(additional_fields)

                if new_status == "submitted":
                    txn["submitted_at"] = datetime.utcnow().isoformat()
                updated = True
                break
        if updated:
            self._write_log_to_s3(data)
            self.logger.info(f"Updated log pushed to S3 with transaction_id for unique_id: {unique_id}")
        return updated

    def find_transactions_by_status(self, status):
        """Return all transactions matching a status."""
        return [txn for txn in self.load_transactions() if txn.get("status") == status]

    def _write_log_to_s3(self, data):
        """Internal method to write updated log to S3."""
        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        upload_file_to_s3(
            bucket=self.bucket,
            region=self.region,
            key=self.log_key,
            access_key=self.access_key,
            secret_key=self.secret_key,
            file_path=json_bytes,
            content_type="application/json"
        )
        
