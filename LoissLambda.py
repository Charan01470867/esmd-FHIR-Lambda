"""
LoissLambda.py

AWS Lambda handler file that runs when a .PDF file is uploaded to:
s3://esmdautomation/REQUESTS/FILES/

This script triggers the LoissFileProcessHandler to:
- Download the latest TXT/PDF from S3
- Convert to CCD .xml
- Submit via FHIR client
"""
import boto3
import json
import urllib.parse
import requests

from esMDFHIRProvidersProcessor.LoissSingleFileProcessHandler import LoissSingleFileProcessHandler

def lambda_handler(event, context):
    """
    Lambda handler for S3 file uploads (bundle submission).
    
    This handler processes PDF files uploaded to S3 and submits them as FHIR bundles.
    Compatible with S3 direct triggers, SNS, and SQS event sources.
    
    For notification retrieval, see the standalone esMDNotificationRetrieval project.
    """
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    logger.info("="*70)
    logger.info("LoissLambda: Processing S3 file upload (Bundle Submission)")
    logger.info("="*70)
    logger.info(f"Raw event: {json.dumps(event)}")
    
    try:
        # Log outbound IP address (useful for VPC debugging)
        try:
            ip = requests.get('https://checkip.amazonaws.com', timeout=5).text.strip()
            logger.info(f"Outbound IP address: {ip}")
        except Exception as ip_err:
            logger.warning(f"Could not determine outbound IP: {ip_err}")
        
        records = event.get('Records', [])
        if not records:
            logger.warning("No 'Records' key or it's empty")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "message": "No records found in event",
                    "status": "error"
                })
            }
        
        results = []
        for record in event['Records']:
            try:
                # Handle SQS event structure: S3 -> SNS -> SQS -> Lambda
                # The SQS record has a 'body' field containing the SNS message
                # The SNS message has a 'Message' field containing the S3 event
                
                bucket = None
                key = None
                
                # Step 1: Parse SQS body
                if 'body' in record:
                    sqs_body = json.loads(record['body'])
                    logger.info(f"SQS body: {json.dumps(sqs_body)}")
                    
                    def extract_from_s3_records(records_list):
                        nonlocal bucket, key
                        for s3_record in records_list or []:
                            if 's3' in s3_record:
                                bucket = s3_record['s3']['bucket']['name']
                                key = urllib.parse.unquote_plus(s3_record['s3']['object']['key'])
                                return
                    
                    # Raw SNS -> SQS: body is the published payload (full S3 event JSON with Records).
                    # Default SNS -> SQS: body is an envelope; S3 event is inside Message.
                    if 'Records' in sqs_body:
                        extract_from_s3_records(sqs_body['Records'])
                    
                    if not bucket or not key:
                        if 'Message' in sqs_body:
                            sns_message_str = sqs_body['Message']
                            sns_message = json.loads(sns_message_str)
                            logger.info(f"SNS message: {json.dumps(sns_message)}")
                            
                            if 'Records' in sns_message:
                                extract_from_s3_records(sns_message['Records'])
                            elif 'bucket' in sns_message and 'key' in sns_message:
                                bucket = sns_message['bucket']
                                key = sns_message['key']
                        elif 'bucket' in sqs_body and 'key' in sqs_body:
                            bucket = sqs_body['bucket']
                            key = sqs_body['key']
                
                # Step 4: Check if record has S3 event directly (direct S3 trigger)
                elif 's3' in record:
                    bucket = record['s3']['bucket']['name']
                    key = urllib.parse.unquote_plus(record['s3']['object']['key'])
                
                # Validate we found bucket and key
                if not bucket or not key:
                    logger.error(f"Could not extract bucket/key from event. Record structure: {json.dumps(record)}")
                    results.append({
                        "status": "error",
                        "message": "Missing bucket or key in S3 event",
                        "record": record
                    })
                    continue
                
                logger.info(f"Processing file: s3://{bucket}/{key}")
                
                # Execute main Loiss file processing
                handler = LoissSingleFileProcessHandler(key)  # config.yaml controls use_s3, etc.
                handler.process()
                
                results.append({
                    "status": "success",
                    "bucket": bucket,
                    "key": key,
                    "message": "File processed and bundle submitted successfully"
                })
                
            except Exception as e:
                logger.exception(f"Error processing record: {e}")
                results.append({
                    "status": "error",
                    "message": str(e)
                })
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Bundle submission processing completed",
                "results": results,
                "status": "success"
            })
        }
    
    except Exception as e:
        logger.exception(f"Error in LoissLambda handler: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": f"Error processing bundle submission: {str(e)}",
                "status": "error"
            })
        }
