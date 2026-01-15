import 'package:flutter/material.dart';
import 'discord_bot_screen.dart';
import 'telegram_bot_screen.dart';
import 'gofile_screen.dart';
import 'scraper_screen.dart';
import 'data_tools_screen.dart';
import 'combo_db_screen.dart';
import 'xbox_screen.dart';
import 'captcha_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('XTools'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.pushNamed(context, '/settings'),
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [Colors.indigo, Colors.indigo.shade700],
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.apps, color: Colors.white, size: 32),
                const SizedBox(width: 12),
                Text(
                  'All Tools',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: GridView.count(
              padding: const EdgeInsets.all(16),
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              children: [
                _buildToolCard(context, 'Gofile', Icons.cloud_upload, Colors.blue, const GofileScreen(), 'Upload files'),
                _buildToolCard(context, 'Scraper', Icons.scanner, Colors.green, const ScraperScreen(), 'Scrape websites'),
                _buildToolCard(context, 'Data Tools', Icons.dataset, Colors.orange, const DataToolsScreen(), 'Process data'),
                _buildToolCard(context, 'Discord', Icons.chat, Colors.purple, const DiscordBotScreen(), 'Bot control'),
                _buildToolCard(context, 'Telegram', Icons.telegram, Colors.blue, const TelegramBotScreen(), 'Bot control'),
                _buildToolCard(context, 'Combo DB', Icons.storage, Colors.teal, const ComboDBScreen(), 'Database'),
                _buildToolCard(context, 'Xbox', Icons.videogame_asset, Colors.red, const XboxScreen(), 'Checker'),
                _buildToolCard(context, 'CAPTCHA', Icons.security, Colors.amber, const CaptchaScreen(), 'Solver'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToolCard(
    BuildContext context,
    String title,
    IconData icon,
    Color color,
    Widget screen,
    String subtitle,
  ) {
    return Card(
      elevation: 4,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => screen)),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 8),
              Text(
                title,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: TextStyle(fontSize: 11, color: Theme.of(context).textTheme.bodySmall?.color),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
