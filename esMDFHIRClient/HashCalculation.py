import hashlib  # For SHA-256 hashing

# Open the XML file in binary mode
with open("C:/Users/AbhilashAravelly/Downloads/claim_submission_3229.xml", "rb") as f:
    data = f.read()  # Read entire file content

    # Compute SHA-256 digest (binary)
    sha256_digest = hashlib.sha256(data).digest()

    # Print SHA-256 in hexadecimal format (64 characters)
    print("SHA-256 (hex):", sha256_digest.hex())


# Example Usage:
# This script is typically used to verify file integrity by comparing hashes.
# For instance, after transmitting a file, the recipient can recompute its MD5 hash
# and match it against the sender's provided hash (Base64 or Hex) to detect corruption.

# import base64
# import hashlib
# import xml.etree.ElementTree as ET
# import os

# def extract_base64_content(xml_file_path):
#     """
#     Extracts base64 content from <text representation="B64"> in an XML file.
#     """
#     try:
#         tree = ET.parse(xml_file_path)
#         root = tree.getroot()
#         ns = {'hl7': 'urn:hl7-org:v3'}
#         b64_node = root.find('.//hl7:text', ns)
#         if b64_node is None or not b64_node.text:
#             print("❌ Base64 content not found in <text> element.")
#             return None
#         return base64.b64decode(b64_node.text.strip())
#     except Exception as e:
#         print(f"❌ Error reading or parsing XML: {e}")
#         return None

# def compute_md5_base64(data_bytes):
#     md5_hash = hashlib.md5(data_bytes).digest()
#     return base64.b64encode(md5_hash).decode('utf-8')

# def compute_sha256_hex(data_bytes):
#     sha256_hash = hashlib.sha256(data_bytes).hexdigest()
#     return sha256_hash

# def main(xml_file_path):
#     if not os.path.exists(xml_file_path):
#         print(f"❌ File not found: {xml_file_path}")
#         return

#     decoded_bytes = extract_base64_content(xml_file_path)
#     if decoded_bytes is None:
#         return

#     md5_b64 = compute_md5_base64(decoded_bytes)
#     sha256_hex = compute_sha256_hex(decoded_bytes)

#     print(f"✅ MD5 (base64):     {md5_b64}")
#     print(f"✅ SHA-256 (hex):    {sha256_hex}")

# if __name__ == "__main__":
#     # 🔧 Set your local XML file path here
#     file_path = r"C:\fhir\testd\ProviderRequests\GeneratedXML\claim_submission_3228.xml"
#     main(file_path)

