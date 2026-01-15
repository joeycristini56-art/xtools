import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';

class CaptchaScreen extends StatefulWidget {
  const CaptchaScreen({super.key});

  @override
  State<CaptchaScreen> createState() => _CaptchaScreenState();
}

class _CaptchaScreenState extends State<CaptchaScreen> {
  String? _selectedFilePath;
  bool _isSolving = false;
  String? _status;
  String? _error;
  String? _result;

  @override
  void initState() {
    super.initState();
  }

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles();

      if (result != null && result.files.single.path != null) {
        setState(() {
          _selectedFilePath = result.files.single.path;
          _status = 'Captcha image selected: ${result.files.single.name}';
          _error = null;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to pick file: $e';
      });
    }
  }

  Future<void> _startServer() async {
    setState(() {
      _isSolving = true;
      _status = 'Starting CAPTCHA solver server...';
      _error = null;
      _result = null;
    });

    try {
      final scriptPath = 'backend/python/captcha-solver/__main__.py';
      final result = await Process.run('python3', [scriptPath]);
      
      if (result.exitCode == 0) {
        setState(() {
          _isSolving = false;
          _status = 'Server started successfully!';
          _result = result.stdout as String;
        });
      } else {
        setState(() {
          _isSolving = false;
          _error = result.stderr?.toString() ?? 'Server failed to start';
          _status = 'Server start failed';
        });
      }
    } catch (e) {
      setState(() {
        _isSolving = false;
        _error = 'Error: $e';
        _status = 'Server start failed';
      });
    }
  }

  Future<void> _solveCaptcha() async {
    if (_selectedFilePath == null) {
      setState(() {
        _error = 'Please select a captcha image first';
      });
      return;
    }

    setState(() {
      _isSolving = true;
      _status = 'Solving CAPTCHA...';
      _error = null;
      _result = null;
    });

    try {
      // Note: This would require the server to be running
      // For now, we'll simulate or call the solver directly
      final scriptPath = 'backend/python/captcha-solver/__main__.py';
      final result = await Process.run('python3', [scriptPath, _selectedFilePath!]);
      
      if (result.exitCode == 0) {
        setState(() {
          _isSolving = false;
          _status = 'CAPTCHA solved successfully!';
          _result = result.stdout as String;
        });
      } else {
        setState(() {
          _isSolving = false;
          _error = result.stderr?.toString() ?? 'Solving failed';
          _status = 'Solving failed';
        });
      }
    } catch (e) {
      setState(() {
        _isSolving = false;
        _error = 'Error: $e';
        _status = 'Solving failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CAPTCHA Solver'),
        actions: [
          if (_selectedFilePath != null || _status != null)
            IconButton(
              icon: const Icon(Icons.clear),
              onPressed: () {
                setState(() {
                  _selectedFilePath = null;
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
                        Icon(Icons.security, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text(
                          'CAPTCHA Solver',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    if (_selectedFilePath != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.amber.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.image, color: Colors.amber),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _selectedFilePath!.split('/').last,
                                style: const TextStyle(color: Colors.amber),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    if (_selectedFilePath == null)
                      const Text(
                        'No captcha image selected',
                        style: TextStyle(color: Colors.grey),
                      ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isSolving ? null : _pickFile,
                            icon: const Icon(Icons.image),
                            label: const Text('Select Image'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isSolving ? null : _startServer,
                            icon: const Icon(Icons.play_arrow),
                            label: const Text('Start Server'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.green,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    ElevatedButton.icon(
                      onPressed: _isSolving || _selectedFilePath == null ? null : _solveCaptcha,
                      icon: _isSolving
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation(Colors.white),
                              ),
                            )
                          : const Icon(Icons.lock_open),
                      label: Text(_isSolving ? 'Processing...' : 'Solve CAPTCHA'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _isSolving ? Colors.grey : Colors.amber,
                        foregroundColor: _isSolving ? Colors.white : Colors.black,
                      ),
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
                          const Text('Solving Result', style: TextStyle(fontWeight: FontWeight.bold)),
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
