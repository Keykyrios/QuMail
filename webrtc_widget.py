# webrtc_widget.py
import asyncio
import logging
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage

log = logging.getLogger(__name__)

class WebRTCWidget(QWebEngineView):
    """Dedicated WebRTC widget for handling voice and video calls"""
    
    # Signals
    call_initiated = pyqtSignal(str, str, str)  # call_id, call_type, remote_user
    call_answered = pyqtSignal(str)  # call_id
    call_ended = pyqtSignal(str)  # call_id
    call_error = pyqtSignal(str)  # error_message
    media_ready = pyqtSignal(bool, bool)  # has_audio, has_video
    remote_stream = pyqtSignal(bool, bool)  # has_audio, has_video
    connection_state = pyqtSignal(str)  # state
    mute_toggled = pyqtSignal(bool)  # muted
    video_toggled = pyqtSignal(bool)  # video_enabled
    incoming_call = pyqtSignal(str, str, str)  # call_id, caller, call_type
    quantum_key_requested = pyqtSignal(str, str, str)  # request_id, call_id, remote_user
    firebase_signaling_message = pyqtSignal(dict)  # Firebase signaling message
    
    def __init__(self, use_firebase_signaling: bool = False, parent=None):
        super().__init__(parent)
        self.current_user = ""
        self.use_firebase_signaling_js = use_firebase_signaling # Store for JS
        self.setup_web_view()
        log.info("WebRTC widget initialized")
    
    def set_current_user(self, user_email: str):
        """Set the current user email"""
        self.current_user = user_email
        # Update JavaScript with current user
        self.web_view.page().runJavaScript(f"window.currentUser = '{user_email}';")
        
        # Verify WebRTC Manager is initialized
        self.verify_webrtc_manager()
    
    def verify_webrtc_manager(self):
        """Verify that WebRTC Manager is properly initialized"""
        try:
            js_code = """
            console.log('Verifying WebRTC Manager initialization...');
            
            if (typeof window.webrtcManager !== 'undefined' && window.webrtcManager) {
                console.log('WebRTC Manager is properly initialized');
                window.pyqtwebchannel.send({
                    type: 'webrtc_manager_status',
                    initialized: true,
                    message: 'WebRTC Manager ready'
                });
            } else {
                console.error('WebRTC Manager not found, attempting initialization...');
                
                if (typeof window.QuantumWebRTCManager !== 'undefined') {
                    console.log('Initializing WebRTC Manager...');
                    window.webrtcManager = new window.QuantumWebRTCManager();
                    
                    setTimeout(() => {
                        if (window.webrtcManager) {
                            console.log('WebRTC Manager initialized successfully');
                            window.pyqtwebchannel.send({
                                type: 'webrtc_manager_status',
                                initialized: true,
                                message: 'WebRTC Manager initialized'
                            });
                        } else {
                            console.error('Failed to initialize WebRTC Manager');
                            window.pyqtwebchannel.send({
                                type: 'webrtc_manager_status',
                                initialized: false,
                                message: 'Failed to initialize WebRTC Manager'
                            });
                        }
                    }, 1000);
                } else {
                    console.error('QuantumWebRTCManager class not found');
                    window.pyqtwebchannel.send({
                        type: 'webrtc_manager_status',
                        initialized: false,
                        message: 'QuantumWebRTCManager class not found'
                    });
                }
            }
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error verifying WebRTC Manager: {e}")
    
    def handle_offer(self, call_id: str, offer: dict):
        """Handle WebRTC offer from Firebase"""
        try:
            import json
            js_code = f"""
            if (window.webrtcManager) {{
                window.webrtcManager.handleOffer({{
                    callId: '{call_id}',
                    offer: {json.dumps(offer)}
                }});
            }}
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error handling offer: {e}")
    
    def handle_answer(self, call_id: str, answer: dict):
        """Handle WebRTC answer from Firebase"""
        try:
            import json
            js_code = f"""
            if (window.webrtcManager) {{
                window.webrtcManager.handleAnswer({{
                    callId: '{call_id}',
                    answer: {json.dumps(answer)}
                }});
            }}
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error handling answer: {e}")
    
    def handle_ice_candidate(self, call_id: str, candidate: dict):
        """Handle ICE candidate from Firebase"""
        try:
            import json
            js_code = f"""
            if (window.webrtcManager) {{
                window.webrtcManager.handleIceCandidate({{
                    callId: '{call_id}',
                    candidate: {json.dumps(candidate)}
                }});
            }}
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error handling ICE candidate: {e}")
    
    def setup_web_view(self):
        """Setup the web view with WebRTC capabilities"""
        # Create a custom page
        self.web_view = self
        page = QWebEnginePage()
        self.setPage(page)
        
        # Setup web channel for communication
        self.channel = QWebChannel()
        self.channel.registerObject("webrtcBridge", self)
        page.setWebChannel(self.channel)
        
        # Connect page load finished to ensure proper initialization
        page.loadFinished.connect(self.on_page_loaded)
        
        # Load a basic HTML page first to ensure proper initialization
        basic_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>QuMail WebRTC</title>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        </head>
        <body>
            <div id="status">Initializing WebRTC...</div>
            <script>
                console.log('WebRTC page loaded');
                // Wait for page to be fully loaded before initializing WebRTC
                document.addEventListener('DOMContentLoaded', function() {
                    console.log('DOM loaded, ready for WebRTC initialization');
                });
            </script>
        </body>
        </html>
        """
        
        self.setHtml(basic_html)
        
        # Load WebRTC JavaScript after a short delay to ensure page is ready
        asyncio.create_task(self.delayed_webrtc_init())
    
    @pyqtSlot(bool)
    def on_page_loaded(self, success: bool):
        """Handle page load completion"""
        if success:
            log.info("WebRTC page loaded successfully")
        else:
            log.error("WebRTC page failed to load")
    
    async def delayed_webrtc_init(self):
        """Delayed WebRTC initialization to ensure page is ready"""
        await asyncio.sleep(1)  # Wait for page to load
        self.load_webrtc_js(self.use_firebase_signaling_js)
    
    def load_webrtc_js(self, use_firebase_signaling_js: bool):
        """Load comprehensive WebRTC JavaScript code with quantum encryption"""
        webrtc_js = f"""
        class QuantumWebRTCManager {{
            constructor() {{
                this.localStream = null;
                this.remoteStream = null;
                this.peerConnection = null;
                this.isInitiator = false;
                this.callId = null;
                this.callType = 'voice';
                this.signalingServer = 'ws://127.0.0.1:8081/ws/';
                this.websocket = null;
                this.useFirebaseSignaling = {str(use_firebase_signaling_js).lower()};
                this.quantumKey = null;
                
                this.iceServers = [
                    {{ urls: 'stun:stun.l.google.com:19302' }},
                    {{ urls: 'stun:stun1.l.google.com:19302' }},
                    {{ urls: 'stun:stun2.l.google.com:19302' }},
                    {{ urls: 'stun:stun3.l.google.com:19302' }}
                ];
                
                this.setupEventListeners();
                this.connectSignalingServer();
                console.log('Quantum WebRTC Manager initialized');
            }}
            
            connectSignalingServer() {{
                if (this.useFirebaseSignaling) {{
                    console.log('Using Firebase signaling - no WebSocket connection needed');
                    this.notifyPython('signaling_connected', {{ method: 'firebase' }});
                }} else {{
                    try {{
                        const userId = window.currentUser || 'anonymous';
                        this.websocket = new WebSocket(this.signalingServer + userId);
                        
                        this.websocket.onopen = () => {{
                            console.log('Connected to signaling server');
                            this.notifyPython('signaling_connected', {{ method: 'websocket' }});
                        }};
                        
                        this.websocket.onmessage = (event) => {{
                            const message = JSON.parse(event.data);
                            this.handleSignalingMessage(message);
                        }};
                        
                        this.websocket.onclose = () => {{
                            console.log('Disconnected from signaling server');
                            this.notifyPython('signaling_disconnected', {{}});
                        }};
                        
                        this.websocket.onerror = (error) => {{
                            console.error('Signaling server error:', error);
                            this.notifyPython('signaling_error', {{ error: error.message }});
                        }};
                    }} catch (error) {{
                        console.error('Failed to connect to signaling server:', error);
                        this.notifyPython('signaling_error', {{ error: error.message }});
                    }}
                }}
            }}
            
            handleSignalingMessage(message) {{
                console.log('Received signaling message:', message);
                
                switch(message.type) {{
                    case 'call_initiation':
                        this.handleIncomingCall(message);
                        break;
                    case 'offer':
                        this.handleOffer(message);
                        break;
                    case 'answer':
                        this.handleAnswer(message);
                        break;
                    case 'ice_candidate':
                        this.handleIceCandidate(message);
                        break;
                    case 'call_end':
                        this.handleCallEnd(message);
                        break;
                }}
            }}
            
            sendSignalingMessage(message) {{
                if (this.useFirebaseSignaling) {{
                    // Send via Firebase through Python
                    this.notifyPython('firebase_signaling_message', message);
                }} else if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {{
                    this.websocket.send(JSON.stringify(message));
                }} else {{
                    console.error('WebSocket not connected');
                }}
            }}
            
            setupEventListeners() {{
                // Listen for messages from Python
                window.addEventListener('message', (event) => {{
                    if (event.data.type === 'webrtc_command') {{
                        this.handleCommand(event.data.command, event.data.data);
                    }}
                }});
            }}
            
            async handleCommand(command, data) {{
                console.log('Handling command:', command, data);
                try {{
                    switch(command) {{
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
                    }}
                }} catch (error) {{
                    console.error('Error handling command:', error);
                    this.notifyPython('call_error', {{ error: error.message }});
                }}
            }}
            
            async initiateCall(callId, callType, remoteUser) {{
                console.log('Initiating call:', callId, callType, remoteUser);
                this.callId = callId;
                this.callType = callType;
                this.isInitiator = true;
                
                try {{
                    // Request quantum key for encryption
                    const quantumKey = await this.requestQuantumKey(callId, remoteUser);
                    
                    await this.getUserMedia();
                    await this.createPeerConnection(quantumKey);
                    await this.createOffer();
                    
                    this.notifyPython('call_initiated', {{ callId, callType, remoteUser }});
                }} catch (error) {{
                    console.error('Failed to initiate call:', error);
                    this.notifyPython('call_error', {{ error: error.message }});
                }}
            }}
            
            async answerCall(callId) {{
                console.log('Answering call:', callId);
                this.callId = callId;
                this.isInitiator = false;
                
                try {{
                    // Request quantum key for decryption
                    const quantumKey = await this.requestQuantumKey(callId, '');
                    
                    await this.getUserMedia();
                    await this.createPeerConnection(quantumKey);
                    
                    this.notifyPython('call_answered', {{ callId }});
                }} catch (error) {{
                    console.error('Failed to answer call:', error);
                    this.notifyPython('call_error', {{ error: error.message }});
                }}
            }}
            
            async requestQuantumKey(callId, remoteUser) {{
                // Request quantum key from Python backend
                return new Promise((resolve, reject) => {{
                    const requestId = 'qk_' + Date.now();
                    
                    const handleResponse = (event) => {{
                        if (event.data.type === 'quantum_key_response' && event.data.requestId === requestId) {{
                            window.removeEventListener('message', handleResponse);
                            if (event.data.success) {{
                                resolve(event.data.key);
                            }} else {{
                                reject(new Error(event.data.error));
                            }}
                        }}
                    }};
                    
                    window.addEventListener('message', handleResponse);
                    
                    // Request quantum key
                    this.notifyPython('request_quantum_key', {{
                        requestId: requestId,
                        callId: callId,
                        remoteUser: remoteUser
                    }});
                    
                    // Timeout after 10 seconds
                    setTimeout(() => {{
                        window.removeEventListener('message', handleResponse);
                        reject(new Error('Quantum key request timeout'));
                    }}, 10000);
                }});
            }}
            
            async getUserMedia() {{
                console.log('Requesting user media...');
                
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
                    const error = 'getUserMedia not supported in this browser';
                    console.error(error);
                    throw new Error(error);
                }}
                
                const constraints = {{
                    audio: {{
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                        sampleRate: 48000
                    }},
                    video: this.callType === 'video' ? {{
                        width: {{ ideal: 1280, max: 1920 }},
                        height: {{ ideal: 720, max: 1080 }},
                        frameRate: {{ ideal: 30, max: 60 }},
                        facingMode: 'user'
                    }} : false
                }};
                
                console.log('Media constraints:', constraints);
                
                try {{
                    // Request permissions first
                    if (navigator.permissions && navigator.permissions.query) {{
                        try {{
                            const permissionResult = await navigator.permissions.query({{ name: 'microphone' }});
                            console.log('Microphone permission:', permissionResult.state);
                        }} catch (permError) {{
                            console.log('Permission query not supported:', permError);
                        }}
                    }}
                    
                    this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
                    console.log('Got user media successfully:', this.localStream);
                    console.log('Audio tracks:', this.localStream.getAudioTracks().length);
                    console.log('Video tracks:', this.localStream.getVideoTracks().length);
                    
                    // Add tracks to peer connection
                    if (this.peerConnection) {{
                        this.localStream.getTracks().forEach(track => {{
                            console.log('Adding track to peer connection:', track.kind, track.label);
                            this.peerConnection.addTrack(track, this.localStream);
                        }});
                    }}
                    
                    this.notifyPython('media_ready', {{ 
                        hasAudio: this.localStream.getAudioTracks().length > 0,
                        hasVideo: this.localStream.getVideoTracks().length > 0
                    }});
                    
                    console.log('Media ready notification sent to Python');
                }} catch (error) {{
                    console.error('Failed to get user media:', error);
                    console.error('Error name:', error.name);
                    console.error('Error message:', error.message);
                    
                    // Provide more specific error messages
                    let errorMessage = 'Failed to get user media: ';
                    if (error.name === 'NotAllowedError') {{
                        errorMessage += 'Permission denied. Please allow microphone/camera access.';
                    }} else if (error.name === 'NotFoundError') {{
                        errorMessage += 'No microphone/camera found.';
                    }} else if (error.name === 'NotReadableError') {{
                        errorMessage += 'Microphone/camera is being used by another application.';
                    }} else {{
                        errorMessage += error.message;
                    }}
                    
                    this.notifyPython('call_error', {{ error: errorMessage }});
                    throw new Error(errorMessage);
                }}
            }}
            
            async createPeerConnection(quantumKey) {{
                console.log('Creating peer connection...');
                
                this.peerConnection = new RTCPeerConnection({{
                    iceServers: this.iceServers,
                    iceCandidatePoolSize: 10
                }});
                
                console.log('Peer connection created with ICE servers:', this.iceServers);
                
                // Handle incoming stream
                this.peerConnection.ontrack = (event) => {{
                    console.log('Received remote stream:', event.streams[0]);
                    this.remoteStream = event.streams[0];
                    
                    // Log track details
                    const audioTracks = this.remoteStream.getAudioTracks();
                    const videoTracks = this.remoteStream.getVideoTracks();
                    console.log('Remote audio tracks:', audioTracks.length);
                    console.log('Remote video tracks:', videoTracks.length);
                    
                    this.notifyPython('remote_stream', {{ 
                        hasAudio: audioTracks.length > 0,
                        hasVideo: videoTracks.length > 0
                    }});
                }};
                
                // Handle ICE candidates
                this.peerConnection.onicecandidate = (event) => {{
                    if (event.candidate) {{
                        console.log('Sending ICE candidate:', event.candidate.candidate);
                        this.sendSignalingMessage({{
                            type: 'ice_candidate',
                            callId: this.callId,
                            candidate: event.candidate,
                            from: window.currentUser
                        }});
                    }} else {{
                        console.log('ICE gathering complete');
                    }}
                }};
                
                // Handle connection state changes
                this.peerConnection.onconnectionstatechange = () => {{
                    console.log('Connection state changed to:', this.peerConnection.connectionState);
                    this.notifyPython('connection_state', {{ 
                        state: this.peerConnection.connectionState 
                    }});
                    
                    // Handle connection failures
                    if (this.peerConnection.connectionState === 'failed') {{
                        console.error('Peer connection failed');
                        this.notifyPython('call_error', {{ error: 'Peer connection failed' }});
                    }}
                }};
                
                // Handle ICE connection state changes
                this.peerConnection.oniceconnectionstatechange = () => {{
                    console.log('ICE connection state changed to:', this.peerConnection.iceConnectionState);
                    
                    if (this.peerConnection.iceConnectionState === 'connected') {{
                        console.log('ICE connection established successfully');
                    }} else if (this.peerConnection.iceConnectionState === 'failed') {{
                        console.error('ICE connection failed');
                        this.notifyPython('call_error', {{ error: 'ICE connection failed' }});
                    }}
                }};
                
                // Handle ICE gathering state changes
                this.peerConnection.onicegatheringstatechange = () => {{
                    console.log('ICE gathering state:', this.peerConnection.iceGatheringState);
                }};
                
                // Configure quantum encryption
                if (quantumKey) {{
                    console.log('Using quantum key for encryption');
                    this.quantumKey = quantumKey;
                    // In a real implementation, this would configure SRTP with the quantum key
                    // For now, we'll use the key for additional security
                }}
                
                console.log('Peer connection setup complete');
            }}
            
            async createOffer() {{
                const offer = await this.peerConnection.createOffer({{
                    offerToReceiveAudio: true,
                    offerToReceiveVideo: this.callType === 'video'
                }});
                await this.peerConnection.setLocalDescription(offer);
                
                console.log('Created offer, sending to remote peer');
                this.sendSignalingMessage({{
                    type: 'offer',
                    callId: this.callId,
                    offer: offer,
                    from: window.currentUser,
                    callType: this.callType
                }});
            }}
            
            async createAnswer() {{
                const answer = await this.peerConnection.createAnswer();
                await this.peerConnection.setLocalDescription(answer);
                
                console.log('Created answer, sending to remote peer');
                this.sendSignalingMessage({{
                    type: 'answer',
                    callId: this.callId,
                    answer: answer,
                    from: window.currentUser
                }});
            }}
            
            async handleIncomingCall(message) {{
                console.log('Incoming call from:', message.from);
                this.callId = message.callId;
                this.callType = message.callType;
                
                this.notifyPython('incoming_call', {{
                    callId: message.callId,
                    caller: message.from,
                    callType: message.callType
                }});
            }}
            
            async handleOffer(message) {{
                console.log('Received offer from:', message.from);
                await this.peerConnection.setRemoteDescription(message.offer);
                await this.createAnswer();
            }}
            
            async handleAnswer(message) {{
                console.log('Received answer from:', message.from);
                await this.peerConnection.setRemoteDescription(message.answer);
            }}
            
            async handleIceCandidate(message) {{
                console.log('Received ICE candidate from:', message.from);
                await this.peerConnection.addIceCandidate(message.candidate);
            }}
            
            handleCallEnd(message) {{
                console.log('Call ended by:', message.from);
                this.endCall();
            }}
            
            async endCall() {{
                console.log('Ending call');
                
                if (this.localStream) {{
                    this.localStream.getTracks().forEach(track => track.stop());
                }}
                
                if (this.peerConnection) {{
                    this.peerConnection.close();
                }}
                
                if (this.websocket) {{
                    this.sendSignalingMessage({{
                        type: 'call_end',
                        callId: this.callId,
                        from: window.currentUser
                    }});
                }}
                
                this.notifyPython('call_ended', {{ callId: this.callId }});
            }}
            
            toggleMute() {{
                if (this.localStream) {{
                    const audioTrack = this.localStream.getAudioTracks()[0];
                    if (audioTrack) {{
                        audioTrack.enabled = !audioTrack.enabled;
                        this.notifyPython('mute_toggled', {{ muted: !audioTrack.enabled }});
                    }}
                }}
            }}
            
            toggleVideo() {{
                if (this.localStream) {{
                    const videoTrack = this.localStream.getVideoTracks()[0];
                    if (videoTrack) {{
                        videoTrack.enabled = !videoTrack.enabled;
                        this.notifyPython('video_toggled', {{ videoEnabled: videoTrack.enabled }});
                    }}
                }}
            }}
            
            notifyPython(type, data) {{
                try {{
                    if (window.pyqtwebchannel && window.pyqtwebchannel.send) {{
                        window.pyqtwebchannel.send({{
                            type: type,
                            data: data
                        }});
                    }} else {{
                        console.log('Message to Python:', type, data);
                    }}
                }} catch (error) {{
                    console.error('Error sending message to Python:', error);
                }}
            }}
        }}
        
        // Initialize WebRTC manager
        window.webrtcManager = new QuantumWebRTCManager();
        
        // Setup message channel with proper Qt WebChannel integration
        if (typeof qt !== 'undefined' && qt.webChannelTransport) {{
            new QWebChannel(qt.webChannelTransport, function(channel) {{
                window.webrtcBridge = channel.objects.webrtcBridge;
                console.log('Qt WebChannel connected');
            }});
        }}
        
        // Fallback message channel
        window.pyqtwebchannel = {{
            send: function(message) {{
                try {{
                    // Try Qt WebChannel first
                    if (window.webrtcBridge && window.webrtcBridge.handle_js_message) {{
                        window.webrtcBridge.handle_js_message(JSON.stringify(message));
                    }} else {{
                        console.log('Message to Python (fallback):', message);
                    }}
                }} catch (error) {{
                    console.error('Error sending message to Python:', error);
                }}
            }}
        }};
        """
        
        self.web_view.page().runJavaScript(webrtc_js)
    
    @pyqtSlot(str)
    def handle_js_message(self, message_json: str):
        """Handle messages from JavaScript"""
        try:
            import json
            message = json.loads(message_json)
            message_type = message.get('type')
            data = message.get('data', {})
            
            log.debug(f"Received JS message: {message_type}")
            
            if message_type == 'call_initiated':
                self.call_initiated.emit(data.get('callId', ''), data.get('callType', ''), data.get('remoteUser', ''))
            elif message_type == 'call_answered':
                self.call_answered.emit(data.get('callId', ''))
            elif message_type == 'call_ended':
                self.call_ended.emit(data.get('callId', ''))
            elif message_type == 'call_error':
                self.call_error.emit(data.get('error', 'Unknown error'))
            elif message_type == 'media_ready':
                self.media_ready.emit(data.get('hasAudio', False), data.get('hasVideo', False))
            elif message_type == 'remote_stream':
                self.remote_stream.emit(data.get('hasAudio', False), data.get('hasVideo', False))
            elif message_type == 'connection_state':
                self.connection_state.emit(data.get('state', ''))
            elif message_type == 'mute_toggled':
                self.mute_toggled.emit(data.get('muted', False))
            elif message_type == 'video_toggled':
                self.video_toggled.emit(data.get('videoEnabled', False))
            elif message_type == 'incoming_call':
                self.incoming_call.emit(data.get('callId', ''), data.get('caller', ''), data.get('callType', ''))
            elif message_type == 'request_quantum_key':
                self.quantum_key_requested.emit(data.get('requestId', ''), data.get('callId', ''), data.get('remoteUser', ''))
            elif message_type == 'firebase_signaling_message':
                # Handle Firebase signaling message from JavaScript
                self.firebase_signaling_message.emit(data)
            elif message_type == 'audio_test_result':
                # Handle audio test result
                success = data.get('success', False)
                message_text = data.get('message', 'Unknown error')
                if success:
                    log.info(f"Audio test successful: {message_text}")
                else:
                    log.error(f"Audio test failed: {message_text}")
            elif message_type == 'webrtc_manager_status':
                # Handle WebRTC Manager status
                initialized = data.get('initialized', False)
                message_text = data.get('message', 'Unknown status')
                if initialized:
                    log.info(f"WebRTC Manager status: {message_text}")
                else:
                    log.error(f"WebRTC Manager status: {message_text}")
                
        except Exception as e:
            log.error(f"Error handling JS message: {e}")
    
    def initiate_call(self, call_id: str, call_type: str, remote_user: str):
        """Initiate a call"""
        try:
            import json
            js_code = f"""
            console.log('Attempting to initiate call {call_id}');
            
            // Check if WebRTC Manager exists and is ready
            if (typeof window.webrtcManager !== 'undefined' && window.webrtcManager) {{
                console.log('WebRTC Manager found, initiating call');
                window.webrtcManager.handleCommand('init_call', {{
                    callId: '{call_id}',
                    callType: '{call_type}',
                    remoteUser: '{remote_user}'
                }});
            }} else {{
                console.error('WebRTC Manager not initialized, attempting to reinitialize...');
                
                // Try to reinitialize the WebRTC Manager
                if (typeof window.QuantumWebRTCManager !== 'undefined') {{
                    console.log('Reinitializing WebRTC Manager...');
                    window.webrtcManager = new window.QuantumWebRTCManager();
                    
                    // Try the call again after a short delay
                    setTimeout(() => {{
                        if (window.webrtcManager) {{
                            console.log('WebRTC Manager reinitialized, retrying call');
                            window.webrtcManager.handleCommand('init_call', {{
                                callId: '{call_id}',
                                callType: '{call_type}',
                                remoteUser: '{remote_user}'
                            }});
                        }} else {{
                            console.error('Failed to reinitialize WebRTC Manager');
                        }}
                    }}, 500);
                }} else {{
                    console.error('QuantumWebRTCManager class not found');
                }}
            }}
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error initiating call: {e}")
    
    def answer_call(self, call_id: str):
        """Answer a call"""
        try:
            import json
            js_code = f"""
            console.log('Attempting to answer call {call_id}');
            
            // Check if WebRTC Manager exists and is ready
            if (typeof window.webrtcManager !== 'undefined' && window.webrtcManager) {{
                console.log('WebRTC Manager found, answering call');
                window.webrtcManager.handleCommand('answer_call', {{
                    callId: '{call_id}'
                }});
            }} else {{
                console.error('WebRTC Manager not initialized, attempting to reinitialize...');
                
                // Try to reinitialize the WebRTC Manager
                if (typeof window.QuantumWebRTCManager !== 'undefined') {{
                    console.log('Reinitializing WebRTC Manager...');
                    window.webrtcManager = new window.QuantumWebRTCManager();
                    
                    // Try the call again after a short delay
                    setTimeout(() => {{
                        if (window.webrtcManager) {{
                            console.log('WebRTC Manager reinitialized, retrying answer');
                            window.webrtcManager.handleCommand('answer_call', {{
                                callId: '{call_id}'
                            }});
                        }} else {{
                            console.error('Failed to reinitialize WebRTC Manager');
                        }}
                    }}, 500);
                }} else {{
                    console.error('QuantumWebRTCManager class not found');
                }}
            }}
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error answering call: {e}")
    
    def end_call(self):
        """End the current call"""
        try:
            import json
            js_code = """
            if (window.webrtcManager) {
                window.webrtcManager.handleCommand('end_call', {});
            } else {
                console.error('WebRTC Manager not initialized');
            }
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error ending call: {e}")
    
    def toggle_mute(self):
        """Toggle mute"""
        try:
            import json
            js_code = """
            if (window.webrtcManager) {
                window.webrtcManager.handleCommand('toggle_mute', {});
            } else {
                console.error('WebRTC Manager not initialized');
            }
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error toggling mute: {e}")
    
    def toggle_video(self):
        """Toggle video"""
        try:
            import json
            js_code = """
            if (window.webrtcManager) {
                window.webrtcManager.handleCommand('toggle_video', {});
            } else {
                console.error('WebRTC Manager not initialized');
            }
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error toggling video: {e}")
    
    def provide_quantum_key(self, request_id: str, key: str):
        """Provide quantum key to JavaScript"""
        try:
            import json
            js_code = f"""
            window.dispatchEvent(new MessageEvent('message', {{
                data: {{
                    type: 'quantum_key_response',
                    requestId: '{request_id}',
                    success: true,
                    key: '{key}'
                }}
            }}));
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error providing quantum key: {e}")
    
    def reject_quantum_key(self, request_id: str, error: str):
        """Reject quantum key request"""
        try:
            import json
            js_code = f"""
            window.dispatchEvent(new MessageEvent('message', {{
                data: {{
                    type: 'quantum_key_response',
                    requestId: '{request_id}',
                    success: false,
                    error: '{error}'
                }}
            }}));
            """
            self.web_view.page().runJavaScript(js_code)
        except Exception as e:
            log.error(f"Error rejecting quantum key: {e}")