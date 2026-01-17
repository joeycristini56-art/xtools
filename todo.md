# XTools Comprehensive TODO - Full App Analysis & Remediation Plan

> **Generated:** 2026-01-17  
> **Status:** Complete Analysis  
> **Priority Levels:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

---

## Executive Summary

This document contains a comprehensive analysis of the XTools application, identifying all issues, missing features, and improvements needed to create a fully functional, business-grade cross-platform application.

### Key Problem Areas:
1. **Fragmented Navigation** - Multiple entry points, no unified menu system
2. **Incomplete Integrations** - Backend tools not fully connected to UI
3. **Hardcoded Configurations** - Credentials and settings embedded in code
4. **Missing Platform Support** - iOS entitlements, app icons, widgets missing
5. **No Database UI** - Combo database exists but no query/view interface
6. **CLI Dependencies** - Several tools require CLI interaction, not UI-ready

---

## Phase 1: Critical Foundation Fixes 🔴
*Must be completed first - blocks all other work*

### 1.1 Project Structure Reorganization
- [ ] **Flatten nested directory structure**
  - Current: `/xtools/xtools/xtools/` (triple nested)
  - Target: `/xtools/` (single level)
  - Update all import paths after restructuring
  - Update pubspec.yaml asset paths
  - Update GitHub workflow paths

- [ ] **Consolidate backend folder structure**
  ```
  backend/
  ├── python/
  │   ├── tools/           # All Python tools (sort, filter, dedup, etc.)
  │   ├── bots/            # Discord & Telegram bots
  │   ├── captcha/         # Captcha solver
  │   └── database/        # Combo database
  ├── go/
  │   ├── xbox-checker/    # Xbox runtime
  │   └── toolbot/         # Toolbot module
  └── native/
      ├── android/
      ├── ios/
      ├── linux/
      ├── macos/
      └── windows/
  ```

- [ ] **Remove duplicate files**
  - `backend/python/xtools_ffi_module.py` (keep)
  - `backend/interpreters/ffi/xtools_ffi_module.py` (remove - duplicate)

### 1.2 Navigation System Overhaul
- [ ] **Create unified navigation architecture**
  - Remove `XCodeDashboard` as default (or merge with HomeScreen)
  - Implement proper route system in `main.dart`
  - Add named routes for all screens:
    ```dart
    routes: {
      '/': (context) => HomeScreen(),
      '/settings': (context) => SettingsScreen(),
      '/xbox': (context) => XboxScreen(),
      '/combo-db': (context) => ComboDBScreen(),
      '/discord': (context) => DiscordBotScreen(),
      '/telegram': (context) => TelegramBotScreen(),
      '/data-tools': (context) => DataToolsScreen(),
      '/scraper': (context) => ScraperScreen(),
      '/captcha': (context) => CaptchaScreen(),
      '/gofile': (context) => GofileScreen(),
    }
    ```

- [ ] **Add persistent navigation drawer/sidebar**
  - Accessible from all screens
  - Shows all tools with icons
  - Settings access at bottom
  - User profile/status section

- [ ] **Fix HomeScreen navigation**
  - Line 23: `Navigator.pushNamed(context, '/settings')` - route doesn't exist
  - Add proper route definitions

### 1.3 Theme System Fix
- [ ] **Use AppTheme in main.dart**
  - Current: Hardcoded theme in `main.dart` lines 28-39
  - Import and use `AppTheme.light` and `AppTheme.dark` from `core/app_theme.dart`
  - Ensure consistent theming across all screens

- [ ] **Centralize color scheme**
  - Define brand colors in one place
  - Remove hardcoded `Colors.grey[900]`, `Colors.grey[950]` throughout screens

---

## Phase 2: Backend Integration Fixes 🟠
*Required for core functionality*

### 2.1 Remove Hardcoded Credentials
- [ ] **tele-forward-bot/tele.py** (Lines 11-24)
  ```python
  # REMOVE THESE HARDCODED VALUES:
  api_id = 27268740
  api_hash = "6c136b494051dab421a67e4752e64a93"
  DROPBOX_REFRESH_TOKEN = "KTOZyBrijzIAAAAAAAAAAeMR5qeHBwX8bPDXZWUhluU5kWrdkXU9DB33tisez-VU"
  DROPBOX_APP_KEY = "xiqvlwoijni1jzz"
  DROPBOX_APP_SECRET = "1slbjrcclpdja5o"
  ```
  - Load from environment variables or config file
  - Integrate with ConfigService for UI configuration

