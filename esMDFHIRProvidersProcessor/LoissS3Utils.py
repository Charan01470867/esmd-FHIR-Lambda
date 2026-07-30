# LoissS3Utils.py

import requests
import boto3
from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth
from botocore.credentials import Credentials



def s3_request(method, bucket, region, key, access_key, secret_key, data=None, content_type="application/octet-stream"):
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    headers = {
        "Host": f"{bucket}.s3.{region}.amazonaws.com",
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD"
    }

    if method == "PUT":
        headers["Content-Type"] = content_type

    aws_request = AWSRequest(method=method, url=url, data=data, headers=headers)
    credentials = Credentials(access_key, secret_key)
    SigV4Auth(credentials, "s3", region).add_auth(aws_request)

    signed_headers = dict(aws_request.headers)

    if method == "GET":
        print(f"[DEBUG] S3 Request URL: {url}")
        print(f"[DEBUG] Method: {method}")
        response = requests.get(url, headers=signed_headers, timeout=10)
        print(f"[DEBUG] Response Status: {response.status_code}")
        return response
    elif method == "PUT":
        return requests.put(url, headers=signed_headers, data=data)
    elif method == "DELETE":
        return requests.delete(url, headers=signed_headers)
    else:
        raise ValueError("Unsupported method. Use GET, PUT, or DELETE.")


def download_file_from_s3(bucket, region, key, access_key, secret_key):
    try:
        print(f"bucket = {bucket} and key is = {key}")
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=bucket, Key=key)
        file_content = response['Body'].read()
        print(f"Downloaded {key} from {bucket}")
        return file_content
    except Exception as e:
        print(f"Error downloading {key} from {bucket}: {e}")
        return None


def upload_file_to_s3(bucket, region, key, access_key, secret_key, file_path, content_type="application/xml"):
    """
    Upload file to S3 bucket.
    
    Args:
        bucket: S3 bucket name
        region: AWS region
        key: S3 object key (path)
        access_key: AWS access key
        secret_key: AWS secret key
        file_path: File data as bytes or file path string
        content_type: Content type for the file
    
    Returns:
        None (raises exception on failure)
    """
    if isinstance(file_path, (bytes, bytearray)):
        file_data = file_path
    else:
        with open(file_path, "rb") as f:
            file_data = f.read()

    # Log upload attempt
    print(f"[S3 Upload] Uploading to s3://{bucket}/{key} (size: {len(file_data)} bytes)")
    
    response = s3_request("PUT", bucket, region, key, access_key, secret_key, data=file_data, content_type=content_type)

    if response.status_code != 200:
        error_msg = f"Failed to upload {key} to s3://{bucket}/{key} | Status: {response.status_code} | Response: {response.text}"
        print(f"[S3 Upload Error] {error_msg}")
        raise Exception(error_msg)
    
    print(f"[S3 Upload Success] Successfully uploaded s3://{bucket}/{key}")


def delete_file_from_s3(bucket, region, key, access_key, secret_key):
    response = s3_request("DELETE", bucket, region, key, access_key, secret_key)
    if response.status_code != 204:
        raise Exception(f"Failed to delete {key} | Status: {response.status_code} | {response.text}")


def move_file_in_s3(bucket, region, source_key, destination_key, access_key, secret_key):
    # Copy
    print(f"[DEBUG] Moving S3 file: {source_key} -> {destination_key}")
    copy_source = f"/{bucket}/{source_key}"
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{destination_key}"
    headers = {
        "x-amz-copy-source": copy_source,
        "x-amz-metadata-directive": "COPY",
        "Host": f"{bucket}.s3.{region}.amazonaws.com",
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD"
    }

    aws_request = AWSRequest(method="PUT", url=url, headers=headers)
    credentials = Credentials(access_key, secret_key)
    SigV4Auth(credentials, "s3", region).add_auth(aws_request)
    signed_headers = dict(aws_request.headers)

    response = requests.put(url, headers=signed_headers)
    if response.status_code != 200:
        raise Exception(f"Failed to copy {source_key} to {destination_key} | Status: {response.status_code} | {response.text}")
    else:
        print(f"Moved file: {source_key} -> {destination_key}")
    # Delete source
    delete_file_from_s3(bucket, region, source_key, access_key, secret_key)





