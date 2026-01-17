import "dart:convert";
import 'dart:ffi';
import 'dart:io';
import 'package:ffi/ffi.dart';
import 'package:path/path.dart' as path;

/// XTools FFI Service - Production-grade native integration
/// Supports both FFI (native libraries) and fallback to Python subprocess
class FFIService {
  static final FFIService _instance = FFIService._internal();
  factory FFIService() => _instance;

  DynamicLibrary? _pythonLib;
  DynamicLibrary? _goLib;
  DynamicLibrary? _toolbotLib;
  bool _ffiAvailable = false;
  String? _backendPath;
  String? _lastError;

  FFIService._internal() {
    _initBackendPath();
  }

  void _initBackendPath() {
    // Determine backend path based on platform and execution context
    final execDir = path.dirname(Platform.resolvedExecutable);
    final possiblePaths = [
      path.join(execDir, 'data', 'flutter_assets', 'backend'),
      path.join(execDir, 'backend'),
      path.join(execDir, '..', 'backend'),
      path.join(execDir, '..', 'lib', 'backend'),
      path.join(Directory.current.path, 'backend'),
      'backend',
      // For development
      path.join(Directory.current.path, '..', 'backend'),
    ];

    for (final p in possiblePaths) {
      final absPath = path.normalize(path.absolute(p));
      if (Directory(absPath).existsSync()) {
        _backendPath = absPath;
        break;
      }
    }
  }

  String get backendPath => _backendPath ?? 'backend';
  String? get lastError => _lastError;
  
  /// Check if all required libraries are available
  Future<Map<String, bool>> checkLibraryStatus() async {
    final status = <String, bool>{};
    
    // Check Python FFI library
    String pythonLibPath;
    if (Platform.isLinux) {
      pythonLibPath = path.join(backendPath, 'interpreters/linux/xtools_ffi.so');
    } else if (Platform.isWindows) {
      pythonLibPath = path.join(backendPath, 'interpreters/windows/xtools_ffi.dll');
    } else if (Platform.isMacOS) {
      pythonLibPath = path.join(backendPath, 'interpreters/macos/xtools_ffi.dylib');
    } else {
      pythonLibPath = '';
    }
    status['python_ffi'] = pythonLibPath.isNotEmpty && File(pythonLibPath).existsSync();
    
    // Check Go Xbox checker library
    String goLibPath;
    if (Platform.isLinux) {
      goLibPath = path.join(backendPath, 'interpreters/linux/libxboxchecker.so');
    } else if (Platform.isWindows) {
      goLibPath = path.join(backendPath, 'interpreters/windows/libxboxchecker.dll');
    } else if (Platform.isMacOS) {
      goLibPath = path.join(backendPath, 'interpreters/macos/libxboxchecker.dylib');
    } else {
      goLibPath = '';
    }
    status['go_xbox'] = goLibPath.isNotEmpty && File(goLibPath).existsSync();
    
    // Check Toolbot library
    String toolbotLibPath;
    if (Platform.isLinux) {
      toolbotLibPath = path.join(backendPath, 'interpreters/linux/libtoolbot.so');
    } else if (Platform.isWindows) {
      toolbotLibPath = path.join(backendPath, 'interpreters/windows/libtoolbot.dll');
    } else if (Platform.isMacOS) {
      toolbotLibPath = path.join(backendPath, 'interpreters/macos/libtoolbot.dylib');
    } else {
      toolbotLibPath = '';
    }
    status['toolbot'] = toolbotLibPath.isNotEmpty && File(toolbotLibPath).existsSync();
    
    // Check Python module
    final pythonModule = path.join(backendPath, 'python/xtools_ffi_module.py');
    status['python_module'] = File(pythonModule).existsSync();
    
    return status;
  }