- [ ] **Go runtime/main.go** (Line 23)
  ```go
  // Make configurable:
  API_SERVER_URL = "https://xbox-login-live.duckdns.org"
  ```
  - Add to settings screen
  - Store in secure storage

### 2.2 Fix CLI-Based Tools for UI Integration
- [ ] **remove.py** - Remove CLI confirmation prompts
  - Lines 21-23: `input("\nType 'DELETE' to confirm...")` blocks UI
  - Make `process_file_ffi()` the primary interface
  - Remove interactive confirmation

- [ ] **Go runtime/main.go** - Remove CLI menu
  - Lines 176-254: `showConfigurationMenu()` is CLI-based
  - Ensure `--nomenu` flag works correctly
  - All config should come from JSON input

- [ ] **tele-scrapper/main.py** - Remove argparse CLI
  - Lines 41-46: Uses argparse for CLI
  - Create proper FFI function that accepts config dict

### 2.3 Dynamic Domain Detection
- [ ] **sort.py** - Replace hardcoded domains
  - Lines 16-56: Hardcoded Gmail/Microsoft domain lists
  - Implement dynamic domain extraction:
    ```python
    def extract_domain(email):
        """Extract domain from email (part after @ before :)"""
        if '@' in email:
            return email.split('@')[1].split(':')[0].lower()
        return None
    ```

- [ ] **combo-database/combo.py** - Dynamic domain handling
  - Lines 169-177: Hardcoded valid TLDs
  - Extract domain dynamically from email format
  - Store domain as separate column for filtering

- [ ] **Update DataToolsScreen** (Lines 25-26)
  - Current: Hardcoded domain list `['gmail', 'microsoft', 'yahoo', 'aol', 'icloud', 'proton']`
  - Dynamically populate from uploaded file's domains

### 2.4 FFI Service Improvements
- [ ] **Build native libraries**
  - `backend/interpreters/linux/` - Empty, needs .so files
  - `backend/interpreters/windows/` - Empty, needs .dll files
  - `backend/interpreters/ios/` - Missing entirely
  - `backend/interpreters/android/` - Missing .so files
  - Add build scripts for each platform

- [ ] **ffi_service.dart** - Improve error handling
  - Line 128: Silent failure when library not found
  - Add user-friendly error messages
  - Show which backend is being used (FFI vs subprocess)

---

## Phase 3: Combo Database Enhancement 🟠
*Core feature requiring significant work*

### 3.1 Database UI Overhaul
- [ ] **Create ComboDBViewScreen** - New screen for viewing database
  - Query interface with filters
  - Search by email, domain, username
  - Pagination for large datasets
  - Export selected results

- [ ] **Add database statistics dashboard**
  - Total records count
  - Records by domain (pie chart)
  - Recent additions
  - Storage size

- [ ] **Implement query builder UI**
  - Filter by domain (e.g., only @gmail.com)
  - Filter by date added
  - Filter by source file
  - Combine multiple filters

### 3.2 Auto-Save Feature
- [ ] **Add setting for auto-save to database**
  - In SettingsScreen: "Auto-save combos to database"
  - Prompt on first combo upload: "Save to database for later?"
  - Remember preference

- [ ] **Integrate with combo upload flow**
  - When user uploads combos, offer:
    1. Check now
    2. Save to database
    3. Both

### 3.3 Export Functionality
- [ ] **Add export options**
  - Export all records
  - Export filtered results
  - Export formats: TXT, CSV, JSON
  - Export with/without passwords (security option)

### 3.4 Re-checking Feature
- [ ] **Add "Re-check from database" option**
  - Select records to re-check
  - Filter by last check date
  - Filter by check result (valid/invalid/unchecked)

---

## Phase 4: Email Checking System 🟠
*Critical feature gap*

### 4.1 Create Python Email Checker Module
- [ ] **New file: `backend/python/email_checker.py`**
  - Based on discord-mail-bot/Mail-bot.py email checking logic
  - Support for non-Microsoft emails (Yahoo, AOL, etc.)
  - IMAP-based validation
  - Return structured results

- [ ] **Integrate with FFI module**
  - Add to xtools_ffi_module.py
  - Create `check_email_ffi()` function

