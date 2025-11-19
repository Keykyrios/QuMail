# firebase_signaling.py
import asyncio
import logging
import json
import time
from typing import Dict, Optional, Callable
from firebase_directory import FirebaseDirectory
from PyQt6.QtCore import QObject, pyqtSignal # Use PyQt6 imports

log = logging.getLogger(__name__)

class FirebaseSignaling(QObject):
    """Firebase-based signaling server for cross-device WebRTC calls"""
    
    user_online = pyqtSignal(str)
    user_offline = pyqtSignal(str)
    call_received = pyqtSignal(str, str, str, str)
    call_answered = pyqtSignal(str)
    call_ended = pyqtSignal(str)
    offer_received = pyqtSignal(str, dict)
    answer_received = pyqtSignal(str, dict)
    ice_candidate_received = pyqtSignal(str, dict)
    quantum_key_requested = pyqtSignal(str, str)
    
    def __init__(self, database_url: str = "https://qu--mail-default-rtdb.firebaseio.com"):
        super().__init__()  # Initialize the QObject parent class
        self.database_url = database_url.rstrip('/')
        self.firebase = FirebaseDirectory(database_url)
        self.current_user = ""
        self.is_connected = False
        self.message_handlers: Dict[str, Callable] = {}
        self.active_calls: Dict[str, Dict] = {}
        self.listen_task: Optional[asyncio.Task] = None
        
        # Setup message handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup message type handlers"""
        self.message_handlers = {
            'call_initiation': self.handle_call_initiation,
            'call_answer': self.handle_call_answer,
            'call_end': self.handle_call_end,
            'offer': self.handle_offer,
            'answer': self.handle_answer,
            'ice_candidate': self.handle_ice_candidate,
            'quantum_key_request': self.handle_quantum_key_request,
            'ping': self.handle_ping,
            'user_online': self.handle_user_online,
            'user_offline': self.handle_user_offline
        }
    
    async def connect(self, user_email: str):
        """Connect to Firebase signaling"""
        self.current_user = user_email
        self.is_connected = True
        
        # Start listening for messages
        self.listen_task = asyncio.create_task(self.listen_for_messages())
        
        # Send connection notification
        await self.send_message({
            'type': 'user_online',
            'user': user_email,
            'timestamp': time.time()
        }, user_email)
        
        log.info(f"Connected to Firebase signaling as {user_email}")
    
    async def disconnect(self):
        """Disconnect from Firebase signaling"""
        self.is_connected = False
        
        # Send offline notification
        if self.current_user:
            await self.send_message({
                'type': 'user_offline',
                'user': self.current_user,
                'timestamp': time.time()
            }, self.current_user)
        
        # Cancel listen task
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
        
        # Close Firebase connection
        await self.firebase.close()
        
        log.info(f"Disconnected from Firebase signaling")
    
    async def listen_for_messages(self):
        """Listen for incoming messages from Firebase"""
        while self.is_connected:
            try:
                messages = await self.get_user_messages_and_clear()
                
                for message in messages:
                    await self.process_message(message)
                
                await asyncio.sleep(1) # Polling interval
                
            except Exception as e:
                log.error(f"Error listening for messages: {e}")
                await asyncio.sleep(5)  # Wait longer on error
    
    async def get_user_messages(self) -> list:
        """Get messages for current user from Firebase"""
        try:
            import httpx
            url = f"{self.database_url}/signaling_messages/{self.current_user.replace('.', '(dot)')}.json"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        # Convert to list and sort by timestamp
                        messages = list(data.values()) if isinstance(data, dict) else []
                        return sorted(messages, key=lambda x: x.get('timestamp', 0))
                return []
        except Exception as e:
            log.error(f"Error getting user messages: {e}")
            return []

    async def get_user_messages_and_clear(self) -> list:
        """Get messages for current user from Firebase and clear them with retry logic"""
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                import httpx
                url = f"{self.database_url}/signaling_messages/{self.current_user.replace('.', '(dot)')}.json"
                
                # Use longer timeout and connection pooling
                timeout = httpx.Timeout(10.0, connect=5.0)
                async with httpx.AsyncClient(timeout=timeout, limits=httpx.Limits(max_connections=10)) as client:
                    # Get messages
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    
                    messages = []
                    if data:
                        messages = list(data.values()) if isinstance(data, dict) else []
                        
                        # Immediately delete messages to prevent reprocessing
                        delete_response = await client.delete(url)
                        delete_response.raise_for_status()
                        log.debug(f"Cleared messages for {self.current_user} from Firebase.")

                    return sorted(messages, key=lambda x: x.get('timestamp', 0))
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404: # No messages, not an error
                    return []
                log.warning(f"HTTP error getting/clearing user messages (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))  # Exponential backoff
                    continue
                log.error(f"HTTP error after {max_retries} attempts: {e}")
                return []
            except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
                log.warning(f"Network error getting/clearing user messages (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))  # Exponential backoff
                    continue
                log.error(f"Network error after {max_retries} attempts: {e}")
                return []
            except Exception as e:
                log.error(f"Unexpected error getting/clearing user messages: {e}")
                return []
        
        return []
    
    async def process_message(self, message: dict):
        """Process a received message"""
        try:
            message_type = message.get('type')
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](message)
            else:
                log.warning(f"Unknown message type: {message_type}")
        except Exception as e:
            log.error(f"Error processing message: {e}")
    
    async def send_message(self, message: dict, target_user: str):
        """Send a message via Firebase to a specific user"""
        try:
            import httpx
            
            # Add timestamp and sender
            message['timestamp'] = time.time()
            message['from'] = self.current_user
            message['to'] = target_user
            
            # Send to target user's message queue
            target_path = target_user.replace('.', '(dot)')
            url = f"{self.database_url}/signaling_messages/{target_path}.json"
            
            async with httpx.AsyncClient() as client:
                # Use POST to let Firebase generate a unique message ID
                response = await client.post(url, json=message)
                response.raise_for_status()
                
                log.debug(f"Sent message {message['type']} to {target_user}")
                
        except Exception as e:
            log.error(f"Error sending message to {target_user}: {e}")
    
    async def initiate_call(self, call_id: str, target_user: str, call_type: str, quantum_key_id: str = None):
        """Initiate a call to another user"""
        message = {
            'type': 'call_initiation',
            'call_id': call_id,
            'call_type': call_type,
            'quantum_key_id': quantum_key_id
        }
        
        # Store call info
        self.active_calls[call_id] = {
            'target_user': target_user,
            'call_type': call_type,
            'status': 'initiated',
            'timestamp': time.time()
        }
        
        await self.send_message(message, target_user)
        log.info(f"Call {call_id} initiated to {target_user}")
    
    async def answer_call(self, call_id: str, target_user: str):
        """Answer an incoming call"""
        message = {
            'type': 'call_answer',
            'call_id': call_id
        }
        
        if call_id in self.active_calls:
            self.active_calls[call_id]['status'] = 'answered'
        
        await self.send_message(message, target_user)
        log.info(f"Call {call_id} answered")
    
    async def end_call(self, call_id: str, target_user: str = None):
        """End a call"""
        message = {
            'type': 'call_end',
            'call_id': call_id
        }
        
        # Remove from active calls
        if call_id in self.active_calls:
            if not target_user:
                target_user = self.active_calls[call_id]['target_user']
            del self.active_calls[call_id]
        
        if target_user:
            await self.send_message(message, target_user)
        
        log.info(f"Call {call_id} ended")
    
    async def send_offer(self, call_id: str, target_user: str, offer: dict):
        """Send WebRTC offer"""
        message = {
            'type': 'offer',
            'call_id': call_id,
            'offer': offer
        }
        
        await self.send_message(message, target_user)
        log.debug(f"Offer sent for call {call_id}")
    
    async def send_answer(self, call_id: str, target_user: str, answer: dict):
        """Send WebRTC answer"""
        message = {
            'type': 'answer',
            'call_id': call_id,
            'answer': answer
        }
        
        await self.send_message(message, target_user)
        log.debug(f"Answer sent for call {call_id}")
    
    async def send_ice_candidate(self, call_id: str, target_user: str, candidate: dict):
        """Send ICE candidate"""
        message = {
            'type': 'ice_candidate',
            'call_id': call_id,
            'candidate': candidate
        }
        
        await self.send_message(message, target_user)
        log.debug(f"ICE candidate sent for call {call_id}")
    
    async def request_quantum_key(self, call_id: str, target_user: str, quantum_key_id: str):
        """Request quantum key from target user"""
        message = {
            'type': 'quantum_key_request',
            'call_id': call_id,
            'quantum_key_id': quantum_key_id
        }
        
        await self.send_message(message, target_user)
        log.debug(f"Quantum key request sent for call {call_id}")
    
    # Message handlers
    async def handle_call_initiation(self, message: dict):
        """Handle incoming call initiation"""
        call_id = message.get('call_id')
        caller = message.get('from')
        call_type = message.get('call_type')
        quantum_key_id = message.get('quantum_key_id')
        
        log.info(f"Incoming call {call_id} from {caller}")
        
        # Emit signal for UI to handle
        if hasattr(self, 'call_received'):
            self.call_received.emit(call_id, caller, call_type, quantum_key_id)
    
    async def handle_call_answer(self, message: dict):
        """Handle call answer"""
        call_id = message.get('call_id')
        log.info(f"Call {call_id} answered")
        
        if hasattr(self, 'call_answered'):
            self.call_answered.emit(call_id)
    
    async def handle_call_end(self, message: dict):
        """Handle call end"""
        call_id = message.get('call_id')
        log.info(f"Call {call_id} ended")
        
        # Remove from active calls
        if call_id in self.active_calls:
            del self.active_calls[call_id]
        
        if hasattr(self, 'call_ended'):
            self.call_ended.emit(call_id)
    
    async def handle_offer(self, message: dict):
        """Handle WebRTC offer"""
        call_id = message.get('call_id')
        offer = message.get('offer')
        log.debug(f"Received offer for call {call_id}")
        
        if hasattr(self, 'offer_received'):
            self.offer_received.emit(call_id, offer)
    
    async def handle_answer(self, message: dict):
        """Handle WebRTC answer"""
        call_id = message.get('call_id')
        answer = message.get('answer')
        log.debug(f"Received answer for call {call_id}")
        
        if hasattr(self, 'answer_received'):
            self.answer_received.emit(call_id, answer)
    
    async def handle_ice_candidate(self, message: dict):
        """Handle ICE candidate"""
        call_id = message.get('call_id')
        candidate = message.get('candidate')
        log.debug(f"Received ICE candidate for call {call_id}")
        
        if hasattr(self, 'ice_candidate_received'):
            self.ice_candidate_received.emit(call_id, candidate)
    
    async def handle_quantum_key_request(self, message: dict):
        """Handle quantum key request"""
        call_id = message.get('call_id')
        quantum_key_id = message.get('quantum_key_id')
        log.debug(f"Received quantum key request for call {call_id}")
        
        if hasattr(self, 'quantum_key_requested'):
            self.quantum_key_requested.emit(call_id, quantum_key_id)
    
    async def handle_ping(self, message: dict):
        """Handle ping message"""
        # Respond with pong
        await self.send_message({
            'type': 'pong',
            'timestamp': time.time()
        }, message.get('from'))
    
    async def handle_user_online(self, message: dict):
        """Handle user_online message"""
        user = message.get('user')
        log.info(f"User {user} is online")
        if hasattr(self, 'user_online'):
            self.user_online.emit(user)
    
    async def handle_user_offline(self, message: dict):
        """Handle user_offline message"""
        user = message.get('user')
        log.info(f"User {user} is offline")
        if hasattr(self, 'user_offline'):
            self.user_offline.emit(user)
    
    async def cleanup_old_messages(self):
        """No longer needed with get_user_messages_and_clear"""
        pass
    
    def get_active_calls(self) -> Dict[str, Dict]:
        """Get active calls"""
        return self.active_calls.copy()
    
    def is_in_call(self) -> bool:
        """Check if user is in any active call"""
        return len(self.active_calls) > 0
