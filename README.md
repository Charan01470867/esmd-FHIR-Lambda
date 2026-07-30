## Overview

A serverless Python application that processes FHIR-based healthcare document workflows using AWS services. The solution validates incoming requests, orchestrates event-driven processing, and provides secure, scalable document handling.

## Features

- FHIR document processing
- Metadata validation
- Event-driven architecture
- AWS Lambda integration
- Amazon S3 document storage
- Amazon SQS message processing
- Amazon SNS notifications
- CloudWatch monitoring
- Error handling and logging
- Configuration-driven deployment

## Technology Stack

- Python
- AWS Lambda
- Amazon S3
- Amazon SQS
- Amazon SNS
- AWS CloudWatch
- YAML
- JSON

## Architecture

```text
Client
   │
   ▼
Amazon S3
   │
   ▼
Amazon SQS
   │
   ▼
AWS Lambda
   │
   ├── Metadata Validation
   ├── FHIR Processing
   ├── Business Logic
   └── Error Handling
   │
   ▼
Amazon SNS
   │
   ▼
CloudWatch Logs
```

## Project Structure

```text
├── handlers/
├── services/
├── utils/
├── yaml/
├── config/
├── requirements.txt
└── README.md
```

## Key Capabilities

- Serverless document processing
- Secure cloud integration
- Metadata validation
- Exception handling
- Logging and monitoring
- Scalable event-driven workflows


