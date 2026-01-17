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
  final _channelIdsController = TextEditingController();
  final _dropboxAppKeyController = TextEditingController();
  final _dropboxAppSecretController = TextEditingController();
  final _dropboxRefreshTokenController = TextEditingController();
  
  final _botService = BotService();
  final _configService = ConfigService();
  
  bool _isRunning = false;
  bool _isLoading = false;
  bool _showDropboxConfig = false;
  String? _status;
  String? _error;
  String? _log;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    final creds = await _configService.getTelegramCredentials();
    if (creds['apiId'] != null) {
      _apiIdController.text = creds['apiId']!;
      _apiHashController.text = creds['apiHash'] ?? '';
      _phoneController.text = creds['phone'] ?? '';
    }
    
    final channels = await _configService.getTelegramChannels();
    if (channels.isNotEmpty) {
      _channelIdsController.text = channels.join('\n');
    }
    
    final dropbox = await _configService.getDropboxCredentials();
    if (dropbox['appKey'] != null) {
      _dropboxAppKeyController.text = dropbox['appKey']!;
      _dropboxAppSecretController.text = dropbox['appSecret'] ?? '';
      _dropboxRefreshTokenController.text = dropbox['refreshToken'] ?? '';
      setState(() {
        _showDropboxConfig = true;
      });
    }
  }

  Future<void> _startBot() async {
    if (_apiIdController.text.isEmpty || _apiHashController.text.isEmpty || _phoneController.text.isEmpty) {
      setState(() {
        _error = 'Please fill in all API credentials first';
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
      // Parse channel IDs
      final channelIds = _channelIdsController.text
          .split('\n')
          .map((e) => e.trim())
          .where((e) => e.isNotEmpty)
          .toList();
      
      // Prepare Dropbox config if enabled
      Map<String, String>? dropboxConfig;
      if (_showDropboxConfig && _dropboxAppKeyController.text.isNotEmpty) {
        dropboxConfig = {
          'app_key': _dropboxAppKeyController.text,
          'app_secret': _dropboxAppSecretController.text,
          'refresh_token': _dropboxRefreshTokenController.text,
        };
      }

      final result = await _botService.startTelegramBot(
        apiId: _apiIdController.text,
        apiHash: _apiHashController.text,
        phone: _phoneController.text,
        channelIds: channelIds.isNotEmpty ? channelIds : null,
        dropboxConfig: dropboxConfig,
      );
      
      setState(() {
        _isLoading = false;
        if (result['success'] == true) {
          _isRunning = true;
          _status = 'Bot is running';
          _log = '''[INFO] Telegram Bot started
[INFO] ${result['message'] ?? 'Connected successfully'}
[INFO] Connecting to Telegram API...
[INFO] Session initialized
[INFO] Monitoring ${channelIds.length} channels...
[INFO] ${_showDropboxConfig ? 'Dropbox integration enabled' : 'No Dropbox integration'}
[INFO] Ready to forward messages''';
        } else {
          _error = result['error'] ?? 'Failed to start bot';
          _log = '[ERROR] ${result['error']}';
        }
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to start: $e';
        _log = '[ERROR] $e';
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
        _log = (_log ?? '') + '\n[INFO] Bot stopped successfully';
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to stop: $e';
      });
    }
  }

  Future<void> _saveConfig() async {
    if (_apiIdController.text.isEmpty || _apiHashController.text.isEmpty || _phoneController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please fill in all API credentials')),
      );
      return;
    }

    await _configService.saveTelegramCredentials(
      _apiIdController.text,
      _apiHashController.text,
      _phoneController.text,
    );
    
    // Save channel IDs
    final channelIds = _channelIdsController.text
        .split('\n')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    await _configService.saveTelegramChannels(channelIds);
    
    // Save Dropbox config if enabled
    if (_showDropboxConfig && _dropboxAppKeyController.text.isNotEmpty) {
      await _configService.saveDropboxCredentials(
        _dropboxAppKeyController.text,
        _dropboxAppSecretController.text,
        _dropboxRefreshTokenController.text,
      );
    }

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Configuration saved securely'), backgroundColor: Colors.green),
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
            // API Credentials Card
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
                        hintText: 'From my.telegram.org',
                        prefixIcon: Icon(Icons.numbers),
                        border: OutlineInputBorder(),
                      ),
                      keyboardType: TextInputType.number,
                      enabled: !_isRunning,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _apiHashController,
                      decoration: const InputDecoration(
                        labelText: 'API Hash',
                        hintText: 'From my.telegram.org',
                        prefixIcon: Icon(Icons.lock),
                        border: OutlineInputBorder(),
                      ),
                      obscureText: true,
                      enabled: !_isRunning,
                    ),
                    const SizedBox(height: 12),
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
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 16),
            
            // Channel IDs Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.forum, color: Theme.of(context).primaryColor),
                        const SizedBox(width: 8),
                        const Text('Channels to Monitor', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _channelIdsController,
                      decoration: const InputDecoration(
                        labelText: 'Channel IDs (one per line)',
                        hintText: '-1001234567890\n-1009876543210',
                        prefixIcon: Icon(Icons.list),
                        border: OutlineInputBorder(),
                      ),
                      maxLines: 4,
                      enabled: !_isRunning,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Enter channel/group IDs to monitor. Get IDs from @userinfobot',
                      style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 16),
            
            // Dropbox Integration Card
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
                            Icon(Icons.cloud, color: Theme.of(context).primaryColor),
                            const SizedBox(width: 8),
                            const Text('Dropbox Integration', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                          ],
                        ),
                        Switch(
                          value: _showDropboxConfig,
                          onChanged: _isRunning ? null : (value) {
                            setState(() {
                              _showDropboxConfig = value;
                            });
                          },
                        ),
                      ],
                    ),
                    if (_showDropboxConfig) ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: _dropboxAppKeyController,
                        decoration: const InputDecoration(
                          labelText: 'App Key',
                          prefixIcon: Icon(Icons.key),
                          border: OutlineInputBorder(),
                        ),
                        enabled: !_isRunning,
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _dropboxAppSecretController,
                        decoration: const InputDecoration(
                          labelText: 'App Secret',
                          prefixIcon: Icon(Icons.lock_outline),
                          border: OutlineInputBorder(),
                        ),
                        obscureText: true,
                        enabled: !_isRunning,
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _dropboxRefreshTokenController,
                        decoration: const InputDecoration(
                          labelText: 'Refresh Token',
                          prefixIcon: Icon(Icons.refresh),
                          border: OutlineInputBorder(),
                        ),
                        obscureText: true,
                        enabled: !_isRunning,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Files will be automatically uploaded to Dropbox',
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
                              'Telegram API Credentials:\n'
                              '1. Go to my.telegram.org\n'
                              '2. Log in with your phone number\n'
                              '3. Go to "API development tools"\n'
                              '4. Create a new application\n'
                              '5. Copy API ID and API Hash\n\n'
                              'Channel IDs:\n'
                              '1. Forward a message from the channel to @userinfobot\n'
                              '2. Copy the channel ID (starts with -100)\n\n'
                              'Dropbox (optional):\n'
                              '1. Create an app at dropbox.com/developers\n'
                              '2. Generate a refresh token\n'
                              '3. Files will be auto-uploaded',
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
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation(Colors.white)))
                      : const Icon(Icons.play_arrow),
                    label: Text(_isRunning ? 'Running' : 'Start Bot'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blue,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _isLoading ? null : (_isRunning ? _stopBot : null),
                    icon: _isLoading && _isRunning
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation(Colors.white)))
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
                        _error != null ? Icons.error : (_isRunning ? Icons.check_circle : Icons.info),
                        color: _error != null 
                            ? Theme.of(context).colorScheme.error 
                            : _isRunning ? Colors.green : Theme.of(context).primaryColor,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _error ?? _status!,
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
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
                          style: const TextStyle(fontFamily: 'monospace', fontSize: 12, height: 1.5),
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

  @override
  void dispose() {
    _apiIdController.dispose();
    _apiHashController.dispose();
    _phoneController.dispose();
    _channelIdsController.dispose();
    _dropboxAppKeyController.dispose();
    _dropboxAppSecretController.dispose();
    _dropboxRefreshTokenController.dispose();
    super.dispose();
  }
}
