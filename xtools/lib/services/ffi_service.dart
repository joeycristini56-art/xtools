import "dart:convert";
import 'dart:ffi';
import 'dart:io';
import 'package:ffi/ffi.dart';

/// XTools FFI Service - True native integration
class FFIService {
  static final FFIService _instance = FFIService._internal();
  factory FFIService() => _instance;

  DynamicLibrary? _pythonLib;
  DynamicLibrary? _goLib;
  DynamicLibrary? _toolbotLib;

  FFIService._internal();

  /// Load Python FFI library
  bool loadPythonLib() {
    if (_pythonLib != null) return true;

    try {
      String libPath;
      if (Platform.isLinux) {
        libPath = 'backend/interpreters/linux/xtools_ffi.so';
      } else if (Platform.isWindows) {
        libPath = 'backend/interpreters/windows/xtools_ffi.dll';
      } else if (Platform.isIOS) {
        libPath = 'backend/interpreters/ios/frameworks/xtools_ffi.framework/xtools_ffi';
      } else {
        return false;
      }

      _pythonLib = DynamicLibrary.open(libPath);
      return true;
    } catch (e) {
      print('Failed to load Python lib: $e');
      return false;
    }
  }

  /// Load Go FFI library
  bool loadGoLib() {
    if (_goLib != null) return true;

    try {
      String libPath;
      if (Platform.isLinux) {
        libPath = 'backend/interpreters/linux/libxboxchecker.so';
      } else if (Platform.isWindows) {
        libPath = 'backend/interpreters/windows/libxboxchecker.dll';
      } else if (Platform.isIOS) {
        libPath = 'backend/interpreters/ios/frameworks/libxboxchecker.framework/libxboxchecker';
      } else {
        return false;
      }

      _goLib = DynamicLibrary.open(libPath);
      return true;
    } catch (e) {
      print('Go lib not available: $e');
      return false;
    }
  }

  /// Load Toolbot Go library
  bool loadToolbotLib() {
    if (_toolbotLib != null) return true;

    try {
      String libPath;
      if (Platform.isLinux) {
        libPath = 'backend/interpreters/linux/libtoolbot.so';
      } else if (Platform.isWindows) {
        libPath = 'backend/interpreters/windows/libtoolbot.dll';
      } else if (Platform.isIOS) {
        libPath = 'backend/interpreters/ios/frameworks/libtoolbot.framework/libtoolbot';
      } else {
        return false;
      }

      _toolbotLib = DynamicLibrary.open(libPath);
      return true;
    } catch (e) {
      print('Toolbot lib not available: $e');
      return false;
    }
  }

  /// Execute Python tool via FFI
  Future<Map<String, dynamic>> executePythonTool(String toolName, String input) async {
    if (!loadPythonLib()) {
      return {'success': false, 'error': 'Python library not loaded'};
    }

    try {
      final functionNames = {
        'gofile': 'gofile_upload',
        'scraper': 'run_scraper',
        'sort': 'run_sort',
        'filter': 'run_filter',
        'dedup': 'run_dedup',
        'split': 'run_split',
        'combo': 'run_combo',
        'captcha': 'run_captcha',
        'discord_bot': 'discord_bot',
        'telegram_bot': 'telegram_bot',
      };

      final functionName = functionNames[toolName];
      if (functionName == null) {
        return {'success': false, 'error': 'Unknown tool: $toolName'};
      }

      final executeTool = _pythonLib!.lookupFunction<
        Pointer<Utf8> Function(Pointer<Utf8> input),
        Pointer<Utf8> Function(Pointer<Utf8> input)
      >(functionName);

      final inputPtr = input.toNativeUtf8();
      final resultPtr = executeTool(inputPtr);
      final result = resultPtr.toDartString();

      malloc.free(inputPtr);

      try {
        return jsonDecode(result);
      } catch (e) {
        return {'success': false, 'error': 'Invalid response: $result'};
      }
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Execute Go tool via FFI
  Future<Map<String, dynamic>> executeGoTool(String toolName, String input) async {
    if (!loadGoLib()) {
      return {'success': false, 'error': 'Go library not loaded'};
    }

    try {
      final executeTool = _goLib!.lookupFunction<
        Pointer<Utf8> Function(Pointer<Utf8> input),
        Pointer<Utf8> Function(Pointer<Utf8> input)
      >('CheckXboxAccount');

      final inputPtr = input.toNativeUtf8();
      final resultPtr = executeTool(inputPtr);
      final result = resultPtr.toDartString();

      malloc.free(inputPtr);

      try {
        return jsonDecode(result);
      } catch (e) {
        return {'success': false, 'error': 'Invalid response: $result'};
      }
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Execute Toolbot via FFI
  Future<Map<String, dynamic>> executeToolbot(String toolName, String input) async {
    if (!loadToolbotLib()) {
      return {'success': false, 'error': 'Toolbot library not loaded'};
    }

    try {
      final executeTool = _toolbotLib!.lookupFunction<
        Pointer<Utf8> Function(Pointer<Utf8> input),
        Pointer<Utf8> Function(Pointer<Utf8> input)
      >('InitializeToolbot');

      final inputPtr = input.toNativeUtf8();
      final resultPtr = executeTool(inputPtr);
      final result = resultPtr.toDartString();

      malloc.free(inputPtr);

      try {
        return jsonDecode(result);
      } catch (e) {
        return {'success': false, 'error': 'Invalid response: $result'};
      }
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }
}
