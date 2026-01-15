import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';

class DataToolsScreen extends StatefulWidget {
  const DataToolsScreen({super.key});

  @override
  State<DataToolsScreen> createState() => _DataToolsScreenState();
}

class _DataToolsScreenState extends State<DataToolsScreen> {
  String? _selectedFilePath;
  String? _selectedTool;
  bool _isProcessing = false;
  String? _status;
  String? _error;
  String? _result;

  final Map<String, String> _tools = {
    'Sort': 'sort.py',
    'Filter': 'filter.py',
    'Deduplicate': 'dedup.py',
    'Split': 'split.py',
  };

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

  Future<void> _processData() async {
    if (_selectedFilePath == null) {
      setState(() {
        _error = 'Please select a file first';
      });
      return;
    }

    if (_selectedTool == null) {
      setState(() {
        _error = 'Please select a tool';
      });
      return;
    }

    setState(() {
      _isProcessing = true;
      _status = 'Processing...';
      _error = null;
      _result = null;
    });

    try {
      final scriptPath = 'backend/python/${_tools[_selectedTool]}';
      final result = await Process.run('python3', [scriptPath, _selectedFilePath!]);
      
      if (result.exitCode == 0) {
        setState(() {
          _isProcessing = false;
          _status = 'Processing completed successfully!';
          _result = result.stdout as String;
        });
      } else {
        setState(() {
          _isProcessing = false;
          _error = result.stderr?.toString() ?? 'Processing failed';
          _status = 'Processing failed';
        });
      }
    } catch (e) {
      setState(() {
        _isProcessing = false;
        _error = 'Error: $e';
        _status = 'Processing failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Data Tools'),
        actions: [
          if (_selectedFilePath != null)
            IconButton(
              icon: const Icon(Icons.clear),
              onPressed: () {
                setState(() {
                  _selectedFilePath = null;
                  _selectedTool = null;
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
                        Icon(Icons.dataset, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text(
                          'Data Processing',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    if (_selectedFilePath != null)
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.blue.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.insert_drive_file, color: Colors.blue),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                _selectedFilePath!.split('/').last,
                                style: const TextStyle(color: Colors.blue),
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
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: _selectedTool,
                      decoration: const InputDecoration(
                        labelText: 'Select Tool',
                        prefixIcon: Icon(Icons.build),
                        border: OutlineInputBorder(),
                      ),
                      items: _tools.keys.map((tool) {
                        return DropdownMenuItem(
                          value: tool,
                          child: Text(tool),
                        );
                      }).toList(),
                      onChanged: _isProcessing ? null : (value) {
                        setState(() {
                          _selectedTool = value;
                        });
                      },
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isProcessing ? null : _pickFile,
                            icon: const Icon(Icons.folder_open),
                            label: const Text('Select File'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isProcessing ? null : (_selectedFilePath != null && _selectedTool != null ? _processData : null),
                            icon: _isProcessing
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation(Colors.white),
                                    ),
                                  )
                                : const Icon(Icons.play_arrow),
                            label: Text(_isProcessing ? 'Processing...' : 'Process'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _isProcessing ? Colors.grey : Colors.orange,
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
                          const Text('Processing Result', style: TextStyle(fontWeight: FontWeight.bold)),
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
