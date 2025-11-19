# settings_dialog.py
import asyncio
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QMessageBox
)
from settings_manager import KeyGenerationError

log = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Application Settings")
        
        self.settings = self.settings_manager.load_settings()
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.email_input = QLineEdit(self.settings.get('email_address', ''))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter new password or leave blank")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.imap_input = QLineEdit(self.settings.get('imap_host', 'imap.gmail.com'))
        self.smtp_input = QLineEdit(self.settings.get('smtp_host', 'smtp.gmail.com'))
        self.smtp_port_input = QLineEdit(self.settings.get('smtp_port', '465'))
        # Default to the new python server
        self.km_url_input = QLineEdit(self.settings.get('km_url', 'http://127.0.0.1:8001'))
        # QKD server URL for quantum key distribution
        self.qkd_url_input = QLineEdit(self.settings.get('qkd_server_url', 'http://127.0.0.1:8080'))
        # Agora
        self.agora_app_id_input = QLineEdit(self.settings.get('agora_app_id', 'd47e822a706d4a2db70fe31ce36e5a0f'))
        self.agora_app_cert_input = QLineEdit()
        self.agora_app_cert_input.setPlaceholderText("Enter App Certificate (stored securely)")
        self.agora_app_cert_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.agora_token_endpoint_input = QLineEdit(self.settings.get('agora_token_endpoint', ''))
        
        form_layout.addRow("Email Address:", self.email_input)
        form_layout.addRow("Password (App Specific):", self.password_input)
        form_layout.addRow("IMAP Server:", self.imap_input)
        form_layout.addRow("SMTP Server:", self.smtp_input)
        form_layout.addRow("SMTP Port:", self.smtp_port_input)
        form_layout.addRow("Key Manager URL:", self.km_url_input)
        form_layout.addRow("QKD Server URL:", self.qkd_url_input)
        form_layout.addRow("Agora App ID:", self.agora_app_id_input)
        form_layout.addRow("Agora App Certificate:", self.agora_app_cert_input)
        form_layout.addRow("Agora Token Endpoint:", self.agora_token_endpoint_input)

        self.layout.addLayout(form_layout)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.handle_save)
        self.button_box.rejected.connect(self.reject)
        
        self.layout.addWidget(self.button_box)

    def handle_save(self):
        """
        Synchronous slot that launches the asynchronous save operation.
        """
        # Disable buttons to prevent double-clicking
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setText("Saving...")
        # create_task schedules the coroutine to run on the event loop
        asyncio.create_task(self.async_save_and_close())

    async def async_save_and_close(self):
        """
        Performs the actual async save operation, handles errors, and closes
        the dialog on success.
        """
        try:
            await self.settings_manager.save_settings(
                email=self.email_input.text(),
                password=self.password_input.text(),
                imap_host=self.imap_input.text(),
                smtp_host=self.smtp_input.text(),
                smtp_port=self.smtp_port_input.text(),
                km_url=self.km_url_input.text(),
                qkd_server_url=self.qkd_url_input.text(),
                agora_app_id=self.agora_app_id_input.text(),
                agora_app_cert=self.agora_app_cert_input.text() or None,
                agora_token_endpoint=self.agora_token_endpoint_input.text(),
            )
            # self.accept() closes the dialog and returns a "True" result
            self.accept()
        except (KeyGenerationError, Exception) as e:
            log.error(f"Failed to save settings: {e}", exc_info=True)
            QMessageBox.critical(self, "Save Failed", str(e))
            # Re-enable the save button on failure
            self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)
            self.button_box.button(QDialogButtonBox.StandardButton.Save).setText("Save")