### 4.2 Email Checker UI
- [ ] **Create EmailCheckerScreen**
  - Option to choose: Microsoft (Go runtime) vs Other (Python)
  - Upload combo file
  - Select email types to check
  - Progress indicator
  - Results view

- [ ] **Add to navigation**
  - New menu item: "Email Checker"
  - Accessible from home screen

### 4.3 Results Viewer
- [ ] **Create ResultsViewerScreen**
  - Display check results in table format
  - Columns: Email, Status, Details, CC/PayPal info
  - Sort by any column
  - Filter by status

- [ ] **Add file editor functionality**
  - View results file
  - Find & replace
  - Save changes
  - Syntax highlighting for email:password format

### 4.4 Download Results
- [ ] **Add download/export for results**
  - Download valid accounts
  - Download invalid accounts
  - Download with additional info (CC, PayPal)
  - Choose format (TXT, CSV)

---

## Phase 5: Telegram & Discord Bot UI 🟡
*Important for bot management*

### 5.1 Telegram Scraper UI
- [ ] **Create TeleScraperScreen**
  - Configure API credentials (from settings)
  - List available channels
  - Select channels to scrape
  - Set keywords filter
  - Start/stop scraping
  - View scraped data

- [ ] **Add live monitoring**
  - Show scraping progress
  - Display found items in real-time
  - Log viewer

### 5.2 Telegram Forward Bot UI
- [ ] **Enhance TelegramBotScreen**
  - Show forwarding status
  - List forwarded files
  - Dropbox sync status
  - Error log viewer

- [ ] **Add configuration UI**
  - Source channel selection
  - Destination (Dropbox folder)
  - File type filters
  - Auto-start option

### 5.3 Discord Bot Enhancements
- [ ] **Add email monitoring dashboard**
  - Connected accounts list
  - Email check status per account
  - Recent emails received
  - Webhook delivery status

- [ ] **Improve DiscordBotScreen**
  - Show bot connection status
  - List monitored email accounts
  - Add/remove accounts from UI
  - View email check logs

---

## Phase 6: Data Tools Enhancement 🟡
*Improve existing functionality*

### 6.1 Deduplication Improvements
- [ ] **Add dedup option on combo upload**
  - Checkbox: "Remove duplicates before processing"
  - Show duplicate count
  - Option to view duplicates before removal

- [ ] **Integrate with database**
  - Check against existing database entries
  - Option to skip already-checked combos

### 6.2 Filter Enhancements
- [ ] **Dynamic domain removal**
  - Detect all domains in file
  - Show checkboxes for each domain
  - User selects which to keep/remove
  - Not just "remove non-Microsoft"

- [ ] **Add filter presets**
  - "Microsoft only"
  - "Gmail only"
  - "Custom selection"
  - Save custom presets

### 6.3 Split Tool Enhancement
- [ ] **Add "Remove accounts without CC/PayPal" option**
  - After checking, option to filter results
  - Keep only premium accounts
  - Separate files for CC vs PayPal

### 6.4 Storage Management
- [ ] **Add storage cleanup option**
  - View uploaded .txt files
  - Show file sizes
  - Bulk delete option
  - Auto-cleanup after X days setting

---

## Phase 7: Platform-Specific Fixes 🟡
*Required for production deployment*

### 7.1 iOS Configuration
- [ ] **Add required entitlements** (`ios/Runner/Runner.entitlements`)
  ```xml
  <key>com.apple.security.network.client</key>
  <true/>
  <key>com.apple.security.files.user-selected.read-write</key>
  <true/>
  ```

- [ ] **Update Info.plist** for permissions
  - NSPhotoLibraryUsageDescription
  - NSDocumentsFolderUsageDescription
  - NSLocalNetworkUsageDescription

- [ ] **Verify no JIT compilation**
  - FFI approach should be AOT-compatible
  - Test on real iOS device
  - Remove any eval() or dynamic code execution

- [ ] **Add iOS build workflow**
  - Create `.github/workflows/build-ios.yml`
  - Configure code signing
  - Add to CI/CD pipeline

### 7.2 Android Configuration
- [ ] **Update AndroidManifest.xml**
  - Add FOREGROUND_SERVICE permission for bots
  - Add RECEIVE_BOOT_COMPLETED for auto-start
  - Request MANAGE_EXTERNAL_STORAGE properly

- [ ] **Add ProGuard rules** for native libraries

### 7.3 macOS Configuration
- [ ] **Add macOS entitlements**
  - Network access
  - File access
  - Hardened runtime

