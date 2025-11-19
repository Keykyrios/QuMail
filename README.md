# 🔐 QuMail - Quantum-Secure Email Client

<div align="center">

![QuMail Logo](https://img.shields.io/badge/QuMail-Quantum%20Secure-blue?style=for-the-badge&logo=mail&logoColor=white)

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=flat-square&logo=python)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg?style=flat-square&logo=qt)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Security](https://img.shields.io/badge/Security-Quantum%20Resistant-red.svg?style=flat-square&logo=shield)](https://github.com)

*A next-generation email client with quantum-resistant encryption and secure voice/video calling*

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Security](#-security) • [Contributing](#-contributing)

</div>

---

## 🌟 Overview

QuMail is a revolutionary email client that combines traditional email functionality with cutting-edge quantum-resistant cryptography. Built with PyQt6, it provides a modern, secure communication platform featuring multiple encryption levels, integrated voice/video calling, and quantum key distribution (QKD) support.

## ✨ Features

### 🔒 **Multi-Level Security**
- **Level 1**: Quantum-Secure One-Time Pad (OTP) encryption
- **Level 2**: Quantum-Aided AES-256-GCM encryption  
- **Level 3**: Post-Quantum Cryptography (Kyber-512 KEM)
- **Level 4**: Plaintext (for testing purposes)

### 📧 **Email Management**
- Modern, intuitive email interface
- Support for multiple email providers (IMAP/SMTP)
- Rich HTML email rendering with dark theme
- Attachment handling with secure encryption
- Folder management and email organization

### 📞 **Integrated Communications**
- **Voice Calls**: Crystal-clear audio communication
- **Video Calls**: High-quality video conferencing
- **WebRTC Support**: Real-time peer-to-peer communication
- **Cross-Platform**: Works across different devices and platforms

### 🔐 **Advanced Cryptography**
- **Kyber-512**: NIST-approved post-quantum cryptography
- **QKD Integration**: Quantum Key Distribution support
- **Firebase Directory**: Secure public key management
- **Local Key Storage**: Encrypted keystore management

### 🎨 **User Experience**
- Dark theme optimized interface
- Responsive design with modern icons
- Real-time status updates
- Comprehensive settings management

## 🚀 Installation

### Prerequisites

- **Python 3.8+**
- **pip** package manager
- **Git** (for cloning the repository)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/qumail.git
   cd qumail
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch QuMail**
   ```bash
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

### First Time Setup

1. **Launch QuMail** using `python launcher.py`
2. **Configure Email Settings**:
   - Go to Settings → Email Configuration
   - Enter your IMAP/SMTP server details
   - Configure authentication credentials
3. **Generate Quantum Keys**:
   - The application will automatically generate your key pair
   - Keys are stored securely in the local keystore

### Sending Secure Emails

1. **Compose Email**: Click the compose button or use `Ctrl+N`
2. **Select Security Level**:
   - Choose from 4 security levels based on your needs
   - Higher levels provide stronger quantum resistance
3. **Add Recipients**: Enter recipient email addresses
4. **Send**: Your email will be encrypted automatically

### Making Calls

1. **Select an Email**: Choose an email from a contact
2. **Initiate Call**: Click the voice or video call button
3. **Accept/Decline**: Handle incoming calls through the call dialog

## 🔐 Security Architecture

### Encryption Levels Explained

| Level | Method | Description | Use Case |
|-------|--------|-------------|----------|
| **1** | Quantum OTP | Perfect secrecy with quantum keys | Maximum security |
| **2** | Quantum AES | AES-256 with quantum-derived keys | High security + performance |
| **3** | Kyber-512 KEM | Post-quantum cryptography | Future-proof security |
| **4** | Plaintext | No encryption | Testing only |

### Key Management

- **Local Generation**: Kyber key pairs generated locally
- **Firebase Directory**: Public key distribution via Firebase
- **QKD Integration**: Quantum key distribution for OTP
- **Secure Storage**: Keys encrypted in local SQLite database

### Communication Security

- **End-to-End Encryption**: All messages encrypted before transmission
- **Perfect Forward Secrecy**: Each message uses unique keys
- **Quantum Resistance**: Protection against quantum computer attacks
- **Authenticated Encryption**: Prevents tampering and forgery

## 🏗️ Architecture

```
QuMail/
├── 📁 kyberk2so/              # Post-quantum cryptography implementation
├── 📄 launcher.py             # Application launcher and process manager
├── 📄 qumail_client.py        # Main application entry point
├── 📄 main_window.py          # Primary GUI interface
├── 📄 email_controller.py     # Email management logic
├── 📄 crypto_services.py      # Encryption/decryption services
├── 📄 call_controller.py      # Voice/video call management
├── 📄 webrtc_service.py       # WebRTC communication handling
├── 📄 firebase_directory.py   # Public key directory service
├── 📄 qkd_service.py          # Quantum key distribution
├── 📄 settings_manager.py     # Configuration management
└── 📄 style.qss              # Application styling
```

## 🛠️ Development

### Running in Development Mode

```bash
# Install development dependencies
pip install -r requirements.txt

# Run the application
python launcher.py

# Run individual components
python pqc_key_server.py      # Key server
python qumail_client.py       # Main client
```

### Building for Production

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --onefile --windowed launcher.py
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Submit a pull request with a clear description

### Code Style

- Follow PEP 8 guidelines
- Use meaningful variable names
- Add docstrings for functions and classes
- Include type hints where appropriate

## 📋 Roadmap

- [ ] **Mobile Support**: Android and iOS applications
- [ ] **Plugin System**: Extensible architecture for third-party plugins
- [ ] **Advanced QKD**: Hardware QKD device integration
- [ ] **Group Messaging**: Secure group communication
- [ ] **File Sharing**: Large file transfer with quantum security
- [ ] **Calendar Integration**: Secure scheduling and events

## 🐛 Known Issues

- WebRTC may require firewall configuration for some networks
- QKD simulation mode is for testing purposes only
- Large attachments may impact performance on slower systems

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **NIST**: For post-quantum cryptography standards
- **PyQt Team**: For the excellent GUI framework
- **Cryptography Community**: For security best practices and implementations
- **Open Source Contributors**: For making this project possible

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/qumail/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/qumail/discussions)
- **Email**: support@qumail.dev

---

<div align="center">

**Made with ❤️ for a quantum-secure future**

[![GitHub stars](https://img.shields.io/github/stars/yourusername/qumail?style=social)](https://github.com/yourusername/qumail/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/yourusername/qumail?style=social)](https://github.com/yourusername/qumail/network)

</div>