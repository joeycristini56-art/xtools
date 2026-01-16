import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:convert';
import '../services/bot_service.dart';

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
  Map<String, dynamic>? _result;
  
  // For Remove tool
  final _patternController = TextEditingController();
  
  // For Sort tool - domain selection
  final List<String> _availableDomains = ['gmail', 'microsoft', 'yahoo', 'aol', 'icloud', 'proton'];
  final Set<String> _selectedDomains = {};

  final BotService _botService = BotService();

  final Map<String, Map<String, dynamic>> _tools = {
    'Sort': {
      'description': 'Extract emails by provider (Gmail, Microsoft, etc.)',
      'icon': Icons.sort,
      'color': Colors.blue,
    },
    'Filter': {
      'description': 'Remove duplicate lines from file',
      'icon': Icons.filter_list,
      'color': Colors.green,
    },
    'Deduplicate': {
      'description': 'Consolidate and deduplicate valid files',
      'icon': Icons.content_copy,
      'color': Colors.orange,
    },
    'Split': {
      'description': 'Filter for CC/PayPal premium accounts',
      'icon': Icons.call_split,
      'color': Colors.purple,
    },
    'Remove': {
      'description': 'Remove lines matching a pattern',
      'icon': Icons.remove_circle,
      'color': Colors.red,
    },
  };

  @override
  void dispose() {
    _patternController.dispose();
    super.dispose();
  }

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

    // Validate Remove tool pattern
    if (_selectedTool == 'Remove' && _patternController.text.isEmpty) {
      setState(() {
        _error = 'Please enter a pattern to remove';
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
      Map<String, dynamic> result;
      
      switch (_selectedTool) {
        case 'Sort':
          final domains = _selectedDomains.isNotEmpty ? _selectedDomains.toList() : null;
          result = await _botService.sortEmails(_selectedFilePath!, domains: domains);
          break;
        case 'Filter':
          result = await _botService.filterFile(_selectedFilePath!);
          break;
        case 'Deduplicate':
          result = await _botService.deduplicateFiles(_selectedFilePath!);
          break;
        case 'Split':
          result = await _botService.splitForPremium(_selectedFilePath!);
          break;
        case 'Remove':
          result = await _botService.removePattern(_selectedFilePath!, _patternController.text);
          break;
        default:
          result = {'success': false, 'error': 'Unknown tool'};
      }
      
      setState(() {
        _isProcessing = false;
        if (result['success'] == true) {
          _status = 'Processing completed successfully!';
          _result = result;
          _error = null;
        } else {
          _error = result['error'] ?? 'Processing failed';
          _status = 'Processing failed';
          _result = null;
        }
      });
    } catch (e) {
      setState(() {
        _isProcessing = false;
        _error = 'Error: $e';
        _status = 'Processing failed';
      });
    }
  }

  Widget _buildToolOptions() {
    if (_selectedTool == 'Sort') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 12),
          const Text('Select email providers to extract:', style: TextStyle(fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _availableDomains.map((domain) {
              final isSelected = _selectedDomains.contains(domain);
              return FilterChip(
                label: Text(domain.toUpperCase()),
                selected: isSelected,
                onSelected: _isProcessing ? null : (selected) {
                  setState(() {
                    if (selected) {
                      _selectedDomains.add(domain);
                    } else {
                      _selectedDomains.remove(domain);
                    }
                  });
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 8),
          Text(
            _selectedDomains.isEmpty 
                ? 'No selection = Gmail & Microsoft (default)' 
                : 'Selected: ${_selectedDomains.join(", ")}',
            style: TextStyle(color: Colors.grey[600], fontSize: 12),
          ),
        ],
      );
    } else if (_selectedTool == 'Remove') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 12),
          TextField(
            controller: _patternController,
            decoration: const InputDecoration(
              labelText: 'Pattern to remove',
              hintText: 'e.g., gmail.com or @yahoo',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
            ),
            enabled: !_isProcessing,
          ),
        ],
      );
    }
    return const SizedBox.shrink();
  }

  String _formatResult(Map<String, dynamic> result) {
    final buffer = StringBuffer();
    
    result.forEach((key, value) {
      if (key != 'success' && key != 'traceback') {
        if (value is List) {
          buffer.writeln('$key:');
          for (var item in value) {
            if (item is Map) {
              item.forEach((k, v) => buffer.writeln('  $k: $v'));
              buffer.writeln();
            } else {
              buffer.writeln('  - $item');
            }
          }
        } else if (value is Map) {
          buffer.writeln('$key:');
          value.forEach((k, v) => buffer.writeln('  $k: $v'));
        } else {
          buffer.writeln('$key: $value');
        }
      }
    });
    
    return buffer.toString();
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
                  _selectedDomains.clear();
                  _patternController.clear();
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
                      items: _tools.entries.map((entry) {
                        final tool = entry.key;
                        final info = entry.value;
                        return DropdownMenuItem(
                          value: tool,
                          child: Row(
                            children: [
                              Icon(info['icon'] as IconData, color: info['color'] as Color, size: 20),
                              const SizedBox(width: 8),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(tool),
                                  Text(
                                    info['description'] as String,
                                    style: TextStyle(fontSize: 10, color: Colors.grey[600]),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                      onChanged: _isProcessing ? null : (value) {
                        setState(() {
                          _selectedTool = value;
                          _selectedDomains.clear();
                          _patternController.clear();
                        });
                      },
                    ),
                    _buildToolOptions(),
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
                              backgroundColor: _isProcessing ? Colors.grey : (_tools[_selectedTool]?['color'] as Color?) ?? Colors.orange,
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
                          const Text('Processing Result', style: TextStyle(fontWeight: FontWeight.bold)),
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
