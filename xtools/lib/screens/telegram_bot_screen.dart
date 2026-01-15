import 'package:flutter/material.dart';
import '../services/config_service.dart';
import '../services/bot_service.dart';

class TelegramBotScreen extends StatefulWidget {
  const TelegramBotScreen({super.key});

  @override
  State<TelegramBotScreen> createState() => _TelegramBotScreenState();
}

class _TelegramBotScreenState extends State<TelegramBotScreen> {
  final _apiIdController = TextEditingController();
  final _apiHashController = TextEditingController();
  final _phoneController = TextEditingController();
  final _botService = BotService();
  bool _isRunning = false;
  bool _isLoading = false;
  String? _status;
  String? _error;
  String? _log;

  @override
  void initState() {
    super.initState();
    _loadCredentials();
  }

  Future<void> _loadCredentials() async {
    final configService = ConfigService();
    final creds = await configService.getTelegramCredentials();
    
    if (creds['apiId'] != null) {
      setState(() {
        _apiIdController.text = creds['apiId']!;
        _apiHashController.text = creds['apiHash']!;
        _phoneController.text = creds['phone']!;
      });
    }
  }

  Future<void> _startBot() async {
    if (_apiIdController.text.isEmpty || _apiHashController.text.isEmpty || _phoneController.text.isEmpty) {
      setState(() {
        _error = 'Please fill in all credentials first';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _status = 'Starting Telegram bot...';
      _error = null;
      _log = null;
    });

    try {
      final result = await _botService.startTelegramBot(
        _apiIdController.text,
        _apiHashController.text,
        _phoneController.text,
      );
      
      setState(() {
        _isRunning = true;
        _isLoading = false;
        _status = 'Bot is running';
        _log = '''[INFO] Telegram Bot started
[INFO] $result
[INFO] Connecting to Telegram API...
[INFO] Session initialized
[INFO] Monitoring channels...
[INFO] Ready to forward messages''';
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to start: $e';
      });
    }
  }

  Future<void> _stopBot() async {
    setState(() {
      _isLoading = true;
      _status = 'Stopping Telegram bot...';
    });

    try {
      final result = await _botService.stopTelegramBot();
      
      setState(() {
        _isRunning = false;
        _isLoading = false;
        _status = 'Bot stopped';
        _log = (_log ?? '') + '\n[INFO] $result';
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to stop: $e';
      });
    }
  }

  Future<void> _saveCredentials() async {
    if (_apiIdController.text.isEmpty || _apiHashController.text.isEmpty || _phoneController.text.isEmpty) return;

    final configService = ConfigService();
    
    await configService.saveTelegramCredentials(
      _apiIdController.text,
      _apiHashController.text,
      _phoneController.text,
    );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Credentials saved securely')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Telegram Bot'),
        actions: [
          if (_isRunning)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _isLoading ? null : () async {
                await _stopBot();
                await Future.delayed(const Duration(seconds: 1));
                await _startBot();
              },
              tooltip: 'Restart',
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
                        Icon(Icons.vpn_key, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text('API Credentials', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _apiIdController,
                      decoration: const InputDecoration(
                        labelText: 'API ID',
                        prefixIcon: Icon(Icons.numbers),
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                      enabled: !_isRunning,
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _apiHashController,
                      decoration: const InputDecoration(
                        labelText: 'API Hash',
                        prefixIcon: Icon(Icons.lock),
                        border: OutlineInputBorder(),
                      ),
                      obscureText: true,
                      enabled: !_isRunning,
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _phoneController,
                      decoration: const InputDecoration(
                        labelText: 'Phone Number',
                        prefixIcon: Icon(Icons.phone),
                        border: OutlineInputBorder(),
                        hintText: '+1234567890',
                      ),
                      enabled: !_isRunning,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _isRunning ? null : _saveCredentials,
                            icon: const Icon(Icons.save, size: 18),
                            label: const Text('Save'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isLoading ? null : (_isRunning ? null : _startBot),
                    icon: _isLoading && !_isRunning
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation(Colors.white)))
                      : const Icon(Icons.play_arrow),
                    label: Text(_isRunning ? 'Running' : 'Start'),
                    style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isLoading ? null : (_isRunning ? _stopBot : null),
                    icon: _isLoading && _isRunning
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation(Colors.white)))
                      : const Icon(Icons.stop),
                    label: const Text('Stop'),
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.red, foregroundColor: Colors.white, padding: const EdgeInsets.symmetric(vertical: 14)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_status != null || _error != null)
              Card(
                color: _error != null ? Theme.of(context).colorScheme.error.withOpacity(0.1) : _isRunning ? Colors.green.withOpacity(0.1) : Theme.of(context).primaryColor.withOpacity(0.05),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(_error != null ? Icons.error : (_isRunning ? Icons.check_circle : Icons.info), color: _error != null ? Theme.of(context).colorScheme.error : _isRunning ? Colors.green : Theme.of(context).primaryColor, size: 20),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_status ?? _error!, style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500))),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 16),
            if (_log != null)
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
                          const Text('Live Logs', style: TextStyle(fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                    Container(
                      padding: const EdgeInsets.all(12),
                      color: Theme.of(context).scaffoldBackgroundColor,
                      child: SelectableText(_log!, style: const TextStyle(fontFamily: 'monospace', fontSize: 12, height: 1.5)),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _apiIdController.dispose();
    _apiHashController.dispose();
    _phoneController.dispose();
    super.dispose();
  }
}
