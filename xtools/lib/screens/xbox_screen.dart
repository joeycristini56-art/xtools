import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../services/bot_service.dart';
import '../services/config_service.dart';

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
  Map<String, dynamic>? _result;
  
  final _apiKeyController = TextEditingController();
  final _maxWorkersController = TextEditingController(text: '1000');
  final _targetCPMController = TextEditingController(text: '20000');
  final _batchSizeController = TextEditingController(text: '1000');
  final _poolSizeController = TextEditingController(text: '1000');
  
  bool _showAdvanced = false;
  bool _resetProgress = false;

  final BotService _botService = BotService();
  final ConfigService _configService = ConfigService();

  @override
  void initState() {
    super.initState();
    _loadSavedConfig();
  }

  Future<void> _loadSavedConfig() async {
    final apiKey = await _configService.getXboxAPIKey();
    if (apiKey != null) {
      _apiKeyController.text = apiKey;
    }
    
    final config = await _configService.getXboxConfig();
    _maxWorkersController.text = config['maxWorkers'].toString();
    _targetCPMController.text = config['targetCPM'].toString();
    _batchSizeController.text = config['batchSize'].toString();
    _poolSizeController.text = config['poolSize'].toString();
  }

  @override
  void dispose() {
    _apiKeyController.dispose();
    _maxWorkersController.dispose();
    _targetCPMController.dispose();
    _batchSizeController.dispose();
    _poolSizeController.dispose();
    super.dispose();
  }

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

    if (_apiKeyController.text.isEmpty) {
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
      // Save config for next time
      await _configService.saveXboxConfig(
        maxWorkers: int.tryParse(_maxWorkersController.text),
        targetCPM: int.tryParse(_targetCPMController.text),
        batchSize: int.tryParse(_batchSizeController.text),
        poolSize: int.tryParse(_poolSizeController.text),
      );

      final result = await _botService.checkXboxAccounts(
        apiKey: _apiKeyController.text,
        comboFile: _selectedFilePath!,
        maxWorkers: int.tryParse(_maxWorkersController.text),
        targetCPM: int.tryParse(_targetCPMController.text),
        batchSize: int.tryParse(_batchSizeController.text),
        poolSize: int.tryParse(_poolSizeController.text),
        resetProgress: _resetProgress,
      );
      
      setState(() {
        _isChecking = false;
        if (result['success'] == true) {
          _status = 'Xbox check completed!';
          _result = result;
          _error = null;
        } else {
          _error = result['error'] ?? 'Checker failed';
          _status = 'Check failed';
          _result = null;
        }
      });
    } catch (e) {
      setState(() {
        _isChecking = false;
        _error = 'Error: $e';
        _status = 'Check failed';
      });
    }
  }

  String _formatResult(Map<String, dynamic> result) {
    final buffer = StringBuffer();
    result.forEach((key, value) {
      if (key != 'success' && key != 'traceback') {
        buffer.writeln('$key: $value');
      }
    });
    return buffer.toString();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Xbox Checker'),
        actions: [
          if (_selectedFilePath != null || _apiKeyController.text.isNotEmpty)
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
                      controller: _apiKeyController,
                      decoration: const InputDecoration(
                        labelText: 'API Key',
                        hintText: 'Enter your API key',
                        prefixIcon: Icon(Icons.key),
                        border: OutlineInputBorder(),
                      ),
                      obscureText: true,
                      enabled: !_isChecking,
                    ),
                    const SizedBox(height: 12),
                    if (_selectedFilePath != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.green.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.insert_drive_file, color: Colors.green),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _selectedFilePath!.split('/').last,
                                style: const TextStyle(color: Colors.green),
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
                    
                    // Advanced settings toggle
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Advanced Settings'),
                      trailing: Switch(
                        value: _showAdvanced,
                        onChanged: _isChecking ? null : (value) {
                          setState(() {
                            _showAdvanced = value;
                          });
                        },
                      ),
                    ),
                    
                    if (_showAdvanced) ...[
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _maxWorkersController,
                              decoration: const InputDecoration(
                                labelText: 'Max Workers',
                                border: OutlineInputBorder(),
                              ),
                              keyboardType: TextInputType.number,
                              enabled: !_isChecking,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextField(
                              controller: _targetCPMController,
                              decoration: const InputDecoration(
                                labelText: 'Target CPM',
                                border: OutlineInputBorder(),
                              ),
                              keyboardType: TextInputType.number,
                              enabled: !_isChecking,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _batchSizeController,
                              decoration: const InputDecoration(
                                labelText: 'Batch Size',
                                border: OutlineInputBorder(),
                              ),
                              keyboardType: TextInputType.number,
                              enabled: !_isChecking,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextField(
                              controller: _poolSizeController,
                              decoration: const InputDecoration(
                                labelText: 'Pool Size',
                                border: OutlineInputBorder(),
                              ),
                              keyboardType: TextInputType.number,
                              enabled: !_isChecking,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Reset Progress'),
                        subtitle: const Text('Start from beginning'),
                        value: _resetProgress,
                        onChanged: _isChecking ? null : (value) {
                          setState(() {
                            _resetProgress = value ?? false;
                          });
                        },
                      ),
                    ],
                    
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
                            onPressed: _isChecking ? null : (_selectedFilePath != null && _apiKeyController.text.isNotEmpty ? _startChecker : null),
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
                              backgroundColor: _isChecking ? Colors.grey : Colors.green,
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
                          _error ?? _status!,
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
                        _formatResult(_result!),
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
