# compose_dialog.py
import asyncio
import re
import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QComboBox, QDialogButtonBox, QMessageBox, QPushButton,
    QLabel, QFileDialog, QHBoxLayout, QWidget
)
from PyQt6.QtCore import pyqtSlot, Qt

log = logging.getLogger(__name__)

class ComposeDialog(QDialog):
    def __init__(self, controller, parent=None, to_addr="", subject="", body=""):
        super().__init__(parent)
        self.controller = controller
        self.attachment_paths = []

        if not self.controller.settings or not self.controller.settings.get('email_address'):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self.reject)
            QMessageBox.critical(self, "Configuration Error", "Cannot compose. Please configure email account.")
            return

        self.setWindowTitle("Compose New Email")
        self.setMinimumSize(700, 550)
        
        self.prefill_to = to_addr
        self.prefill_subject = subject
        self.prefill_body = body

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.to_input = QLineEdit(self.prefill_to)
        self.subject_input = QLineEdit(self.prefill_subject)
        self.body_input = QTextEdit(self.prefill_body)
        self.body_input.moveCursor(self.body_input.textCursor().Start)

        # --- REINSTATED: Security Level ComboBox ---
        self.security_level_input = QComboBox()
        self.security_level_input.addItems([
            "Level 4: No Security (Plaintext)",
            "Level 3: Post-Quantum (Code-Based)",
            "Level 2: Quantum-Aided (AES)",
            "Level 1: Quantum-Secure (OTP)"
        ])
        # Default to the most secure, practical level
        self.security_level_input.setCurrentIndex(1) 
        
        # --- NEW: Encryption Method ComboBox for Level 1 and 2 ---
        self.encryption_method_input = QComboBox()
        self.encryption_method_input.addItems([
            "QKD (Quantum Key Distribution)",
            "PQC (Post-Quantum Cryptography)"
        ])
        self.encryption_method_input.setCurrentIndex(0)  # Default to QKD
        self.encryption_method_input.setVisible(False)  # Initially hidden 

        form_layout.addRow("To:", self.to_input)
        form_layout.addRow("Subject:", self.subject_input)
        form_layout.addRow("Security:", self.security_level_input) # ADDED BACK
        form_layout.addRow("Method:", self.encryption_method_input) # NEW: Encryption method
        layout.addLayout(form_layout)
        
        # Connect security level change to show/hide encryption method
        self.security_level_input.currentIndexChanged.connect(self.on_security_level_changed)
        
        attachment_widget = QWidget()
        attachment_layout = QHBoxLayout(attachment_widget)
        attachment_layout.setContentsMargins(0, 5, 0, 5)
        attach_button = QPushButton("Attach File...")
        attach_button.clicked.connect(self.open_file_dialog)
        self.attachment_label = QLabel("No attachments")
        self.attachment_label.setStyleSheet("color: grey;")
        attachment_layout.addWidget(attach_button)
        attachment_layout.addWidget(self.attachment_label, 1)
        layout.addWidget(attachment_widget)
        layout.addWidget(self.body_input)

        self.button_box = QDialogButtonBox(self)
        self.send_button = self.button_box.addButton("Send", QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.send_button.clicked.connect(self.on_send_button_clicked)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.button_box)

    @pyqtSlot()
    def open_file_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Attach")
        if file_paths:
            self.attachment_paths.extend(file_paths)
            filenames = [os.path.basename(p) for p in self.attachment_paths]
            self.attachment_label.setText(f"Attached: {', '.join(filenames)}")
            self.attachment_label.setStyleSheet("")

    @pyqtSlot(int)
    def on_security_level_changed(self, index):
        """Show/hide encryption method selection based on security level"""
        # Level 1 and 2 support both QKD and PQC
        # Level 3 only supports PQC (Kyber)
        # Level 4 is plaintext
        if index in [2, 3]:  # Level 1 or 2
            self.encryption_method_input.setVisible(True)
        else:  # Level 3 or 4
            self.encryption_method_input.setVisible(False)

    @pyqtSlot()
    def on_send_button_clicked(self):
        asyncio.create_task(self.async_send_email())

    async def async_send_email(self):
        to_addr = self.to_input.text().strip()
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\s*,\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})*$'
        if not re.match(email_regex, to_addr):
            QMessageBox.warning(self, "Invalid Email", f"The address '{to_addr}' is not valid.")
            return
        subject = self.subject_input.text()
        if not subject:
            QMessageBox.warning(self, "Input Error", "The 'Subject' cannot be empty.")
            return
        body = self.body_input.toPlainText()
        
        # --- REINSTATED: Mapping from ComboBox index to security level ---
        level_map = {0: 4, 1: 3, 2: 2, 3: 1}
        security_level = level_map[self.security_level_input.currentIndex()]
        
        # --- NEW: Get encryption method for Level 1 and 2 ---
        encryption_method = "pqc"  # Default
        if security_level in [1, 2]:
            method_map = {0: "qkd", 1: "pqc"}
            encryption_method = method_map[self.encryption_method_input.currentIndex()]

        self.send_button.setEnabled(False)
        self.send_button.setText("Sending...")
        self.cancel_button.setEnabled(False)

        attachments = []
        try:
            for path in self.attachment_paths:
                with open(path, 'rb') as f:
                    attachments.append({'filename': os.path.basename(path), 'content': f.read()})
        except IOError as e:
            QMessageBox.critical(self, "File Error", f"Could not read attachment:\n{e}")
            self.send_button.setEnabled(True); self.send_button.setText("Send"); self.cancel_button.setEnabled(True)
            return

        success = await self.controller.handle_send_email(to_addr, subject, body, attachments, security_level, encryption_method)

        if success:
            self.accept()
        else:
            self.send_button.setEnabled(True); self.send_button.setText("Send"); self.cancel_button.setEnabled(True)