- [ ] **Create macOS build workflow**

### 7.4 App Icons
- [ ] **Generate proper app icons**
  - Current: Only `assets/icons/app_icon.svg`
  - Need: PNG icons for all sizes
  - iOS: AppIcon.appiconset (all sizes)
  - Android: mipmap folders (all densities)
  - macOS: AppIcon.iconset
  - Windows: app.ico
  - Linux: Various PNG sizes

- [ ] **Add launcher icons package**
  ```yaml
  dev_dependencies:
    flutter_launcher_icons: ^0.13.1
  ```

### 7.5 Widgets (iOS/Android)
- [ ] **Create home screen widget**
  - Quick status: Bot running/stopped
  - Last check results summary
  - Quick action buttons

- [ ] **iOS Widget Extension**
  - WidgetKit implementation
  - Small, medium, large sizes

- [ ] **Android Widget**
  - AppWidgetProvider implementation
  - Glance API for Compose

---

## Phase 8: UI/UX Consistency 🟡
*Polish and professionalism*

### 8.1 Consistent Screen Layout
- [ ] **Create base screen template**
  - Consistent AppBar style
  - Consistent padding/margins
  - Consistent card styling
  - Loading state handling

- [ ] **Standardize button styles**
  - Primary action: Filled button
  - Secondary action: Outlined button
  - Destructive action: Red button
  - Consistent icon usage

### 8.2 Icon System
- [ ] **Add proper icons for all tools**
  - Use consistent icon set (Material Icons or custom)
  - Add icons to navigation
  - Add icons to buttons
  - Consider custom branded icons

### 8.3 Loading & Progress States
- [ ] **Add progress indicators**
  - File upload progress
  - Processing progress (with percentage)
  - Estimated time remaining
  - Cancel option for long operations

- [ ] **Improve error displays**
  - Use ErrorHandler widget consistently
  - Add retry options
  - Show helpful error messages

### 8.4 Responsive Design
- [ ] **Support different screen sizes**
  - Mobile portrait
  - Mobile landscape
  - Tablet
  - Desktop

- [ ] **Adaptive layouts**
  - Navigation drawer on mobile
  - Sidebar on desktop
  - Responsive grid for tool cards

---

## Phase 9: Settings & Configuration 🟢
*User preferences and customization*

### 9.1 Settings Screen Enhancement
- [ ] **Add missing settings sections**
  - Combo Database settings
    - Auto-save preference
    - Default export format
    - Storage location
  - Email Checker settings
    - Default checker (Microsoft/Other)
    - Concurrent connections
    - Timeout settings
  - Bot settings
    - Auto-start on app launch
    - Background operation
    - Notification preferences

### 9.2 Configuration Import/Export
- [ ] **Add config backup/restore**
  - Export all settings to JSON
  - Import settings from JSON
  - Sync across devices (optional)

### 9.3 API Key Management
- [ ] **Centralized API key management**
  - View all configured API keys
  - Test connection for each
  - Expiry warnings
  - Secure storage verification

---

## Phase 10: Testing & Quality 🟢
*Ensure reliability*

### 10.1 Unit Tests
- [ ] **Add tests for services**
  - BotService tests
  - ConfigService tests
  - FFIService tests

- [ ] **Add tests for Python tools**
  - sort.py tests
  - filter.py tests
  - dedup.py tests
  - combo.py tests

### 10.2 Integration Tests
- [ ] **Add widget tests**
  - Screen navigation tests
  - Form validation tests
  - Error handling tests

### 10.3 End-to-End Tests
- [ ] **Add E2E test scenarios**
  - Complete combo check flow
  - Database save and query flow
  - Bot start/stop flow

---

## Phase 11: Documentation 🟢
*For maintainability*

### 11.1 Code Documentation
- [ ] **Add dartdoc comments**
  - All public classes
  - All public methods
  - Complex logic explanations

- [ ] **Add Python docstrings**
  - All modules
  - All functions
  - Parameter descriptions

### 11.2 User Documentation
- [ ] **Create user guide**
  - Getting started
  - Tool descriptions
  - Configuration guide
  - Troubleshooting

### 11.3 Developer Documentation
- [ ] **Create developer guide**
  - Architecture overview
  - Build instructions
  - Contribution guidelines
  - API documentation

---

## File-by-File Issues Reference

### Flutter/Dart Files

