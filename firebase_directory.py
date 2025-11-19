# firebase_directory.py
import httpx
import asyncio
import logging

log = logging.getLogger(__name__)


class FirebaseDirectory:
    def __init__(self, database_url: str):
        self.database_url = database_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=10.0)

    async def close(self):
        if not self.client.is_closed:
            await self.client.aclose()

    def _key_path(self, email: str) -> str:
        safe_email = email.replace('.', '(dot)')
        return f"{self.database_url}/pqc_public_keys/{safe_email}.json"

    async def publish_public_key(self, email: str, public_key_b64: str) -> None:
        url = self._key_path(email)
        payload = {"public_key_b64": public_key_b64}
        try:
            resp = await self.client.put(url, json=payload)
            resp.raise_for_status()
            log.info(f"Published public key for {email} to Firebase.")
        except httpx.HTTPError as e:
            log.error(f"Failed to publish public key to Firebase: {e}", exc_info=True)
            raise

    async def fetch_public_key(self, email: str) -> str | None:
        url = self._key_path(email)
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return data.get("public_key_b64")
            return None
        except httpx.HTTPError as e:
            log.error(f"Failed to fetch public key from Firebase: {e}", exc_info=True)
            return None


