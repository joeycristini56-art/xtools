import 'dart:io';
import 'package:flutter/material.dart';

class ScraperScreen extends StatefulWidget {
  const ScraperScreen({super.key});

  @override
  State<ScraperScreen> createState() => _ScraperScreenState();
}

class _ScraperScreenState extends State<ScraperScreen> {
  final _urlController = TextEditingController();
  final _outputController = TextEditingController();
  bool _isScraping = false;
  String? _status;
  String? _error;
  String? _result;

  @override
  void dispose() {
    _urlController.dispose();
    _outputController.dispose();
    super.dispose();
  }

  Future<void> _startScraping() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) {
      setState(() {
        _error = 'Please enter a URL to scrape';
      });
      return;
    }

    setState(() {
      _isScraping = true;
      _status = 'Scraping...';
      _error = null;
      _result = null;
    });

    try {
      // Use the tele-scrapper script
      final scriptPath = 'backend/python/tele-scrapper/main.py';
      final args = ['python3', scriptPath];
      
      if (_outputController.text.isNotEmpty) {
        args.addAll(['--output', _outputController.text]);
      }
      args.add(url);

      final result = await Process.run(args[0], args.sublist(1));
      
      if (result.exitCode == 0) {
        setState(() {
          _isScraping = false;
          _status = 'Scraping completed successfully!';
          _result = result.stdout as String;
        });
      } else {
        setState(() {
          _isScraping = false;
          _error = result.stderr?.toString() ?? 'Scraping failed';
          _status = 'Scraping failed';
        });
      }
    } catch (e) {
      setState(() {
        _isScraping = false;
        _error = 'Error: $e';
        _status = 'Scraping failed';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Web Scraper'),
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
                        Icon(Icons.scanner, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text(
                          'Scraper Configuration',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _urlController,
                      decoration: const InputDecoration(
                        labelText: 'Target URL',
                        hintText: 'https://example.com',
                        prefixIcon: Icon(Icons.link),
                        border: OutlineInputBorder(),
                      ),
                      enabled: !_isScraping,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _outputController,
                      decoration: const InputDecoration(
                        labelText: 'Output File (optional)',
                        hintText: 'results.txt',
                        prefixIcon: Icon(Icons.save_alt),
                        border: OutlineInputBorder(),
                      ),
                      enabled: !_isScraping,
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      onPressed: _isScraping ? null : _startScraping,
                      icon: _isScraping
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation(Colors.white),
                              ),
                            )
                          : const Icon(Icons.play_arrow),
                      label: Text(_isScraping ? 'Scraping...' : 'Start Scraping'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
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
                          const Text('Scraping Results', style: TextStyle(fontWeight: FontWeight.bold)),
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
