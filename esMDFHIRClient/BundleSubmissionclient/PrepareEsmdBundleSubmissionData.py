from datetime import datetime
import uuid
from esMDFHIRClient.BundleSubmissionclient.logger import setup_logger
import pytz
import re
import logging

# AttachmentControlNumber extension URL (optional; add only when contentTypeCode is 7)
ACN_EXTENSION_URL = "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-AttachmentControlNumber"
ACN_MAX_LENGTH = 80  # CMS constraint: if present, length must be 1-80 characters

class PrepareBundleSubmission:
    def __init__(self, bundle_id, list_id, extensions_data, identifiers_data):
        self.bundle_id = bundle_id
        self.list_id = list_id
        self.extensions_data = extensions_data
        self.identifiers_data = identifiers_data
        self.entries = []
        self.logger = logging.getLogger(__name__)

    def generate_fhir_timestamp(self):
        tz = pytz.timezone('America/New_York')
        current_time = datetime.now(tz)
        fhir_timestamp = current_time.strftime('%Y-%m-%dT%H:%M:%S%z')
        return fhir_timestamp[:-2] + ':' + fhir_timestamp[-2:]

    def is_valid_split_number(self, split):
        return bool(re.match(r"^\d{3}-\d$", split))

    def add_document_reference(self, doc_id, attachments):
        content_list = []
        for attachment in attachments:
            sha256_hash = attachment.get('sha256_hash')
            if not sha256_hash:
                self.logger.error("Missing SHA-256 hash in attachment!")
                raise ValueError("SHA-256 hash is required for DocumentReference")

            self.logger.debug(f"Using SHA-256 hash for DocumentReference: {sha256_hash}")
            content_list.append({
                "attachment": {
                    "id": attachment.get("filename"),
                    "contentType": attachment.get("content_type", "application/xml"),
                    "url": attachment.get("uploaded_url"),
                    "size": attachment.get("size", 0),
                    "hash": sha256_hash,
                    "title": attachment.get("filename"),
                    "creation": self.generate_fhir_timestamp()
                },
                "format": {
                    "system": "urn:oid:1.3.6.1.4.1.19376.1.2.3",
                    "code": "urn:ihe:pcc:handp:2008"
                }
            })

        identifiers = [
            {
                "use": "official",
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "ACSN",
                        "display": "Accession ID"
                    }]
                },
                "system": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Idn-UniqueId",
                "value": self.identifiers_data.get("UniqueIdValue")
            }
        ]

        if self.identifiers_data.get("LetterIdValue"):
            identifiers.append({
                "use": "official",
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "FILL",
                        "display": "Filler Identifier"
                    }]
                },
                "system": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Idn-LetterId",
                "value": self.identifiers_data.get("LetterIdValue")
            })

        document_reference_entry = {
            "fullUrl": f"{doc_id}",
            "resource": {
                "resourceType": "DocumentReference",
                "id": f"{doc_id}",
                "meta": {
                    "profile": [
                        "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-DocumentReference"
                    ],
                    "security": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                            "code": "V",
                            "display": "very restricted"
                        }
                    ]
                },
                "text": {
                    "status": "generated",
                    "div": "<div xmlns='http://www.w3.org/1999/xhtml'>DocumentReference for esMD submission</div>"
                },
                "identifier": identifiers,
                "status": "current",
                "date": self.generate_fhir_timestamp(),
                "category": [
                    {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": "47039-3",
                                "display": "Inpatient Admission history and physical note"
                            }
                        ]
                    }
                ],
                "securityLabel": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                                "code": "V",
                                "display": "Very-Restricted"
                            }
                        ]
                    }
                ],
                "content": content_list,
                "context": {
                    "facilityType": {
                        "coding": [
                            {
                                "system": "https://terminology.esmduat.cms.gov:8099/fhir/CodeSystem/Esmd-CS-FacilityTypeCodes",
                                "code": "hih",
                                "display": "Health Information Handler (HIH)"
                            }
                        ]
                    }
                }
            },
            "request": {
                "method": "POST",
                "url": "DocumentReference"
            }
        }
        self.entries.append(document_reference_entry)

    def build_bundle(self):
        extensions = [
            {
                "url": "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-Ext-OrganizationId",
                "valueString": self.extensions_data.get("SenderOidValue")
            },
            {
                "url": self.extensions_data.get("IntendedRecipient"),
                "valueCode": self.extensions_data.get("IntendedRecipientValue")
            },
            {
                "url": self.extensions_data.get("LinesOfBusinessId"),
                "valueCode": self.extensions_data.get("LinesOfBusinessIdValue")
            },
            {
                "url": self.extensions_data.get("UniqueId"),
                "valueString": self.extensions_data.get("UniqueIdValue")
            },
            {
                "url": self.extensions_data.get("Npi"),
                "valueString": self.extensions_data.get("NpiValue")
            }
        ]

        if self.extensions_data.get("CaseIdValue"):
            extensions.append({
                "url": self.extensions_data.get("CaseId"),
                "valueString": self.extensions_data.get("CaseIdValue")
            })

        if self.extensions_data.get("ParentUniqueIdValue"):
            extensions.append({
                "url": self.extensions_data.get("ParentUniqueId"),
                "valueString": self.extensions_data.get("ParentUniqueIdValue")
            })

        if self.extensions_data.get("SplitNumberValue"):
            extensions.append({
                "url": self.extensions_data.get("SplitNumber"),
                "valueString": self.extensions_data.get("SplitNumberValue")
            })

        if self.extensions_data.get("ClaimIdValue"):
            extensions.append({
                "url": self.extensions_data.get("ClaimId"),
                "valueString": self.extensions_data.get("ClaimIdValue")
            })

        # AttachmentControlNumber is optional; add only when contentTypeCode is 7
        # CMS constraint: if present, length must be 1-80 characters
        contentTypeCode = str(self.extensions_data.get("LinesOfBusinessIdValue", "")).strip()
        if contentTypeCode == "7":
            acn_value = self.extensions_data.get("AttachmentControlNumberValue")
            if acn_value and str(acn_value).strip():
                # Use provided value, ensure 1-80 chars
                acn_value = str(acn_value).strip()[:ACN_MAX_LENGTH]
            else:
                # Generate UUID-based value (alphanumeric, always valid, 36 chars)
                acn_value = str(uuid.uuid4())
            acn_url = self.extensions_data.get("AttachmentControlNumber") or ACN_EXTENSION_URL
            extensions.append({
                "url": acn_url,
                "valueString": acn_value
            })

        if self.extensions_data.get("ResponseTypeCategoryValue"):
            extensions.append({
                "url": self.extensions_data.get("ResponseTypeCategory"),
                "valueString": self.extensions_data.get("ResponseTypeCategoryValue")
            })

        if self.extensions_data.get("ReviewContractorOidValue"):
            extensions.append({
                "url": self.extensions_data.get("ReviewContractorOid"),
                "valueCode": self.extensions_data.get("ReviewContractorOidValue")
            })

        identifiers = [
            {
                "system": self.identifiers_data.get("UniqueIdSystem"),
                "value": self.identifiers_data.get("UniqueIdValue")
            },
            {
                "system": self.identifiers_data.get("NpiSystem"),
                "value": self.identifiers_data.get("NpiValue")
            }
        ]

        list_entry = {
            "fullUrl": f"{self.list_id}",
            "resource": {
                "resourceType": "List",
                "id": f"{self.list_id}",
                "meta": {
                    "profile": [
                        "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-ListSubmissionSet"
                    ],
                    "security": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                            "code": "V",
                            "display": "very restricted"
                        }
                    ]
                },
                "text": {
                    "status": "generated",
                    "div": "<div xmlns='http://www.w3.org/1999/xhtml'>Submission Set List for esMD</div>"
                },
                "extension": extensions,
                "identifier": identifiers,
                "status": "current",
                "mode": "working",
                "title": "Submission Set Title",
                "date": self.generate_fhir_timestamp(),
                "entry": [
                    {
                        "item": {
                            "reference": f"DocumentReference/{self.entries[0]['resource']['id']}"
                        }
                    }
                ]
            },
            "request": {
                "method": "POST",
                "url": "List"
            }
        }

        bundle = {
            "resourceType": "Bundle",
            "id": f"{self.bundle_id}",
            "meta": {
                "profile": [
                    "https://terminology.esmduat.cms.gov:8099/fhir/StructureDefinition/Esmd-BundleSubmission"
                ],
                "security": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                        "code": "V"
                    }
                ]
            },
            "type": "transaction",
            "timestamp": self.generate_fhir_timestamp(),
            "entry": self.entries + [list_entry]
        }

        return bundle