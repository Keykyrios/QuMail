# email_controller.py

import asyncio
import logging
import json
from email.header import decode_header, make_header
from email.utils import getaddresses

from email_services import ImapHandler, SmtpHandler, EmailServiceError
# --- THE FUCKING FIX IS HERE: The class name was wrong. ---
from crypto_services import CryptoService, DecryptionError, EncryptionError
from settings_manager import SettingsManager, KeyGenerationError
from call_controller import CallController
import html_templates

log = logging.getLogger(__name__)

PAGE_SIZE = 50
NETWORK_TIMEOUT = 15  # seconds

class EmailController:
    def __init__(self, main_window):
        self.main_window = main_window
        self.settings_manager = SettingsManager()
        self.settings = None
        self.imap_handler, self.smtp_handler, self.crypto_service = None, None, None
        self.current_folder_original_name, self.current_folder_uids, self.loaded_uids_count = None, [], 0
        self.current_folder_load_task, self.current_email_load_task = None, None
        self.current_email_object = None
        self.call_controller = None

    async def apply_settings_and_connect(self):
        self.main_window.set_busy_state()
        try:
            self.settings = self.settings_manager.load_settings()
            
            if not self.settings.get('email_address') or not self.settings.get('password'):
                log.warning("Application is not configured. Aborting connection attempt.")
                self.main_window.show_info_message("Welcome to QuMail", "Please configure your email account in Settings to begin.")
                self.main_window.populate_folder_list([])
                self.main_window.clear_email_list()
                return

            self._initialize_handlers()
            
            # Initialize QKD service if available
            if self.crypto_service and self.crypto_service.qkd_service:
                self.main_window.update_status_bar("Initializing QKD service...")
                await asyncio.wait_for(self.crypto_service.qkd_service.initialize(), timeout=NETWORK_TIMEOUT)

            self.main_window.update_status_bar("Connecting to email server...")
            await asyncio.wait_for(self.imap_handler.connect(), timeout=NETWORK_TIMEOUT)
            
            self.main_window.update_status_bar("Connection successful. Fetching folder list...")
            folders_with_original_names = await asyncio.wait_for(self.imap_handler.list_folders(), timeout=NETWORK_TIMEOUT)
            self.main_window.populate_folder_list(folders_with_original_names)
            
            inbox_item = self.main_window.find_folder_item('Inbox')
            if inbox_item:
                self.main_window.folder_list_widget.setCurrentItem(inbox_item)
            elif folders_with_original_names:
                self.main_window.folder_list_widget.setCurrentRow(0)
            
            # Initialize call controller
            if self.settings.get('email_address'):
                self.main_window.initialize_call_controller(self.settings['email_address'])
            
        except asyncio.TimeoutError:
            log.error("IMAP connection or folder listing timed out.")
            self.main_window.show_error_message("Connection Timed Out", f"The email server did not respond within {NETWORK_TIMEOUT} seconds.")
        except EmailServiceError as e:
            log.error(f"Initialization failed: {e}", exc_info=True)
            self.main_window.show_error_message("Connection Failed", f"Failed to connect: {e}")
        except Exception as e:
            log.error(f"An unexpected error occurred during initialization: {e}", exc_info=True)
            self.main_window.show_error_message("Initialization Error", f"An unexpected error occurred: {e}")
        finally:
            self.main_window.set_idle_state()

    async def handle_settings_updated(self):
        await self.shutdown()
        await self.apply_settings_and_connect()

    async def shutdown(self):
        if self.current_folder_load_task and not self.current_folder_load_task.done(): self.current_folder_load_task.cancel()
        if self.current_email_load_task and not self.current_email_load_task.done(): self.current_email_load_task.cancel()
        if self.imap_handler: await self.imap_handler.disconnect()
        if self.crypto_service: await self.crypto_service.close()

    def _initialize_handlers(self):
        s = self.settings
        self.imap_handler = ImapHandler(s['imap_host'], s['email_address'], s['password'])
        self.smtp_handler = SmtpHandler(s['smtp_host'], s['smtp_port'], s['email_address'], s['password'])
        
        # Initialize crypto service with QKD support
        qkd_server_url = s.get('qkd_server_url')
        self.crypto_service = CryptoService(s['km_url'], qkd_server_url)

    def start_folder_selection(self, folder_name):
        if self.current_folder_load_task and not self.current_folder_load_task.done():
            self.current_folder_load_task.cancel()
        self.current_folder_load_task = asyncio.create_task(self.handle_folder_selection(folder_name))

    async def handle_folder_selection(self, original_folder_name):
        try:
            self.main_window.set_busy_state()
            self.main_window.update_conversation_actions(enabled=False)
            self.current_email_object = None
            self.current_folder_original_name = original_folder_name
            all_uids = await asyncio.wait_for(self.imap_handler.get_all_uids_in_folder(original_folder_name), timeout=NETWORK_TIMEOUT)
            self.current_folder_uids = list(reversed(all_uids))
            self.loaded_uids_count = 0
            self.main_window.clear_email_list()
            await self.load_next_page_of_emails()
        except asyncio.TimeoutError:
            self.main_window.show_error_message("Folder Load Timed Out", f"Could not retrieve email list from server within {NETWORK_TIMEOUT} seconds.")
        except asyncio.CancelledError:
            log.info("Folder load task was successfully cancelled.")
            raise
        except EmailServiceError as e:
            self.main_window.show_error_message("Folder Load Failed", str(e))
        finally:
            self.main_window.set_idle_state()

    async def load_next_page_of_emails(self):
        if self.loaded_uids_count >= len(self.current_folder_uids): return
        self.main_window.set_busy_state()
        start, end = self.loaded_uids_count, self.loaded_uids_count + PAGE_SIZE
        try:
            headers = await asyncio.wait_for(self.imap_handler.fetch_email_headers(self.current_folder_original_name, self.current_folder_uids[start:end]), timeout=NETWORK_TIMEOUT)
            self.main_window.append_emails_to_list(headers)
            self.loaded_uids_count += len(headers)
        except asyncio.TimeoutError:
            self.main_window.show_error_message("Fetch Timed Out", f"Could not fetch more emails within {NETWORK_TIMEOUT} seconds.")
        except EmailServiceError as e:
            self.main_window.show_error_message("Fetch Error", str(e))
        finally:
             self.main_window.set_idle_state()


    def handle_refresh_emails(self):
        if self.current_folder_original_name:
            self.start_folder_selection(self.current_folder_original_name)

    def start_email_selection(self, uid):
        if self.current_email_load_task and not self.current_email_load_task.done():
            self.current_email_load_task.cancel()
        self.current_email_load_task = asyncio.create_task(self.handle_email_selection(uid))

    async def handle_email_selection(self, uid):
        try:
            self.main_window.set_busy_state()
            self.main_window.update_conversation_actions(enabled=False)
            self.current_email_object = None
            self.main_window.display_email_content({})
            
            self.current_email_object = await asyncio.wait_for(self.imap_handler.fetch_full_email(uid), timeout=NETWORK_TIMEOUT)
            
            json_payload_str = self.current_email_object.get('plain_body')
            is_qumail, qumail_data = False, None
            if json_payload_str:
                try:
                    data = json.loads(json_payload_str)
                    if "qumail_version" in data:
                        is_qumail, qumail_data = True, data
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if is_qumail:
                self.main_window.display_email_content({'html_body': html_templates.LOCKED_MESSAGE_TEMPLATE})
                security_level = qumail_data.get("security_level")
                decrypted_payload = None

                if security_level == 3:
                    private_key_b64 = self.settings.get('pqc_private_key_b64')
                    if not private_key_b64:
                        raise DecryptionError("Cannot decrypt Level 3 message: PQC private key not found in settings.")
                    decrypted_payload = await self.crypto_service.decrypt(json_payload_str, private_key_b64=private_key_b64)

                elif security_level in [1, 2]:
                    encryption_method = qumail_data.get("encryption_method", "pqc")
                    
                    if encryption_method == "qkd":
                        # QKD-based decryption - no additional parameters needed
                        # The key is retrieved using the key_id from the message
                        decrypted_payload = await self.crypto_service.decrypt(json_payload_str)
                    else:
                        # PQC-based decryption (legacy)
                        raise DecryptionError("Legacy PQC message level unsupported after QKD upgrade.")

                elif security_level == 4 and "plaintext_payload" in qumail_data:
                     decrypted_payload = qumail_data.get("plaintext_payload")
                
                if decrypted_payload:
                    self.main_window.display_email_content({
                        'html_body': decrypted_payload.get('body'), 
                        'attachments': decrypted_payload.get('attachments', [])
                    })
                else:
                    raise DecryptionError("Decryption process yielded no content.")
            else:
                self.main_window.display_email_content(self.current_email_object)
            
            self.main_window.update_conversation_actions(enabled=True)

        except asyncio.TimeoutError:
            self.main_window.show_error_message("Fetch Timed Out", f"Could not fetch the full email within {NETWORK_TIMEOUT} seconds.")
        except asyncio.CancelledError:
            log.info("Email load task was successfully cancelled.")
            raise
        except (KeyGenerationError, DecryptionError, EmailServiceError) as e:
            failed_html = html_templates.DECRYPTION_FAILED_TEMPLATE.format(error_message=e)
            self.main_window.display_email_content({'html_body': failed_html})
        except Exception as e:
            log.error(f"Unexpected error displaying email: {e}", exc_info=True)
            failed_html = html_templates.DECRYPTION_FAILED_TEMPLATE.format(error_message=f"An unexpected error occurred: {e}")
            self.main_window.display_email_content({'html_body': failed_html})
        finally:
            self.main_window.set_idle_state()

    def _format_quoted_body(self):
        if not self.current_email_object: return ""
        msg = self.current_email_object['raw_message']
        from_addr = str(make_header(decode_header(msg.get('From', ''))))
        date_str = msg.get('Date', '')
        original_body = self.current_email_object.get('plain_body', '')
        
        try:
            qumail_data = json.loads(original_body)
            if 'plaintext_payload' in qumail_data:
                 original_body = qumail_data['plaintext_payload'].get('body', '')
        except (json.JSONDecodeError, TypeError):
            pass

        quoted_lines = [f"> {line}" for line in original_body.splitlines()]
        return (f"\n\n\n----- Original Message -----\nFrom: {from_addr}\nDate: {date_str}\n"
                f"Subject: {str(make_header(decode_header(msg.get('Subject', ''))))}\n\n" + "\n".join(quoted_lines))

    def handle_reply(self):
        if not self.current_email_object: return
        msg = self.current_email_object['raw_message']
        reply_to = msg.get('Reply-To') or msg.get('From')
        to_addr = getaddresses([reply_to])[0][1]
        subject = str(make_header(decode_header(msg.get('Subject', ''))))
        new_subject = f"Re: {subject}" if not subject.lower().startswith('re:') else subject
        self.main_window.open_compose_dialog(to_addr=to_addr, subject=new_subject, body=self._format_quoted_body())

    def handle_reply_all(self):
        if not self.current_email_object: return
        msg = self.current_email_object['raw_message']
        my_address = self.settings['email_address']
        recipients = getaddresses(msg.get_all('To', []) + msg.get_all('Cc', []))
        from_recipient = getaddresses([msg.get('From', '')])
        recipient_set = {addr for name, addr in recipients + from_recipient if addr.lower() != my_address.lower()}
        to_addr = ", ".join(sorted(list(recipient_set)))
        subject = str(make_header(decode_header(msg.get('Subject', ''))))
        new_subject = f"Re: {subject}" if not subject.lower().startswith('re:') else subject
        self.main_window.open_compose_dialog(to_addr=to_addr, subject=new_subject, body=self._format_quoted_body())

    def handle_forward(self):
        if not self.current_email_object: return
        msg = self.current_email_object['raw_message']
        subject = str(make_header(decode_header(msg.get('Subject', ''))))
        new_subject = f"Fwd: {subject}" if not subject.lower().startswith('fwd:') else subject
        self.main_window.open_compose_dialog(to_addr="", subject=new_subject, body=self._format_quoted_body())

    async def handle_send_email(self, to_addr, subject, body, attachments, security_level, encryption_method="pqc"):
        if not self.smtp_handler: return False
        from_addr = self.settings['email_address']
        final_body = body
        try:
            if security_level == 3:
                recipient_public_key_b64 = await self.crypto_service.get_public_key(to_addr.split(',')[0].strip())
                final_body = await self.crypto_service.encrypt(body.encode('utf-8'), attachments, security_level=3, recipient_public_key_b64=recipient_public_key_b64)
            
            elif security_level in [1, 2]:
                if encryption_method == "qkd":
                    # Use QKD for quantum-secure encryption
                    recipient_email = to_addr.split(',')[0].strip()
                    final_body = await self.crypto_service.encrypt(
                        body.encode('utf-8'), attachments, 
                        security_level=security_level, 
                        encryption_method="qkd",
                        recipient_email=recipient_email
                    )
                else:
                    # Use PQC for backward compatibility
                    # For Level 1 OTP, we need a key as long as the payload
                    payload_size = len(json.dumps({
                        'body': body,
                        'attachments': [{'filename': att['filename'], 'content_b64': base64.b64encode(att['content']).decode('utf-8')} for att in attachments]
                    }).encode('utf-8'))
                    key_length = payload_size if security_level == 1 else 32
                    key_id, key_hex = await self.crypto_service.get_symmetric_key(key_length)
                    final_body = await self.crypto_service.encrypt(
                        body.encode('utf-8'), attachments, 
                        security_level=security_level, 
                        encryption_method="pqc",
                        key_id=key_id,
                        key_hex=key_hex
                    )
            
            await self.smtp_handler.send_email(to_addr, subject, final_body, from_addr, attachments if security_level == 4 else [])
            return True
            
        except (KeyGenerationError, EncryptionError, EmailServiceError) as e:
            log.error(f"Failed to send email: {e}", exc_info=True)
            self.main_window.show_error_message("Send Failed", str(e))
            return False
        except Exception as e:
            log.error(f"An unexpected error occurred during send: {e}", exc_info=True)
            self.main_window.show_error_message("Send Failed", f"An unexpected error occurred: {e}")
            return False