  /// Load Python FFI library
  bool loadPythonLib() {
    if (_pythonLib != null) return true;

    try {
      String libPath;
      if (Platform.isLinux) {
        libPath = path.join(backendPath, 'interpreters/linux/xtools_ffi.so');
      } else if (Platform.isWindows) {
        libPath = path.join(backendPath, 'interpreters/windows/xtools_ffi.dll');
      } else if (Platform.isMacOS) {
        libPath = path.join(backendPath, 'interpreters/macos/xtools_ffi.dylib');
      } else if (Platform.isIOS) {
        libPath = path.join(backendPath, 'interpreters/ios/frameworks/xtools_ffi.framework/xtools_ffi');
      } else if (Platform.isAndroid) {
        // On Android, libraries are loaded from the app's native library directory
        libPath = 'libxtools_ffi.so';
      } else {
        _lastError = 'Unsupported platform for Python FFI';
        return false;
      }

      if (Platform.isAndroid || File(libPath).existsSync()) {
        _pythonLib = DynamicLibrary.open(libPath);
        _ffiAvailable = true;
        _lastError = null;
        return true;
      }
      _lastError = 'Python FFI library not found at: $libPath';
      return false;
    } catch (e) {
      _lastError = 'Failed to load Python lib: $e';
      print(_lastError);
      return false;
    }
  }

  /// Load Go FFI library
  bool loadGoLib() {
    if (_goLib != null) return true;

    try {
      String libPath;
      if (Platform.isLinux) {
        libPath = path.join(backendPath, 'interpreters/linux/libxboxchecker.so');
      } else if (Platform.isWindows) {
        libPath = path.join(backendPath, 'interpreters/windows/libxboxchecker.dll');
      } else if (Platform.isMacOS) {
        libPath = path.join(backendPath, 'interpreters/macos/libxboxchecker.dylib');
      } else if (Platform.isIOS) {
        libPath = path.join(backendPath, 'interpreters/ios/frameworks/libxboxchecker.framework/libxboxchecker');
      } else if (Platform.isAndroid) {
        libPath = 'libxboxchecker.so';
      } else {
        _lastError = 'Unsupported platform for Go FFI';
        return false;
      }

      if (Platform.isAndroid || File(libPath).existsSync()) {
        _goLib = DynamicLibrary.open(libPath);
        _lastError = null;
        return true;
      }
      _lastError = 'Go library not found at: $libPath';
      return false;
    } catch (e) {
      _lastError = 'Go lib not available: $e';
      print(_lastError);
      return false;
    }
  }

  /// Load Toolbot Go library
  bool loadToolbotLib() {
    if (_toolbotLib != null) return true;

    try {
      String libPath;
      if (Platform.isLinux) {
        libPath = path.join(backendPath, 'interpreters/linux/libtoolbot.so');
      } else if (Platform.isWindows) {
        libPath = path.join(backendPath, 'interpreters/windows/libtoolbot.dll');
      } else if (Platform.isMacOS) {
        libPath = path.join(backendPath, 'interpreters/macos/libtoolbot.dylib');
      } else if (Platform.isIOS) {
        libPath = path.join(backendPath, 'interpreters/ios/frameworks/libtoolbot.framework/libtoolbot');
      } else if (Platform.isAndroid) {
        libPath = 'libtoolbot.so';
      } else {
        _lastError = 'Unsupported platform for Toolbot';
        return false;
      }

      if (Platform.isAndroid || File(libPath).existsSync()) {
        _toolbotLib = DynamicLibrary.open(libPath);
        _lastError = null;
        return true;
      }
      _lastError = 'Toolbot library not found at: $libPath';
      return false;
    } catch (e) {
      _lastError = 'Toolbot lib not available: $e';
      print(_lastError);
      return false;
    }
  }

  /// Execute Python tool - tries FFI first, falls back to subprocess
  Future<Map<String, dynamic>> executePythonTool(String toolName, String input) async {
    // Try FFI first
    if (loadPythonLib()) {
      try {
        final result = await _executePythonToolFFI(toolName, input);
        if (result['success'] == true) return result;
      } catch (e) {
        print('FFI execution failed, falling back to subprocess: $e');
      }
    }

    // Fallback to subprocess
    return await _executePythonToolSubprocess(toolName, input);
  }

