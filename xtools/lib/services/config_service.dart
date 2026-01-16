import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// ConfigService - Production-grade configuration management
/// Handles secure storage of API keys, credentials, and app settings
class ConfigService {
  final FlutterSecureStorage _storage;
  final Future<SharedPreferences> _prefs;

  // Default constructor
  ConfigService()
      : _storage = const FlutterSecureStorage(),
        _prefs = SharedPreferences.getInstance();

  // Constructor with dependencies (for testing or custom initialization)
  ConfigService.withDependencies(this._storage, this._prefs);

  // ============================================================================
  // DISCORD
  // ============================================================================

  Future<void> saveDiscordToken(String token) async {
    await _storage.write(key: 'discord_token', value: token);
    final prefs = await _prefs;
    await prefs.setString('discord_token', token);
  }

  Future<String?> getDiscordToken() async {
    return await _storage.read(key: 'discord_token');
  }

  Future<void> saveDiscordIMAPConfig(String host, String user, String pass, String channelId) async {
    await _storage.write(key: 'discord_imap_host', value: host);
    await _storage.write(key: 'discord_imap_user', value: user);
    await _storage.write(key: 'discord_imap_pass', value: pass);
    await _storage.write(key: 'discord_channel_id', value: channelId);
  }

  Future<Map<String, String?>> getDiscordIMAPConfig() async {
    return {
      'host': await _storage.read(key: 'discord_imap_host'),
      'user': await _storage.read(key: 'discord_imap_user'),
      'pass': await _storage.read(key: 'discord_imap_pass'),
      'channelId': await _storage.read(key: 'discord_channel_id'),
    };
  }

  // ============================================================================
  // TELEGRAM
  // ============================================================================

  Future<void> saveTelegramCredentials(String apiId, String apiHash, String phone) async {
    await _storage.write(key: 'telegram_api_id', value: apiId);
    await _storage.write(key: 'telegram_api_hash', value: apiHash);
    await _storage.write(key: 'telegram_phone', value: phone);
    final prefs = await _prefs;
    await prefs.setString('telegram_api_id', apiId);
    await prefs.setString('telegram_api_hash', apiHash);
    await prefs.setString('telegram_phone', phone);
  }

  Future<Map<String, String?>> getTelegramCredentials() async {
    return {
      'apiId': await _storage.read(key: 'telegram_api_id'),
      'apiHash': await _storage.read(key: 'telegram_api_hash'),
      'phone': await _storage.read(key: 'telegram_phone'),
    };
  }

  Future<void> saveTelegramChannels(List<String> channelIds) async {
    final prefs = await _prefs;
    await prefs.setStringList('telegram_channels', channelIds);
  }

  Future<List<String>> getTelegramChannels() async {
    final prefs = await _prefs;
    return prefs.getStringList('telegram_channels') ?? [];
  }

  // ============================================================================
  // DROPBOX
  // ============================================================================

  Future<void> saveDropboxCredentials(String appKey, String appSecret, String refreshToken) async {
    await _storage.write(key: 'dropbox_app_key', value: appKey);
    await _storage.write(key: 'dropbox_app_secret', value: appSecret);
    await _storage.write(key: 'dropbox_refresh_token', value: refreshToken);
    final prefs = await _prefs;
    await prefs.setString('dropbox_app_key', appKey);
    await prefs.setString('dropbox_app_secret', appSecret);
    await prefs.setString('dropbox_refresh_token', refreshToken);
  }

  Future<Map<String, String?>> getDropboxCredentials() async {
    return {
      'appKey': await _storage.read(key: 'dropbox_app_key'),
      'appSecret': await _storage.read(key: 'dropbox_app_secret'),
      'refreshToken': await _storage.read(key: 'dropbox_refresh_token'),
    };
  }

  // ============================================================================
  // XBOX CHECKER
  // ============================================================================

  Future<void> saveXboxAPIKey(String apiKey) async {
    await _storage.write(key: 'xbox_api_key', value: apiKey);
  }

  Future<String?> getXboxAPIKey() async {
    return await _storage.read(key: 'xbox_api_key');
  }

  Future<void> saveXboxConfig({
    int? maxWorkers,
    int? targetCPM,
    int? batchSize,
    int? poolSize,
  }) async {
    final prefs = await _prefs;
    if (maxWorkers != null) await prefs.setInt('xbox_max_workers', maxWorkers);
    if (targetCPM != null) await prefs.setInt('xbox_target_cpm', targetCPM);
    if (batchSize != null) await prefs.setInt('xbox_batch_size', batchSize);
    if (poolSize != null) await prefs.setInt('xbox_pool_size', poolSize);
  }

  Future<Map<String, int>> getXboxConfig() async {
    final prefs = await _prefs;
    return {
      'maxWorkers': prefs.getInt('xbox_max_workers') ?? 1000,
      'targetCPM': prefs.getInt('xbox_target_cpm') ?? 20000,
      'batchSize': prefs.getInt('xbox_batch_size') ?? 1000,
      'poolSize': prefs.getInt('xbox_pool_size') ?? 1000,
    };
  }

  // ============================================================================
  // CAPTCHA
  // ============================================================================

  Future<void> saveCaptchaAPIKey(String apiKey) async {
    await _storage.write(key: 'captcha_api_key', value: apiKey);
  }

  Future<String?> getCaptchaAPIKey() async {
    return await _storage.read(key: 'captcha_api_key');
  }

  // ============================================================================
  // GOFILE
  // ============================================================================

  Future<void> saveGoFileToken(String token) async {
    await _storage.write(key: 'gofile_token', value: token);
  }

  Future<String?> getGoFileToken() async {
    return await _storage.read(key: 'gofile_token');
  }

  // ============================================================================
  // THEME
  // ============================================================================

  Future<void> saveThemeMode(String mode) async {
    final prefs = await _prefs;
    await prefs.setString('theme_mode', mode);
  }

  Future<String> getThemeMode() async {
    final prefs = await _prefs;
    return prefs.getString('theme_mode') ?? 'system';
  }

  // ============================================================================
  // UTILITY
  // ============================================================================

  /// Clear all stored credentials (for logout/reset)
  Future<void> clearAllCredentials() async {
    await _storage.deleteAll();
    final prefs = await _prefs;
    await prefs.clear();
  }

  /// Check if initial setup is complete
  Future<bool> isSetupComplete() async {
    final prefs = await _prefs;
    return prefs.getBool('setup_complete') ?? false;
  }

  /// Mark setup as complete
  Future<void> setSetupComplete(bool complete) async {
    final prefs = await _prefs;
    await prefs.setBool('setup_complete', complete);
  }

  /// Get all configured services status
  Future<Map<String, bool>> getConfiguredServices() async {
    return {
      'discord': (await getDiscordToken()) != null,
      'telegram': (await getTelegramCredentials())['apiId'] != null,
      'dropbox': (await getDropboxCredentials())['appKey'] != null,
      'xbox': (await getXboxAPIKey()) != null,
      'captcha': (await getCaptchaAPIKey()) != null,
      'gofile': (await getGoFileToken()) != null,
    };
  }
}
