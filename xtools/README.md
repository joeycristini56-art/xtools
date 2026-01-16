# XTools - Cross-Platform Tool Suite

A production-grade cross-platform Flutter application integrating Python and Go backend tools for data processing, file management, bot automation, and account checking.

## Features

### 📊 Data Processing Tools
- **Sort**: Extract emails by provider (Gmail, Microsoft, Yahoo, AOL, iCloud, ProtonMail)
- **Filter**: Remove duplicate lines from files
- **Deduplicate**: Consolidate and deduplicate valid files
- **Split**: Filter for CC/PayPal premium accounts
- **Remove**: Remove lines matching a pattern

### 📤 File Upload
- **GoFile**: Upload files to GoFile.io with progress tracking

### 🔍 Web Scraping
- **Web Scraper**: Scrape data from websites
- **Telegram Scraper**: Scrape data from Telegram channels

### 🤖 Bot Management
- **Discord Bot**: Email monitoring and notifications
- **Telegram Bot**: Message forwarding with Dropbox integration

### 🎮 Xbox Checker
- High-performance Xbox account validation
- Configurable workers, CPM, batch size
- API key authentication

### 🔐 CAPTCHA Solving
- Multiple CAPTCHA type support
- 2Captcha integration

### 💾 Combo Database
- SQLite-based combo storage
- Search and export functionality

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | ✅ Full | Native FFI + subprocess fallback |
| Windows | ✅ Full | Native FFI + subprocess fallback |
| macOS | ✅ Full | Native FFI + subprocess fallback |
| Android | 🔄 In Progress | JNI bridge required |
| iOS | 🔄 In Progress | Framework compilation required |

## Installation

### Prerequisites

- Flutter SDK 3.0+
- Python 3.8+
- Go 1.20+
- GCC (for Linux)
- MinGW (for Windows cross-compile)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-repo/xtools.git
cd xtools/xtools

# Install Flutter dependencies
flutter pub get

# Build native libraries (Linux)
chmod +x build_all.sh
./build_all.sh

# Run the app
flutter run
```

### Building Native Libraries

```bash
# Linux
./build_all.sh

# macOS
./build_all.sh

# iOS (macOS only)
./build_ios.sh
```

## Architecture

```
Flutter App (Dart)
    ↓
FFI Service (dart:ffi)
    ↓
Native Libraries (.so/.dll/.dylib)
    ↓
Python/Go Code
    ↓
JSON Response
```

### Fallback Mode

If native libraries are not available, the app automatically falls back to subprocess execution:

```
Flutter App (Dart)
    ↓
Process.run()
    ↓
Python/Go Scripts
    ↓
JSON Response
```

## Project Structure

```
xtools/
├── lib/
│   ├── main.dart              # App entry point
│   ├── core/                  # App state and theme
│   ├── screens/               # UI screens
│   └── services/              # Business logic
│       ├── ffi_service.dart   # FFI integration
│       ├── bot_service.dart   # Tool execution
│       └── config_service.dart # Configuration
├── backend/
│   ├── python/                # Python tools
│   │   ├── sort.py
│   │   ├── filter.py
│   │   ├── gofile.py
│   │   └── xtools_ffi_module.py
│   ├── go/
│   │   ├── runtime/           # Xbox checker
│   │   └── toolbot/           # Telegram toolbot
│   └── interpreters/          # Compiled libraries
│       ├── linux/
│       ├── windows/
│       ├── macos/
│       └── android/
└── pubspec.yaml
```

## Configuration

### Settings Screen

Configure API credentials in the Settings screen:
- Discord Bot Token
- Telegram API ID, Hash, Phone
- Dropbox App Key, Secret, Refresh Token
- Xbox API Key
- CAPTCHA API Key

### Secure Storage

All credentials are stored securely using:
- `flutter_secure_storage` for sensitive data
- `shared_preferences` for non-sensitive settings

## Usage

### Data Tools

1. Navigate to "Data Tools"
2. Select a file using the file picker
3. Choose a tool (Sort, Filter, etc.)
4. Configure options (e.g., domains for Sort)
5. Click "Process"

### Xbox Checker

1. Navigate to "Xbox Checker"
2. Enter your API key
3. Select a combo file
4. (Optional) Configure advanced settings
5. Click "Start Check"

### Bot Management

1. Configure credentials in Settings
2. Navigate to Discord/Telegram Bot screen
3. Configure bot-specific settings
4. Click "Start Bot"

## Development

### Adding New Tools

1. Create Python/Go implementation in `backend/`
2. Add FFI wrapper function
3. Update `xtools_ffi_module.py`
4. Add service method in `bot_service.dart`
5. Create/update UI screen

### Testing

```bash
# Run Flutter tests
flutter test

# Test Python tools
cd backend/python
python3 xtools_ffi_module.py status
```

## Troubleshooting

### "Python library not loaded"

The app will automatically fall back to subprocess execution. Ensure Python 3 is installed and accessible.

### "Go library not loaded"

The app will automatically fall back to subprocess execution. Ensure Go is installed and the runtime is built.

### "File not found"

Ensure the backend directory is in the correct location relative to the executable.

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and feature requests, please use the GitHub issue tracker.
