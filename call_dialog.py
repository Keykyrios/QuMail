# call_dialog.py
import asyncio
import logging
import time
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QWidget, QFrame, QSpacerItem, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
import qtawesome as qta
from webrtc_service import WebRTCService, CallType, CallState, CallSession
try:
    from native_webrtc_service import CallSession as NativeCallSession
except ImportError:
    NativeCallSession = CallSession

log = logging.getLogger(__name__)

class VideoPlaceholder(QWidget):
    """Avatar placeholder for when video is disabled"""
    
    def __init__(self, user_name="User", parent=None):
        super().__init__(parent)
        self.user_name = user_name
        self.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Avatar circle
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(120, 120)
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
                border: 4px solid #ffffff;
                border-radius: 60px;
                color: white;
                font-size: 48px;
                font-weight: bold;
            }}
        """)
        self.avatar_label.setText(initials)
        
        # Name label
        self.name_label = QLabel(user_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("""
            QLabel {
                color: #e2e8f0;
                font-size: 18px;
                font-weight: 500;
                background-color: transparent;
                margin-top: 15px;
            }
        """)
        
        layout.addWidget(self.avatar_label)
        layout.addWidget(self.name_label)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Background styling
        self.setStyleSheet("""
            VideoPlaceholder {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #4a5568, stop:1 #2d3748);
                border: 2px solid #4a5568;
                border-radius: 12px;
            }
        """)

class VideoWidget(QWidget):
    """Custom widget for displaying video streams"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: 2px solid #555;
                border-radius: 8px;
            }
        """)
        self.video_label = QLabel("No Video", self)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 14px;
                background-color: transparent;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.video_label)
        layout.setContentsMargins(0, 0, 0, 0)
    
    def set_video_stream(self, has_video: bool):
        """Update video display based on stream availability"""
        if has_video:
            self.video_label.setText("Video Stream Active")
            self.video_label.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-size: 14px;
                    background-color: transparent;
                }
            """)
        else:
            self.video_label.setText("No Video")
            self.video_label.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-size: 14px;
                    background-color: transparent;
                }
            """)

class CallDialog(QDialog):
    """Main call dialog for voice and video calls"""
    
    call_ended = pyqtSignal(str)  # call_id
    
    def __init__(self, call_widget, call_session: CallSession, parent=None, use_native=False):
        super().__init__(parent)
        self.call_widget = call_widget  # Can be WebRTCWidget or NativeCallWidget
        self.call_session = call_session
        self.use_native = use_native
        self.start_time = None
        self.call_timer = QTimer()
        self.call_timer.timeout.connect(self.update_call_duration)
        
        self.setWindowTitle(f"QuMail Call - {call_session.remote_user}")
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: #e2e8f0; border: 1px solid #334155; }
            QLabel { background: transparent; }
        """)
        
        self.init_ui()
        self.setup_webrtc_connections()
        
        # Start call timer if connected
        if call_session.state == CallState.CONNECTED:
            self.start_call_timer()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header with caller info
        header_layout = QHBoxLayout()
        
        # Caller avatar
        avatar_label = QLabel()
        avatar_label.setFixedSize(50, 50)
        
        # Generate initials for avatar
        initials = ''.join([word[0].upper() for word in self.call_session.remote_user.split()[:2]])
        if not initials:
            initials = "U"
        
        # Color based on user
        colors = ["#667eea", "#f093fb", "#4facfe", "#43e97b", "#fa709a"]
        color = colors[hash(self.call_session.remote_user) % len(colors)]
        
        avatar_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border: 2px solid #ffffff;
                border-radius: 25px;
                color: white;
                font-size: 18px;
                font-weight: bold;
            }}
        """)
        avatar_label.setText(initials)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Caller info
        caller_info_layout = QVBoxLayout()
        self.caller_name_label = QLabel(self.call_session.remote_user)
        self.caller_name_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.caller_name_label.setStyleSheet("color: #e2e8f0;")
        
        self.call_status_label = QLabel(self.get_status_text())
        self.call_status_label.setStyleSheet("color: #a0aec0; font-size: 12px;")
        
        caller_info_layout.addWidget(self.caller_name_label)
        caller_info_layout.addWidget(self.call_status_label)
        
        header_layout.addWidget(avatar_label)
        header_layout.addLayout(caller_info_layout)
        header_layout.addStretch()
        
        # Call duration
        self.duration_label = QLabel("00:00")
        self.duration_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.duration_label.setStyleSheet("color: #22c55e; background-color: #1f2937; padding: 4px 8px; border-radius: 6px;")
        header_layout.addWidget(self.duration_label)
        
        layout.addLayout(header_layout)
        
        # Distinct UI: video shows the widget; voice shows a clean avatar view
        if self.call_session.call_type == CallType.VIDEO:
            layout.addWidget(self.call_widget)
        else:
            voice_placeholder = VideoPlaceholder(self.call_session.remote_user)
            layout.addWidget(voice_placeholder)

        
        layout.addStretch()
        
        # Control buttons
        self.setup_control_buttons(layout)
    
    def setup_control_buttons(self, layout):
        """Setup call control buttons"""
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)
        
        # Mute button
        self.mute_button = QPushButton()
        self.mute_button.setIcon(qta.icon('fa5s.microphone', color='#dcdcdc'))
        self.mute_button.setFixedSize(50, 50)
        self.mute_button.setStyleSheet("""
            QPushButton { background-color: #1f2937; border: 1px solid #334155; border-radius: 25px; }
            QPushButton:hover { background-color: #111827; }
        """)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.mute_button.setToolTip("Mute/Unmute")
        
        # Video toggle button (only visible for video calls)
        self.video_button = QPushButton()
        self.video_button.setIcon(qta.icon('fa5s.video', color='#dcdcdc'))
        self.video_button.setFixedSize(50, 50)
        self.video_button.setStyleSheet("""
            QPushButton { background-color: #1f2937; border: 1px solid #334155; border-radius: 25px; }
            QPushButton:hover { background-color: #111827; }
        """)
        self.video_button.clicked.connect(self.toggle_video)
        self.video_button.setToolTip("Turn Video On/Off")
        self.video_button.setVisible(self.call_session.call_type == CallType.VIDEO)
        
        # End call button
        self.end_call_button = QPushButton()
        self.end_call_button.setIcon(qta.icon('fa5s.phone-slash', color='#dcdcdc'))
        self.end_call_button.setFixedSize(60, 60)
        self.end_call_button.setStyleSheet("""
            QPushButton { background-color: #ef4444; border: none; border-radius: 30px; }
            QPushButton:hover { background-color: #dc2626; }
        """)
        self.end_call_button.clicked.connect(self.end_call)
        self.end_call_button.setToolTip("End Call")
        
        # Add buttons to layout
        controls_layout.addStretch()
        controls_layout.addWidget(self.mute_button)
        controls_layout.addWidget(self.video_button)
        controls_layout.addWidget(self.end_call_button)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
    
    def setup_webrtc_connections(self):
        """Setup call widget connections"""
        # Connect to call widget signals
        if self.use_native:
            # Native widget connections
            if hasattr(self.call_widget, 'call_disconnected'):
                self.call_widget.call_disconnected.connect(self.on_call_ended_native)
            if hasattr(self.call_widget, 'call_error'):
                self.call_widget.call_error.connect(self.on_error_occurred)
        else:
            # WebRTC widget connections
            if hasattr(self.call_widget, 'call_ended'):
                self.call_widget.call_ended.connect(self.on_call_ended)
            if hasattr(self.call_widget, 'call_error'):
                self.call_widget.call_error.connect(self.on_error_occurred)
            if hasattr(self.call_widget, 'connection_state'):
                self.call_widget.connection_state.connect(self.on_connection_state)
    
    @pyqtSlot(str)
    def on_call_ended(self, call_id: str):
        """Handle call ended"""
        if call_id == self.call_session.call_id:
            self.end_call_timer()
            self.accept()
    
    @pyqtSlot(str)
    def on_connection_state(self, state: str):
        """Handle connection state changes"""
        if state == "connected":
            self.start_call_timer()
        elif state == "disconnected":
            self.end_call_timer()
    
    @pyqtSlot(str)
    def on_error_occurred(self, error_message: str):
        """Handle WebRTC errors"""
        QMessageBox.critical(self, "Call Error", f"An error occurred during the call:\n{error_message}")
        self.end_call()
    
    def get_status_text(self) -> str:
        """Get status text based on call state"""
        status_map = {
            CallState.INITIATING: "Initiating call...",
            CallState.RINGING: "Ringing...",
            CallState.CONNECTING: "Connecting...",
            CallState.CONNECTED: "Connected",
            CallState.ENDED: "Call ended",
            CallState.FAILED: "Call failed"
        }
        return status_map.get(self.call_session.state, "Unknown")
    
    def start_call_timer(self):
        """Start the call duration timer"""
        if not self.start_time:
            self.start_time = time.time()
            self.call_timer.start(1000)  # Update every second
    
    def end_call_timer(self):
        """Stop the call duration timer"""
        self.call_timer.stop()
    
    def update_call_duration(self):
        """Update call duration display"""
        if self.start_time:
            duration = int(time.time() - self.start_time)
            minutes = duration // 60
            seconds = duration % 60
            self.duration_label.setText(f"{minutes:02d}:{seconds:02d}")
    
    def toggle_mute(self):
        """Toggle mute state"""
        if hasattr(self.call_widget, 'toggle_mute'):
            self.call_widget.toggle_mute()
    
    def toggle_video(self):
        """Toggle video state"""
        if hasattr(self.call_widget, 'toggle_video'):
            self.call_widget.toggle_video()
    
    def end_call(self):
        """End the call"""
        if hasattr(self.call_widget, 'end_call'):
            self.call_widget.end_call()
        self.call_ended.emit(self.call_session.call_id)
        self.accept()
    
    @pyqtSlot()
    def on_call_ended_native(self):
        """Handle call ended from native widget"""
        self.end_call_timer()
        self.call_ended.emit(self.call_session.call_id)
        self.accept()
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        self.end_call()
        event.accept()

class IncomingCallDialog(QDialog):
    """Dialog for incoming calls"""
    
    call_accepted = pyqtSignal(str)  # call_id
    call_rejected = pyqtSignal(str)  # call_id
    
    def __init__(self, call_id: str, caller: str, call_type: str, webrtc_widget, parent=None):
        super().__init__(parent)
        self.call_id = call_id
        self.caller = caller
        self.call_type = call_type
        self.webrtc_widget = webrtc_widget
        self.call_handled = False
        
        self.setWindowTitle("Incoming Call")
        self.setModal(True)
        self.setFixedSize(400, 200)
        self.setStyleSheet("""
            QDialog {
                background-color: #3c3f41;
                color: #dcdcdc;
            }
        """)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Caller info
        caller_layout = QHBoxLayout()
        
        # Caller avatar
        avatar_label = QLabel()
        avatar_label.setFixedSize(50, 50)
        avatar_label.setStyleSheet("""
            QLabel {
                background-color: #555;
                border-radius: 25px;
                border: 2px solid #777;
            }
        """)
        avatar_label.setText("👤")
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_label.setFont(QFont("Arial", 20))
        
        # Caller details
        caller_info_layout = QVBoxLayout()
        caller_name_label = QLabel(self.caller)
        caller_name_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        
        call_type_label = QLabel(f"Incoming {self.call_type.title()} Call")
        call_type_label.setStyleSheet("color: #888; font-size: 12px;")
        
        caller_info_layout.addWidget(caller_name_label)
        caller_info_layout.addWidget(call_type_label)
        
        caller_layout.addWidget(avatar_label)
        caller_layout.addLayout(caller_info_layout)
        caller_layout.addStretch()
        
        layout.addLayout(caller_layout)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        # Reject button
        reject_button = QPushButton()
        reject_button.setIcon(qta.icon('fa5s.phone-slash', color='#dcdcdc'))
        reject_button.setFixedSize(50, 50)
        reject_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: 2px solid #d32f2f;
                border-radius: 25px;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
        """)
        reject_button.clicked.connect(self.reject_call)
        reject_button.setToolTip("Reject Call")
        
        # Accept button
        accept_button = QPushButton()
        accept_button.setIcon(qta.icon('fa5s.phone', color='#dcdcdc'))
        accept_button.setFixedSize(50, 50)
        accept_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: 2px solid #45a049;
                border-radius: 25px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        accept_button.clicked.connect(self.accept_call)
        accept_button.setToolTip("Accept Call")
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(reject_button)
        buttons_layout.addWidget(accept_button)
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
    
    def accept_call(self):
        """Accept the incoming call"""
        self.call_handled = True
        self.webrtc_widget.answer_call(self.call_id)
        self.call_accepted.emit(self.call_id)
        self.accept()
    
    def reject_call(self):
        """Reject the incoming call"""
        self.call_handled = True
        self.webrtc_widget.end_call()
        self.call_rejected.emit(self.call_id)
        self.accept()
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        if not hasattr(self, 'call_handled') or not self.call_handled:
            self.reject_call()
        event.accept()

class ActiveCallDialog(CallDialog):
    """Active call dialog - alias for CallDialog for compatibility"""
    
    def __init__(self, remote_user: str, call_type: str, parent=None, use_native=False):
        # Create a mock call session for compatibility
        from webrtc_service import CallSession, CallType, CallState
        import uuid
        
        call_session = CallSession(
            call_id=str(uuid.uuid4()),
            call_type=CallType.VIDEO if call_type == "video" else CallType.VOICE,
            local_user="",
            remote_user=remote_user,
            state=CallState.CONNECTED
        )
        
        # Create appropriate call widget
        if use_native:
            from native_call_widget import NativeCallWidget
            call_widget = NativeCallWidget()
        else:
            from webrtc_widget import WebRTCWidget
            call_widget = WebRTCWidget()
        
        super().__init__(call_widget, call_session, parent, use_native)
