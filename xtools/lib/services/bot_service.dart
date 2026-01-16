import 'dart:io';
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'ffi_service.dart';
import 'config_service.dart';

/// BotService - Production-grade service for managing all XTools operations
class BotService {
  final _storage = const FlutterSecureStorage();
  final _ffi = FFIService();
  final _config = ConfigService();

  // ============================================================================
  // DISCORD BOT
  // ============================================================================

  /// Start Discord bot with full configuration
  Future<Map<String, dynamic>> startDiscordBot({
    required String token,
    String? imapHost,
    String? imapUser,
    String? imapPass,
    String? channelId,
  }) async {
    if (token.isEmpty) {
      return {'success': false, 'error': 'Discord token cannot be empty'};
    }

    // Save credentials
    await _config.saveDiscordToken(token);
    if (imapHost != null && imapUser != null && imapPass != null) {
      await _config.saveDiscordIMAPConfig(imapHost, imapUser, imapPass, channelId ?? '');
    }

    final config = jsonEncode({
      'token': token,
      'imap_host': imapHost ?? '',
      'imap_user': imapUser ?? '',
      'imap_pass': imapPass ?? '',
      'channel_id': channelId ?? '',
    });

    return await _ffi.executePythonTool('discord_bot', config);
  }

  Future<Map<String, dynamic>> stopDiscordBot() async {
    return await _ffi.executePythonTool('discord_bot_stop', '{}');
  }

  // ============================================================================
  // TELEGRAM BOT
  // ============================================================================

  /// Start Telegram bot with full configuration
  Future<Map<String, dynamic>> startTelegramBot({
    required String apiId,
    required String apiHash,
    required String phone,
    List<String>? channelIds,
    Map<String, String>? dropboxConfig,
  }) async {
    if ([apiId, apiHash, phone].any((e) => e.isEmpty)) {
      return {'success': false, 'error': 'Telegram credentials cannot be empty'};
    }

    // Save credentials
    await _config.saveTelegramCredentials(apiId, apiHash, phone);

    final config = jsonEncode({
      'api_id': apiId,
      'api_hash': apiHash,
      'phone': phone,
      'channel_ids': channelIds ?? [],
      'dropbox': dropboxConfig ?? {},
    });

    return await _ffi.executePythonTool('telegram_bot', config);
  }

  Future<Map<String, dynamic>> stopTelegramBot() async {
    return await _ffi.executePythonTool('telegram_bot_stop', '{}');
  }

  // ============================================================================
  // FILE PROCESSING TOOLS
  // ============================================================================

  /// Sort/extract emails by domain
  Future<Map<String, dynamic>> sortEmails(String filePath, {List<String>? domains}) async {
    if (!await File(filePath).exists()) {
      return {'success': false, 'error': 'File not found: $filePath'};
    }

    final input = domains != null && domains.isNotEmpty
        ? '$filePath|${domains.join(',')}'
        : filePath;

    return await _ffi.executePythonTool('sort', input);
  }

  /// Filter/deduplicate lines
  Future<Map<String, dynamic>> filterFile(String filePath) async {
    if (!await File(filePath).exists()) {
      return {'success': false, 'error': 'File not found: $filePath'};
    }
    return await _ffi.executePythonTool('filter', filePath);
  }

  /// Deduplicate valid files
  Future<Map<String, dynamic>> deduplicateFiles(String pathOrDir) async {
    return await _ffi.executePythonTool('dedup', pathOrDir);
  }

  /// Split/filter for CC/PayPal
  Future<Map<String, dynamic>> splitForPremium(String pathOrDir) async {
    return await _ffi.executePythonTool('split', pathOrDir);
  }

  /// Remove lines matching pattern
  Future<Map<String, dynamic>> removePattern(String filePath, String pattern) async {
    if (!await File(filePath).exists()) {
      return {'success': false, 'error': 'File not found: $filePath'};
    }
    if (pattern.isEmpty) {
      return {'success': false, 'error': 'Pattern cannot be empty'};
    }
    return await _ffi.executePythonTool('remove', '$filePath|$pattern');
  }

