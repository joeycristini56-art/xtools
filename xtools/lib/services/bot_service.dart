import 'dart:io';
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'ffi_service.dart';

class BotService {
  final _storage = FlutterSecureStorage();
  final _ffi = FFIService();

  /// Start Discord bot
  Future<String> startDiscordBot(String token) async {
    if (token.isEmpty) throw Exception('Discord token cannot be empty');
    await _storage.write(key: 'discord_token', value: token);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('discord_token', token);

    final result = await _ffi.executePythonTool('discord_bot', token);
    if (result['success']) {
      return result['output'] ?? 'Discord bot configured via FFI';
    }
    throw Exception(result['error'] ?? 'Failed to configure Discord bot');
  }

  Future<String> stopDiscordBot() async {
    return 'Discord bot stopped';
  }

  /// Start Telegram bot
  Future<String> startTelegramBot(String apiId, String apiHash, String phone) async {
    if ([apiId, apiHash, phone].any((e) => e.isEmpty)) {
      throw Exception('Telegram credentials cannot be empty');
    }
    await _storage.write(key: 'telegram_api_id', value: apiId);
    await _storage.write(key: 'telegram_api_hash', value: apiHash);
    await _storage.write(key: 'telegram_phone', value: phone);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('telegram_api_id', apiId);
    await prefs.setString('telegram_api_hash', apiHash);
    await prefs.setString('telegram_phone', phone);

    final config = jsonEncode({'api_id': apiId, 'api_hash': apiHash, 'phone': phone});
    final result = await _ffi.executePythonTool('telegram_bot', config);
    if (result['success']) {
      return result['output'] ?? 'Telegram bot configured via FFI';
    }
    throw Exception(result['error'] ?? 'Failed to configure Telegram bot');
  }

  Future<String> stopTelegramBot() async {
    return 'Telegram bot stopped';
  }

  /// Execute any tool via FFI
  Future<Map<String, dynamic>> executeTool(String tool, [Map<String, dynamic>? params]) async {
    if (params == null) params = {};

    // Determine input based on params
    String input;
    if (params.containsKey('file')) {
      input = params['file'];
    } else if (params.containsKey('url')) {
      input = params['url'];
    } else if (params.containsKey('image')) {
      input = params['image'];
    } else if (params.containsKey('api_id')) {
      // Telegram config
      input = jsonEncode(params);
    } else if (params.containsKey('token')) {
      // Discord token
      input = params['token'];
    } else {
      input = jsonEncode(params);
    }

    // Execute via FFI
    final result = await _ffi.executePythonTool(tool, input);
    
    if (result['success']) {
      return result;
    }
    
    throw Exception(result['error'] ?? 'Tool execution failed');
  }
}