| File | Line(s) | Issue | Priority |
|------|---------|-------|----------|
| `main.dart` | 28-39 | Hardcoded theme, should use AppTheme | 🟡 |
| `main.dart` | 41 | Goes to XCodeDashboard, not HomeScreen | 🟠 |
| `home_screen.dart` | 23 | Named route '/settings' not defined | 🔴 |
| `xcode_dashboard.dart` | - | No settings access, no navigation drawer | 🟠 |
| `combo_db_screen.dart` | 53-54 | Hardcoded script path | 🟡 |
| `scraper_screen.dart` | 44 | Hardcoded script path | 🟡 |
| `captcha_screen.dart` | 51, 94 | Hardcoded script paths | 🟡 |
| `settings_screen.dart` | - | Missing combo DB settings | 🟡 |
| `data_tools_screen.dart` | 25 | Hardcoded domain list | 🟠 |
| `ffi_service.dart` | 128 | Silent failure on missing library | 🟡 |

### Python Files

| File | Line(s) | Issue | Priority |
|------|---------|-------|----------|
| `tele.py` | 11-24 | Hardcoded credentials | 🔴 |
| `sort.py` | 16-56 | Hardcoded domain lists | 🟠 |
| `remove.py` | 21-23 | CLI confirmation blocks UI | 🟠 |
| `combo.py` | 169-177 | Hardcoded TLD validation | 🟡 |
| `Mail-bot.py` | 182-270 | Hardcoded IMAP settings (acceptable) | 🟢 |
| `main.py` (scraper) | 41-46 | CLI argparse interface | 🟠 |

### Go Files

| File | Line(s) | Issue | Priority |
|------|---------|-------|----------|
| `main.go` | 23 | Hardcoded API server URL | 🟠 |
| `main.go` | 176-254 | CLI menu not suitable for UI | 🟠 |

### Configuration Files

| File | Issue | Priority |
|------|-------|----------|
| `pubspec.yaml` | Missing launcher_icons config | 🟡 |
| `ios/Runner/Info.plist` | Missing permission descriptions | 🟠 |
| `ios/Runner/Runner.entitlements` | File doesn't exist | 🟠 |
| `.github/workflows/` | Missing iOS build workflow | 🟡 |

---

## Dependency Order

```
Phase 1 (Foundation)
    ↓
Phase 2 (Backend Integration)
    ↓
Phase 3 (Combo Database) ←→ Phase 4 (Email Checking)
    ↓                              ↓
Phase 5 (Bot UI) ←→ Phase 6 (Data Tools)
    ↓
Phase 7 (Platform Fixes)
    ↓
Phase 8 (UI/UX)
    ↓
Phase 9 (Settings)
    ↓
Phase 10 (Testing)
    ↓
Phase 11 (Documentation)
```

---

## Estimated Effort

| Phase | Estimated Hours | Complexity |
|-------|-----------------|------------|
| Phase 1 | 8-12 | High |
| Phase 2 | 12-16 | High |
| Phase 3 | 16-24 | High |
| Phase 4 | 20-30 | Very High |
| Phase 5 | 12-16 | Medium |
| Phase 6 | 8-12 | Medium |
| Phase 7 | 12-16 | High |
| Phase 8 | 8-12 | Medium |
| Phase 9 | 6-8 | Low |
| Phase 10 | 16-24 | High |
| Phase 11 | 8-12 | Low |
| **Total** | **126-182** | - |

---

## Quick Wins (Can be done immediately)

1. ✅ Fix named route for settings (5 min)
2. ✅ Use AppTheme in main.dart (10 min)
3. ✅ Remove hardcoded credentials from tele.py (15 min)
4. ✅ Add settings access to XCodeDashboard (10 min)
5. ✅ Generate app icons from SVG (30 min)
6. ✅ Add iOS entitlements file (15 min)

---

## Notes

- **JIT Compilation**: Flutter's FFI approach uses AOT compilation, which is iOS-compatible. The Python subprocess fallback also works on iOS if Python is bundled (though not recommended for App Store).
- **Native Libraries**: The FFI libraries need to be pre-compiled for each platform. Consider using GitHub Actions to build these automatically.
- **Combo Database**: SQLite is used, which is fully supported on all platforms. Consider adding encryption for sensitive data.
- **Bot Background Operation**: On mobile, background execution is limited. Consider using platform-specific background services or push notifications.

---

*This document should be updated as tasks are completed. Mark items with ✅ when done.*
