"""Load sensitive credentials from AWS Secrets Manager."""
import json
import logging

_logger = logging.getLogger(__name__)
_cached = {}


def get_secrets(secret_name):
    """
    Fetch and parse secrets from AWS Secrets Manager.
    Returns dict of secret key-value pairs. Cached per secret_name.
    On failure, returns empty dict; callers will fall back to auth/LoissS3Bucket in config.yaml.
    Secret test/esmdfhir: auth.token_endpoint, auth.client_id, auth.client_secret, auth.scope, auth.grant_type
    Secret test/loisssecrets: S3_Bucket_Aws_Access_Key_Id, S3_Bucket_Aws_Secret_Access_Key
    """
    if secret_name in _cached:
        return _cached[secret_name]
    try:
        import boto3
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=secret_name)
        raw = resp.get("SecretString", "{}")
        data = json.loads(raw) if isinstance(raw, str) else raw
        _cached[secret_name] = data
        return data
    except Exception as e:
        _logger.warning(
            "Secrets Manager failed for %s: %s. Using auth and LoissS3Bucket from config.yaml.",
            secret_name, e
        )
        _cached[secret_name] = {}
        return {}


def get_from_secrets(secrets, key, alt_keys=None):
    """Get value from secrets dict, trying primary key and alternates."""
    if not secrets:
        return None
    for k in ([key] + (alt_keys or [])):
        v = secrets.get(k)
        if v:
            return v
    return None
