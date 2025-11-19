# pqc_key_server.py
import base64
import logging
import secrets
import uuid
import sqlite3
import atexit
import sys
from typing import Optional

import oqs
from kyberk2so.kem import (
    kem_keypair_512 as kyber_kem_keypair_512,
    kem_encrypt_512 as kyber_kem_encrypt_512,
    kem_decrypt_512 as kyber_kem_decrypt_512,
)
from kyberk2so.params import Kyber512PKBytes, Kyber512SKBytes
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("PQC_Key_Server")

# --- Database Setup ---
DB_FILE = "keystore.db"

def init_db():
    log.info(f"Initializing and connecting to database at {DB_FILE}...")
    try:
        con = sqlite3.connect(DB_FILE, check_same_thread=False)
        cur = con.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS pqc_keys (
                userId TEXT PRIMARY KEY,
                publicKey_b64 TEXT NOT NULL,
                privateKey_b64 TEXT NOT NULL
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS symmetric_keys (
                key_id TEXT PRIMARY KEY,
                key_hex TEXT NOT NULL
            )
        ''')
        con.commit()
        log.info("Database initialized successfully.")
        return con
    except sqlite3.Error as e:
        log.critical(f"FATAL: Database initialization failed: {e}", exc_info=True)
        sys.exit(1)

db_connection = init_db()
atexit.register(db_connection.close)

# --- PQC Algorithm Definition ---
# Try a more reliable algorithm if Classic-McEliece-348864 is failing
PQC_ALGORITHM = "Kyber512"

app = FastAPI(
    title="Python Hybrid PQC & Symmetric Key Service (with Persistence)",
    version="3.3.1"
)

# --- Pydantic Models ---
class GenerateKeysRequest(BaseModel):
    userId: str

class GenerateKeysResponse(BaseModel):
    publicKey_b64: str
    privateKey_b64: str

class PublicKeyResponse(BaseModel):
    publicKey_b64: str

class EncapsulateRequest(BaseModel):
    publicKey_b64: str
    plaintextKey_b64: str

class EncapsulateResponse(BaseModel):
    kem_ciphertext_b64: str
    encrypted_symmetric_key_b64: str

class DecapsulateRequest(BaseModel):
    userId: str
    kem_ciphertext_b64: str
    encrypted_symmetric_key_b64: str

class DecapsulateResponse(BaseModel):
    plaintextKey_b64: str

class SymmetricKeyResponse(BaseModel):
    key_id: str
    key_hex: str

class SymmetricKeyByIdResponse(BaseModel):
    key_hex: str

def xor_bytes(a: bytes, b: bytes) -> bytes:
    # Pad the shorter input to the length of the longer one
    max_len = max(len(a), len(b))
    a = a.ljust(max_len, b'\0')
    b = b.ljust(max_len, b'\0')
    return bytes(x ^ y for x, y in zip(a, b))

# --- API Endpoints (Rewritten for DB) ---

@app.post("/generate-keys", response_model=GenerateKeysResponse)
def generate_keys(request: GenerateKeysRequest):
    log.info(f"Generating new key pair for userId: {request.userId}")
    try:
        kem = oqs.KEM(PQC_ALGORITHM)
        public_key = kem.generate_keypair()
        private_key = kem.export_secret_key()
        # Defensive: check for None or empty keys
        if not public_key or not private_key:
            log.error("Key generation returned empty keys.")
            raise Exception("Key generation failed: empty keys.")
    except Exception as e:
        log.critical(
            f"FATAL: OQS key generation failed. Attempting Kyber K2SO fallback. Error: {e}",
            exc_info=True,
        )
        try:
            private_key, public_key = kyber_kem_keypair_512()
        except Exception as k2e:
            log.critical("Kyber K2SO fallback key generation failed.", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Server crypto library failed to generate keys (OQS and Kyber K2SO). Error: {k2e}",
            )

    try:
        public_key_b64 = base64.b64encode(public_key).decode('utf-8')
        private_key_b64 = base64.b64encode(private_key).decode('utf-8')
    except Exception as e:
        log.error(f"Base64 encoding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Base64 encoding failed for generated keys.")

    try:
        cur = db_connection.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO pqc_keys (userId, publicKey_b64, privateKey_b64) VALUES (?, ?, ?)",
            (request.userId, public_key_b64, private_key_b64)
        )
        db_connection.commit()
        log.info(f"Stored PQC keys for {request.userId} in database.")
        return GenerateKeysResponse(publicKey_b64=public_key_b64, privateKey_b64=private_key_b64)
    except sqlite3.Error as e:
        log.error(f"DB Error on key generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error during key storage.")

@app.get("/get-public-key/{userId}", response_model=PublicKeyResponse)
def get_public_key(userId: str):
    try:
        cur = db_connection.cursor()
        cur.execute("SELECT publicKey_b64 FROM pqc_keys WHERE userId = ?", (userId,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail=f"Public key for user '{userId}' not found.")
        return PublicKeyResponse(publicKey_b64=result[0])
    except Exception as e:
        log.error(f"Error fetching public key for {userId}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch public key.")

@app.post("/decapsulate", response_model=DecapsulateResponse)
def decapsulate(request: DecapsulateRequest):
    log.info(f"Starting decapsulation for user {request.userId}")
    try:
        cur = db_connection.cursor()
        cur.execute("SELECT privateKey_b64 FROM pqc_keys WHERE userId = ?", (request.userId,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail=f"Private key for user '{request.userId}' not found.")

        private_key = base64.b64decode(result[0])
        kem_ciphertext = base64.b64decode(request.kem_ciphertext_b64)
        encrypted_symmetric_key = base64.b64decode(request.encrypted_symmetric_key_b64)

        try:
            kem = oqs.KEM(PQC_ALGORITHM)
            shared_secret = kem.decap_secret(kem_ciphertext, private_key)
        except Exception as e:
            log.warning(
                f"OQS decapsulation failed, trying Kyber K2SO fallback for user {request.userId}: {e}",
                exc_info=True,
            )
            # Fallback to Kyber K2SO
            try:
                shared_secret = kyber_kem_decrypt_512(kem_ciphertext, private_key)
            except Exception as k2e:
                log.error(f"Kyber K2SO decapsulation also failed: {k2e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Decapsulation failed.")
        decrypted_symmetric_key = xor_bytes(encrypted_symmetric_key, shared_secret)

        return DecapsulateResponse(
            plaintextKey_b64=base64.b64encode(decrypted_symmetric_key).decode('utf-8')
        )
    except Exception as e:
        log.error(f"Decapsulation failed for user {request.userId}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Decapsulation failed.")

@app.post("/encapsulate", response_model=EncapsulateResponse)
def encapsulate(request: EncapsulateRequest):
    try:
        public_key = base64.b64decode(request.publicKey_b64)
        plaintext_key = base64.b64decode(request.plaintextKey_b64)
        try:
            kem = oqs.KEM(PQC_ALGORITHM)
            kem_ciphertext, shared_secret = kem.encap_secret(public_key)
        except Exception as e:
            log.warning(
                f"OQS encapsulation failed, trying Kyber K2SO fallback: {e}",
                exc_info=True,
            )
            try:
                kem_ciphertext, shared_secret = kyber_kem_encrypt_512(public_key)
            except Exception as k2e:
                log.error(f"Kyber K2SO encapsulation also failed: {k2e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Encapsulation failed.")
        encrypted_symmetric_key = xor_bytes(plaintext_key, shared_secret)
        return EncapsulateResponse(
            kem_ciphertext_b64=base64.b64encode(kem_ciphertext).decode('utf-8'),
            encrypted_symmetric_key_b64=base64.b64encode(encrypted_symmetric_key).decode('utf-8')
        )
    except Exception as e:
        log.error(f"Encapsulation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Encapsulation failed.")

@app.get("/get-symmetric-key", response_model=SymmetricKeyResponse)
def get_symmetric_key(key_length_bytes: int):
    key_id = str(uuid.uuid4())
    key_hex = secrets.token_hex(key_length_bytes)
    try:
        cur = db_connection.cursor()
        cur.execute("INSERT INTO symmetric_keys (key_id, key_hex) VALUES (?, ?)", (key_id, key_hex))
        db_connection.commit()
        return SymmetricKeyResponse(key_id=key_id, key_hex=key_hex)
    except sqlite3.Error as e:
        log.error(f"DB Error on symmetric key generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error.")

@app.get("/get-symmetric-key-by-id/{key_id}", response_model=SymmetricKeyByIdResponse)
def get_symmetric_key_by_id(key_id: str):
    try:
        cur = db_connection.cursor()
        cur.execute("SELECT key_hex FROM symmetric_keys WHERE key_id = ?", (key_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Symmetric key not found.")
        key_hex = result[0]
        cur.execute("DELETE FROM symmetric_keys WHERE key_id = ?", (key_id,))
        db_connection.commit()
        return SymmetricKeyByIdResponse(key_hex=key_hex)
    except HTTPException:
        # Propagate explicit HTTP errors (e.g., 404) without converting to 500
        raise
    except Exception as e:
        log.error(f"Error fetching/deleting symmetric key {key_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch/delete symmetric key.")

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="127.0.0.1", port=8001)
    except Exception as e:
        log.critical(f"Uvicorn server failed to start: {e}", exc_info=True)
        sys.exit(1)
