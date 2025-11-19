# qumail_client.py

import sys
import asyncio
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from main_window import MainWindow
from email_controller import EmailController
import qasync

log = logging.getLogger(__name__)

def main():
    """The main entry point for the application."""
    try:
        # --- Central Logging Configuration ---
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)-20s - %(levelname)-8s - %(message)s',
            handlers=[
                logging.FileHandler("qumail_app.log"), # Log to a file
                logging.StreamHandler() # Also log to the console
            ]
        )
        log.info("==================================================")
        log.info("Application starting up...")
        
        app = QApplication(sys.argv)

        try:
            with open('style.qss', 'r') as f:
                app.setStyleSheet(f.read())
            log.info("Successfully loaded and applied style.qss.")
        except FileNotFoundError:
            log.warning("style.qss not found. Application will use default system styles.")
        except Exception as e:
            log.error(f"Failed to load stylesheet: {e}")
        
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)

        # --- THE FUCKING FIX IS HERE: Correct the initialization order ---
        # 1. Create the controller first, but don't give it a window yet.
        controller = EmailController(None)
        
        # 2. Now create the window and give it the real controller.
        #    The window's init_ui() will now have a valid controller object to connect signals to.
        main_win = MainWindow(controller)
        
        # 3. Finally, give the controller its reference to the now-existing window.
        controller.main_window = main_win

        # Show the main window immediately
        main_win.show()
        
        def schedule_initial_task():
            log.info("Event loop is running. Scheduling initial application task.")
            asyncio.create_task(controller.apply_settings_and_connect())

        QTimer.singleShot(0, schedule_initial_task)

        # Start the event loop
        with loop:
            loop.run_forever()
            
    except KeyboardInterrupt:
        log.info("Application shut down by user (KeyboardInterrupt).")
    except Exception as e:
        log.critical(f"A critical error occurred, and the application must close: {e}", exc_info=True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Fatal Error", f"A critical error occurred:\n{e}\n\nPlease check the 'qumail_app.log' file for details.")

if __name__ == '__main__':
    main()

