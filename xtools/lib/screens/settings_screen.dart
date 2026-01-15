import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/app_state.dart';
import '../services/config_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _discordTokenController = TextEditingController();
  final _telegramApiIdController = TextEditingController();
  final _telegramApiHashController = TextEditingController();
  final _telegramPhoneController = TextEditingController();
  final _dropboxAppKeyController = TextEditingController();
  final _dropboxAppSecretController = TextEditingController();
  final _dropboxRefreshTokenController = TextEditingController();
  
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    setState(() => _isLoading = true);
    
    final configService = ConfigService();

    // Load Discord
    final discordToken = await configService.getDiscordToken();
    if (discordToken != null) {
      _discordTokenController.text = discordToken;
    }

    // Load Telegram
    final telegramCreds = await configService.getTelegramCredentials();
    if (telegramCreds['apiId'] != null) {
      _telegramApiIdController.text = telegramCreds['apiId']!;
    }
    if (telegramCreds['apiHash'] != null) {
      _telegramApiHashController.text = telegramCreds['apiHash']!;
    }
    if (telegramCreds['phone'] != null) {
      _telegramPhoneController.text = telegramCreds['phone']!;
    }

    // Load Dropbox
    final dropboxCreds = await configService.getDropboxCredentials();
    if (dropboxCreds['appKey'] != null) {
      _dropboxAppKeyController.text = dropboxCreds['appKey']!;
    }
    if (dropboxCreds['appSecret'] != null) {
      _dropboxAppSecretController.text = dropboxCreds['appSecret']!;
    }
    if (dropboxCreds['refreshToken'] != null) {
      _dropboxRefreshTokenController.text = dropboxCreds['refreshToken']!;
    }

    setState(() => _isLoading = false);
  }

  Future<void> _saveDiscordConfig() async {
    if (_discordTokenController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Token cannot be empty')),
      );
      return;
    }

    final configService = ConfigService();

    await configService.saveDiscordToken(_discordTokenController.text);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Discord token saved securely'),
          backgroundColor: Colors.green,
        ),
      );
    }
  }

  Future<void> _saveTelegramConfig() async {
    if (_telegramApiIdController.text.isEmpty ||
        _telegramApiHashController.text.isEmpty ||
        _telegramPhoneController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('All Telegram fields are required')),
      );
      return;
    }

    final configService = ConfigService();

    await configService.saveTelegramCredentials(
      _telegramApiIdController.text,
      _telegramApiHashController.text,
      _telegramPhoneController.text,
    );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Telegram credentials saved securely'),
          backgroundColor: Colors.green,
        ),
      );
    }
  }

  Future<void> _saveDropboxConfig() async {
    if (_dropboxAppKeyController.text.isEmpty ||
        _dropboxAppSecretController.text.isEmpty ||
        _dropboxRefreshTokenController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('All Dropbox fields are required')),
      );
      return;
    }

    final configService = ConfigService();

    await configService.saveDropboxCredentials(
      _dropboxAppKeyController.text,
      _dropboxAppSecretController.text,
      _dropboxRefreshTokenController.text,
    );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Dropbox credentials saved securely'),
          backgroundColor: Colors.green,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final appState = Provider.of<AppState>(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        actions: [
          IconButton(
            icon: Icon(appState.themeMode == ThemeMode.dark ? Icons.light_mode : Icons.dark_mode),
            onPressed: () {
              appState.toggleTheme();
              _saveThemeMode(appState.themeMode);
            },
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Theme
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.dark_mode),
                      title: const Text('Dark Mode'),
                      trailing: Switch(
                        value: appState.themeMode == ThemeMode.dark,
                        onChanged: (value) {
                          appState.setTheme(value ? ThemeMode.dark : ThemeMode.light);
                          _saveThemeMode(appState.themeMode);
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Discord
                  _buildSection(
                    'Discord Bot',
                    Icons.chat,
                    [
                      TextField(
                        controller: _discordTokenController,
                        decoration: const InputDecoration(
                          labelText: 'Bot Token',
                          prefixIcon: Icon(Icons.lock),
                          border: OutlineInputBorder(),
                        ),
                        obscureText: true,
                      ),
                      const SizedBox(height: 8),
                      ElevatedButton.icon(
                        onPressed: _saveDiscordConfig,
                        icon: const Icon(Icons.save),
                        label: const Text('Save Discord Config'),
                      ),
                    ],
                  ),

                  const SizedBox(height: 16),

                  // Telegram
                  _buildSection(
                    'Telegram',
                    Icons.telegram,
                    [
                      TextField(
                        controller: _telegramApiIdController,
                        decoration: const InputDecoration(
                          labelText: 'API ID',
                          prefixIcon: Icon(Icons.numbers),
                          border: OutlineInputBorder(),
                        ),
                        keyboardType: TextInputType.number,
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _telegramApiHashController,
                        decoration: const InputDecoration(
                          labelText: 'API Hash',
                          prefixIcon: Icon(Icons.lock),
                          border: OutlineInputBorder(),
                        ),
                        obscureText: true,
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _telegramPhoneController,
                        decoration: const InputDecoration(
                          labelText: 'Phone Number',
                          prefixIcon: Icon(Icons.phone),
                          border: OutlineInputBorder(),
                          hintText: '+1234567890',
                        ),
                      ),
                      const SizedBox(height: 8),
                      ElevatedButton.icon(
                        onPressed: _saveTelegramConfig,
                        icon: const Icon(Icons.save),
                        label: const Text('Save Telegram Config'),
                      ),
                    ],
                  ),

                  const SizedBox(height: 16),

                  // Dropbox
                  _buildSection(
                    'Dropbox',
                    Icons.cloud,
                    [
                      TextField(
                        controller: _dropboxAppKeyController,
                        decoration: const InputDecoration(
                          labelText: 'App Key',
                          prefixIcon: Icon(Icons.key),
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _dropboxAppSecretController,
                        decoration: const InputDecoration(
                          labelText: 'App Secret',
                          prefixIcon: Icon(Icons.lock),
                          border: OutlineInputBorder(),
                        ),
                        obscureText: true,
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _dropboxRefreshTokenController,
                        decoration: const InputDecoration(
                          labelText: 'Refresh Token',
                          prefixIcon: Icon(Icons.refresh),
                          border: OutlineInputBorder(),
                        ),
                        obscureText: true,
                      ),
                      const SizedBox(height: 8),
                      ElevatedButton.icon(
                        onPressed: _saveDropboxConfig,
                        icon: const Icon(Icons.save),
                        label: const Text('Save Dropbox Config'),
                      ),
                    ],
                  ),

                  const SizedBox(height: 24),

                  // About
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.info),
                      title: const Text('About XTools'),
                      subtitle: const Text('v1.0.0 - Cross-platform tool suite'),
                      onTap: () {
                        showAboutDialog(
                          context: context,
                          applicationName: 'XTools',
                          applicationVersion: '1.0.0',
                          applicationLegalese: '© 2026 XTools',
                          children: [
                            const SizedBox(height: 8),
                            const Text('All your tools in one place.'),
                            const Text('Secure, fast, and cross-platform.'),
                          ],
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildSection(String title, IconData icon, List<Widget> children) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: Theme.of(context).primaryColor),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...children,
          ],
        ),
      ),
    );
  }

  Future<void> _saveThemeMode(ThemeMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('theme_mode', mode.toString().split('.').last);
  }

  @override
  void dispose() {
    _discordTokenController.dispose();
    _telegramApiIdController.dispose();
    _telegramApiHashController.dispose();
    _telegramPhoneController.dispose();
    _dropboxAppKeyController.dispose();
    _dropboxAppSecretController.dispose();
    _dropboxRefreshTokenController.dispose();
    super.dispose();
  }
}
