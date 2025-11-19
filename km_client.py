# km_client.py

import httpx
import logging

# --- Setup comprehensive logging ---
log = logging.getLogger(__name__)
if not log.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.INFO)

class KeyManagerError(Exception):
    """Custom exception for Key Manager client errors."""
    pass

class KMClient:
    """
    A resilient, asynchronous client for the simulated QKD Key Manager.
    """
    def __init__(self, base_url, slave_sae_id):
        self.base_url = base_url.rstrip('/')
        self.slave_sae_id = slave_sae_id
        self.get_key_url = f"{self.base_url}/api/v1/keys/{self.slave_sae_id}/enc_keys"
        # --- FIX: Instantiate a persistent client for connection pooling ---
        self.client = httpx.AsyncClient(timeout=10.0)
        log.info(f"KMClient initialized for base URL: {self.base_url}")

    async def fetch_key(self, key_id_to_fetch=None):
        """
        Asynchronously fetches a key from the Key Manager.

        Args:
            key_id_to_fetch (str, optional): The specific ID of the key to fetch. 
                                            If None, fetches a new key.

        Returns:
            tuple: A tuple containing the key_ID (str) and the key (str).
        
        Raises:
            KeyManagerError: If the key cannot be fetched or the response is invalid.
        """
        request_url = self.get_key_url
        params = {'number': 1}
        if key_id_to_fetch:
            # The simulated server uses this param to find a specific key
            params['key_ID'] = key_id_to_fetch
            log.info(f"Requesting specific key with ID: {key_id_to_fetch}")
        else:
            log.info("Requesting a new key from the pool.")

        try:
            # --- FIX: Use the persistent self.client ---
            response = await self.client.get(request_url, params=params)
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses

            data = response.json()
            if "keys" in data and len(data["keys"]) > 0:
                key_data = data["keys"][0]
                key_id = key_data.get("key_ID")
                key_hex = key_data.get("key")
                if key_id and key_hex:
                    log.info(f"Successfully fetched key with ID: {key_id}")
                    return key_id, key_hex
            
            # If we reach here, the response format was invalid
            err_msg = "Invalid JSON response from Key Manager."
            log.error(f"{err_msg} Response: {data}")
            raise KeyManagerError(err_msg)

        except httpx.HTTPStatusError as e:
            err_msg = f"Key Manager returned an error: {e.response.status_code} {e.response.reason_phrase}"
            log.error(f"{err_msg} URL: {e.request.url}")
            raise KeyManagerError(err_msg)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            err_msg = f"Network error connecting to Key Manager: {e}"
            log.error(err_msg)
            raise KeyManagerError(err_msg)
        except Exception as e:
            err_msg = f"An unexpected error occurred in KMClient: {e}"
            log.error(err_msg, exc_info=True)
            raise KeyManagerError(err_msg)

    async def close(self):
        """
        --- NEW: Graceful shutdown method ---
        Properly closes the underlying HTTP client session.
        """
        log.info("Closing Key Manager client's HTTP session...")
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            log.info("Key Manager client session closed.")

