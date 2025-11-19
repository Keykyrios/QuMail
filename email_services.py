# email_services.py
import asyncio
import imaplib
import smtplib
import logging
import re
import base64
import json
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.parser import BytesParser
from email.header import decode_header, make_header
from email.utils import getaddresses
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

class EmailServiceError(Exception):
    pass

class ImapHandler:
    def __init__(self, host, user, password):
        self.host, self.user, self.password = host, user, password
        self.imap, self.is_connected = None, False

    async def connect(self):
        def _blocking_connect():
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(15) # 15-second timeout for all socket operations
            try:
                log.info(f"Attempting IMAP connection to {self.host}...")
                imap_conn = imaplib.IMAP4_SSL(self.host)
                log.info("IMAP connection established, logging in...")
                imap_conn.login(self.user, self.password)
                log.info("IMAP login successful.")
                return imap_conn
            finally:
                socket.setdefaulttimeout(original_timeout)
        
        try:
            loop = asyncio.get_running_loop()
            self.imap = await loop.run_in_executor(None, _blocking_connect)
            self.is_connected = True
        except (imaplib.IMAP4.error, socket.gaierror, socket.timeout) as e:
            self.is_connected = False
            log.error(f"IMAP connection failed: {e}", exc_info=True)
            raise EmailServiceError(f"IMAP connection failed. Check credentials and server address. Error: {e}")

    async def _ensure_connected(self):
        if not self.is_connected:
            await self.connect()

    async def disconnect(self):
        if not self.imap:
            self.is_connected = False
            return
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(loop.run_in_executor(None, self.imap.logout), timeout=5)
        except Exception:
            try:
                if hasattr(self.imap, '_sock') and self.imap._sock:
                    try:
                        self.imap._sock.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    try:
                        self.imap._sock.close()
                    except Exception:
                        pass
            finally:
                try:
                    self.imap.shutdown()
                except Exception:
                    pass
        finally:
            self.is_connected = False

    async def list_folders(self):
        await self._ensure_connected()
        log.info("Fetching folder list from IMAP server...")
        try:
            _status, folders_data = await asyncio.get_running_loop().run_in_executor(None, self.imap.list)
            log.info("Successfully fetched folder list.")
            raw_folders = []
            pattern = re.compile(r'\((?P<flags>.*?)\) "(?P<delimiter>.*)" "?(?P<name>[^"]*)"?')
            for fd in folders_data:
                match = pattern.match(fd.decode('utf-8', 'ignore'))
                if match and r'\Noselect' not in match.group('flags'):
                    raw_folders.append(match.group('name'))
            
            cleaned_folders = {}
            for name in raw_folders:
                clean_name = name.strip('"').split('/')[-1].capitalize()
                cleaned_folders[clean_name] = name
            
            priority = ['Inbox', 'Starred', 'Snoozed', 'Sent', 'Drafts', 'Important', 'All mail', 'Spam', 'Trash']
            sorted_names = sorted(cleaned_folders.keys(), key=lambda x: priority.index(x) if x in priority else len(priority))
            return [(name, cleaned_folders[name]) for name in sorted_names]
        except (imaplib.IMAP4.error, socket.timeout) as e:
            raise EmailServiceError(f"Could not list folders: {e}")
            
    async def get_all_uids_in_folder(self, folder_name):
        await self._ensure_connected()
        await asyncio.get_running_loop().run_in_executor(None, self.imap.select, f'"{folder_name}"', True)
        # Use UID SEARCH to get stable unique identifiers
        _st, messages = await asyncio.get_running_loop().run_in_executor(None, self.imap.uid, 'SEARCH', None, 'ALL')
        return [uid.decode() for uid in messages[0].split()]

    async def fetch_email_headers(self, folder_name, uids_to_fetch):
        if not uids_to_fetch: return []
        await self._ensure_connected()
        # UID FETCH expects a message-set: comma-separated IDs and/or ranges
        uid_string = ','.join(uids_to_fetch)
        _st, data = await asyncio.get_running_loop().run_in_executor(
            None, self.imap.uid, 'FETCH', uid_string, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])'
        )
        headers, uid_map = [], {}
        for item in data:
            if isinstance(item, tuple):
                uid_match = re.search(r'UID\s+(\d+)', item[0].decode('utf-8', 'ignore'))
                if not uid_match: continue
                uid = uid_match.group(1)
                msg = BytesParser().parsebytes(item[1])
                s_val, s_enc = decode_header(msg['Subject'])[0]
                f_val, f_enc = decode_header(msg['From'])[0]
                from_d = f_val.decode(f_enc or 'utf-8', 'ignore') if isinstance(f_val, bytes) else f_val
                subj_d = s_val.decode(s_enc or 'utf-8', 'ignore') if isinstance(s_val, bytes) else s_val
                uid_map[uid] = {'uid': uid, 'from': from_d, 'subject': subj_d, 'date': msg['Date']}
        return [uid_map[uid] for uid in uids_to_fetch if uid in uid_map]

    async def fetch_full_email(self, uid):
        await self._ensure_connected()
        # Use UID FETCH for message retrieval as well
        _status, data = await asyncio.get_running_loop().run_in_executor(None, self.imap.uid, 'FETCH', uid, '(RFC822)')
        if not data or data[0] is None:
            raise EmailServiceError(f"No data returned for UID {uid}.")
        msg = BytesParser().parsebytes(data[0][1])
        result = {'raw_message': msg, 'html_body': None, 'plain_body': None, 'attachments': []}
            
        for part in msg.walk():
            if part.get_content_type() == 'application/x-qumail-json':
                result['plain_body'] = part.get_payload(decode=True).decode('utf-8', 'ignore')
                return result
        
        parts = {'attachments': [], 'inlines': [], 'html_candidates': [], 'plain_candidates': []}
        for part in msg.walk():
            disposition = str(part.get("Content-Disposition") or "").lower()
            content_type = part.get_content_type().lower()
            if ("attachment" in disposition) or (part.get_filename() and content_type != 'text/plain' and content_type != 'text/html'):
                parts['attachments'].append(part)
            elif ("inline" in disposition) or part.get("Content-ID"):
                parts['inlines'].append(part)
            elif content_type == 'text/html':
                parts['html_candidates'].append(part)
            elif content_type == 'text/plain':
                parts['plain_candidates'].append(part)
        
        for part in parts['attachments']:
            filename = part.get_filename()
            if filename:
                try:
                    filename = str(make_header(decode_header(filename)))
                except Exception:
                    pass
                result['attachments'].append({'filename': filename, 'content': part.get_payload(decode=True)})
        
        inline_images = {}
        for part in parts['inlines']:
            if cid := part.get("Content-ID"):
                cid_cleaned = cid.strip()[1:-1]
                b64_data = base64.b64encode(part.get_payload(decode=True)).decode('utf-8')
                inline_images[cid_cleaned] = f"data:{part.get_content_type()};base64,{b64_data}"

        html_part = next((p for p in parts['html_candidates'] if p not in parts['attachments'] and p not in parts['inlines']), None)
        if html_part: result['html_body'] = html_part.get_payload(decode=True).decode(html_part.get_content_charset() or 'utf-8', 'ignore')
        else:
            plain_part = next((p for p in parts['plain_candidates'] if p not in parts['attachments'] and p not in parts['inlines']), None)
            if plain_part: result['plain_body'] = plain_part.get_payload(decode=True).decode(plain_part.get_content_charset() or 'utf-8', 'ignore')
        
        if result['html_body']:
            soup = BeautifulSoup(result['html_body'], 'lxml')
            # Inline CID replacements
            if inline_images:
                for img_tag in soup.find_all('img'):
                    src = img_tag.get('src')
                    if src and src.startswith('cid:'):
                        cid = src[4:]
                        if cid in inline_images:
                            img_tag['src'] = inline_images[cid]
            # Common lazy-load attributes → src and fix protocol-relative URLs
            for img_tag in soup.find_all('img'):
                if not img_tag.get('src'):
                    for attr in ['data-src', 'data-original', 'data-lazy-src']:
                        if img_tag.get(attr):
                            img_tag['src'] = img_tag.get(attr)
                            break
                src_val = img_tag.get('src')
                if src_val and src_val.startswith('//'):
                    img_tag['src'] = 'https:' + src_val
                # Ensure images scale within the view
                style = img_tag.get('style', '')
                if 'max-width' not in style:
                    img_tag['style'] = (style + '; max-width: 100%; height: auto;').strip(';')
            result['html_body'] = str(soup)
        
        return result

