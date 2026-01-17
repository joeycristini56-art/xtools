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
  final _imapHostController = TextEditingController();
  final _imapUserController = TextEditingController();
  final _imapPassController = TextEditingController();
  final _channelIdController = TextEditingController();
  
  final _botService = BotService();
  final _configService = ConfigService();
  
  bool _isRunning = false;
  bool _isLoading = false;
  bool _showImapConfig = false;
  String? _status;
  String? _error;
  String? _log;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadConfig();
  }

  @override
  void dispose() {
    _tokenController.dispose();
    _imapHostController.dispose();
    _imapUserController.dispose();
    _imapPassController.dispose();
    _channelIdController.dispose();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.detached) {
      if (_isRunning) {
        _stopBot();
      }
    }
  }

  Future<void> _loadConfig() async {
    final token = await _configService.getDiscordToken();
    if (token != null) {
      _tokenController.text = token;
    }
    
    final imapConfig = await _configService.getDiscordIMAPConfig();
    if (imapConfig['host'] != null) {
      _imapHostController.text = imapConfig['host']!;
      _imapUserController.text = imapConfig['user'] ?? '';
      _imapPassController.text = imapConfig['pass'] ?? '';
      _channelIdController.text = imapConfig['channelId'] ?? '';
      setState(() {
        _showImapConfig = true;
      });
    }
  }

  Future<void> _saveConfig() async {
    if (_tokenController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Token cannot be empty')),
      );
      return;
    }

    await _configService.saveDiscordToken(_tokenController.text);
    
    if (_showImapConfig && _imapHostController.text.isNotEmpty) {
      await _configService.saveDiscordIMAPConfig(
        _imapHostController.text,
        _imapUserController.text,
        _imapPassController.text,
        _channelIdController.text,
      );
    }

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Configuration saved securely'), backgroundColor: Colors.green),
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
      final result = await _botService.startDiscordBot(
        token: _tokenController.text,
        imapHost: _showImapConfig ? _imapHostController.text : null,
        imapUser: _showImapConfig ? _imapUserController.text : null,
        imapPass: _showImapConfig ? _imapPassController.text : null,
        channelId: _channelIdController.text.isNotEmpty ? _channelIdController.text : null,
      );
      
      setState(() {
        _isLoading = false;
        if (result['success'] == true) {
          _isRunning = true;
          _status = 'Bot is running';
          _log = '''[INFO] Discord Bot started
[INFO] ${result['message'] ?? 'Connected successfully'}
[INFO] Monitoring emails...
[INFO] Connected to Discord API
[INFO] Ready to receive notifications''';
        } else {
          _error = result['error'] ?? 'Failed to start bot';
          _log = '[ERROR] ${result['error']}';
        }
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
        _log = (_log ?? '') + '\n[INFO] Bot stopped successfully';
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
            // Bot Token Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.smart_toy, color: Theme.of(context).primaryColor),
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
                    TextField(
                      controller: _channelIdController,
                      decoration: const InputDecoration(
                        labelText: 'Channel ID (optional)',
                        hintText: 'Channel to send notifications',
                        prefixIcon: Icon(Icons.tag),
                        border: OutlineInputBorder(),
                      ),
                      enabled: !_isRunning,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // IMAP Configuration Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.email, color: Theme.of(context).primaryColor),
                            const SizedBox(width: 8),
                            const Text(
                              'Email Monitoring (IMAP)',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                            ),
                          ],
                        ),
                        Switch(
                          value: _showImapConfig,
                          onChanged: _isRunning ? null : (value) {
                            setState(() {
                              _showImapConfig = value;
                            });
                          },
                        ),
                      ],
                    ),
                    if (_showImapConfig) ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: _imapHostController,
                        decoration: const InputDecoration(
                          labelText: 'IMAP Host',
                          hintText: 'e.g., imap.gmail.com',
                          prefixIcon: Icon(Icons.dns),
                          border: OutlineInputBorder(),
                        ),
                        enabled: !_isRunning,
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _imapUserController,
                        decoration: const InputDecoration(
                          labelText: 'Email Address',
                          hintText: 'your@email.com',
                          prefixIcon: Icon(Icons.person),
                          border: OutlineInputBorder(),
                        ),
                        enabled: !_isRunning,
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _imapPassController,
                        decoration: const InputDecoration(
                          labelText: 'Email Password / App Password',
                          hintText: 'Enter password',
                          prefixIcon: Icon(Icons.password),
                          border: OutlineInputBorder(),
                        ),
                        obscureText: true,
                        enabled: !_isRunning,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'For Gmail, use an App Password from Google Account settings',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                      ),
                    ],
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // Save and Help buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _isRunning ? null : _saveConfig,
                    icon: const Icon(Icons.save, size: 18),
                    label: const Text('Save Config'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      showDialog(
                        context: context,
                        builder: (context) => AlertDialog(
                          title: const Text('Setup Guide'),
                          content: const SingleChildScrollView(
                            child: Text(
                              'Discord Bot Token:\n'
                              '1. Go to Discord Developer Portal\n'
                              '2. Create a new application\n'
                              '3. Go to Bot section\n'
                              '4. Copy the token\n\n'
                              'IMAP Email Monitoring:\n'
                              '1. Enable IMAP in your email settings\n'
                              '2. For Gmail, create an App Password\n'
                              '3. Enter your email and app password\n\n'
                              'The bot will monitor your inbox and send notifications to Discord.',
                            ),
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

            const SizedBox(height: 16),

            // Start/Stop buttons
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
                    label: Text(_isRunning ? 'Running' : 'Start Bot'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
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
                    label: const Text('Stop Bot'),
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

            // Status Card
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

            const SizedBox(height: 16),

            // Logs Card
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
                      constraints: const BoxConstraints(maxHeight: 200),
                      color: Theme.of(context).scaffoldBackgroundColor,
                      child: SingleChildScrollView(
                        child: SelectableText(
                          _log!,
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 12,
                            height: 1.5,
                          ),
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
