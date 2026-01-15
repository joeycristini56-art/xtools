import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';

class XboxScreen extends StatefulWidget {
  const XboxScreen({super.key});

  @override
  State<XboxScreen> createState() => _XboxScreenState();
}

class _XboxScreenState extends State<XboxScreen> {
  String? _selectedFilePath;
  bool _isChecking = false;
  String? _status;
  String? _error;
  String? _result;
  String? _apiKey;

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles();

      if (result != null && result.files.single.path != null) {
        setState(() {
          _selectedFilePath = result.files.single.path;
          _status = 'Combo file selected: ${result.files.single.name}';
          _error = null;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to pick file: $e';
      });
    }
  }

  Future<void> _startChecker() async {
    if (_selectedFilePath == null) {
      setState(() {
        _error = 'Please select a combo file first';
      });
      return;
    }

    if (_apiKey == null || _apiKey!.isEmpty) {
      setState(() {
        _error = 'Please enter an API key';
      });
      return;
    }

    setState(() {
      _isChecking = true;
      _status = 'Starting Xbox checker...';
      _error = null;
      _result = null;
    });

    try {
      // Create a temporary API key file
      final apiKeyFile = File('.api_key');
      await apiKeyFile.writeAsString(_apiKey!);

      // Create config file
      final configFile = File('.config.json');
      await configFile.writeAsString('{"InputFile":"$_selectedFilePath","OutputFile":"valid.txt","MaxWorkers":1000,"TargetCPM":20000,"BatchSize":1000,"PoolSize":1000,"ResetProgress":false}');

      final scriptPath = 'backend/go/runtime/main.go';
      
      // Run Go checker
      final result = await Process.run('go', ['run', scriptPath, '--nomenu']);
      
      if (result.exitCode == 0) {
        setState(() {
          _isChecking = false;
          _status = 'Xbox check completed!';
          _result = result.stdout as String;
        });
      } else {
        setState(() {
          _isChecking = false;
          _error = result.stderr?.toString() ?? 'Checker failed';
          _status = 'Check failed';
        });
      }
    } catch (e) {
      setState(() {
        _isChecking = false;
        _error = 'Error: $e';
        _status = 'Check failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Xbox Checker'),
        actions: [
          if (_selectedFilePath != null || _apiKey != null)
            IconButton(
              icon: const Icon(Icons.clear),
              onPressed: () {
                setState(() {
                  _selectedFilePath = null;
                  _apiKey = null;
                  _status = null;
                  _error = null;
                  _result = null;
                });
              },
              tooltip: 'Clear',
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.videogame_asset, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text(
                          'Xbox Account Checker',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      decoration: const InputDecoration(
                        labelText: 'API Key',
                        hintText: 'Enter your API key',
                        prefixIcon: Icon(Icons.key),
                        border: OutlineInputBorder(),
                      ),
                      obscureText: true,
                      onChanged: (value) {
                        setState(() {
                          _apiKey = value;
                        });
                      },
                      enabled: !_isChecking,
                    ),
                    const SizedBox(height: 12),
                    if (_selectedFilePath != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.insert_drive_file, color: Colors.red),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _selectedFilePath!.split('/').last,
                                style: const TextStyle(color: Colors.red),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    if (_selectedFilePath == null)
                      const Text(
                        'No combo file selected',
                        style: TextStyle(color: Colors.grey),
                      ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isChecking ? null : _pickFile,
                            icon: const Icon(Icons.folder_open),
                            label: const Text('Select Combos'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isChecking ? null : (_selectedFilePath != null && _apiKey != null && _apiKey!.isNotEmpty ? _startChecker : null),
                            icon: _isChecking
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation(Colors.white),
                                    ),
                                  )
                                : const Icon(Icons.play_arrow),
                            label: Text(_isChecking ? 'Checking...' : 'Start Check'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _isChecking ? Colors.grey : Colors.red,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            if (_status != null || _error != null)
              Card(
                color: _error != null
                    ? Theme.of(context).colorScheme.error.withOpacity(0.1)
                    : Colors.green.withOpacity(0.1),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(
                        _error != null ? Icons.error : Icons.check_circle,
                        color: _error != null ? Theme.of(context).colorScheme.error : Colors.green,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _status ?? _error!,
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            if (_result != null)
              const SizedBox(height: 16),
            if (_result != null)
              Card(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          Icon(Icons.terminal, size: 18, color: Theme.of(context).primaryColor),
                          const SizedBox(width: 8),
                          const Text('Checker Results', style: TextStyle(fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                    Container(
                      padding: const EdgeInsets.all(12),
                      color: Theme.of(context).scaffoldBackgroundColor,
                      child: SelectableText(
                        _result!,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
