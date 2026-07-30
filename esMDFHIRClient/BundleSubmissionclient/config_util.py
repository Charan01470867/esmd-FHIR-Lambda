import os
import yaml
import logging

from esMDFHIRClient.BundleSubmissionclient.secrets_loader import get_secrets, get_from_secrets

_logger = logging.getLogger(__name__)


class ConfigUtility:
    # (secret_key, alt_keys, secret_source: "auth"|"loiss")
    # Uses auth.* key names from Secrets Manager (auth.token_endpoint, auth.client_id, etc.)
    _SECRET_KEYS = {
        "auth.token_endpoint": ("auth.token_endpoint", ["token_endpoint", "auth_token_endpoint"], "auth"),
        "auth.client_id": ("auth.client_id", ["client_id", "auth_client_id"], "auth"),
        "auth.client_secret": ("auth.client_secret", ["client_secret", "auth_client_secret"], "auth"),
        "auth.scope": ("auth.scope", ["scope", "auth_scope"], "auth"),
        "auth.grant_type": ("auth.grant_type", ["grant_type", "auth_grant_type"], "auth"),
        "LoissS3Bucket.S3_Bucket_Aws_Access_Key_Id": ("S3_Bucket_Aws_Access_Key_Id", ["s3_access_key_id"], "loiss"),
        "LoissS3Bucket.S3_Bucket_Aws_Secret_Access_Key": ("S3_Bucket_Aws_Secret_Access_Key", ["s3_secret_access_key"], "loiss"),
    }

    def __init__(self, config_file='config.yaml'):
        # Resolve config path: try cwd, then project root (for Lambda)
        _base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        for path in (config_file, os.path.join(_base, config_file), os.path.join(os.getcwd(), config_file)):
            if os.path.isfile(path):
                config_file = path
                break
        with open(config_file, 'r') as file:
            self.config = yaml.safe_load(file)
        auth_secret = self.config.get("secrets_manager_secret")
        loiss_secret = self.config.get("secrets_manager_secret_loiss")
        self._secrets = get_secrets(auth_secret) if auth_secret else {}
        self._loiss_secrets = get_secrets(loiss_secret) if loiss_secret else {}
        if not self._secrets:
            _logger.info("Using auth credentials from config.yaml (Secrets Manager unavailable or empty)")
        if not self._loiss_secrets:
            _logger.info("Using LoissS3Bucket credentials from config.yaml (Secrets Manager unavailable or empty)")

    def get_fhir_server_url(self):
        return self.config['server']['base_url']

    def get_presigned_url_base(self):
        return self.config['server']['presigned_base_url']

    def get_timeout(self):
        return self.config['server']['timeout']

    def get_auth_token(self):
        return os.getenv('ACCESS_TOKEN')

    def get_token_endpoint(self):
        v = get_from_secrets(self._secrets, "auth.token_endpoint", ["token_endpoint", "auth_token_endpoint"])
        return v or self.config.get('auth', {}).get('token_endpoint', '')

    def get_client_id(self):
        v = get_from_secrets(self._secrets, "auth.client_id", ["client_id", "auth_client_id"])
        return v or self.config.get('auth', {}).get('client_id', '')

    def get_client_secret(self):
        v = get_from_secrets(self._secrets, "auth.client_secret", ["client_secret", "auth_client_secret"])
        return v or self.config.get('auth', {}).get('client_secret', '')

    def get_scope(self):
        v = get_from_secrets(self._secrets, "auth.scope", ["scope", "auth_scope"])
        return v or self.config.get('auth', {}).get('scope', '')

    def get_grant_type(self):
        v = get_from_secrets(self._secrets, "auth.grant_type", ["grant_type", "auth_grant_type"])
        return v or self.config.get('auth', {}).get('grant_type', 'client_credentials')

    def _get_from_config(self, key_path, default=""):
        """Fallback: get value from config.yaml (auth or LoissS3Bucket)."""
        try:
            keys = key_path.split(".")
            value = self.config
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_oid(self):
        return self.config['org']['oid']

    def get_logging_level(self):
        return self.config['logging']['level']

    def get_value(self, key_path):
        """Get value; prefer AWS Secrets Manager, fall back to auth/LoissS3Bucket in config.yaml."""
        mapping = self._SECRET_KEYS.get(key_path)
        if mapping:
            secret_key, alts, source = mapping
            secrets = self._loiss_secrets if source == "loiss" else self._secrets
            v = get_from_secrets(secrets, secret_key, alts)
            if v:
                return v
            # Secrets Manager unavailable or missing key: use config.yaml
            return self._get_from_config(key_path, "")
        return self._get_from_config(key_path, "")


# Usage example:
if __name__ == "__main__":
    config_util = ConfigUtility()

    # Example usage
    print("FHIR Server URL:", config_util.get_fhir_server_url())
    print("Client ID:", config_util.get_client_id())
    print("Timeout:", config_util.get_timeout())

    # Make sure to set the ACCESS_TOKEN environment variable
    print("Access Token:", config_util.get_auth_token())
