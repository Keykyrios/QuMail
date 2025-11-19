# settings_manager.py
import configparser
import keyring
import os
from pathlib import Path
import httpx
import logging

log = logging.getLogger(__name__)

class KeyGenerationError(Exception):
    pass

class SettingsManager:
    def __init__(self):
        app_data_dir = Path.home() / ".qumail"
        os.makedirs(app_data_dir, exist_ok=True)
        self.config_path = app_data_dir / "config.ini"
        self.config = configparser.ConfigParser()
        # Preload file if exists to allow getters before save
        self.config.read(self.config_path)

    async def save_settings(self, email, password, imap_host, smtp_host, smtp_port, km_url, qkd_server_url=None, agora_app_id=None, agora_app_cert=None, agora_token_endpoint=None):
        self.config['DEFAULT'] = {
            'email_address': email,
            'imap_host': imap_host,
            'smtp_host': smtp_host,
            'smtp_port': smtp_port,
            'km_url': km_url,
            'qkd_server_url': qkd_server_url or '',
            'agora_app_id': (agora_app_id or self.config.get('DEFAULT', 'agora_app_id', fallback='')),
            # Do NOT store cert in plain text file; use keyring
            'agora_token_endpoint': (agora_token_endpoint or self.config.get('DEFAULT', 'agora_token_endpoint', fallback='')),
        }
        
        try:
            async with httpx.AsyncClient() as client:
                log.info(f"Requesting new PQC key pair from {km_url}/generate-keys for {email}")
                response = await client.post(f"{km_url}/generate-keys", json={"userId": email}, timeout=20.0)
                response.raise_for_status()
                key_data = response.json()
                
                public_key_b64 = key_data['publicKey_b64']
                private_key_b64 = key_data['privateKey_b64']
                
                self.config['DEFAULT']['pqc_public_key_b64'] = public_key_b64
                try:
                    keyring.set_password("QuMail_PQC_Private", email, private_key_b64)
                    log.info(f"Successfully stored new PQC private key for {email} in secure keyring.")
                except Exception as ke:
                    # Fallback: write to app data file if Windows Credential Manager fails
                    fallback_priv_path = Path.home() / ".qumail" / f"{email}.pqc_priv.b64"
                    try:
                        with open(fallback_priv_path, 'w') as f:
                            f.write(private_key_b64)
                        log.warning(
                            f"Keyring storage failed; wrote PQC private key to fallback file: {fallback_priv_path}")
                    except Exception as fe:
                        log.error(f"Failed to persist PQC private key via fallback file: {fe}", exc_info=True)
                        raise KeyGenerationError(
                            "Failed to securely store PQC private key. Keyring and file fallback both failed.")

            # Publish public key to Firebase directory (best-effort)
            try:
                from firebase_directory import FirebaseDirectory
                directory = FirebaseDirectory("https://qu--mail-default-rtdb.firebaseio.com")
                await directory.publish_public_key(email, public_key_b64)
                await directory.close()
            except Exception:
                log.warning("Failed to publish public key to Firebase; continuing with local save.")

            # --- CRITICAL FIX: Only write the config file and password if all API calls succeed ---
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)

            if password:
                keyring.set_password("QuMail", email, password)
            # Store Agora certificate in keyring if provided
            if agora_app_cert:
                try:
                    keyring.set_password("QuMail_Agora_Cert", "agora", agora_app_cert)
                except Exception as ke:
                    log.warning(f"Failed to store Agora certificate in keyring: {ke}")

        except httpx.HTTPStatusError as e:
            error_message = f"Client error '{e.response.status_code} {e.response.reason_phrase}' for url '{e.request.url}'"
            log.error(error_message, exc_info=True)
            raise KeyGenerationError(f"Could not generate PQC keys from the Key Management service.\n\nPlease ensure the service URL is correct and the service is running.\n\nError: {error_message}")
        except httpx.RequestError as e:
            log.error(f"Network error during key generation: {e}", exc_info=True)
            raise KeyGenerationError(f"Could not connect to the Key Management service.\n\nPlease ensure the service is running and the URL is correct.\n\nError: {e}")

    def load_settings(self):
        if not self.config.read(self.config_path):
            return {}

        settings = dict(self.config['DEFAULT'])
        
        # --- AUTO-MIGRATION FIX for stale config URL ---
        km_url = settings.get("km_url")
        if km_url == "http://127.0.0.1:8000":
            log.warning("Detected outdated key manager URL. Auto-updating to port 8001.")
            settings["km_url"] = "http://127.0.0.1:8001"
            self.config['DEFAULT']['km_url'] = "http://127.0.0.1:8001"
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
        
        email_address = settings.get("email_address")
        if not email_address:
            return settings

        settings['password'] = keyring.get_password("QuMail", email_address)
        pqc_priv = keyring.get_password("QuMail_PQC_Private", email_address)
        if pqc_priv is None:
            # Try fallback file if keyring missing
            fallback_priv_path = Path.home() / ".qumail" / f"{email_address}.pqc_priv.b64"
            try:
                if fallback_priv_path.exists():
                    with open(fallback_priv_path, 'r') as f:
                        pqc_priv = f.read().strip()
                    log.warning(f"Loaded PQC private key from fallback file: {fallback_priv_path}")
            except Exception as e:
                log.error(f"Failed reading PQC private key fallback file: {e}", exc_info=True)
        settings['pqc_private_key_b64'] = pqc_priv

        # Load Agora settings
        settings['agora_app_id'] = self.config.get('DEFAULT', 'agora_app_id', fallback='')
        settings['agora_token_endpoint'] = self.config.get('DEFAULT', 'agora_token_endpoint', fallback='')
        try:
            settings['agora_app_cert'] = keyring.get_password("QuMail_Agora_Cert", "agora")
        except Exception:
            settings['agora_app_cert'] = None
        
        return settings

