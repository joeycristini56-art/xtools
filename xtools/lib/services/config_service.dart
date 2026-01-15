import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ConfigService {
  final FlutterSecureStorage _storage;
  final Future<SharedPreferences> _prefs;

  // Default constructor
  ConfigService()
      : _storage = FlutterSecureStorage(),
        _prefs = SharedPreferences.getInstance();

  // Constructor with dependencies (for testing or custom initialization)
  ConfigService.withDependencies(this._storage, this._prefs);

  // Discord
  Future<void> saveDiscordToken(String token) async {
    await _storage.write(key: 'discord_token', value: token);
    final prefs = await _prefs;
    await prefs.setString('discord_token', token);
  }

  Future<String?> getDiscordToken() async {
    return await _storage.read(key: 'discord_token');
  }

  // Telegram
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

  // Dropbox
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

  // Theme
  Future<void> saveThemeMode(String mode) async {
    final prefs = await _prefs;
    await prefs.setString('theme_mode', mode);
  }

  Future<String> getThemeMode() async {
    final prefs = await _prefs;
    return prefs.getString('theme_mode') ?? 'system';
  }
}
