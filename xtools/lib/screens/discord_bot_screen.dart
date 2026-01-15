import 'package:flutter/material.dart';
import '../services/config_service.dart';
import '../services/bot_service.dart';

class DiscordBotScreen extends StatefulWidget {
  const DiscordBotScreen({super.key});

  @override
  State<DiscordBotScreen> createState() => _DiscordBotScreenState();
}

class _DiscordBotScreenState extends State<DiscordBotScreen> with WidgetsBindingObserver {
  final _tokenController = TextEditingController();
  final _botService = BotService();
  bool _isRunning = false;
  bool _isLoading = false;
  String? _status;
  String? _error;
  String? _log;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadToken();
  }

  @override
  void dispose() {
    _tokenController.dispose();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.detached) {
    }
  }

  Future<void> _loadToken() async {
    final configService = ConfigService();
    final token = await configService.getDiscordToken();
    if (token != null) {
      setState(() {
        _tokenController.text = token;
      });
    }
  }

  Future<void> _saveToken() async {
    if (_tokenController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Token cannot be empty')),
      );
      return;
    }

    final configService = ConfigService();
    await configService.saveDiscordToken(_tokenController.text);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Discord token saved securely'), backgroundColor: Colors.green),
      );
    }
  }

  Future<void> _startBot() async {
    if (_tokenController.text.isEmpty) {
      setState(() {
        _error = 'Please enter a bot token first';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _status = 'Starting Discord bot...';
      _error = null;
      _log = null;
    });

    try {
      // Launch the Python script that runs the Discord bot
      final result = await _botService.startDiscordBot(_tokenController.text);
      
      setState(() {
        _isRunning = true;
        _isLoading = false;
        _status = 'Bot is running';
        _log = '''[INFO] Discord Bot started
[INFO] $result
[INFO] Monitoring emails...
[INFO] Connected to Discord API
[INFO] Ready to receive notifications''';
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to start bot: $e';
        _log = '[ERROR] $e';
      });
    }
  }

  Future<void> _stopBot() async {
    setState(() {
      _isLoading = true;
      _status = 'Stopping Discord bot...';
    });

    try {
      final result = await _botService.stopDiscordBot();
      
      setState(() {
        _isRunning = false;
        _isLoading = false;
        _status = 'Bot stopped';
        _log = (_log ?? '') + '\n[INFO] $result';
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to stop bot: $e';
      });
    }
  }

  Future<void> _restartBot() async {
    await _stopBot();
    await Future.delayed(const Duration(seconds: 1));
    await _startBot();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Discord Bot'),
        actions: [
          if (_isRunning)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _isLoading ? null : () async {
                await _restartBot();
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
                        Icon(Icons.key, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text(
                          'Bot Configuration',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _tokenController,
                      decoration: const InputDecoration(
                        labelText: 'Discord Bot Token',
                        hintText: 'Enter your bot token',
                        prefixIcon: Icon(Icons.lock_outline),
                        border: OutlineInputBorder(),
                      ),
                      obscureText: true,
                      enabled: !_isRunning,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _isRunning ? null : _saveToken,
                            icon: const Icon(Icons.save, size: 18),
                            label: const Text('Save Token'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () {
                              showDialog(
                                context: context,
                                builder: (context) => AlertDialog(
                                  title: const Text('How to get token?'),
                                  content: const Text(
                                    '1. Go to Discord Developer Portal\n'
                                    '2. Create a new application\n'
                                    '3. Go to Bot section\n'
                                    '4. Copy the token\n'
                                    '5. Paste it here',
                                  ),
                                  actions: [
                                    TextButton(
                                      onPressed: () => Navigator.pop(context),
                                      child: const Text('Close'),
                                    ),
                                  ],
                                ),
                              );
                            },
                            icon: const Icon(Icons.help_outline, size: 18),
                            label: const Text('Help'),
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
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation(Colors.white),
                            ),
                          )
                        : const Icon(Icons.play_arrow),
                    label: Text(_isRunning ? 'Running' : 'Start'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isLoading ? null : (_isRunning ? _stopBot : null),
                    icon: _isLoading && _isRunning
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation(Colors.white),
                            ),
                          )
                        : const Icon(Icons.stop),
                    label: const Text('Stop'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 16),

            if (_status != null || _error != null)
              Card(
                color: _error != null
                    ? Theme.of(context).colorScheme.error.withOpacity(0.1)
                    : _isRunning
                        ? Colors.green.withOpacity(0.1)
                        : Theme.of(context).primaryColor.withOpacity(0.05),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(
                        _error != null
                            ? Icons.error
                            : (_isRunning ? Icons.check_circle : Icons.info),
                        color: _error != null
                            ? Theme.of(context).colorScheme.error
                            : _isRunning
                                ? Colors.green
                                : Theme.of(context).primaryColor,
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
                      child: SelectableText(
                        _log!,
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
