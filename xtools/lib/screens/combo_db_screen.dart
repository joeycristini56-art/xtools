import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';

class ComboDBScreen extends StatefulWidget {
  const ComboDBScreen({super.key});

  @override
  State<ComboDBScreen> createState() => _ComboDBScreenState();
}

class _ComboDBScreenState extends State<ComboDBScreen> {
  String? _selectedFilePath;
  bool _isProcessing = false;
  String? _status;
  String? _error;
  String? _result;

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles();

      if (result != null && result.files.single.path != null) {
        setState(() {
          _selectedFilePath = result.files.single.path;
          _status = 'File selected: ${result.files.single.name}';
          _error = null;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to pick file: $e';
      });
    }
  }

  Future<void> _addToDatabase() async {
    if (_selectedFilePath == null) {
      setState(() {
        _error = 'Please select a file first';
      });
      return;
    }

    setState(() {
      _isProcessing = true;
      _status = 'Adding to database...';
      _error = null;
      _result = null;
    });

    try {
      final scriptPath = 'backend/python/combo-database/combo.py';
      final result = await Process.run('python3', [scriptPath, _selectedFilePath!]);
      
      if (result.exitCode == 0) {
        setState(() {
          _isProcessing = false;
          _status = 'Added to database successfully!';
          _result = result.stdout as String;
        });
      } else {
        setState(() {
          _isProcessing = false;
          _error = result.stderr?.toString() ?? 'Failed to add to database';
          _status = 'Failed';
        });
      }
    } catch (e) {
      setState(() {
        _isProcessing = false;
        _error = 'Error: $e';
        _status = 'Failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Combo Database'),
        actions: [
          if (_selectedFilePath != null)
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
              tooltip: 'Clear selection',
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
                        Icon(Icons.storage, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text(
                          'Combo Database Manager',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    if (_selectedFilePath != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.teal.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.insert_drive_file, color: Colors.teal),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _selectedFilePath!.split('/').last,
                                style: const TextStyle(color: Colors.teal),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    if (_selectedFilePath == null)
                      const Text(
                        'No file selected',
                        style: TextStyle(color: Colors.grey),
                      ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isProcessing ? null : _pickFile,
                            icon: const Icon(Icons.folder_open),
                            label: const Text('Select Combo File'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isProcessing ? null : (_selectedFilePath != null ? _addToDatabase : null),
                            icon: _isProcessing
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation(Colors.white),
                                    ),
                                  )
                                : const Icon(Icons.storage),
                            label: Text(_isProcessing ? 'Processing...' : 'Add to DB'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _isProcessing ? Colors.grey : Colors.teal,
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
                          const Text('Database Result', style: TextStyle(fontWeight: FontWeight.bold)),
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
