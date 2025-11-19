# crypto_services.py
import base64
import json
import os
import logging
import httpx
from kyberk2so.kem import (
    kem_encrypt_512 as kyber_kem_encrypt_512,
    kem_decrypt_512 as kyber_kem_decrypt_512,
)
from firebase_directory import FirebaseDirectory
from qkd_service import QKDService, QKDServiceError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

log = logging.getLogger(__name__)

class DecryptionError(Exception): pass
class EncryptionError(Exception): pass

class CryptoService:
    def __init__(self, base_url, qkd_server_url=None):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=20.0)
        self.directory = FirebaseDirectory("https://qu--mail-default-rtdb.firebaseio.com")
        
        # Initialize QKD service if URL is provided
        self.qkd_service = None
        if qkd_server_url:
            self.qkd_service = QKDService(qkd_server_url)
        else:
            # Initialize with default QKD server for simulation
            self.qkd_service = QKDService("http://127.0.0.1:8080")
        
        log.info(f"CryptoService initialized (local KEM, Firebase directory, QKD: enabled)")

    async def close(self):
        await self.client.aclose()
        await self.directory.close()
        if self.qkd_service:
            await self.qkd_service.close()
        
    async def get_public_key(self, user_id: str) -> str:
        pk_b64 = await self.directory.fetch_public_key(user_id)
        if not pk_b64:
            raise EncryptionError("Recipient public key not found in directory.")
        return pk_b64
        
    async def get_symmetric_key(self, key_length_bytes: int) -> (str, str):
        url = f"{self.base_url}/get-symmetric-key?key_length_bytes={key_length_bytes}"
        response = await self.client.get(url)
        response.raise_for_status()
        data = response.json()
        return data["key_id"], data["key_hex"]

    async def get_symmetric_key_by_id(self, key_id: str) -> str:
        url = f"{self.base_url}/get-symmetric-key-by-id/{key_id}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()["key_hex"]

    async def get_quantum_key(self, key_length_bytes: int = 32, recipient_email: str = None) -> dict:
        """Get a quantum key from QKD service"""
        if not self.qkd_service or not self.qkd_service.qkd_client:
            raise EncryptionError("QKD service not available or not initialized")
        
        try:
            return await self.qkd_service.get_quantum_key(key_length_bytes, recipient_email)
        except QKDServiceError as e:
            raise EncryptionError(f"Failed to get quantum key: {e}")

    async def get_quantum_key_by_id(self, key_id: str) -> dict:
        """Get a quantum key by ID from QKD service"""
        if not self.qkd_service or not self.qkd_service.qkd_client:
            raise EncryptionError("QKD service not available or not initialized")
        
        try:
            return await self.qkd_service.get_quantum_key_by_id(key_id)
        except QKDServiceError as e:
            raise EncryptionError(f"Failed to get quantum key by ID: {e}")

    def _derive_aes_key_from_quantum(self, quantum_key_hex: str, salt: bytes = None) -> bytes:
        """Derive AES key from quantum key using PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
        
        quantum_key_bytes = bytes.fromhex(quantum_key_hex)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit AES key
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(quantum_key_bytes)

    async def encrypt(self, main_body_bytes: bytes, attachments: list, **kwargs) -> str:
        security_level = kwargs.get("security_level")
        payload_dict = {
            'body': main_body_bytes.decode('utf-8'),
            'attachments': [{'filename': att['filename'], 'content_b64': base64.b64encode(att['content']).decode('utf-8')} for att in attachments]
        }
        
        if security_level == 4:
            return json.dumps({"qumail_version": "4.0", "security_level": 4, "plaintext_payload": payload_dict})

        plaintext_payload_bytes = json.dumps(payload_dict).encode('utf-8')
        
        if security_level == 3:
            aes_key = os.urandom(32)
            nonce = os.urandom(12)
            cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce))
            encryptor = cipher.encryptor()
            aes_ciphertext = encryptor.update(plaintext_payload_bytes) + encryptor.finalize()
            # Local Kyber KEM encapsulation using recipient public key from Firebase
            recipient_public_key_b64 = kwargs["recipient_public_key_b64"]
            kem_ciphertext, shared_secret = kyber_kem_encrypt_512(base64.b64decode(recipient_public_key_b64))
            encrypted_symmetric_key = bytes(x ^ y for x, y in zip(aes_key.ljust(len(shared_secret), b'\0'), shared_secret))
            return json.dumps({
                "qumail_version": "4.0", "security_level": 3,
                "kem_ciphertext_b64": base64.b64encode(kem_ciphertext).decode('utf-8'),
                "encrypted_symmetric_key_b64": base64.b64encode(encrypted_symmetric_key).decode('utf-8'),
                "aes_payload": {
                    "nonce_b64": base64.b64encode(nonce).decode('utf-8'),
                    "auth_tag_b64": base64.b64encode(encryptor.tag).decode('utf-8'),
                    "ciphertext_b64": base64.b64encode(aes_ciphertext).decode('utf-8')
                }
            })

        elif security_level in [1, 2]:
            encryption_method = kwargs.get("encryption_method", "pqc")  # Default to PQC for backward compatibility
            
            if encryption_method == "qkd":
                # Use QKD for quantum-secure encryption
                recipient_email = kwargs.get("recipient_email")
                if not recipient_email:
                    raise EncryptionError("Recipient email required for QKD encryption")
                
                # Get quantum key
                quantum_key_data = await self.get_quantum_key(
                    key_length_bytes=len(plaintext_payload_bytes), # Ensure key length matches payload for OTP
                    recipient_email=recipient_email
                )
                
                key_id = quantum_key_data["key_id"]
                quantum_key_hex = quantum_key_data["key_hex"]
                quantum_key = bytes.fromhex(quantum_key_hex)
                
                encrypted_payload = {}
                
                if security_level == 2: # Quantum-aided AES
                    # Derive AES key from quantum key
                    salt = os.urandom(16)
                    aes_key = self._derive_aes_key_from_quantum(quantum_key_hex, salt)
                    nonce = os.urandom(12)
                    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce))
                    encryptor = cipher.encryptor()
                    aes_ciphertext = encryptor.update(plaintext_payload_bytes) + encryptor.finalize()
                    encrypted_payload = {
                        'ciphertext_b64': base64.b64encode(aes_ciphertext).decode('utf-8'),
                        'nonce_b64': base64.b64encode(nonce).decode('utf-8'),
                        'auth_tag_b64': base64.b64encode(encryptor.tag).decode('utf-8'),
                        'salt_b64': base64.b64encode(salt).decode('utf-8')
                    }
                
                elif security_level == 1: # Quantum-secure OTP
                    if len(quantum_key) < len(plaintext_payload_bytes):
                        raise EncryptionError("Quantum OTP key is shorter than payload.")
                    xor_ciphertext = bytes([p ^ k for p, k in zip(plaintext_payload_bytes, quantum_key)])
                    encrypted_payload = {'ciphertext_b64': base64.b64encode(xor_ciphertext).decode('utf-8')}
                
                return json.dumps({
                    "qumail_version": "4.0", "security_level": security_level, 
                    "encryption_method": "qkd", "key_id": key_id,
                    "payload": encrypted_payload
                })
            
            else:
                # Use PQC for backward compatibility
                key_hex = kwargs["key_hex"]
                key_id = kwargs["key_id"]
                key = bytes.fromhex(key_hex)
                encrypted_payload = {}

                if security_level == 2: # AES
                    aes_key = key[:32]
                    nonce = os.urandom(12)
                    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce))
                    encryptor = cipher.encryptor()
                    aes_ciphertext = encryptor.update(plaintext_payload_bytes) + encryptor.finalize()
                    encrypted_payload = {
                        'ciphertext_b64': base64.b64encode(aes_ciphertext).decode('utf-8'),
                        'nonce_b64': base64.b64encode(nonce).decode('utf-8'),
                        'auth_tag_b64': base64.b64encode(encryptor.tag).decode('utf-8')
                    }
                
                elif security_level == 1: # OTP
                    if len(key) < len(plaintext_payload_bytes): 
                        raise EncryptionError("OTP key is shorter than payload.")
                    xor_ciphertext = bytes([p ^ k for p, k in zip(plaintext_payload_bytes, key)])
                    encrypted_payload = {'ciphertext_b64': base64.b64encode(xor_ciphertext).decode('utf-8')}
                
                return json.dumps({
                    "qumail_version": "4.0", "security_level": security_level, 
                    "encryption_method": "pqc", "key_id": key_id,
                    "payload": encrypted_payload
                })

    async def decrypt(self, json_string: str, **kwargs) -> dict:
        data = json.loads(json_string)
        security_level = data['security_level']
        
        if security_level == 4:
            payload = data.get("plaintext_payload", {})
            for att in payload.get('attachments', []):
                att['content'] = base64.b64decode(att['content_b64'])
            return payload

        decrypted_payload_bytes = b''
        if security_level == 3:
            aes_payload = data["aes_payload"]
            # Prefer local Kyber decapsulation using provided private key
            private_key_b64 = kwargs.get("private_key_b64")
            if private_key_b64:
                kem_ciphertext = base64.b64decode(data["kem_ciphertext_b64"])
                encrypted_symmetric_key = base64.b64decode(data["encrypted_symmetric_key_b64"])
                shared_secret = kyber_kem_decrypt_512(kem_ciphertext, base64.b64decode(private_key_b64))
                aes_key = bytes(x ^ y for x, y in zip(encrypted_symmetric_key, shared_secret))
            else:
                raise DecryptionError("Missing private key for local decapsulation.")

            aes_ciphertext = base64.b64decode(aes_payload['ciphertext_b64'])
            nonce = base64.b64decode(aes_payload['nonce_b64'])
            tag = base64.b64decode(aes_payload['auth_tag_b64'])
            
            try:
                cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce, tag))
                decryptor = cipher.decryptor()
                decrypted_payload_bytes = decryptor.update(aes_ciphertext) + decryptor.finalize()
            except InvalidTag:
                raise DecryptionError("AES-GCM tag verification failed. Message may be tampered with.")

        elif security_level in [1, 2]:
            encryption_method = data.get("encryption_method", "pqc")  # Default to PQC for backward compatibility
            
            if encryption_method == "qkd":
                # Use QKD for quantum-secure decryption
                key_id = data["key_id"]
                quantum_key_data = await self.get_quantum_key_by_id(key_id)
                quantum_key_hex = quantum_key_data["key_hex"]
                quantum_key = bytes.fromhex(quantum_key_hex)
                payload = data["payload"]
                
                if security_level == 2: # Quantum-aided AES
                    salt = base64.b64decode(payload['salt_b64'])
                    aes_key = self._derive_aes_key_from_quantum(quantum_key_hex, salt)
                    aes_ciphertext = base64.b64decode(payload['ciphertext_b64'])
                    nonce = base64.b64decode(payload['nonce_b64'])
                    tag = base64.b64decode(payload['auth_tag_b64'])
                    try:
                        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce, tag))
                        decryptor = cipher.decryptor()
                        decrypted_payload_bytes = decryptor.update(aes_ciphertext) + decryptor.finalize()
                    except InvalidTag:
                        raise DecryptionError("AES-GCM tag verification failed. Message may be tampered with.")

                elif security_level == 1: # Quantum-secure OTP
                    xor_ciphertext = base64.b64decode(payload['ciphertext_b64'])
                    if len(quantum_key) < len(xor_ciphertext): 
                        raise DecryptionError("Quantum OTP key is shorter than ciphertext.")
                    decrypted_payload_bytes = bytes([c ^ k for c, k in zip(xor_ciphertext, quantum_key)])
            
            else:
                # Use PQC for backward compatibility
                key_hex = kwargs["key_hex"]
                key = bytes.fromhex(key_hex)
                payload = data["payload"]
                
                if security_level == 2:
                    aes_key = key[:32]
                    aes_ciphertext = base64.b64decode(payload['ciphertext_b64'])
                    nonce = base64.b64decode(payload['nonce_b64'])
                    tag = base64.b64decode(payload['auth_tag_b64'])
                    try:
                        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce, tag))
                        decryptor = cipher.decryptor()
                        decrypted_payload_bytes = decryptor.update(aes_ciphertext) + decryptor.finalize()
                    except InvalidTag:
                        raise DecryptionError("AES-GCM tag verification failed. Message may be tampered with.")

                elif security_level == 1:
                    xor_ciphertext = base64.b64decode(payload['ciphertext_b64'])
                    if len(key) < len(xor_ciphertext): 
                        raise DecryptionError("OTP key is shorter than ciphertext.")
                    decrypted_payload_bytes = bytes([c ^ k for c, k in zip(xor_ciphertext, key)])
        
        decrypted_payload = json.loads(decrypted_payload_bytes)
        for att in decrypted_payload.get('attachments', []):
            att['content'] = base64.b64decode(att['content_b64'])
        return decrypted_payload