  // ============================================================================
  // FILE UPLOAD
  // ============================================================================

  /// Upload file to GoFile
  Future<Map<String, dynamic>> uploadToGoFile(String filePath) async {
    if (!await File(filePath).exists()) {
      return {'success': false, 'error': 'File not found: $filePath'};
    }
    return await _ffi.executePythonTool('gofile', filePath);
  }

  // ============================================================================
  // SCRAPING
  // ============================================================================

  /// Scrape URL for combos
  Future<Map<String, dynamic>> scrapeUrl(String url) async {
    if (url.isEmpty) {
      return {'success': false, 'error': 'URL cannot be empty'};
    }
    final config = jsonEncode({'type': 'web', 'url': url});
    return await _ffi.executePythonTool('scraper', config);
  }

  /// Scrape Telegram channels
  Future<Map<String, dynamic>> scrapeTelegram({
    required String apiId,
    required String apiHash,
    required String phone,
    required Map<String, List<String>> channels,
    List<String>? keywords,
  }) async {
    final config = jsonEncode({
      'type': 'telegram',
      'api_id': apiId,
      'api_hash': apiHash,
      'phone': phone,
      'channels': channels,
      'keywords': keywords ?? [],
    });
    return await _ffi.executePythonTool('scraper', config);
  }

  // ============================================================================
  // XBOX CHECKER
  // ============================================================================

  /// Run Xbox account checker
  Future<Map<String, dynamic>> checkXboxAccounts({
    required String apiKey,
    required String comboFile,
    String? outputFile,
    int? maxWorkers,
    int? targetCPM,
    int? batchSize,
    int? poolSize,
    bool? resetProgress,
  }) async {
    if (apiKey.isEmpty) {
      return {'success': false, 'error': 'API key cannot be empty'};
    }
    if (!await File(comboFile).exists()) {
      return {'success': false, 'error': 'Combo file not found: $comboFile'};
    }

    // Save API key
    await _config.saveXboxAPIKey(apiKey);

    final config = jsonEncode({
      'api_key': apiKey,
      'combo_file': comboFile,
      'output_file': outputFile ?? 'valid.txt',
      'max_workers': maxWorkers ?? 1000,
      'target_cpm': targetCPM ?? 20000,
      'batch_size': batchSize ?? 1000,
      'pool_size': poolSize ?? 1000,
      'reset_progress': resetProgress ?? false,
    });

    return await _ffi.executeGoTool('xbox', config);
  }

  // ============================================================================
  // COMBO DATABASE
  // ============================================================================

  /// Process combo file into database
  Future<Map<String, dynamic>> processComboDatabase(String filePath) async {
    if (!await File(filePath).exists()) {
      return {'success': false, 'error': 'File not found: $filePath'};
    }
    return await _ffi.executePythonTool('combo', filePath);
  }

  // ============================================================================
  // CAPTCHA SOLVING
  // ============================================================================

  /// Solve CAPTCHA
  Future<Map<String, dynamic>> solveCaptcha({
    required String type,
    String? imagePath,
    String? siteKey,
    String? pageUrl,
    String? apiKey,
  }) async {
    final config = jsonEncode({
      'type': type,
      'image_path': imagePath ?? '',
      'site_key': siteKey ?? '',
      'page_url': pageUrl ?? '',
      'api_key': apiKey ?? '',
    });
    return await _ffi.executePythonTool('captcha', config);
  }

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  /// Get status of all tools
  Future<Map<String, dynamic>> getToolStatus() async {
    return await _ffi.getToolStatus();
  }

  /// Generic tool execution
  Future<Map<String, dynamic>> executeTool(String tool, [Map<String, dynamic>? params]) async {
    params ??= {};
    final input = jsonEncode(params);
    
    // Route to appropriate backend
    if (tool == 'xbox') {
      return await _ffi.executeGoTool(tool, input);
    }
    return await _ffi.executePythonTool(tool, input);
  }
}
