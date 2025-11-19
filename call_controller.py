# call_controller.py
import asyncio
import logging
import uuid
from typing import Optional, Dict
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
try:
    from native_webrtc_service import NativeWebRTCService, CallType, CallState, CallSession
except ImportError:
    from webrtc_service import WebRTCService as NativeWebRTCService, CallType, CallState, CallSession
from call_dialog import CallDialog, IncomingCallDialog
from webrtc_widget import WebRTCWidget
from settings_manager import SettingsManager
from agora_service import AgoraWidget
from firebase_directory import FirebaseDirectory
from firebase_signaling import FirebaseSignaling

log = logging.getLogger(__name__)

class CallController(QObject):
    """Controller for managing voice and video calls"""
    
    # Signals
    call_initiated = pyqtSignal(str, str, str)  # call_id, remote_user, call_type
    call_received = pyqtSignal(str, str, str)  # call_id, caller, call_type
    call_ended = pyqtSignal(str)  # call_id
    call_failed = pyqtSignal(str, str)  # call_id, error_message
    
    def __init__(self, current_user: str, use_firebase_signaling: bool = True):
        super().__init__()
        self.current_user = current_user
        self.use_firebase_signaling = use_firebase_signaling
        # Load settings for Agora
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load_settings()
        # Ensure an App ID is always present (App ID only mode)
        self.agora_app_id = self.settings.get('agora_app_id') or 'd47e822a706d4a2db70fe31ce36e5a0f'
        self.agora_token_endpoint = self.settings.get('agora_token_endpoint')
        self.agora_widget = None
        if self.agora_app_id:
            self.agora_widget = AgoraWidget(self.agora_app_id, self.agora_token_endpoint or '')
        self.use_agora = self.agora_widget is not None
        # Track incoming call metadata
        self._incoming_calls: Dict[str, Dict] = {}
        
        # Initialize Firebase signaling for cross-device communication
        if use_firebase_signaling:
            self.firebase_signaling = FirebaseSignaling()
            self.signaling_server_url = "firebase"  # Indicate Firebase usage
        else:
            # Fallback to local signaling server
            self.signaling_server_url = "http://127.0.0.1:8081"
            self.firebase_signaling = None
        
        # Initialize native WebRTC service (used only when not using Agora)
        self.webrtc_service = NativeWebRTCService(self.signaling_server_url)
        
        # Create legacy widgets only if not using Agora
        self.native_call_widget = None
        if not self.use_agora:
            try:
                from native_call_widget import NativeCallWidget
                self.native_call_widget = NativeCallWidget()
            except ImportError:
                log.warning("Native call widget not available, using WebRTC widget")
                self.native_call_widget = None
        
        self.webrtc_widget = None
        if not self.use_agora:
            self.webrtc_widget = WebRTCWidget(use_firebase_signaling=use_firebase_signaling)
            self.webrtc_widget.set_current_user(current_user)
        
        # No need to explicitly set firebase_signaling on widget anymore
        # if use_firebase_signaling:
        #     self.webrtc_widget.set_firebase_signaling(True)
        
        # Active call dialogs
        self.active_call_dialogs: Dict[str, CallDialog] = {}
        self.incoming_call_dialog: Optional[IncomingCallDialog] = None
        
        # Setup connections
        self.setup_connections()
        
        # Initialize WebRTC service
        self.initialization_task = asyncio.create_task(self.initialize_webrtc())
    
    def setup_connections(self):
        """Setup signal connections"""
        # Native WebRTC service signals (only when not using Agora)
        if not self.use_agora:
            self.webrtc_service.call_state_changed.connect(self.on_call_state_changed)
            self.webrtc_service.call_received.connect(self.on_call_received)
            self.webrtc_service.call_ended.connect(self.on_call_ended)
            self.webrtc_service.error_occurred.connect(self.on_error_occurred)
            self.webrtc_service.media_ready.connect(self.on_media_ready_native)
        
        # Native call widget signals (if available)
        if not self.use_agora and self.native_call_widget:
            self.native_call_widget.call_connected.connect(self.on_native_call_connected)
            self.native_call_widget.call_disconnected.connect(self.on_native_call_disconnected)
            self.native_call_widget.call_error.connect(self.on_native_call_error)
        
        # WebRTC widget signals
        if not self.use_agora and self.webrtc_widget:
            self.webrtc_widget.call_initiated.connect(self.on_webrtc_call_initiated)
            self.webrtc_widget.call_answered.connect(self.on_webrtc_call_answered)
            self.webrtc_widget.call_ended.connect(self.on_webrtc_call_ended)
            self.webrtc_widget.call_error.connect(self.on_webrtc_error)
            self.webrtc_widget.media_ready.connect(self.on_media_ready)
            self.webrtc_widget.remote_stream.connect(self.on_remote_stream)
            self.webrtc_widget.connection_state.connect(self.on_connection_state)
            self.webrtc_widget.mute_toggled.connect(self.on_mute_toggled)
            self.webrtc_widget.video_toggled.connect(self.on_video_toggled)
            self.webrtc_widget.incoming_call.connect(self.on_incoming_call)
            self.webrtc_widget.quantum_key_requested.connect(self.on_quantum_key_requested)
            self.webrtc_widget.firebase_signaling_message.connect(self.on_firebase_signaling_message)
        
        # Firebase signaling signals (if using Firebase)
        if self.firebase_signaling:
            # Connect Firebase signaling signals
            if hasattr(self.firebase_signaling, 'call_received'):
                self.firebase_signaling.call_received.connect(self.on_firebase_call_received)
            if hasattr(self.firebase_signaling, 'call_answered'):
                self.firebase_signaling.call_answered.connect(self.on_firebase_call_answered)
            if hasattr(self.firebase_signaling, 'call_ended'):
                self.firebase_signaling.call_ended.connect(self.on_firebase_call_ended)
            if hasattr(self.firebase_signaling, 'offer_received'):
                self.firebase_signaling.offer_received.connect(self.on_firebase_offer_received)
            if hasattr(self.firebase_signaling, 'answer_received'):
                self.firebase_signaling.answer_received.connect(self.on_firebase_answer_received)
            if hasattr(self.firebase_signaling, 'ice_candidate_received'):
                self.firebase_signaling.ice_candidate_received.connect(self.on_firebase_ice_candidate_received)
            if hasattr(self.firebase_signaling, 'quantum_key_requested'):
                self.firebase_signaling.quantum_key_requested.connect(self.on_firebase_quantum_key_requested)
    
    async def initialize_webrtc(self):
        """Initialize WebRTC service"""
        try:
            # Initialize WebRTC widget only when not using Agora
            if not self.use_agora:
                log.info("Initializing WebRTC widget...")
            
            # Initialize Firebase signaling if enabled
            if self.firebase_signaling:
                try:
                    await self.firebase_signaling.connect(self.current_user)
                    log.info("Firebase signaling connected successfully")
                except Exception as e:
                    log.error(f"Firebase signaling connection failed: {e}")
                    # Fallback to local signaling
                    self.use_firebase_signaling = False
                    self.firebase_signaling = None
                    self.signaling_server_url = "http://127.0.0.1:8081"
                    self.webrtc_service = NativeWebRTCService(self.signaling_server_url)
                    log.info("Falling back to local signaling server")
            
            # Try to initialize WebRTC service only when not using Agora
            if not self.use_agora:
                try:
                    success = await self.webrtc_service.initialize()
                    if success:
                        log.info("WebRTC service initialized successfully")
                    else:
                        log.warning("WebRTC service initialization failed - will retry on first call")
                except Exception as e:
                    log.warning(f"WebRTC service initialization failed: {e} - will retry on first call")
            
            # Test WebRTC widget functionality
            if not self.use_agora and self.webrtc_widget:
                try:
                    # Set up the WebRTC widget with proper error handling
                    self.webrtc_widget.set_current_user(self.current_user)
                    log.info("WebRTC widget configured successfully")
                except Exception as e:
                    log.error(f"Failed to configure WebRTC widget: {e}")
            
            log.info("Call controller initialized successfully")
            
        except Exception as e:
            log.error(f"Error initializing call controller: {e}")
            self.call_failed.emit("", f"Error initializing call service: {e}")
    
    def get_webrtc_widget(self):
        """Get the WebRTC widget"""
        return self.webrtc_widget
    
    async def initiate_call(self, remote_user: str, call_type: CallType) -> Optional[str]:
        """Initiate a new call"""
        try:
            # Check if user is already in a call
            if self.active_call_dialogs:
                QMessageBox.warning(
                    None, 
                    "Call in Progress", 
                    "You are already in a call. Please end the current call before starting a new one."
                )
                return None
            
            # Try to initialize WebRTC service if not already done
            if not self.webrtc_service.is_initialized:
                log.info("WebRTC service not initialized, attempting to initialize...")
                success = await self.webrtc_service.initialize()
                if not success:
                    log.warning("WebRTC service initialization failed, proceeding with local call only")
            
            # Initiate call using WebRTC widget
            call_id = str(uuid.uuid4())
            # Agora channel naming: call_{conversationId}
            conversation_id = call_id  # default fallback
            channel_name = f"call_{conversation_id}"
            
            # Create call session
            call_session = CallSession(
                call_id=call_id,
                call_type=call_type,
                local_user=self.current_user,
                remote_user=remote_user,
                state=CallState.INITIATING
            )
            
            # Create and show call dialog
            # Prefer Agora when configured
            call_widget = self.agora_widget if self.agora_widget else (self.native_call_widget if self.native_call_widget else self.webrtc_widget)
            use_native = self.native_call_widget is not None
            call_dialog = CallDialog(call_widget, call_session, use_native=use_native)
            call_dialog.call_ended.connect(self.on_call_dialog_ended)
            self.active_call_dialogs[call_id] = call_dialog
            
            # Show dialog
            call_dialog.show()
            
            # Start native call if available
            if self.agora_widget:
                # Compute UIDs from Firebase public keys or email
                try:
                    directory = FirebaseDirectory("https://qu--mail-default-rtdb.firebaseio.com")
                    remote_pub = await directory.fetch_public_key(remote_user)
                    await directory.close()
                except Exception:
                    remote_pub = None
                uid_source = remote_pub or remote_user
                await self.agora_widget.join(channel_name, uid_source, with_video=(call_type.value == 'video'))
            elif self.native_call_widget:
                success = self.native_call_widget.start_call(call_id, call_type.value, remote_user)
                if not success:
                    # Fallback to WebRTC widget
                    log.warning("Native call failed, falling back to WebRTC widget")
                    self.webrtc_widget.initiate_call(call_id, call_type.value, remote_user)
            else:
                # Use WebRTC widget
                self.webrtc_widget.initiate_call(call_id, call_type.value, remote_user)
            
            # Send call initiation via Firebase signaling for cross-device support
            if self.firebase_signaling:
                try:
                    quantum_key_id = f"qk_{call_id}"
                    await self.firebase_signaling.initiate_call(call_id, remote_user, call_type.value, quantum_key_id)
                    log.info(f"Call initiation sent via Firebase to {remote_user}")
                except Exception as e:
                    log.warning(f"Failed to send call initiation via Firebase: {e}")
            else:
                # Fallback to local signaling server
                try:
                    await self.send_call_initiation(call_id, remote_user, call_type.value)
                except Exception as e:
                    log.warning(f"Failed to send call initiation to local signaling server: {e}")
            
            # Emit signal
            self.call_initiated.emit(call_id, remote_user, call_type.value)
            
            log.info(f"Call {call_id} initiated to {remote_user}")
            return call_id
            
        except Exception as e:
            log.error(f"Failed to initiate call: {e}")
            QMessageBox.critical(None, "Call Failed", f"Failed to initiate call:\n{e}")
            self.call_failed.emit("", str(e))
            return None
    
    async def answer_call(self, call_id: str) -> bool:
        """Answer an incoming call"""
        try:
            success = await self.webrtc_service.answer_call(call_id)
            if success:
                # Also start native call widget if available
                call_session = self.webrtc_service.get_call_session(call_id)
                if call_session and self.native_call_widget:
                    self.native_call_widget.start_call(call_id, call_session.call_type.value, call_session.remote_user)
                
                log.info(f"Call {call_id} answered")
                return True
            else:
                log.error(f"Failed to answer call {call_id}")
                return False
        except Exception as e:
            log.error(f"Error answering call: {e}")
            return False
    
    async def end_call(self, call_id: str) -> bool:
        """End a call"""
        try:
            # End native call if available
            if self.native_call_widget:
                self.native_call_widget.end_call()
            
            success = await self.webrtc_service.end_call(call_id)
            if success:
                # Close call dialog if exists
                if call_id in self.active_call_dialogs:
                    dialog = self.active_call_dialogs[call_id]
                    dialog.close()
                    del self.active_call_dialogs[call_id]
                
                log.info(f"Call {call_id} ended")
                return True
            else:
                log.error(f"Failed to end call {call_id}")
                return False
        except Exception as e:
            log.error(f"Error ending call: {e}")
            return False
    
    def end_all_calls(self):
        """End all active calls"""
        for call_id in list(self.active_call_dialogs.keys()):
            asyncio.create_task(self.end_call(call_id))
    
    def toggle_mute(self, call_id: str) -> bool:
        """Toggle mute for a call"""
        return self.webrtc_service.toggle_mute(call_id)
    
    def toggle_video(self, call_id: str) -> bool:
        """Toggle video for a call"""
        return self.webrtc_service.toggle_video(call_id)
    
    def get_active_calls(self) -> Dict[str, CallSession]:
        """Get all active calls"""
        return self.webrtc_service.get_active_calls()
    
    def is_in_call(self) -> bool:
        """Check if user is currently in a call"""
        return len(self.active_call_dialogs) > 0
    
    @pyqtSlot(str, str, str)
    def on_webrtc_call_initiated(self, call_id: str, call_type: str, remote_user: str):
        """Handle WebRTC call initiated"""
        log.info(f"WebRTC call {call_id} initiated to {remote_user}")
    
    @pyqtSlot(str)
    def on_webrtc_call_answered(self, call_id: str):
        """Handle WebRTC call answered"""
        log.info(f"WebRTC call {call_id} answered")
    
    @pyqtSlot(str)
    def on_webrtc_call_ended(self, call_id: str):
        """Handle WebRTC call ended"""
        log.info(f"WebRTC call {call_id} ended")
    
    @pyqtSlot(str)
    def on_webrtc_error(self, error_message: str):
        """Handle WebRTC error"""
        log.error(f"WebRTC error: {error_message}")
        QMessageBox.critical(None, "WebRTC Error", f"WebRTC error: {error_message}")
    
    @pyqtSlot(bool, bool)
    def on_media_ready(self, has_audio: bool, has_video: bool):
        """Handle media ready from WebRTC widget"""
        log.info(f"WebRTC media ready - Audio: {has_audio}, Video: {has_video}")
    
    @pyqtSlot(bool, bool)
    def on_media_ready_native(self, has_audio: bool, has_video: bool):
        """Handle media ready from native service"""
        log.info(f"Native media ready - Audio: {has_audio}, Video: {has_video}")
    
    @pyqtSlot()
    def on_native_call_connected(self):
        """Handle native call connected"""
        log.info("Native call connected successfully")
    
    @pyqtSlot()
    def on_native_call_disconnected(self):
        """Handle native call disconnected"""
        log.info("Native call disconnected")
    
    @pyqtSlot(str)
    def on_native_call_error(self, error_message: str):
        """Handle native call error"""
        log.error(f"Native call error: {error_message}")
        QMessageBox.critical(None, "Call Error", f"Native call error: {error_message}")
    
    @pyqtSlot(bool, bool)
    def on_remote_stream(self, has_audio: bool, has_video: bool):
        """Handle remote stream"""
        log.info(f"Remote stream - Audio: {has_audio}, Video: {has_video}")
    
    @pyqtSlot(str)
    def on_connection_state(self, state: str):
        """Handle connection state change"""
        log.info(f"Connection state: {state}")
    
    @pyqtSlot(bool)
    def on_mute_toggled(self, muted: bool):
        """Handle mute toggle"""
        log.info(f"Mute toggled: {muted}")
    
    @pyqtSlot(bool)
    def on_video_toggled(self, video_enabled: bool):
        """Handle video toggle"""
        log.info(f"Video toggled: {video_enabled}")

    @pyqtSlot(str, str)
    def on_call_state_changed(self, call_id: str, state: str):
        """Handle call state changes"""
        log.info(f"Call {call_id} state changed to {state}")
        
        # Update call dialog if exists
        if call_id in self.active_call_dialogs:
            dialog = self.active_call_dialogs[call_id]
            # The dialog will handle its own state updates
    
    @pyqtSlot(str, str, str)
    def on_call_received(self, call_id: str, caller: str, call_type: str):
        """Handle incoming call"""
        log.info(f"Incoming call {call_id} from {caller}")
        # Remember caller to compute UID later
        self._incoming_calls[call_id] = { 'caller': caller, 'call_type': call_type }
        
        # Check if user is already in a call
        if self.active_call_dialogs:
            log.warning(f"Rejecting incoming call {call_id} - user already in call")
            asyncio.create_task(self.webrtc_service.end_call(call_id))
            return
        
        # Show incoming call dialog
        self.incoming_call_dialog = IncomingCallDialog(
            call_id, caller, call_type, self.webrtc_widget if not self.use_agora else None
        )
        
        # Connect signals
        self.incoming_call_dialog.call_accepted.connect(self.on_incoming_call_accepted)
        self.incoming_call_dialog.call_rejected.connect(self.on_incoming_call_rejected)
        
        # Show dialog
        self.incoming_call_dialog.show()
        
        # Emit signal
        self.call_received.emit(call_id, caller, call_type)
    
    @pyqtSlot(str)
    def on_call_ended(self, call_id: str):
        """Handle call ended"""
        log.info(f"Call {call_id} ended")
        # Leave Agora channel if joined
        if self.agora_widget:
            asyncio.create_task(self.agora_widget.leave())
        
        # Close call dialog if exists
        if call_id in self.active_call_dialogs:
            dialog = self.active_call_dialogs[call_id]
            dialog.close()
            del self.active_call_dialogs[call_id]
        
        # Emit signal
        self.call_ended.emit(call_id)
    
    @pyqtSlot(str)
    def on_error_occurred(self, error_message: str):
        """Handle WebRTC errors"""
        log.error(f"WebRTC error: {error_message}")
        QMessageBox.critical(None, "Call Error", f"An error occurred during the call:\n{error_message}")
    
    @pyqtSlot(str)
    def on_call_dialog_ended(self, call_id: str):
        """Handle call dialog ended"""
        if call_id in self.active_call_dialogs:
            del self.active_call_dialogs[call_id]
    
    @pyqtSlot(str)
    def on_incoming_call_accepted(self, call_id: str):
        """Handle incoming call accepted"""
        log.info(f"Incoming call {call_id} accepted")
        
        # Check if call is already being handled
        if call_id in self.active_call_dialogs:
            log.warning(f"Call {call_id} already being handled, ignoring duplicate accept")
            return
        
        # Close incoming call dialog
        if self.incoming_call_dialog:
            self.incoming_call_dialog.close()
            self.incoming_call_dialog = None
        
        # Create call dialog
        call_session = CallSession(
            call_id=call_id,
            call_type=CallType.VOICE,  # Default to voice, could be determined from signaling
            local_user=self.current_user,
            remote_user="",  # Will be set from signaling
            state=CallState.CONNECTING
        )
        
        call_widget = self.native_call_widget if self.native_call_widget else self.webrtc_widget
        use_native = self.native_call_widget is not None
        call_dialog = CallDialog(call_widget, call_session, use_native=use_native)
        call_dialog.call_ended.connect(self.on_call_dialog_ended)
        self.active_call_dialogs[call_id] = call_dialog
        
        # Show dialog
        call_dialog.show()
        
        # Answer the call using Agora when enabled
        try:
            if self.agora_widget:
                conversation_id = call_id
                channel_name = f"call_{conversation_id}"
                caller = self._incoming_calls.get(call_id, {}).get('caller', '')
                # Use caller public key when available
                async def _join_agora():
                    try:
                        directory = FirebaseDirectory("https://qu--mail-default-rtdb.firebaseio.com")
                        caller_pub = await directory.fetch_public_key(caller) if caller else None
                        await directory.close()
                    except Exception:
                        caller_pub = None
                    uid_source = caller_pub or caller or self.current_user
                    await self.agora_widget.join(channel_name, uid_source, with_video=True)
                asyncio.create_task(_join_agora())
            else:
                asyncio.create_task(self.answer_call(call_id))
                log.info(f"Call {call_id} answered")
        except Exception as e:
            log.error(f"Failed to answer call {call_id}: {e}")
            # Clean up on failure
            if call_id in self.active_call_dialogs:
                del self.active_call_dialogs[call_id]
    
    @pyqtSlot(str)
    def on_incoming_call_rejected(self, call_id: str):
        """Handle incoming call rejected"""
        log.info(f"Incoming call {call_id} rejected")

        # Close incoming call dialog
        if self.incoming_call_dialog:
            self.incoming_call_dialog.close()
            self.incoming_call_dialog = None
        
        # End the call using available widgets
        if self.native_call_widget:
            self.native_call_widget.end_call()
        self.webrtc_widget.end_call()

        # Emit signal (optional, but good for consistency)
        self.call_ended.emit(call_id)
    
    @pyqtSlot(str, str, str)
    def on_incoming_call(self, call_id: str, caller: str, call_type: str):
        """Handle incoming call from WebRTC widget"""
        log.info(f"Incoming call {call_id} from {caller}")
        
        # Check if user is already in a call
        if self.active_call_dialogs:
            log.warning(f"Rejecting incoming call {call_id} - user already in call")
            self.webrtc_widget.end_call()
            return
        
        # Show incoming call dialog
        self.incoming_call_dialog = IncomingCallDialog(
            call_id, caller, call_type, self.webrtc_widget
        )
        
        # Connect signals
        self.incoming_call_dialog.call_accepted.connect(self.on_incoming_call_accepted)
        self.incoming_call_dialog.call_rejected.connect(self.on_incoming_call_rejected)
        
        # Show dialog
        self.incoming_call_dialog.show()
        
        # Emit signal
        self.call_received.emit(call_id, caller, call_type)
    
    @pyqtSlot(str, str, str)
    def on_quantum_key_requested(self, request_id: str, call_id: str, remote_user: str):
        """Handle quantum key request from WebRTC widget"""
        log.info(f"Quantum key requested for call {call_id} with {remote_user}")
        
        try:
            # Request quantum key from QKD service
            # This is a simplified implementation - in reality, you'd integrate with your QKD service
            quantum_key = self.generate_quantum_key(call_id, remote_user)
            
            if quantum_key:
                self.webrtc_widget.provide_quantum_key(request_id, quantum_key)
                log.info(f"Quantum key provided for call {call_id}")
            else:
                self.webrtc_widget.reject_quantum_key(request_id, "Failed to generate quantum key")
                log.error(f"Failed to generate quantum key for call {call_id}")
                
        except Exception as e:
            log.error(f"Error handling quantum key request: {e}")
            self.webrtc_widget.reject_quantum_key(request_id, str(e))
    
    def generate_quantum_key(self, call_id: str, remote_user: str) -> Optional[str]:
        """Generate or retrieve quantum key for call encryption"""
        try:
            # This is a simplified implementation
            # In reality, you would:
            # 1. Request a quantum key from your QKD service
            # 2. Use the existing quantum key infrastructure
            # 3. Ensure both parties have the same key
            
            # For now, generate a mock quantum key
            import hashlib
            import time
            
            # Create a deterministic key based on call participants and time
            key_data = f"{self.current_user}:{remote_user}:{call_id}:{int(time.time() / 60)}"  # Changes every minute
            quantum_key = hashlib.sha256(key_data.encode()).hexdigest()[:32]  # 32 char key
            
            log.info(f"Generated quantum key for call {call_id}")
            return quantum_key
            
        except Exception as e:
            log.error(f"Error generating quantum key: {e}")
            return None
    
    async def send_call_initiation(self, call_id: str, remote_user: str, call_type: str):
        """Send call initiation to signaling server for cross-device support"""
        try:
            import httpx
            
            call_data = {
                "call_id": call_id,
                "from_user": self.current_user,
                "to_user": remote_user,
                "call_type": call_type,
                "quantum_key_id": f"qk_{call_id}"  # Generate quantum key ID
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.signaling_server_url}/initiate_call",
                    json=call_data,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    log.info(f"Call initiation sent to signaling server for {remote_user}")
                else:
                    log.warning(f"Failed to send call initiation: {response.status_code}")
                    
        except Exception as e:
            log.error(f"Error sending call initiation: {e}")
            # Don't fail the call if signaling fails - WebRTC can still work locally
    
    # Firebase signaling signal handlers
    @pyqtSlot(str, str, str, str)
    def on_firebase_call_received(self, call_id: str, caller: str, call_type: str, quantum_key_id: str):
        """Handle incoming call from Firebase signaling"""
        log.info(f"Firebase: Incoming call {call_id} from {caller}")
        self.on_call_received(call_id, caller, call_type)
    
    @pyqtSlot(str)
    def on_firebase_call_answered(self, call_id: str):
        """Handle call answered via Firebase signaling"""
        log.info(f"Firebase: Call {call_id} answered")
        self.on_webrtc_call_answered(call_id)
    
    @pyqtSlot(str)
    def on_firebase_call_ended(self, call_id: str):
        """Handle call ended via Firebase signaling"""
        log.info(f"Firebase: Call {call_id} ended")
        self.on_call_ended(call_id)
    
    @pyqtSlot(str, dict)
    def on_firebase_offer_received(self, call_id: str, offer: dict):
        """Handle WebRTC offer received via Firebase"""
        log.debug(f"Firebase: Offer received for call {call_id}")
        # Forward to WebRTC widget
        self.webrtc_widget.handle_offer(call_id, offer)
    
    @pyqtSlot(str, dict)
    def on_firebase_answer_received(self, call_id: str, answer: dict):
        """Handle WebRTC answer received via Firebase"""
        log.debug(f"Firebase: Answer received for call {call_id}")
        # Forward to WebRTC widget
        self.webrtc_widget.handle_answer(call_id, answer)
    
    @pyqtSlot(str, dict)
    def on_firebase_ice_candidate_received(self, call_id: str, candidate: dict):
        """Handle ICE candidate received via Firebase"""
        log.debug(f"Firebase: ICE candidate received for call {call_id}")
        # Forward to WebRTC widget
        self.webrtc_widget.handle_ice_candidate(call_id, candidate)
    
    @pyqtSlot(str, str)
    def on_firebase_quantum_key_requested(self, call_id: str, quantum_key_id: str):
        """Handle quantum key request via Firebase"""
        log.debug(f"Firebase: Quantum key requested for call {call_id}")
        # Generate and provide quantum key
        quantum_key = self.generate_quantum_key(call_id, "")
        if quantum_key:
            # Send quantum key back via Firebase
            asyncio.create_task(self.firebase_signaling.send_message({
                'type': 'quantum_key_response',
                'call_id': call_id,
                'quantum_key': quantum_key,
                'quantum_key_id': quantum_key_id
            }))
    
    @pyqtSlot(dict)
    def on_firebase_signaling_message(self, message: dict):
        """Handle Firebase signaling message from WebRTC widget"""
        if self.firebase_signaling:
            asyncio.create_task(self.firebase_signaling.send_message(message, message.get('to')))
    
    async def test_audio_functionality(self):
        """Test basic audio functionality"""
        try:
            log.info("Testing audio functionality...")
            
            # Test if WebRTC widget can access media devices
            test_js = """
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({audio: true})
                    .then(stream => {
                        console.log('Audio test successful:', stream.getAudioTracks().length, 'audio tracks');
                        stream.getTracks().forEach(track => track.stop());
                        window.pyqtwebchannel.send({
                            type: 'audio_test_result',
                            success: true,
                            message: 'Audio access successful'
                        });
                    })
                    .catch(error => {
                        console.error('Audio test failed:', error);
                        window.pyqtwebchannel.send({
                            type: 'audio_test_result',
                            success: false,
                            message: error.message
                        });
                    });
            } else {
                window.pyqtwebchannel.send({
                    type: 'audio_test_result',
                    success: false,
                    message: 'getUserMedia not supported'
                });
            }
            """
            
            self.webrtc_widget.page().runJavaScript(test_js)
            log.info("Audio test initiated")
            
        except Exception as e:
            log.error(f"Failed to test audio functionality: {e}")
    
    async def shutdown(self):
        """Shutdown call controller"""
        # End all active calls
        self.end_all_calls()
        
        # Disconnect Firebase signaling
        if self.firebase_signaling:
            await self.firebase_signaling.disconnect()
        
        # Close WebRTC service
        if self.webrtc_service:
            await self.webrtc_service.close()
        
        log.info("Call controller shutdown complete")