class SmtpHandler:
    def __init__(self, host, port, user, password):
        self.host, self.port, self.user, self.password = host, int(port), user, password

    async def send_email(self, to_addr, subject, body, from_addr, attachments=[]):
        is_qumail = "qumail_version" in body
        msg = MIMEMultipart('mixed')
        msg['From'], msg['To'], msg['Subject'] = from_addr, to_addr, subject
        
        body_part = MIMEMultipart('alternative')
        msg.attach(body_part)
        
        if is_qumail:
            body_part.attach(MIMEText("This is a quantum-secure message from QuMail...", 'plain'))
            qumail_part = MIMEApplication(body.encode('utf-8'), 'x-qumail-json', name='secure.qm')
            qumail_part.add_header('Content-Disposition', 'attachment', filename='secure.qm')
            msg.attach(qumail_part)
        else:
            body_part.attach(MIMEText(body, 'plain'))
            for att in attachments:
                part = MIMEApplication(att['content'], Name=att['filename'])
                part['Content-Disposition'] = f'attachment; filename="{att["filename"]}"'
                msg.attach(part)
        
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._send_email_blocking, msg)

    def _send_email_blocking(self, msg):
        try:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=15) as server:
                server.login(self.user, self.password)
                server.send_message(msg)
        except (smtplib.SMTPException, TimeoutError, socket.gaierror) as e:
            raise EmailServiceError(f"Could not send email: {e}")

