<div align="center">

# 🔐 QuMail - Post-Quantum Email Client

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=flat-square&logo=python)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg?style=flat-square&logo=qt)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Security](https://img.shields.io/badge/Security-Post%20Quantum-red.svg?style=flat-square&logo=shield)](https://github.com)

*An experimental email client implementing post-quantum cryptography and quantum key distribution*

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Technical Details](#-technical-details) • [Contributing](#-contributing)

</div>

---

## 🌟 Overview

QuMail implements multiple cryptographic approaches including Kyber-512 KEM, quantum key distribution simulation, and traditional AES-GCM encryption. The project serves as a research platform for post-quantum cryptography in email communications, featuring a modern PyQt6 interface with integrated voice/video calling capabilities.

## ✨ Features

### 🔒 **Cryptographic Implementation**
- **Kyber-512 KEM**: NIST-standardized post-quantum key encapsulation
- **AES-256-GCM**: Authenticated encryption for message payloads
- **One-Time Pad**: XOR-based encryption with quantum-derived keys
- **QKD Simulation**: Quantum key distribution protocol simulation

### 📧 **Email Management**
- Full IMAP/SMTP support for standard email providers
- Rich HTML email rendering with WebEngine
- Secure attachment encryption and decryption
- SQLite-based encrypted local keystore
- Firebase Realtime Database for public key distribution

### 📞 **Integrated Communications**
- WebRTC-based voice and video calling
- Agora.io integration for reliable signaling
- Cross-platform multimedia support
- Real-time communication capabilities

### 🚀 **Implementation Status**
- ✅ **Production Ready**: Kyber-512 encryption, email client, local keystore
- 🔧 **Active Development**: QKD simulation, WebRTC calling, Firebase integration
- 📋 **Planned**: Hardware QKD support, mobile clients, group messaging

## 🚀 Installation

### Prerequisites
- Python 3.8+
- pip package manager

### Setup

```bash
git clone https://github.com/yourusername/qumail.git
cd qumail
pip install -r requirements.txt
python launcher.py
```

### Dependencies

```
PyQt6>=6.4.0
PyQt6-WebEngine>=6.4.0
PyQt6-Multimedia>=6.4.0
PyQt6-MultimediaWidgets>=6.4.0
qtawesome>=1.2.0
qasync>=0.24.0
httpx>=0.24.0
cryptography>=3.4.8
keyring>=23.0.0
configparser>=5.0.0
fastapi>=0.100.0
uvicorn>=0.22.0
websockets>=11.0.0
pydantic>=2.0.0
agora-token-builder>=1.0.0
```

## 📖 Usage

### Configuration
1. Launch with `python launcher.py`
2. Configure IMAP/SMTP settings in Settings dialog
3. Kyber key pairs are generated automatically on first run

### Encryption Levels
- **Level 1**: One-time pad with simulated quantum keys
- **Level 2**: AES-256-GCM with quantum-derived keys
- **Level 3**: Kyber-512 KEM with AES-256-GCM
- **Level 4**: Plaintext (testing only)

### Voice/Video Calls
Experimental WebRTC implementation. Requires Agora.io configuration for signaling server.

## 🔧 Technical Details

### Cryptographic Implementation

| Level | Algorithm | Key Exchange | Notes |
|-------|-----------|--------------|-------|
| 1 | XOR (OTP) | Simulated QKD | Perfect secrecy if keys are truly random |
| 2 | AES-256-GCM | PBKDF2 from QKD keys | Quantum-derived symmetric keys |
| 3 | AES-256-GCM | Kyber-512 KEM | NIST PQC standardized algorithm |
| 4 | None | None | Plaintext for testing |

### Key Management
- **Local**: Kyber-512 keypairs stored in SQLite with encryption
- **Distribution**: Firebase Realtime Database for public key sharing
- **QKD**: HTTP-based simulation server (not actual quantum hardware)

### Architecture Components
- `kyberk2so/`: Pure Python implementation of Kyber-512
- `crypto_services.py`: Encryption/decryption logic
- `firebase_directory.py`: Public key distribution
- `qkd_service.py`: Simulated quantum key distribution
- `webrtc_service.py`: WebRTC calling implementation

### 📁 Project Structure

```
QuMail/
├── 📁 kyberk2so/              # Kyber-512 implementation
├── 🚀 launcher.py             # Process manager
├── 📱 qumail_client.py        # Main application
├── 🖥️  main_window.py          # PyQt6 GUI
├── 📧 email_controller.py     # Email logic
├── 🔐 crypto_services.py      # Encryption services
├── 📞 call_controller.py      # WebRTC calls
├── 🔑 firebase_directory.py   # Key distribution
├── ⚛️  qkd_service.py          # QKD simulation
└── 🔧 pqc_key_server.py       # Local key server
```

## 🛠️ Development

### Running Components
```bash
python pqc_key_server.py      # Local key server (port 8080)
python qumail_client.py       # Main GUI application
python launcher.py            # Runs both automatically
```

### Testing
- Use Level 4 (plaintext) for debugging message flow
- QKD service runs in simulation mode by default
- Firebase configuration required for key distribution

## 🤝 Contributing

### 🎯 Areas for Enhancement
- Hardware QKD device integration
- Mobile client development (Android/iOS)
- Group messaging and conference calling
- Performance optimization for large file handling
- Comprehensive security auditing

### Code Style
- Follow PEP 8
- Add type hints
- Document cryptographic functions thoroughly

## ⚠️ Current Limitations

- QKD uses simulation rather than quantum hardware
- WebRTC may require network/firewall configuration
- Public key distribution depends on Firebase
- Forward secrecy not yet implemented
- Large file handling could be optimized
- Encryption operations may briefly block UI

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 📚 References

- [NIST Post-Quantum Cryptography](https://csrc.nist.gov/projects/post-quantum-cryptography)
- [Kyber Algorithm Specification](https://pq-crystals.org/kyber/)
- [PyQt6 Documentation](https://doc.qt.io/qtforpython/)
- [WebRTC Standards](https://webrtc.org/)

---

