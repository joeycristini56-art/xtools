import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:provider/provider.dart';
import '../services/bot_service.dart';
import '../core/app_state.dart';

class XCodeDashboard extends StatefulWidget {
  const XCodeDashboard({super.key});

  @override
  State<XCodeDashboard> createState() => _XCodeDashboardState();
}

class _XCodeDashboardState extends State<XCodeDashboard> {
  String? _selectedFile;
  String? _selectedTool;
  String? _inputText;
  bool _isProcessing = false;
  String? _output;
  String? _error;

  final Map<String, Map<String, dynamic>> _tools = {
    'GoFile Upload': {
      'icon': Icons.cloud_upload,
      'color': Colors.blue,
      'type': 'file',
      'tool': 'gofile',
    },
    'Sort': {
      'icon': Icons.sort,
      'color': Colors.green,
      'type': 'file',
      'tool': 'sort',
    },
    'Filter': {
      'icon': Icons.filter_alt,
      'color': Colors.orange,
      'type': 'file',
      'tool': 'filter',
    },
    'Deduplicate': {
      'icon': Icons.content_copy,
      'color': Colors.purple,
      'type': 'file',
      'tool': 'dedup',
    },
    'Split': {
      'icon': Icons.call_split,
      'color': Colors.red,
      'type': 'file',
      'tool': 'split',
    },
    'Remove': {
      'icon': Icons.delete,
      'color': Colors.redAccent,
      'type': 'file+text',
      'tool': 'remove',
    },
    'Combo DB': {
      'icon': Icons.storage,
      'color': Colors.teal,
      'type': 'file',
      'tool': 'combo',
    },
    'Scraper': {
      'icon': Icons.language,
      'color': Colors.indigo,
      'type': 'text',
      'tool': 'scraper',
    },
    'CAPTCHA': {
      'icon': Icons.security,
      'color': Colors.amber,
      'type': 'file',
      'tool': 'captcha',
    },
    'Discord Bot': {
      'icon': Icons.chat,
      'color': Colors.purple,
      'type': 'text',
      'tool': 'discord_bot',
    },
    'Telegram Bot': {
      'icon': Icons.message,
      'color': Colors.blue,
      'type': 'multi',
      'tool': 'telegram_bot',
    },
  };

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles();
      if (result != null && result.files.single.path != null) {
        setState(() {
          _selectedFile = result.files.single.path;
          _error = null;
        });
      }
    } catch (e) {
      setState(() => _error = 'File pick failed: $e');
    }
  }

  Future<void> _executeTool() async {
    if (_selectedTool == null) {
      setState(() => _error = 'Select a tool first');
      return;
    }

    setState(() {
      _isProcessing = true;
      _error = null;
      _output = null;
    });

    try {
      final botService = BotService();
      final toolInfo = _tools[_selectedTool!]!;
      final tool = toolInfo['tool'] as String;
      final type = toolInfo['type'] as String;

      Map<String, dynamic> params = {};

      if (type == 'file' || type == 'file+text') {
        if (_selectedFile == null) {
          setState(() {
            _error = 'File required';
            _isProcessing = false;
          });
          return;
        }
        params['file'] = _selectedFile;
      }

      if (type == 'text' || type == 'file+text') {
        if (_inputText == null || _inputText!.isEmpty) {
          setState(() {
            _error = 'Input required';
            _isProcessing = false;
          });
          return;
        }
        if (type == 'text') {
          params['url'] = _inputText;
          params['token'] = _inputText;
        } else {
          params['pattern'] = _inputText;
        }
      }

      if (type == 'multi') {
        // Telegram needs multiple inputs
        // For now, just use inputText as JSON
        if (_inputText != null) {
          try {
            params = Map<String, dynamic>.from(_inputText as Map);
          } catch (e) {
            params['input'] = _inputText;
          }
        }
      }

      final result = await botService.executeTool(tool, params);
      
      setState(() {
        _output = result['output'] ?? result.toString();
        _isProcessing = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isProcessing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('XTools - XCode Style'),
        backgroundColor: Colors.grey[900],
        elevation: 0,
      ),
      body: Container(
        color: Colors.grey[950],
        child: Row(
          children: [
            // Left Sidebar - Tools
            Container(
              width: 250,
              color: Colors.grey[900],
              child: Column(
                children: [
                  const Padding(
                    padding: EdgeInsets.all(16.0),
                    child: Text('TOOLS', style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.bold)),
                  ),
                  Expanded(
                    child: ListView.builder(
                      itemCount: _tools.length,
                      itemBuilder: (context, index) {
                        final toolName = _tools.keys.elementAt(index);
                        final tool = _tools[toolName]!;
                        final isSelected = _selectedTool == toolName;
                        
                        return ListTile(
                          leading: Icon(tool['icon'], color: tool['color'], size: 20),
                          title: Text(toolName, style: TextStyle(color: isSelected ? Colors.white : Colors.white70)),
                          selected: isSelected,
                          selectedTileColor: Colors.grey[800],
                          onTap: () {
                            setState(() {
                              _selectedTool = toolName;
                              _error = null;
                            });
                          },
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
            
            // Main Content Area
            Expanded(
              child: Column(
                children: [
                  // Input Section
                  Container(
                    padding: const EdgeInsets.all(16),
                    color: Colors.grey[900],
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            ElevatedButton.icon(
                              onPressed: _pickFile,
                              icon: const Icon(Icons.attach_file),
                              label: Text(_selectedFile != null 
                                ? _selectedFile!.split('/').last 
                                : 'Select File'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.blue,
                                foregroundColor: Colors.white,
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: TextField(
                                decoration: InputDecoration(
                                  hintText: 'Enter text (URL, token, pattern, or JSON)',
                                  hintStyle: TextStyle(color: Colors.grey[400]),
                                  filled: true,
                                  fillColor: Colors.grey[800],
                                  border: OutlineInputBorder(
                                    borderRadius: BorderRadius.circular(8),
                                    borderSide: BorderSide.none,
                                  ),
                                ),
                                style: const TextStyle(color: Colors.white),
                                onChanged: (value) => _inputText = value,
                              ),
                            ),
                            const SizedBox(width: 16),
                            ElevatedButton.icon(
                              onPressed: _isProcessing ? null : _executeTool,
                              icon: _isProcessing 
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                  )
                                : const Icon(Icons.play_arrow),
                              label: Text(_isProcessing ? 'Processing...' : 'Execute'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: _isProcessing ? Colors.grey : Colors.green,
                                foregroundColor: Colors.white,
                              ),
                            ),
                          ],
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: Colors.red[900],
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error, color: Colors.red, size: 16),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(_error!, style: const TextStyle(color: Colors.red)),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  
                  // Output Section
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'OUTPUT',
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Expanded(
                            child: Container(
                              decoration: BoxDecoration(
                                color: Colors.black,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: Colors.grey[800]!),
                              ),
                              padding: const EdgeInsets.all(12),
                              child: SingleChildScrollView(
                                child: Text(
                                  _output ?? 'No output yet...',
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    color: Colors.greenAccent,
                                    height: 1.5,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
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
