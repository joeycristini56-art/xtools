import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:io';
import 'dart:convert';
import '../services/bot_service.dart';

class GofileScreen extends StatefulWidget {
  const GofileScreen({super.key});

  @override
  State<GofileScreen> createState() => _GofileScreenState();
}

class _GofileScreenState extends State<GofileScreen> {
  bool _isUploading = false;
  String? _status;
  String? _error;
  Map<String, dynamic>? _result;
  String? _selectedFilePath;
  
  final BotService _botService = BotService();

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        withData: true,
      );

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

  Future<void> _uploadFile() async {
    if (_selectedFilePath == null) {
      setState(() {
        _error = 'Please select a file first';
      });
      return;
    }

    setState(() {
      _isUploading = true;
      _status = 'Uploading to GoFile...';
      _error = null;
      _result = null;
    });

    try {
      final file = File(_selectedFilePath!);
      
      if (!await file.exists()) {
        throw Exception('File no longer exists');
      }

      final result = await _botService.uploadToGoFile(_selectedFilePath!);
      
      setState(() {
        _isUploading = false;
        if (result['success'] == true) {
          _status = 'Upload completed successfully!';
          _result = result;
          _error = null;
        } else {
          _error = result['error'] ?? 'Upload failed';
          _status = 'Upload failed';
          _result = null;
        }
      });
    } catch (e) {
      setState(() {
        _isUploading = false;
        _error = 'Error: $e';
        _status = 'Upload failed';
      });
    }
  }
  
  void _copyToClipboard(String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Copied to clipboard!')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('GoFile Upload'),
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
                        Icon(Icons.cloud_upload, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text(
                          'File Upload',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
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
                        'No file selected',
                        style: TextStyle(color: Colors.grey),
                      ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isUploading ? null : _pickFile,
                            icon: const Icon(Icons.folder_open),
                            label: const Text('Select File'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _isUploading ? null : (_selectedFilePath != null ? _uploadFile : null),
                            icon: _isUploading
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation(Colors.white),
                                    ),
                                  )
                                : const Icon(Icons.upload),
                            label: Text(_isUploading ? 'Uploading...' : 'Upload'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _isUploading ? Colors.grey : Colors.blue,
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
                          Icon(Icons.link, size: 18, color: Theme.of(context).primaryColor),
                          const SizedBox(width: 8),
                          const Text('Upload Result', style: TextStyle(fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                    if (_result!['download_page'] != null && _result!['download_page'].toString().isNotEmpty)
                      ListTile(
                        leading: const Icon(Icons.download, color: Colors.blue),
                        title: const Text('Download Link'),
                        subtitle: Text(_result!['download_page'].toString()),
                        trailing: IconButton(
                          icon: const Icon(Icons.copy),
                          onPressed: () => _copyToClipboard(_result!['download_page'].toString()),
                        ),
                      ),
                    if (_result!['file_name'] != null)
                      ListTile(
                        leading: const Icon(Icons.insert_drive_file),
                        title: const Text('File Name'),
                        subtitle: Text(_result!['file_name'].toString()),
                      ),
                    if (_result!['file_size'] != null)
                      ListTile(
                        leading: const Icon(Icons.data_usage),
                        title: const Text('File Size'),
                        subtitle: Text('${(_result!['file_size'] / 1024 / 1024).toStringAsFixed(2)} MB'),
                      ),
                    if (_result!['server'] != null)
                      ListTile(
                        leading: const Icon(Icons.dns),
                        title: const Text('Server'),
                        subtitle: Text(_result!['server'].toString()),
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
