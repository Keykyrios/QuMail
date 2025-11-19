# launcher.py
import subprocess
import sys
import os
import time
import logging

# Configure basic logging for the launcher
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Determine the base path for bundled resources if running as an executable
if getattr(sys, 'frozen', False):
    # Running as a PyInstaller bundle
    BASE_DIR = sys._MEIPASS
else:
    # Running in a normal Python environment
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to the PQC Key Server script
pqc_server_script = os.path.join(BASE_DIR, 'pqc_key_server.py')
# Path to the QuMail Client script
qumail_client_script = os.path.join(BASE_DIR, 'qumail_client.py')
# Path to the Signaling Server script
signaling_server_script = os.path.join(BASE_DIR, 'signaling_server.py')

server_process = None
signaling_process = None

def start_server():
    """Starts the PQC Key Server in the background without a console window."""
    global server_process
    log.info("Attempting to start PQC Key Server...")
    try:
        # Use CREATE_NO_WINDOW to hide the console window on Windows
        # For non-Windows OS, this flag is ignored.
        # We also redirect stdout/stderr to PIPE to prevent them from showing up.
        server_process = subprocess.Popen(
            [sys.executable, pqc_server_script],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True # Important to make it an independent process group
        )
        log.info(f"PQC Key Server started with PID: {server_process.pid}")
        # Give the server a moment to start up
        time.sleep(2)
    except FileNotFoundError:
        log.error(f"Error: {pqc_server_script} not found. Ensure it's in the bundle.")
        sys.exit(1)
    except Exception as e:
        log.error(f"Failed to start PQC Key Server: {e}", exc_info=True)
        sys.exit(1)

def start_signaling_server():
    """Starts the Signaling Server in the background without a console window."""
    global signaling_process
    log.info("Attempting to start Signaling Server...")
    try:
        # Use CREATE_NO_WINDOW to hide the console window on Windows
        # For non-Windows OS, this flag is ignored.
        # We also redirect stdout/stderr to PIPE to prevent them from showing up.
        signaling_process = subprocess.Popen(
            [sys.executable, signaling_server_script],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True # Important to make it an independent process group
        )
        log.info(f"Signaling Server started with PID: {signaling_process.pid}")
        # Give the server more time to start up
        time.sleep(5)
        
        # Test if server is responding
        try:
            import httpx
            response = httpx.get("http://127.0.0.1:8081/health", timeout=5.0)
            if response.status_code == 200:
                log.info("Signaling Server is responding correctly")
            else:
                log.warning(f"Signaling Server health check failed: {response.status_code}")
        except Exception as e:
            log.warning(f"Could not verify Signaling Server health: {e}")
            
    except FileNotFoundError:
        log.error(f"Error: {signaling_server_script} not found. Ensure it's in the bundle.")
        sys.exit(1)
    except Exception as e:
        log.error(f"Failed to start Signaling Server: {e}", exc_info=True)
        sys.exit(1)

def start_client():
    """Starts the QuMail Client application."""
    log.info("Attempting to start QuMail Client...")
    try:
        # We will directly execute the client script.
        # It will use the same Python interpreter or the bundled one.
        # The client will run in the foreground.
        subprocess.run([sys.executable, qumail_client_script], check=True)
        log.info("QuMail Client finished.")
    except FileNotFoundError:
        log.error(f"Error: {qumail_client_script} not found. Ensure it's in the bundle.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        log.error(f"QuMail Client exited with an error: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Failed to start QuMail Client: {e}", exc_info=True)
        sys.exit(1)

def cleanup_server():
    """Attempts to terminate the server process when the client exits."""
    global server_process, signaling_process
    
    # Cleanup PQC Key Server
    if server_process and server_process.poll() is None: # If server is still running
        log.info(f"Terminating PQC Key Server (PID: {server_process.pid})...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5) # Give it some time to terminate
            log.info("PQC Key Server terminated successfully.")
        except subprocess.TimeoutExpired:
            log.warning("PQC Key Server did not terminate gracefully, killing it.")
            server_process.kill()
        except Exception as e:
            log.error(f"Error during PQC server cleanup: {e}", exc_info=True)
    else:
        log.info("PQC Key Server was already stopped or not started.")
    
    # Cleanup Signaling Server
    if signaling_process and signaling_process.poll() is None: # If signaling server is still running
        log.info(f"Terminating Signaling Server (PID: {signaling_process.pid})...")
        signaling_process.terminate()
        try:
            signaling_process.wait(timeout=5) # Give it some time to terminate
            log.info("Signaling Server terminated successfully.")
        except subprocess.TimeoutExpired:
            log.warning("Signaling Server did not terminate gracefully, killing it.")
            signaling_process.kill()
        except Exception as e:
            log.error(f"Error during signaling server cleanup: {e}", exc_info=True)
    else:
        log.info("Signaling Server was already stopped or not started.")

if __name__ == "__main__":
    try:
        start_server()
        start_signaling_server()
        
        # Wait a bit more to ensure signaling server is ready
        time.sleep(3)
        
        start_client() # This will block until the client GUI is closed
    finally:
        cleanup_server()
        log.info("Launcher finished.")
