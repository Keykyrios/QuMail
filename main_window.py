# main_window.py
import logging
import asyncio
import os
import html
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QListWidget, QTableWidget,
    QToolBar, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QMessageBox, QListWidgetItem, QFileDialog, QLabel,
    QApplication, QVBoxLayout
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QAction, QCursor, QColor
from PyQt6.QtCore import pyqtSlot, Qt, QUrl
from compose_dialog import ComposeDialog
from settings_dialog import SettingsDialog
from call_dialog import CallDialog, IncomingCallDialog
from call_controller import CallController
from webrtc_service import CallType
import qtawesome as qta
import html_templates

log = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.is_loading_more = False
        self.setWindowTitle("QuMail")
        self.setGeometry(100, 100, 1280, 800)
        self.folder_icons = {
            'Inbox': 'fa5s.inbox', 'Sent': 'fa5s.paper-plane', 'Drafts': 'fa5s.file-alt',
            'Spam': 'fa5s.bug', 'Trash': 'fa5s.trash-alt', 'Important': 'fa5s.bookmark',
            'Starred': 'fa5s.star', 'Archive': 'fa5s.archive', 'All mail': 'fa5s.envelope-open-text'
        }
        self.default_folder_icon = 'fa5s.folder'
        
        # Initialize call controller
        self.call_controller = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        grid_layout = QGridLayout(central_widget)
        self.folder_list_widget = QListWidget()
        grid_layout.addWidget(self.folder_list_widget, 0, 0, 3, 1)
        self.email_list_widget = QTableWidget()
        self.email_list_widget.setColumnCount(3)
        self.email_list_widget.setHorizontalHeaderLabels(["From", "Subject", "Date"])
        self.email_list_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.email_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.email_list_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.email_list_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.email_list_widget.setColumnWidth(0, 250)
        self.email_list_widget.setColumnWidth(2, 180)
        self.email_list_widget.setSortingEnabled(False)
        grid_layout.addWidget(self.email_list_widget, 0, 1)
        self.email_content_browser = QWebEngineView()
        self.email_content_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.email_content_browser.page().setBackgroundColor(QColor("#3c3f41"))
        self.email_content_browser.setHtml(html_templates.EMPTY_VIEW_TEMPLATE)
        grid_layout.addWidget(self.email_content_browser, 1, 1)
        self.email_content_browser.loadFinished.connect(self.on_web_view_load_finished)
        self.attachment_container = QWidget()
        attachment_layout = QVBoxLayout(self.attachment_container)
        attachment_layout.setContentsMargins(0, 5, 0, 5)
        attachment_label = QLabel("Attachments:")
        self.attachment_list_widget = QListWidget()
        self.attachment_list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.attachment_list_widget.setFixedHeight(60)
        attachment_layout.addWidget(attachment_label)
        attachment_layout.addWidget(self.attachment_list_widget)
        grid_layout.addWidget(self.attachment_container, 2, 1)
        self.attachment_container.setVisible(False)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 4)
        grid_layout.setRowStretch(0, 1)
        grid_layout.setRowStretch(1, 2)
        grid_layout.setRowStretch(2, 0)
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        self.refresh_button = QAction(qta.icon('fa5s.sync-alt', color='#dcdcdc'), "Refresh", self)
        self.compose_button = QAction(qta.icon('fa5s.pencil-alt', color='#dcdcdc'), "Compose", self)
        self.reply_button = QAction(qta.icon('fa5s.reply', color='#dcdcdc'), "Reply", self)
        self.reply_all_button = QAction(qta.icon('fa5s.reply-all', color='#dcdcdc'), "Reply All", self)
        self.forward_button = QAction(qta.icon('fa5s.share', color='#dcdcdc'), "Forward", self)
        self.voice_call_button = QAction(qta.icon('fa5s.phone', color='#dcdcdc'), "Voice Call", self)
        self.video_call_button = QAction(qta.icon('fa5s.video', color='#dcdcdc'), "Video Call", self)
        self.settings_button = QAction(qta.icon('fa5s.cog', color='#dcdcdc'), "Settings", self)
        toolbar.addAction(self.refresh_button)
        toolbar.addAction(self.compose_button)
        toolbar.addAction(self.reply_button)
        toolbar.addAction(self.reply_all_button)
        toolbar.addAction(self.forward_button)
        toolbar.addSeparator()
        toolbar.addAction(self.voice_call_button)
        toolbar.addAction(self.video_call_button)
        toolbar.addSeparator()
        toolbar.addAction(self.settings_button)
        self.update_conversation_actions(enabled=False)
        self.statusBar()
        self.update_status_bar("Ready.")
        self.compose_button.triggered.connect(lambda: self.open_compose_dialog())
        self.settings_button.triggered.connect(self.open_settings_dialog)
        self.refresh_button.triggered.connect(self.controller.handle_refresh_emails)
        self.reply_button.triggered.connect(self.controller.handle_reply)
        self.reply_all_button.triggered.connect(self.controller.handle_reply_all)
        self.forward_button.triggered.connect(self.controller.handle_forward)
        self.voice_call_button.triggered.connect(self.initiate_voice_call)
        self.video_call_button.triggered.connect(self.initiate_video_call)
        self.folder_list_widget.currentItemChanged.connect(self.on_folder_selected)
        self.email_list_widget.itemSelectionChanged.connect(self.on_email_selected)
        self.email_list_widget.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.attachment_list_widget.itemClicked.connect(self.on_attachment_clicked)

    def update_conversation_actions(self, enabled):
        self.reply_button.setEnabled(enabled)
        self.reply_all_button.setEnabled(enabled)
        self.forward_button.setEnabled(enabled)
        self.voice_call_button.setEnabled(enabled)
        self.video_call_button.setEnabled(enabled)

    @pyqtSlot(bool)
    def on_web_view_load_finished(self, ok):
        if not ok: return
        js_code = """
        document.body.style.backgroundColor = '#3c3f41';
        var allElements = document.getElementsByTagName('*');
        for (var i = 0, len = allElements.length; i < len; i++) {
            var element = allElements[i];
            var style = getComputedStyle(element);
            if (style.getPropertyValue('background-color') === 'rgb(255, 255, 255)') {
                element.style.backgroundColor = '#3c3f41';
            }
             if (style.getPropertyValue('color') === 'rgb(0, 0, 0)') {
                element.style.color = '#dcdcdc';
            }
        }
        """
        self.email_content_browser.page().runJavaScript(js_code)
    
    def set_busy_state(self):
        self.is_loading_more = True
        self.refresh_button.setEnabled(False); self.compose_button.setEnabled(False)
        self.folder_list_widget.setEnabled(False); self.email_list_widget.setEnabled(False)
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))

    def set_idle_state(self):
        self.is_loading_more = False
        self.refresh_button.setEnabled(True); self.compose_button.setEnabled(True)
        self.folder_list_widget.setEnabled(True); self.email_list_widget.setEnabled(True)
        self.unsetCursor()

    def populate_folder_list(self, folders_with_original_names):
        self.folder_list_widget.blockSignals(True)
        self.folder_list_widget.clear()
        for clean_name, original_name in folders_with_original_names:
            icon = qta.icon(self.folder_icons.get(clean_name, self.default_folder_icon), color='#dcdcdc')
            item = QListWidgetItem(icon, clean_name)
            item.setData(Qt.ItemDataRole.UserRole, original_name)
            self.folder_list_widget.addItem(item)
        self.folder_list_widget.blockSignals(False)

    def find_folder_item(self, clean_name_to_find):
        for i in range(self.folder_list_widget.count()):
            if (item := self.folder_list_widget.item(i)).text() == clean_name_to_find:
                return item
        return None

    @pyqtSlot(QListWidgetItem)
    def on_folder_selected(self, current_item):
        if current_item:
            original_folder_name = current_item.data(Qt.ItemDataRole.UserRole)
            self.clear_email_list()
            self.display_email_content({})
            self.controller.start_folder_selection(original_folder_name)
            
    def display_email_content(self, content_dict):
        # --- ADDED: Forensic Logging ---
        log.debug(f"Displaying content: HTML body is {len(content_dict.get('html_body', '')) if content_dict.get('html_body') else 'None'} bytes, "
                  f"Plain body is {len(content_dict.get('plain_body', '')) if content_dict.get('plain_body') else 'None'} bytes, "
                  f"Found {len(content_dict.get('attachments', []))} attachments.")

        html_content, plain_content = content_dict.get('html_body'), content_dict.get('plain_body')
        attachments = content_dict.get('attachments', [])
        if not html_content and not plain_content:
            self.email_content_browser.setHtml(html_templates.EMPTY_VIEW_TEMPLATE)
        elif html_content:
            # Load HTML without forcing a file:// base URL so remote images resolve correctly
            self.email_content_browser.setHtml(html_content)
        elif plain_content:
            escaped = html.escape(plain_content)
            html_from_plain = f"<html><body style='background-color:#3c3f41;color:#dcdcdc;font-family:monospace;white-space:pre-wrap;'>{escaped}</body></html>"
            self.email_content_browser.setHtml(html_from_plain)
        self.display_attachments(attachments)

    def display_attachments(self, attachments):
        # --- ADDED: Defensive Check ---
        if not isinstance(attachments, list):
            log.error(f"CRITICAL RENDER BUG: Received attachments of type {type(attachments)}, expected a list. Aborting display.")
            self.attachment_container.setVisible(False)
            # --- ADDED: Force Repaint ---
            self.attachment_container.layout().activate()
            self.attachment_container.adjustSize()
            return

        self.attachment_list_widget.clear()
        if attachments:
            # --- ADDED: Forensic Logging ---
            log.info(f"Displaying {len(attachments)} attachments: {[att['filename'] for att in attachments]}")
            self.attachment_container.setVisible(True)
            for att in attachments:
                item = QListWidgetItem(qta.icon('fa5s.file-download'), att['filename'])
                item.setData(Qt.ItemDataRole.UserRole, att['content'])
                self.attachment_list_widget.addItem(item)
        else:
            self.attachment_container.setVisible(False)
        
        # --- ADDED: Force Repaint ---
        self.attachment_container.layout().activate()
        self.attachment_container.adjustSize()


    def clear_email_list(self):
        self.email_list_widget.setSortingEnabled(False)
        self.email_list_widget.setRowCount(0)

    def append_emails_to_list(self, headers):
        self.email_list_widget.setSortingEnabled(False)
        start_row = self.email_list_widget.rowCount()
        for i, header in enumerate(headers):
            row, from_item, subject_item, date_item = start_row + i, QTableWidgetItem(header.get('from')), QTableWidgetItem(header.get('subject')), QTableWidgetItem(header.get('date'))
            self.email_list_widget.insertRow(row)
            if uid := header.get('uid'): from_item.setData(Qt.ItemDataRole.UserRole, uid)
            self.email_list_widget.setItem(row, 0, from_item)
            self.email_list_widget.setItem(row, 1, subject_item)
            self.email_list_widget.setItem(row, 2, date_item)

    @pyqtSlot(int)
    def on_scroll(self, value):
        scrollbar = self.email_list_widget.verticalScrollBar()
        if value >= scrollbar.maximum() * 0.9 and not self.is_loading_more:
            asyncio.create_task(self.controller.load_next_page_of_emails())

    @pyqtSlot()
    def on_email_selected(self):
        selected_items = self.email_list_widget.selectedItems()
        if not selected_items: return
        uid_item = self.email_list_widget.item(selected_items[0].row(), 0)
        if uid_item and (uid := uid_item.data(Qt.ItemDataRole.UserRole)):
            self.controller.start_email_selection(uid)
    
    def open_compose_dialog(self, to_addr="", subject="", body=""):
        ComposeDialog(self.controller, self, to_addr, subject, body).exec()

    def open_settings_dialog(self):
        if SettingsDialog(self.controller.settings_manager).exec():
            asyncio.create_task(self.controller.handle_settings_updated())

    def update_status_bar(self, message): self.statusBar().showMessage(message)
    def show_error_message(self, title, message): QMessageBox.critical(self, title, message)
    def show_info_message(self, title, message): QMessageBox.information(self, title, message)

    @pyqtSlot(QListWidgetItem)
    def on_attachment_clicked(self, item):
        filename, content = item.text(), item.data(Qt.ItemDataRole.UserRole)
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Attachment", os.path.join(os.path.expanduser("~/Downloads"), filename))
        if save_path:
            try:
                with open(save_path, 'wb') as f: f.write(content)
            except IOError as e: self.show_error_message("Save Failed", f"Could not save file:\n{e}")

    def initialize_call_controller(self, current_user: str):
        """Initialize the call controller"""
        if not self.call_controller:
            self.call_controller = CallController(current_user)
            log.info("Call controller initialized")
            
            # Test audio functionality after initialization
            asyncio.create_task(self.test_audio_after_init())
    
    async def test_audio_after_init(self):
        """Test audio functionality after call controller initialization"""
        try:
            # Wait a bit for initialization to complete
            await asyncio.sleep(2)
            
            if self.call_controller:
                await self.call_controller.test_audio_functionality()
        except Exception as e:
            log.error(f"Failed to test audio after initialization: {e}")
    
    def initiate_voice_call(self):
        """Initiate a voice call with the current email sender"""
        if not self.controller.current_email_object:
            self.show_info_message("No Email Selected", "Please select an email to initiate a call.")
            return

        if not self.call_controller:
            self.show_error_message("Call Service Not Available", "Call service is not initialized.")
            return

        if self.call_controller.is_in_call():
            self.show_info_message("Call in Progress", "You are already in a call. Please end the current call before starting a new one.")
            return

        # Get sender email from current email
        msg = self.controller.current_email_object['raw_message']
        sender_email = msg.get('From', '').split('<')[-1].split('>')[0].strip()
        if not sender_email or '@' not in sender_email:
            self.show_error_message("Invalid Sender", "Could not determine sender email address.")
            return

        # Initialize call controller if not already done
        if not self.call_controller:
            self.initialize_call_controller(self.controller.settings.get('email_address', ''))

        # Initiate voice call with cross-device support
        asyncio.create_task(self.call_controller.initiate_call(sender_email, CallType.VOICE))
    
    def initiate_video_call(self):
        """Initiate a video call with the current email sender"""
        if not self.controller.current_email_object:
            self.show_info_message("No Email Selected", "Please select an email to initiate a call.")
            return
        
        if not self.call_controller:
            self.show_error_message("Call Service Not Available", "Call service is not initialized.")
            return
        
        if self.call_controller.is_in_call():
            self.show_info_message("Call in Progress", "You are already in a call. Please end the current call before starting a new one.")
            return
        
        # Get sender email from current email
        msg = self.controller.current_email_object['raw_message']
        sender_email = msg.get('From', '').split('<')[-1].split('>')[0].strip()
        if not sender_email or '@' not in sender_email:
            self.show_error_message("Invalid Sender", "Could not determine sender email address.")
            return
        
        # Initialize call controller if not already done
        if not self.call_controller:
            self.initialize_call_controller(self.controller.settings.get('email_address', ''))
        
        # Initiate video call
        asyncio.create_task(self.call_controller.initiate_call(sender_email, CallType.VIDEO))

    def closeEvent(self, event):
        self.setEnabled(False)
        async def close_sequence():
            try: 
                # Shutdown call controller
                if self.call_controller:
                    await self.call_controller.shutdown()
                await self.controller.shutdown()
            except Exception as e: log.error(f"Error during shutdown: {e}", exc_info=True)
            finally: QApplication.instance().quit()
        asyncio.create_task(close_sequence())
        event.ignore()
