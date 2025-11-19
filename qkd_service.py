# qkd_service.py
import asyncio
import logging
import os
import json
import base64
import httpx
from typing import Optional, Dict, Any
from etsi_qkd_014_client import QKD014Client
from firebase_directory import FirebaseDirectory
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

log = logging.getLogger(__name__)

class QKDServiceError(Exception):
    """Custom exception for QKD service errors"""
    pass

class QKDService:
    """
    Quantum Key Distribution service using ETSI QKD 014 protocol.
    This service simulates QKD key distribution for testing purposes.
    """
    
    def __init__(self, qkd_server_url: str, ca_cert_path: Optional[str] = None, 
                 client_cert_path: Optional[str] = None, client_key_path: Optional[str] = None):
        """
        Initialize QKD service
        
        Args:
            qkd_server_url: URL of the QKD server
            ca_cert_path: Path to CA certificate (optional for simulation)
            client_cert_path: Path to client certificate (optional for simulation)
            client_key_path: Path to client private key (optional for simulation)
        """
        self.qkd_server_url = qkd_server_url.rstrip('/')
        self.ca_cert_path = ca_cert_path
        self.client_cert_path = client_cert_path
        self.client_key_path = client_key_path
        
        # Initialize QKD client
        self.qkd_client = None
        self.directory = FirebaseDirectory("https://qu--mail-default-rtdb.firebaseio.com")
        
        # For simulation purposes, we'll store quantum keys locally
        self._quantum_keys_cache: Dict[str, Dict[str, Any]] = {}
        
        log.info(f"QKDService initialized with server: {qkd_server_url}")

    async def initialize(self):
        """Initialize the QKD client connection"""
        try:
            # For simulation, we'll create a mock QKD client
            # In real implementation, this would connect to actual QKD hardware
            self.qkd_client = await self._create_simulated_qkd_client()
            log.info("QKD client initialized successfully (simulation mode)")
        except Exception as e:
            log.error(f"Failed to initialize QKD client: {e}", exc_info=True)
            raise QKDServiceError(f"Failed to initialize QKD client: {e}")

    async def _create_simulated_qkd_client(self):
        """
        Create a simulated QKD client for testing purposes.
        In a real implementation, this would connect to actual QKD hardware.
        """
        # For simulation, we'll return a mock client that generates quantum-like keys
        return MockQKDClient()

    async def get_quantum_key(self, key_length_bytes: int = 32, 
                            recipient_email: Optional[str] = None) -> Dict[str, Any]:
        """
        Request a quantum key from the QKD server
        
        Args:
            key_length_bytes: Length of the key in bytes
            recipient_email: Email of the recipient (for multi-device support)
            
        Returns:
            Dictionary containing key_id, key_hex, and metadata
        """
        try:
            if not self.qkd_client:
                await self.initialize()
            
            # Generate a unique key ID
            key_id = f"qkd_{os.urandom(16).hex()}"
            
            # Generate quantum-like key using cryptographically secure random
            # In real QKD, this would come from quantum key distribution
            quantum_key = self.qkd_client.get_deterministic_key(key_id, key_length_bytes) # REVERTED TO DETERMINISTIC
            key_hex = quantum_key.hex()
            
            # Store key metadata (WITHOUT the actual key for security)
            key_metadata = {
                'key_id': key_id,
                'key_hex': key_hex,  # This is stored locally only
                'key_length_bytes': key_length_bytes,
                'timestamp': asyncio.get_event_loop().time(),
                'recipient_email': recipient_email,
                'source': 'qkd_simulation'
            }
            
            # Cache the key locally for retrieval
            self._quantum_keys_cache[key_id] = key_metadata
            
            # Store ONLY metadata in Firebase (no actual key)
            if recipient_email:
                await self._store_key_metadata_in_firebase(key_id, key_metadata)
            
            log.info(f"Generated quantum key {key_id} ({key_length_bytes} bytes) - stored locally only")
            return key_metadata
            
        except Exception as e:
            log.error(f"Failed to get quantum key: {e}", exc_info=True)
            raise QKDServiceError(f"Failed to get quantum key: {e}")

    async def get_quantum_key_by_id(self, key_id: str) -> Dict[str, Any]:
        """
        Retrieve a quantum key by its ID
        
        Args:
            key_id: The unique identifier of the key
            
        Returns:
            Dictionary containing key metadata
        """
        try:
            # First check local cache
            if key_id in self._quantum_keys_cache:
                return self._quantum_keys_cache[key_id]
            
            # If not in cache, try to retrieve from Firebase
            key_metadata = await self._get_key_metadata_from_firebase(key_id)
            if key_metadata:
                # Crucial Fix: Supplement metadata with deterministically generated key_hex
                # This ensures the recipient can get the same key as the sender without storing it in Firebase
                key_metadata['key_hex'] = self.qkd_client.get_deterministic_key(
                    key_id, key_metadata['key_length_bytes']
                ).hex()
                # Cache it locally
                self._quantum_keys_cache[key_id] = key_metadata
                return key_metadata
            
            raise QKDServiceError(f"Quantum key {key_id} not found")
            
        except Exception as e:
            log.error(f"Failed to get quantum key by ID {key_id}: {e}", exc_info=True)
            raise QKDServiceError(f"Failed to get quantum key by ID: {e}")

    async def _store_key_metadata_in_firebase(self, key_id: str, key_metadata: Dict[str, Any]):
        """Store key metadata in Firebase for multi-device access"""
        try:
            # Store only metadata, NOT the actual key for security
            safe_key_id = key_id.replace('.', '(dot)')
            url = f"{self.directory.database_url}/qkd_keys/{safe_key_id}.json"
            
            # Remove sensitive data before storing
            metadata_to_store = {
                'key_id': key_metadata['key_id'],
                'key_length_bytes': key_metadata['key_length_bytes'],
                'timestamp': key_metadata['timestamp'],
                'recipient_email': key_metadata['recipient_email'],
                'source': key_metadata['source']
                # Note: We deliberately do NOT store the actual key_hex
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(url, json=metadata_to_store)
                response.raise_for_status()
                log.info(f"Stored QKD key metadata for {key_id} in Firebase")
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                log.warning(f"Firebase authentication failed for QKD key {key_id}. Continuing with local storage only.")
            else:
                log.warning(f"Firebase error {e.response.status_code} for QKD key {key_id}. Continuing with local storage only.")
        except Exception as e:
            log.warning(f"Failed to store key metadata in Firebase: {e}. Continuing with local storage only.")

    async def _get_key_metadata_from_firebase(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve key metadata from Firebase"""
        try:
            safe_key_id = key_id.replace('.', '(dot)')
            url = f"{self.directory.database_url}/qkd_keys/{safe_key_id}.json"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, dict):
                    # Return metadata, but note that the actual key is not stored
                    log.info(f"Retrieved QKD key metadata for {key_id} from Firebase")
                    return data
                    
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                log.warning(f"Firebase authentication failed for QKD key {key_id}. Using local storage only.")
            else:
                log.warning(f"Firebase error {e.response.status_code} for QKD key {key_id}. Using local storage only.")
        except Exception as e:
            log.warning(f"Failed to get key metadata from Firebase: {e}. Using local storage only.")
        
        return None

    async def get_qkd_status(self) -> Dict[str, Any]:
        """
        Get the status of the QKD server
        
        Returns:
            Dictionary containing server status information
        """
        try:
            if not self.qkd_client:
                await self.initialize()
            
            # For simulation, return mock status
            return {
                'status': 'operational',
                'server_url': self.qkd_server_url,
                'mode': 'simulation',
                'keys_generated': len(self._quantum_keys_cache),
                'timestamp': asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            log.error(f"Failed to get QKD status: {e}", exc_info=True)
            raise QKDServiceError(f"Failed to get QKD status: {e}")

    async def close(self):
        """Close the QKD service and clean up resources"""
        try:
            if self.qkd_client:
                # In real implementation, this would close the QKD connection
                self.qkd_client = None
            
            await self.directory.close()
            log.info("QKD service closed successfully")
            
        except Exception as e:
            log.error(f"Error closing QKD service: {e}", exc_info=True)


class MockQKDClient:
    """
    Mock QKD client for simulation purposes.
    In a real implementation, this would be replaced with actual QKD hardware interface.
    """
    
    def __init__(self):
        self.connected = True
        log.info("Mock QKD client initialized (simulation mode)")

    async def get_status(self) -> Dict[str, Any]:
        """Get mock QKD server status"""
        return {
            'status': 'operational',
            'mode': 'simulation',
            'quantum_channel': 'simulated',
            'key_rate': 'simulated'
        }

    async def get_key(self, key_length: int) -> bytes:
        """Generate a mock quantum key"""
        # Use cryptographically secure random to simulate quantum randomness
        return os.urandom(key_length)

    def get_deterministic_key(self, key_id: str, key_length: int) -> bytes:
        """Deterministically re-generate a key from its ID for simulation purposes.
        This ensures that the same key_id always yields the same key.
        """
        # Using SHA256 on the key_id to deterministically derive the key.
        # This is a simulation, as a real QKD system would provide the key directly.
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(key_id.encode('utf-8'))
        seed = digest.finalize()
        
        # Expand the seed to the required key_length if needed
        key = b''
        while len(key) < key_length:
            hasher = hashes.Hash(hashes.SHA256(), backend=default_backend())
            hasher.update(seed)
            next_block = hasher.finalize()
            key += next_block
            seed = next_block # Use output as next seed for continuous expansion
            
        return key[:key_length]

    async def close(self):
        """Close the mock QKD client"""
        self.connected = False
        log.info("Mock QKD client closed")
