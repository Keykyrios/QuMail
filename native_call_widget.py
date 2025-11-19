# native_call_widget.py
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread, pyqtSlot, Qt
from PyQt6.QtMultimedia import QMediaDevices, QAudioInput, QAudioOutput, QCamera, QMediaCaptureSession, QAudioSink, QAudioSource
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QIODevice, QByteArray
import socket
import json
import asyncio
import threading

log = logging.getLogger(__name__)

class AudioStreamer(QObject):
    """Handle audio streaming for voice calls"""
    
    def __init__(self):
        super().__init__()
        self.audio_input = None
        self.audio_output = None
        self.audio_sink = None
        self.audio_source = None
        self.is_streaming = False
        self.remote_socket = None
        
    def start_audio_stream(self, remote_host: str, remote_port: int):
        """Start audio streaming"""
        try:
            # Setup audio input (microphone)
            audio_device = QMediaDevices.defaultAudioInput()
            if not audio_device.isNull():
                self.audio_input = QAudioInput(audio_device)
                
            # Setup audio output (speakers)
            output_device = QMediaDevices.defaultAudioOutput()
            if not output_device.isNull():
                self.audio_output = QAudioOutput(output_device)
                
            # Create socket for audio streaming
            self.remote_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            self.is_streaming = True
            log.info("Audio streaming started")
            return True
            
        except Exception as e:
            log.error(f"Failed to start audio stream: {e}")
            return False
    
    def stop_audio_stream(self):
        """Stop audio streaming"""
        self.is_streaming = False
        if self.remote_socket:
            self.remote_socket.close()
        log.info("Audio streaming stopped")

class VideoStreamer(QObject):
    """Handle video streaming for video calls"""
    
    def __init__(self):
        super().__init__()
        self.camera = None
        self.capture_session = None
        self.is_streaming = False
        
    def start_video_stream(self, video_widget: QVideoWidget):
        """Start video streaming"""
        try:
            # Get default camera
            cameras = QMediaDevices.videoInputs()
            if cameras:
                self.camera = QCamera(cameras[0])
                self.capture_session = QMediaCaptureSession()
                self.capture_session.setCamera(self.camera)
                self.capture_session.setVideoOutput(video_widget)
                
                self.camera.start()
                self.is_streaming = True
                log.info("Video streaming started")
                return True
            else:
                log.error("No cameras found")
                return False
                
        except Exception as e:
            log.error(f"Failed to start video stream: {e}")
            return False
    
    def stop_video_stream(self):
        """Stop video streaming"""
        if self.camera:
            self.camera.stop()
        self.is_streaming = False
        log.info("Video streaming stopped")