  Future<Map<String, dynamic>> _executePythonToolFFI(String toolName, String input) async {
    final functionNames = {
      'gofile': 'gofile_upload',
      'scraper': 'run_scraper',
      'sort': 'run_sort',
      'filter': 'run_filter',
      'dedup': 'run_dedup',
      'split': 'run_split',
      'remove': 'run_remove',
      'combo': 'run_combo',
      'captcha': 'run_captcha',
      'discord_bot': 'discord_bot',
      'telegram_bot': 'telegram_bot',
    };

    final functionName = functionNames[toolName];
    if (functionName == null) {
      return {'success': false, 'error': 'Unknown tool: $toolName'};
    }

    try {
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

  Future<Map<String, dynamic>> _executePythonToolSubprocess(String toolName, String input) async {
    try {
      final pythonScript = path.join(backendPath, 'python/xtools_ffi_module.py');
      
      if (!File(pythonScript).existsSync()) {
        return {'success': false, 'error': 'Python module not found at $pythonScript'};
      }

      // Determine Python executable
      final pythonExe = Platform.isWindows ? 'python' : 'python3';

      final result = await Process.run(
        pythonExe,
        [pythonScript, toolName, input],
        workingDirectory: path.join(backendPath, 'python'),
      );

      if (result.exitCode == 0) {
        try {
          final output = result.stdout.toString().trim();
          return jsonDecode(output);
        } catch (e) {
          return {
            'success': true,
            'output': result.stdout.toString(),
          };
        }
      } else {
        return {
          'success': false,
          'error': result.stderr.toString().isNotEmpty 
              ? result.stderr.toString() 
              : 'Process exited with code ${result.exitCode}',
        };
      }
    } catch (e) {
      return {'success': false, 'error': 'Subprocess execution failed: $e'};
    }
  }

  /// Execute Go tool via FFI or subprocess
  Future<Map<String, dynamic>> executeGoTool(String toolName, String input) async {
    // Try FFI first
    if (loadGoLib()) {
      try {
        return await _executeGoToolFFI(toolName, input);
      } catch (e) {
        print('Go FFI execution failed, falling back to subprocess: $e');
      }
    }

    // Fallback to subprocess
    return await _executeGoToolSubprocess(toolName, input);
  }

  Future<Map<String, dynamic>> _executeGoToolFFI(String toolName, String input) async {
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

  Future<Map<String, dynamic>> _executeGoToolSubprocess(String toolName, String input) async {
    try {
      final goScript = path.join(backendPath, 'go/runtime/main.go');
      
      if (!File(goScript).existsSync()) {
        return {'success': false, 'error': 'Go module not found at $goScript'};
      }

      // Parse input JSON to get config
      Map<String, dynamic> config;
      try {
        config = jsonDecode(input);
      } catch (e) {
        return {'success': false, 'error': 'Invalid input JSON'};
      }

      // Write API key file
      final apiKey = config['api_key'] ?? '';
      if (apiKey.isNotEmpty) {
        await File('.api_key').writeAsString(apiKey);
      }

      // Write config file
      final configFile = File('.config.json');
      await configFile.writeAsString(jsonEncode({
        'InputFile': config['combo_file'] ?? 'combos.txt',
        'OutputFile': config['output_file'] ?? 'valid.txt',
        'MaxWorkers': config['max_workers'] ?? 1000,
        'TargetCPM': config['target_cpm'] ?? 20000,
        'BatchSize': config['batch_size'] ?? 1000,
        'PoolSize': config['pool_size'] ?? 1000,
        'ResetProgress': config['reset_progress'] ?? false,
      }));

      final result = await Process.run(
        'go',
        ['run', goScript, '--nomenu'],
        workingDirectory: path.join(backendPath, 'go/runtime'),
      );

      if (result.exitCode == 0) {
        return {
          'success': true,
          'output': result.stdout.toString(),
          'message': 'Xbox checker completed',
        };
      } else {
        return {
          'success': false,
          'error': result.stderr.toString().isNotEmpty 
              ? result.stderr.toString() 
              : 'Process exited with code ${result.exitCode}',
        };
      }
    } catch (e) {
      return {'success': false, 'error': 'Go subprocess execution failed: $e'};
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

  /// Get status of all available tools
  Future<Map<String, dynamic>> getToolStatus() async {
    final libStatus = await checkLibraryStatus();
    return {
      'success': true,
      'ffi_available': _ffiAvailable,
      'python_lib_loaded': _pythonLib != null,
      'go_lib_loaded': _goLib != null,
      'toolbot_lib_loaded': _toolbotLib != null,
      'backend_path': backendPath,
      'last_error': _lastError,
      'library_status': libStatus,
      'platform': Platform.operatingSystem,
    };
  }
  
  /// Initialize all libraries
  Future<Map<String, dynamic>> initializeAll() async {
    final results = <String, dynamic>{};
    
    results['python'] = loadPythonLib();
    results['go'] = loadGoLib();
    results['toolbot'] = loadToolbotLib();
    results['backend_path'] = backendPath;
    results['last_error'] = _lastError;
    
    return results;
  }
}
