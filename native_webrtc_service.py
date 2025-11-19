# native_webrtc_service.py
import asyncio
import json
import logging
import uuid
import socket
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread
from PyQt6.QtNetwork import QUdpSocket, QHostAddress
from PyQt6.QtMultimedia import QMediaDevices, QAudioInput, QAudioOutput
import httpx

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
    local_port: Optional[int] = None
    remote_port: Optional[int] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

class AudioHandler(QObject):
    """Handle audio streaming using Qt multimedia"""
    
    def __init__(self):
        super().__init__()
        self.audio_input = None
        self.audio_output = None
        self.udp_socket = QUdpSocket()
        self.is_streaming = False
        self.remote_address = None
        self.remote_port = None
        
    def start_streaming(self, remote_host: str, remote_port: int, local_port: int):
        """Start audio streaming"""
        try:
            # Setup UDP socket for audio
            self.udp_socket.bind(QHostAddress.LocalHost, local_port)
            self.remote_address = QHostAddress(remote_host)
            self.remote_port = remote_port
            
            # Setup audio input
            audio_device = QMediaDevices.defaultAudioInput()
            if not audio_device.isNull():
                self.audio_input = QAudioInput(audio_device)
                
            # Setup audio output
            output_device = QMediaDevices.defaultAudioOutput()
            if not output_device.isNull():
                self.audio_output = QAudioOutput(output_device)
            
            self.is_streaming = True
            log.info(f"Audio streaming started on port {local_port}")
            return True
            
        except Exception as e:
            log.error(f"Failed to start audio streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Stop audio streaming"""
        self.is_streaming = False
        if self.udp_socket:
            self.udp_socket.close()
        log.info("Audio streaming stopped")

class NativeWebRTCService(QObject):
    """Native WebRTC service using Qt multimedia and networking"""
    
    # Signals for UI updates
    call_state_changed = pyqtSignal(str, str)  # call_id, state
    call_received = pyqtSignal(str, str, str)  # call_id, caller, call_type
    call_ended = pyqtSignal(str)  # call_id
    error_occurred = pyqtSignal(str)  # error_message
    media_ready = pyqtSignal(bool, bool)  # has_audio, has_video
    
    def __init__(self, signaling_server_url: str = "http://127.0.0.1:8081"):
        super().__init__()
        self.signaling_server_url = signaling_server_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=10.0)
        self.active_calls: Dict[str, CallSession] = {}
        self.audio_handler = AudioHandler()
        self.is_initialized = False
        self.base_port = 8090  # Base port for media streaming
        
    async def initialize(self) -> bool:
        """Initialize the native WebRTC service"""
        try:
            # Check multimedia devices
            audio_inputs = QMediaDevices.audioInputs()
            audio_outputs = QMediaDevices.audioOutputs()
            video_inputs = QMediaDevices.videoInputs()
            
            if not audio_inputs:
                log.error("No audio input devices found")
                self.error_occurred.emit("No microphone found")
                return False
                
            if not audio_outputs:
                log.error("No audio output devices found")
                self.error_occurred.emit("No speakers found")
                return False
            
            log.info(f"Found {len(audio_inputs)} audio inputs, {len(audio_outputs)} audio outputs, {len(video_inputs)} video inputs")
            
            # Test signaling server connection
            try:
                response = await self.client.get(f"{self.signaling_server_url}/health", timeout=5.0)
                if response.status_code == 200:
                    self.is_initialized = True
                    log.info("Native WebRTC service initialized successfully")
                    self.media_ready.emit(True, len(video_inputs) > 0)
                    return True
                else:
                    log.warning(f"Signaling server health check failed: {response.status_code}")
            except Exception as e:
                log.warning(f"Signaling server connection failed: {e}")
            
            # Initialize without signaling server (local mode)
            self.is_initialized = True
            log.info("Native WebRTC service initialized in local mode")
            self.media_ready.emit(True, len(video_inputs) > 0)
            return True
            
        except Exception as e:
            log.error(f"Failed to initialize native WebRTC service: {e}")
            self.error_occurred.emit(f"Failed to initialize: {e}")
            return False
    
    async def initiate_call(self, call_type: CallType, remote_user: str, local_user: str = "") -> str:
        """Initiate a new call"""
        if not self.is_initialized:
            raise RuntimeError("Native WebRTC service not initialized")
        
        call_id = str(uuid.uuid4())
        local_port = self.base_port + len(self.active_calls)
        
        call_session = CallSession(
            call_id=call_id,
            call_type=call_type,
            local_user=local_user,
            remote_user=remote_user,
            state=CallState.INITIATING,
            local_port=local_port
        )
        
        self.active_calls[call_id] = call_session
        self.call_state_changed.emit(call_id, CallState.INITIATING.value)
        
        try:
            # Send call initiation to signaling server
            await self._send_signaling_message({
                "type": "call_initiation",
                "call_id": call_id,
                "call_type": call_type.value,
                "from": local_user,
                "to": remote_user,
                "local_port": local_port
            })
            
            # Start media streaming
            if not self.audio_handler.start_streaming("127.0.0.1", local_port + 1, local_port):
                raise Exception("Failed to start audio streaming")
            
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
                "call_id": call_id,
                "local_port": call_session.local_port
            })
            
            # Start media streaming
            if not self.audio_handler.start_streaming("127.0.0.1", call_session.remote_port or 8091, call_session.local_port):
                raise Exception("Failed to start audio streaming")
            
            call_session.state = CallState.CONNECTED
            call_session.start_time = asyncio.get_event_loop().time()
            self.call_state_changed.emit(call_id, CallState.CONNECTED.value)
            
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
            
            # Stop media streaming
            self.audio_handler.stop_streaming()
            
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
        
        # In a real implementation, this would mute the audio stream
        log.info(f"Toggled mute for call {call_id}")
        return True
    
    def toggle_video(self, call_id: str) -> bool:
        """Toggle video for a call"""
        if call_id not in self.active_calls:
            return False
        
        # In a real implementation, this would toggle video stream
        log.info(f"Toggled video for call {call_id}")
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
            # Don't raise in local mode
            if self.signaling_server_url != "local":
                raise
    
    async def handle_incoming_call(self, call_data: Dict[str, Any]):
        """Handle incoming call from signaling server"""
        call_id = call_data.get("call_id")
        caller = call_data.get("from")
        call_type = CallType(call_data.get("call_type", "voice"))
        remote_port = call_data.get("local_port", 8091)
        
        local_port = self.base_port + len(self.active_calls)
        
        call_session = CallSession(
            call_id=call_id,
            call_type=call_type,
            local_user="",  # Will be set by receiver
            remote_user=caller,
            state=CallState.RINGING,
            local_port=local_port,
            remote_port=remote_port
        )
        
        self.active_calls[call_id] = call_session
        self.call_received.emit(call_id, caller, call_type.value)
        
        log.info(f"Incoming call from {caller}: {call_id}")
    
    def get_call_session(self, call_id: str) -> Optional[CallSession]:
        """Get call session by ID"""
        return self.active_calls.get(call_id)
    
    def get_active_calls(self) -> Dict[str, CallSession]:
        """Get all active calls"""
        return self.active_calls.copy()
    
    async def close(self):
        """Close the native WebRTC service"""
        # End all active calls
        for call_id in list(self.active_calls.keys()):
            await self.end_call(call_id)
        
        # Stop audio handler
        self.audio_handler.stop_streaming()
        
        # Close HTTP client
        await self.client.aclose()
        
        log.info("Native WebRTC service closed")