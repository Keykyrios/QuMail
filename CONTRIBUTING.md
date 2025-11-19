# Contributing to QuMail

Thank you for your interest in contributing to QuMail! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Git
- Basic understanding of cryptography concepts
- Familiarity with PyQt6 (for GUI contributions)

### Development Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/qumail.git
   cd qumail
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Test the installation**
   ```bash
   python launcher.py
   ```

## 🎯 Areas for Contribution

### High Priority
- **Hardware QKD Integration**: Replace simulation with actual quantum hardware APIs
- **Mobile Clients**: Android/iOS implementations
- **Security Auditing**: Cryptographic implementation review
- **Performance Optimization**: Large file handling and memory usage

### Medium Priority
- **Group Messaging**: Multi-party secure communication
- **Forward Secrecy**: Implement perfect forward secrecy
- **UI/UX Improvements**: Enhanced user interface design
- **Documentation**: Code documentation and user guides

### Low Priority
- **Plugin System**: Extensible architecture
- **Additional Protocols**: Support for other post-quantum algorithms
- **Internationalization**: Multi-language support

## 📝 Code Style Guidelines

### Python Code
- Follow **PEP 8** style guide
- Use **type hints** for all function parameters and return values
- Add **docstrings** for all public functions and classes
- Maximum line length: **88 characters** (Black formatter compatible)

### Cryptographic Code
- **Document all cryptographic functions** thoroughly
- Include **security assumptions** and **threat model** in comments
- Use **constant-time operations** where applicable
- **Never implement custom crypto** - use established libraries

### Example
```python
def encrypt_message(
    plaintext: bytes, 
    recipient_key: bytes, 
    security_level: int
) -> str:
    """
    Encrypt a message using the specified security level.
    
    Args:
        plaintext: The message to encrypt
        recipient_key: Public key of the recipient
        security_level: Encryption level (1-4)
        
    Returns:
        JSON string containing encrypted message
        
    Raises:
        EncryptionError: If encryption fails
        
    Security Note:
        Level 3 provides post-quantum security using Kyber-512 KEM.
        Assumes recipient_key is authentic and not compromised.
    """
```

## 🔧 Development Workflow

### Branch Naming
- `feature/description` - New features
- `fix/description` - Bug fixes
- `crypto/description` - Cryptographic changes
- `ui/description` - User interface changes

### Commit Messages
Use conventional commit format:
```
type(scope): description

feat(crypto): add Dilithium signature support
fix(ui): resolve email list scrolling issue
docs(readme): update installation instructions
```

### Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, documented code
   - Add tests if applicable
   - Update documentation

3. **Test your changes**
   ```bash
   python launcher.py  # Test GUI functionality
   python -m pytest   # Run unit tests (if available)
   ```

4. **Submit pull request**
   - Provide clear description of changes
   - Reference any related issues
   - Include screenshots for UI changes

## 🧪 Testing Guidelines

### Manual Testing
- Test all encryption levels (1-4)
- Verify email sending/receiving functionality
- Test WebRTC calling features
- Check cross-platform compatibility

### Security Testing
- Verify cryptographic implementations
- Test key generation and storage
- Check for timing attacks in crypto code
- Validate input sanitization

## 🔒 Security Considerations

### Reporting Security Issues
- **DO NOT** open public issues for security vulnerabilities
- Email security issues to: [security@qumail.dev]
- Include detailed reproduction steps
- Allow reasonable time for fixes before disclosure

### Cryptographic Changes
- All cryptographic modifications require thorough review
- Include references to academic papers or standards
- Provide security analysis and threat model
- Consider backward compatibility

## 📚 Resources

### Documentation
- [NIST Post-Quantum Cryptography](https://csrc.nist.gov/projects/post-quantum-cryptography)
- [Kyber Specification](https://pq-crystals.org/kyber/)
- [PyQt6 Documentation](https://doc.qt.io/qtforpython/)

### Development Tools
- **Code Formatter**: Black (`pip install black`)
- **Linter**: Flake8 (`pip install flake8`)
- **Type Checker**: mypy (`pip install mypy`)

## 🤝 Community Guidelines

### Code of Conduct
- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn
- Maintain professional communication

### Getting Help
- Open an issue for bugs or feature requests
- Use discussions for questions and ideas
- Join our development chat (if available)

## 📋 Checklist for Contributors

Before submitting a pull request:

- [ ] Code follows PEP 8 style guidelines
- [ ] All functions have type hints and docstrings
- [ ] Cryptographic code is thoroughly documented
- [ ] Changes have been manually tested
- [ ] No sensitive data (keys, logs) included
- [ ] Pull request description is clear and complete


Thank you for helping make QuMail more secure and robust!