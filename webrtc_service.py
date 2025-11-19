# webrtc_service.py
import asyncio
import json
import logging
import uuid
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import httpx
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl

log = logging.getLogger(__name__)

class CallType(Enum):
    VOICE = "voice"
    VIDEO = "video"

class CallState(Enum):
    IDLE = "idle"
    INITIATING = "initiating"
    RINGING = "ringing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ENDED = "ended"
    FAILED = "failed"

@dataclass
class CallSession:
    call_id: str
    call_type: CallType
    local_user: str
    remote_user: str
    state: CallState
    start_time: Optional[float] = None
    end_time: Optional[float] = None

class WebRTCService(QObject):
    """WebRTC service for peer-to-peer voice and video calls"""
    
    # Signals for UI updates
    call_state_changed = pyqtSignal(str, str)  # call_id, state
    call_received = pyqtSignal(str, str, str)  # call_id, caller, call_type
    call_ended = pyqtSignal(str)  # call_id
    error_occurred = pyqtSignal(str)  # error_message
    
    def __init__(self, signaling_server_url: str = "http://127.0.0.1:8081"):  # Changed from 8080 to 8081
        super().__init__()
        self.signaling_server_url = signaling_server_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=10.0)
        self.active_calls: Dict[str, CallSession] = {}
        self.web_view: Optional[QWebEngineView] = None
        self.is_initialized = False
        
        # WebRTC JavaScript code
        self.webrtc_js = """
        class WebRTCManager {
            constructor() {
                this.localStream = null;
                this.remoteStream = null;
                this.peerConnection = null;
                this.dataChannel = null;
                this.isInitiator = false;
                this.callId = null;
                this.callType = 'voice';
                
                this.iceServers = [
                    { urls: 'stun:stun.l.google.com:19302' },
                    { urls: 'stun:stun1.l.google.com:19302' }
                ];
                
                this.setupEventListeners();
            }
            
            setupEventListeners() {
                // Listen for messages from Python
                window.addEventListener('message', (event) => {
                    if (event.data.type === 'webrtc_command') {
                        this.handleCommand(event.data.command, event.data.data);
                    }
                });
            }
            
            async handleCommand(command, data) {
                switch(command) {
                    case 'init_call':
                        await this.initiateCall(data.callId, data.callType, data.remoteUser);
                        break;
                    case 'answer_call':
                        await this.answerCall(data.callId);
                        break;
                    case 'end_call':
                        await this.endCall();
                        break;
                    case 'toggle_mute':
                        this.toggleMute();
                        break;
                    case 'toggle_video':
                        this.toggleVideo();
                        break;
                }
            }
            
            async initiateCall(callId, callType, remoteUser) {
                this.callId = callId;
                this.callType = callType;
                this.isInitiator = true;
                
                try {
                    await this.getUserMedia();
                    await this.createPeerConnection();
                    await this.createOffer();
                    
                    // Send offer to signaling server
                    this.sendToSignaling('offer', {
                        callId: callId,
                        callType: callType,
                        from: this.getCurrentUser(),
                        to: remoteUser,
                        offer: this.peerConnection.localDescription
                    });
                    
                    this.notifyPython('call_initiated', { callId, callType });
                } catch (error) {
                    console.error('Failed to initiate call:', error);
                    this.notifyPython('call_error', { error: error.message });
                }
            }
            
            async answerCall(callId) {
                this.callId = callId;
                this.isInitiator = false;
                
                try {
                    await this.getUserMedia();
                    await this.createPeerConnection();
                    
                    this.notifyPython('call_answered', { callId });
                } catch (error) {
                    console.error('Failed to answer call:', error);
                    this.notifyPython('call_error', { error: error.message });
                }
            }
            
            async getUserMedia() {
                const constraints = {
                    audio: true,
                    video: this.callType === 'video' ? {
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                        frameRate: { ideal: 30 }
                    } : false
                };
                
                this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
                
                // Add tracks to peer connection
                if (this.peerConnection) {
                    this.localStream.getTracks().forEach(track => {
                        this.peerConnection.addTrack(track, this.localStream);
                    });
                }
                
                this.notifyPython('media_ready', { 
                    hasAudio: this.localStream.getAudioTracks().length > 0,
                    hasVideo: this.localStream.getVideoTracks().length > 0
                });
            }
            
            async createPeerConnection() {
                this.peerConnection = new RTCPeerConnection({
                    iceServers: this.iceServers
                });
                
                // Handle incoming stream
                this.peerConnection.ontrack = (event) => {
                    this.remoteStream = event.streams[0];
                    this.notifyPython('remote_stream', { 
                        hasAudio: this.remoteStream.getAudioTracks().length > 0,
                        hasVideo: this.remoteStream.getVideoTracks().length > 0
                    });
                };
                
                // Handle ICE candidates
                this.peerConnection.onicecandidate = (event) => {
                    if (event.candidate) {
                        this.sendToSignaling('ice_candidate', {
                            callId: this.callId,
                            candidate: event.candidate
                        });
                    }
                };
                
                // Handle connection state changes
                this.peerConnection.onconnectionstatechange = () => {
                    this.notifyPython('connection_state', { 
                        state: this.peerConnection.connectionState 
                    });
                };
            }
            
            async createOffer() {
                const offer = await this.peerConnection.createOffer();
                await this.peerConnection.setLocalDescription(offer);
            }
            
            async createAnswer() {
                const answer = await this.peerConnection.createAnswer();
                await this.peerConnection.setLocalDescription(answer);
                
                this.sendToSignaling('answer', {
                    callId: this.callId,
                    answer: answer
                });
            }
            
            async handleOffer(offer) {
                await this.peerConnection.setRemoteDescription(offer);
                await this.createAnswer();
            }
            
            async handleAnswer(answer) {
                await this.peerConnection.setRemoteDescription(answer);
            }
            
            async handleIceCandidate(candidate) {
                await this.peerConnection.addIceCandidate(candidate);
            }
            
            async endCall() {
                if (this.localStream) {
                    this.localStream.getTracks().forEach(track => track.stop());
                }
                
                if (this.peerConnection) {
                    this.peerConnection.close();
                }
                
                this.notifyPython('call_ended', { callId: this.callId });
            }
            
            toggleMute() {
                if (this.localStream) {
                    const audioTrack = this.localStream.getAudioTracks()[0];
                    if (audioTrack) {
                        audioTrack.enabled = !audioTrack.enabled;
                        this.notifyPython('mute_toggled', { muted: !audioTrack.enabled });
                    }
                }
            }
            
            toggleVideo() {
                if (this.localStream) {
                    const videoTrack = this.localStream.getVideoTracks()[0];
                    if (videoTrack) {
                        videoTrack.enabled = !videoTrack.enabled;
                        this.notifyPython('video_toggled', { videoEnabled: videoTrack.enabled });
                    }
                }
            }
            
            sendToSignaling(type, data) {
                // This would normally send to a signaling server
                // For now, we'll simulate it
                console.log('Sending to signaling server:', type, data);
            }
            
            notifyPython(type, data) {
                window.pyqtwebchannel.send({
                    type: type,
                    data: data
                });
            }
            
            getCurrentUser() {
                return window.currentUser || 'user@example.com';
            }
        }
        
        // Initialize WebRTC manager
        window.webrtcManager = new WebRTCManager();
        """
    
    async def initialize(self) -> bool:
        """Initialize the WebRTC service"""
        try:
            # If using Firebase for signaling, no direct HTTP health check needed
            if self.signaling_server_url == "firebase":
                log.info("WebRTC service configured for Firebase signaling. Skipping HTTP health check.")
                self.is_initialized = True
                return True

            # Test signaling server connection with retries
            for attempt in range(3):
                try:
                    response = await self.client.get(f"{self.signaling_server_url}/health", timeout=5.0)
                    if response.status_code == 200:
                        self.is_initialized = True
                        log.info("WebRTC service initialized successfully")
                        return True
                    else:
                        log.warning(f"Signaling server health check failed: {response.status_code} (attempt {attempt + 1})")
                except Exception as e:
                    log.warning(f"Signaling server connection failed (attempt {attempt + 1}): {e}")
                
                if attempt < 2:  # Don't sleep on last attempt
                    await asyncio.sleep(2)
            
            log.warning("WebRTC service initialization failed - signaling server not available")
            self.is_initialized = False
            return False
            
        except Exception as e:
            log.error(f"Failed to initialize WebRTC service: {e}")
            self.error_occurred.emit(f"Failed to initialize WebRTC service: {e}")
            self.is_initialized = False
            return False
    
    def setup_web_view(self, web_view: QWebEngineView, current_user: str):
        """Setup the WebRTC web view"""
        self.web_view = web_view
        
        # Set current user in JavaScript context
        web_view.page().runJavaScript(f"window.currentUser = '{current_user}';")
        
        # Load WebRTC JavaScript with proper error handling
        web_view.page().runJavaScript("""
            // Check if webrtcManager already exists
            if (typeof window.webrtcManager === 'undefined') {
                """ + self.webrtc_js + """
            }
        """)
        
        # Setup message channel with better error handling
        web_view.page().runJavaScript("""
            if (typeof window.pyqtwebchannel === 'undefined') {
                window.pyqtwebchannel = {
                    send: function(message) {
                        try {
                            // Send message to Python
                            if (window.external && window.external.notify) {
                                window.external.notify(JSON.stringify(message));
                            } else {
                                console.log('Message to Python:', message);
                            }
                        } catch (error) {
                            console.error('Error sending message to Python:', error);
                        }
                    }
                };
            }
        """)
        
        log.info("WebRTC web view setup completed")
    
    async def initiate_call(self, call_type: CallType, remote_user: str) -> str:
        """Initiate a new call"""
        if not self.is_initialized:
            raise RuntimeError("WebRTC service not initialized")
        
        call_id = str(uuid.uuid4())
        call_session = CallSession(
            call_id=call_id,
            call_type=call_type,
            local_user="",  # Will be set by caller
            remote_user=remote_user,
            state=CallState.INITIATING
        )
        
        self.active_calls[call_id] = call_session
        self.call_state_changed.emit(call_id, CallState.INITIATING.value)
        
        try:
            # Send call initiation to signaling server
            await self._send_signaling_message({
                "type": "call_initiation",
                "call_id": call_id,
                "call_type": call_type.value,
                "to": remote_user
            })
            
            # Start WebRTC call
            if self.web_view:
                self.web_view.page().runJavaScript(f"""
                    try {{
                        if (typeof window.webrtcManager !== 'undefined') {{
                            window.webrtcManager.handleCommand('init_call', {{
                                callId: '{call_id}',
                                callType: '{call_type.value}',
                                remoteUser: '{remote_user}'
                            }});
                        }} else {{
                            console.error('WebRTC Manager not initialized');
                        }}
                    }} catch (error) {{
                        console.error('Error initiating call:', error);
                    }}
                """)
            
            call_session.state = CallState.RINGING
            self.call_state_changed.emit(call_id, CallState.RINGING.value)
            
            log.info(f"Call {call_id} initiated to {remote_user}")
            return call_id
            
        except Exception as e:
            log.error(f"Failed to initiate call: {e}")
            call_session.state = CallState.FAILED
            self.call_state_changed.emit(call_id, CallState.FAILED.value)
            self.error_occurred.emit(f"Failed to initiate call: {e}")
            raise
    
    async def answer_call(self, call_id: str) -> bool:
        """Answer an incoming call"""
        if call_id not in self.active_calls:
            log.error(f"Call {call_id} not found")
            return False
        
        call_session = self.active_calls[call_id]
        call_session.state = CallState.CONNECTING
        self.call_state_changed.emit(call_id, CallState.CONNECTING.value)
        
        try:
            # Send answer to signaling server
            await self._send_signaling_message({
                "type": "call_answer",
                "call_id": call_id
            })
            
            # Answer WebRTC call
            if self.web_view:
                self.web_view.page().runJavaScript(f"""
                    try {{
                        if (typeof window.webrtcManager !== 'undefined') {{
                            window.webrtcManager.handleCommand('answer_call', {{
                                callId: '{call_id}'
                            }});
                        }} else {{
                            console.error('WebRTC Manager not initialized');
                        }}
                    }} catch (error) {{
                        console.error('Error answering call:', error);
                    }}
                """)
            
            log.info(f"Call {call_id} answered")
            return True
            
        except Exception as e:
            log.error(f"Failed to answer call: {e}")
            call_session.state = CallState.FAILED
            self.call_state_changed.emit(call_id, CallState.FAILED.value)
            self.error_occurred.emit(f"Failed to answer call: {e}")
            return False
    
    async def end_call(self, call_id: str) -> bool:
        """End a call"""
        if call_id not in self.active_calls:
            log.error(f"Call {call_id} not found")
            return False
        
        call_session = self.active_calls[call_id]
        call_session.state = CallState.ENDED
        call_session.end_time = asyncio.get_event_loop().time()
        
        try:
            # Send end call to signaling server
            await self._send_signaling_message({
                "type": "call_end",
                "call_id": call_id
            })
            
            # End WebRTC call
            if self.web_view:
                self.web_view.page().runJavaScript(f"""
                    try {{
                        if (typeof window.webrtcManager !== 'undefined') {{
                            window.webrtcManager.handleCommand('end_call', {{}});
                        }} else {{
                            console.error('WebRTC Manager not initialized');
                        }}
                    }} catch (error) {{
                        console.error('Error ending call:', error);
                    }}
                """)
            
            # Remove from active calls
            del self.active_calls[call_id]
            
            self.call_ended.emit(call_id)
            log.info(f"Call {call_id} ended")
            return True
            
        except Exception as e:
            log.error(f"Failed to end call: {e}")
            self.error_occurred.emit(f"Failed to end call: {e}")
            return False
    
    def toggle_mute(self, call_id: str) -> bool:
        """Toggle mute for a call"""
        if call_id not in self.active_calls:
            return False
        
        if self.web_view:
            self.web_view.page().runJavaScript(f"""
                try {{
                    if (typeof window.webrtcManager !== 'undefined') {{
                        window.webrtcManager.handleCommand('toggle_mute', {{}});
                    }} else {{
                        console.error('WebRTC Manager not initialized');
                    }}
                }} catch (error) {{
                    console.error('Error toggling mute:', error);
                }}
            """)
        
        return True
    
    def toggle_video(self, call_id: str) -> bool:
        """Toggle video for a call"""
        if call_id not in self.active_calls:
            return False
        
        if self.web_view:
            self.web_view.page().runJavaScript(f"""
                try {{
                    if (typeof window.webrtcManager !== 'undefined') {{
                        window.webrtcManager.handleCommand('toggle_video', {{}});
                    }} else {{
                        console.error('WebRTC Manager not initialized');
                    }}
                }} catch (error) {{
                    console.error('Error toggling video:', error);
                }}
            """)
        
        return True
    
    async def _send_signaling_message(self, message: Dict[str, Any]):
        """Send message to signaling server"""
        try:
            response = await self.client.post(
                f"{self.signaling_server_url}/signaling",
                json=message,
                timeout=5.0
            )
            response.raise_for_status()
        except Exception as e:
            log.error(f"Failed to send signaling message: {e}")
            raise
    
    async def _handle_signaling_message(self, message: Dict[str, Any]):
        """Handle incoming signaling message"""
        message_type = message.get("type")
        call_id = message.get("call_id")
        
        if message_type == "call_initiation":
            # Incoming call
            caller = message.get("from")
            call_type = CallType(message.get("call_type", "voice"))
            
            call_session = CallSession(
                call_id=call_id,
                call_type=call_type,
                local_user="",  # Will be set by receiver
                remote_user=caller,
                state=CallState.RINGING
            )
            
            self.active_calls[call_id] = call_session
            self.call_received.emit(call_id, caller, call_type.value)
            
        elif message_type == "call_answer":
            # Call answered
            if call_id in self.active_calls:
                self.active_calls[call_id].state = CallState.CONNECTED
                self.call_state_changed.emit(call_id, CallState.CONNECTED.value)
        
        elif message_type == "call_end":
            # Call ended
            if call_id in self.active_calls:
                await self.end_call(call_id)
    
    def get_call_session(self, call_id: str) -> Optional[CallSession]:
        """Get call session by ID"""
        return self.active_calls.get(call_id)
    
    def get_active_calls(self) -> Dict[str, CallSession]:
        """Get all active calls"""
        return self.active_calls.copy()
    
    async def close(self):
        """Close the WebRTC service"""
        # End all active calls
        for call_id in list(self.active_calls.keys()):
            await self.end_call(call_id)
        
        # Close HTTP client
        await self.client.aclose()
        
        log.info("WebRTC service closed")