class VideoPlaceholder(QWidget):
    """Avatar placeholder for when video is disabled"""
    
    def __init__(self, user_name="User", is_local=False, parent=None):
        super().__init__(parent)
        self.user_name = user_name
        self.is_local = is_local
        self.setMinimumSize(200, 150)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Avatar circle
        self.avatar_label = QLabel()
        size = 60 if is_local else 80
        self.avatar_label.setFixedSize(size, size)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Generate initials
        initials = ''.join([word[0].upper() for word in user_name.split()[:2]])
        if not initials:
            initials = "U"
        
        # Color based on user
        colors = ["#667eea", "#f093fb", "#4facfe", "#43e97b", "#fa709a"]
        color = colors[hash(user_name) % len(colors)]
        
        self.avatar_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border: 3px solid #ffffff;
                border-radius: {size//2}px;
                color: white;
                font-size: {size//3}px;
                font-weight: bold;
            }}
        """)
        self.avatar_label.setText(initials)
        
        # Name label
        self.name_label = QLabel("You" if is_local else user_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("""
            QLabel {
                color: #e2e8f0;
                font-size: 14px;
                font-weight: 500;
                background-color: transparent;
                margin-top: 8px;
            }
        """)
        
        layout.addWidget(self.avatar_label)
        layout.addWidget(self.name_label)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Background styling
        self.setStyleSheet("""
            VideoPlaceholder {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #4a5568, stop:1 #2d3748);
                border: 2px solid #4a5568;
                border-radius: 12px;
            }
        """)

class NativeCallWidget(QWidget):
    """Native Qt multimedia call widget"""
    
    # Signals
    call_connected = pyqtSignal()
    call_disconnected = pyqtSignal()
    call_error = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.call_id = ""
        self.call_type = "voice"
        self.remote_user = ""
        self.is_connected = False
        self.video_enabled = True
        
        # Multimedia components
        self.audio_streamer = AudioStreamer()
        self.video_streamer = VideoStreamer()
        
        # UI components
        self.local_video = QVideoWidget()
        self.remote_video = QVideoWidget()
        self.local_placeholder = None
        self.remote_placeholder = None
        
        self.setup_ui()
        self.setup_multimedia()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main video area
        self.video_container = QWidget()
        self.video_layout = QHBoxLayout(self.video_container)
        self.video_layout.setContentsMargins(10, 10, 10, 10)
        self.video_layout.setSpacing(10)
        
        # Local video area (smaller, top-left overlay style)
        self.local_container = QWidget()
        self.local_container.setFixedSize(200, 150)
        self.local_layout = QVBoxLayout(self.local_container)
        self.local_layout.setContentsMargins(0, 0, 0, 0)
        
        # Remote video area (main area)
        self.remote_container = QWidget()
        self.remote_container.setMinimumSize(400, 300)
        self.remote_layout = QVBoxLayout(self.remote_container)
        self.remote_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add to video layout
        self.video_layout.addWidget(self.local_container)
        self.video_layout.addWidget(self.remote_container, 1)
        
        layout.addWidget(self.video_container, 1)
        
        # Controls (minimal, modern style)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(20)
        
        self.mute_btn = QPushButton()
        self.mute_btn.setFixedSize(50, 50)
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a5568;
                border: none;
                border-radius: 25px;
                color: white;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #5a6578;
            }
            QPushButton:checked {
                background-color: #e53e3e;
            }
        """)
        self.mute_btn.setText("🎤")
        
        self.video_btn = QPushButton()
        self.video_btn.setFixedSize(50, 50)
        self.video_btn.setCheckable(True)
        self.video_btn.clicked.connect(self.toggle_video)
        self.video_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a5568;
                border: none;
                border-radius: 25px;
                color: white;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #5a6578;
            }
            QPushButton:checked {
                background-color: #e53e3e;
            }
        """)
        self.video_btn.setText("📹")
        
        self.end_btn = QPushButton()
        self.end_btn.setFixedSize(60, 60)
        self.end_btn.clicked.connect(self.end_call)
        self.end_btn.setStyleSheet("""
            QPushButton {
                background-color: #e53e3e;
                border: none;
                border-radius: 30px;
                color: white;
                font-size: 24px;
            }
            QPushButton:hover {
                background-color: #c53030;
            }
        """)
        self.end_btn.setText("📞")
        
        controls_layout.addStretch()
        controls_layout.addWidget(self.mute_btn)
        controls_layout.addWidget(self.video_btn)
        controls_layout.addWidget(self.end_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        self.setLayout(layout)
        
        # Set dark theme
        self.setStyleSheet("""
            NativeCallWidget {
                background-color: #1a202c;
            }
        """)
        
    def setup_multimedia(self):
        """Setup multimedia devices"""
        try:
            # Check available devices
            audio_inputs = QMediaDevices.audioInputs()
            audio_outputs = QMediaDevices.audioOutputs()
            video_inputs = QMediaDevices.videoInputs()
            
            log.info(f"Found {len(audio_inputs)} audio input devices")
            log.info(f"Found {len(audio_outputs)} audio output devices")
            log.info(f"Found {len(video_inputs)} video input devices")
            
            if not audio_inputs:
                self.call_error.emit("No microphone found")
                return False
                
            if not audio_outputs:
                self.call_error.emit("No speakers found")
                return False
                
            return True
            
        except Exception as e:
            log.error(f"Failed to setup multimedia: {e}")
            self.call_error.emit(f"Multimedia setup failed: {e}")
            return False
    
    def start_call(self, call_id: str, call_type: str, remote_user: str):
        """Start a call"""
        self.call_id = call_id
        self.call_type = call_type
        self.remote_user = remote_user
        
        try:
            # Start audio streaming
            if not self.audio_streamer.start_audio_stream("127.0.0.1", 8082):
                self.call_error.emit("Failed to start audio")
                return False
            
            # Setup video or placeholders
            if call_type == "video":
                # Start video streaming
                if self.video_streamer.start_video_stream(self.local_video):
                    self.show_video_widgets()
                else:
                    # Fallback to placeholders if video fails
                    self.show_placeholder_widgets()
            else:
                # Voice call - show placeholders
                self.show_placeholder_widgets()
            
            self.is_connected = True
            self.call_connected.emit()
            
            log.info(f"Call started: {call_id} ({call_type})")
            return True
            
        except Exception as e:
            log.error(f"Failed to start call: {e}")
            self.call_error.emit(f"Failed to start call: {e}")
            return False
    
    def show_video_widgets(self):
        """Show actual video widgets"""
        # Clear placeholders
        self.clear_containers()
        
        # Add video widgets
        self.local_layout.addWidget(self.local_video)
        self.remote_layout.addWidget(self.remote_video)
        
        self.local_video.show()
        self.remote_video.show()
    
    def show_placeholder_widgets(self):
        """Show avatar placeholders"""
        # Clear video widgets
        self.clear_containers()
        
        # Create placeholders
        self.local_placeholder = VideoPlaceholder("You", is_local=True)
        self.remote_placeholder = VideoPlaceholder(self.remote_user, is_local=False)
        
        # Add placeholders
        self.local_layout.addWidget(self.local_placeholder)
        self.remote_layout.addWidget(self.remote_placeholder)
    
    def clear_containers(self):
        """Clear all widgets from containers"""
        # Clear local container
        while self.local_layout.count():
            child = self.local_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
        
        # Clear remote container
        while self.remote_layout.count():
            child = self.remote_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
    
    def end_call(self):
        """End the current call"""
        try:
            self.audio_streamer.stop_audio_stream()
            self.video_streamer.stop_video_stream()
            
            self.is_connected = False
            self.call_disconnected.emit()
            
            log.info(f"Call ended: {self.call_id}")
            
        except Exception as e:
            log.error(f"Error ending call: {e}")
    
    def toggle_mute(self):
        """Toggle microphone mute"""
        if self.mute_btn.isChecked():
            self.mute_btn.setText("🔇")
        else:
            self.mute_btn.setText("🎤")
    
    def toggle_video(self):
        """Toggle video on/off"""
        if self.call_type != "video":
            return  # Can't toggle video in voice call
        
        self.video_enabled = not self.video_btn.isChecked()
        
        if self.video_enabled:
            # Show video
            self.show_video_widgets()
            self.video_btn.setText("📹")
        else:
            # Show placeholders
            self.show_placeholder_widgets()
            self.video_btn.setText("🚫")
    
    def get_local_video_widget(self):
        """Get the local video widget for external use"""
        return self.local_video
    
    def get_remote_video_widget(self):
        """Get the remote video widget for external use"""
        return self.remote_video