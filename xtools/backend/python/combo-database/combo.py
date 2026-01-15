#!/usr/bin/env python3
"""
Combo Parser - Extracts domain, username/email, and password from combo files
Stores clean domain names (like google.com) instead of full URLs
"""

import os
import re
import sqlite3
import urllib.parse
import time
from pathlib import Path
from typing import List, Tuple, Optional
import logging
import sys
import argparse
import fcntl

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComboParser:
    def __init__(self, db_path: str = "combos.db"):
        """Initialize the combo parser with database connection"""
        self.db_path = db_path
        self.lock_path = f"{db_path}.lock"
        self.init_database()
        
        # Email regex pattern - more comprehensive
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
        
        # Batch processing for better performance
        self.batch_size = 20000
        self.batch_data = []
    
    def acquire_lock(self):
        """Acquire database lock"""
        lock_file = open(self.lock_path, 'w')
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            logger.info(f"Database lock acquired: {self.lock_path}")
            return lock_file
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            lock_file.close()
            return None

    def release_lock(self, lock_file):
        """Release database lock"""
        if lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
                logger.info(f"Database lock released: {self.lock_path}")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")

    def init_database(self):
        """Initialize SQLite database with combos table"""
        try:
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)

            # Acquire lock before database operations
            lock_file = self.acquire_lock()
            if not lock_file:
                raise Exception("Could not acquire database lock")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''CREATE TABLE IF NOT EXISTS combos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                username TEXT,
                password TEXT,
                UNIQUE(url, username, password)
            )''')

            # Create indexes for faster lookups
            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_username
                ON combos (username)''')

            cursor.execute('''CREATE INDEX IF NOT EXISTS idx_url
                ON combos (url)''')

            conn.commit()
            conn.close()

            # Release lock after database operations
            self.release_lock(lock_file)

            logger.info(f"Database initialized: {self.db_path}")

        except Exception as e:
            # Release lock in case of error
            if 'lock_file' in locals() and lock_file:
                self.release_lock(lock_file)
            logger.error(f"Error initializing database: {e}")
            raise
    
    def extract_domain(self, url: str) -> Optional[str]:
        """Extract clean domain name from URL with strict validation"""
        url = url.strip()
        
        # Skip obviously malformed entries
        if not url or len(url) > 500:
            return None
        
        # Handle special android URLs - filter out meaningless ones
        if url.startswith('android://'):
            # Skip android URLs that are just random tokens/hashes
            android_path = url[10:]  # Remove 'android://' prefix
            
            # If it's just a long random string (likely a token), skip it
            if len(android_path) > 20 and not '.' in android_path:
                return None
            
            # If it contains a recognizable domain pattern, extract it
            if '.' in android_path and not android_path.startswith('http'):
                # Try to extract domain from android URL
                domain_part = android_path.split('/')[0]
                if '.' in domain_part:
                    return self.extract_domain(domain_part)
            
            # For other android URLs, return as-is but with cleaner format
            return f"android-app://{android_path}"
        
        try:
            # Remove protocol if present
            if '://' in url:
                url = url.split('://', 1)[1]
            
            # Remove path, query, fragment
            url = url.split('/')[0].split('?')[0].split('#')[0]
            
            # Remove port (but handle IPv6)
            if ':' in url and not url.count(':') > 1:
                url = url.split(':')[0]
            
            # Remove www. prefix if present
            if url.startswith('www.'):
                url = url[4:]
            
            url = url.lower().strip()
            
            # Validate IP addresses
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', url):
                # Valid IPv4
                parts = url.split('.')
                if all(0 <= int(part) <= 255 for part in parts):
                    return url
                else:
                    return None
            
            # Validate domain names
            if not url or '.' not in url:
                return None
            
            # Check for valid domain format
            if url.startswith('.') or url.endswith('.') or '..' in url:
                return None
            
            # Must contain valid TLD
            valid_tlds = {
                'com', 'org', 'net', 'edu', 'gov', 'mil', 'int', 'co', 'io', 'ai', 'me', 'tv', 'cc',
                'de', 'uk', 'fr', 'it', 'es', 'nl', 'be', 'ch', 'at', 'se', 'no', 'dk', 'fi', 'pl',
                'ru', 'ua', 'by', 'kz', 'uz', 'kg', 'tj', 'tm', 'am', 'az', 'ge', 'md', 'lt', 'lv', 'ee',
                'cn', 'jp', 'kr', 'in', 'sg', 'my', 'th', 'vn', 'ph', 'id', 'au', 'nz', 'hk', 'tw',
                'br', 'ar', 'cl', 'co', 'pe', 'mx', 've', 'ec', 'uy', 'py', 'bo', 'cr', 'gt', 'pa',
                'ca', 'us', 'za', 'ng', 'ke', 'gh', 'eg', 'ma', 'tn', 'dz', 'ly', 'sd', 'et', 'ug',
                'xyz', 'top', 'site', 'online', 'tech', 'store', 'app', 'dev', 'blog', 'news', 'info',
                'biz', 'name', 'pro', 'mobi', 'tel', 'travel', 'jobs', 'cat', 'asia', 'xxx', 'museum'
            }
            
            # Get TLD (last part after final dot)
            tld = url.split('.')[-1]
            if tld not in valid_tlds:
                # Allow some common country code TLDs that might be missing
                if len(tld) == 2 and tld.isalpha():  # Country codes
                    pass  # Allow 2-letter country codes
                elif len(tld) < 2 or len(tld) > 10:  # Invalid TLD length
                    return None
            
            # Check for invalid characters
            if not re.match(r'^[a-z0-9.-]+$', url):
                return None
            
            # Must have at least one letter (not just numbers and dots)
            if not re.search(r'[a-z]', url):
                return None
            
            # Domain parts validation
            parts = url.split('.')
            if len(parts) < 2:
                return None
            
            # Each part must be valid
            for part in parts:
                if not part or len(part) > 63:  # DNS label limit
                    return None
                if part.startswith('-') or part.endswith('-'):
                    return None
                if not re.match(r'^[a-z0-9-]+$', part):
                    return None
            
            return url
            
        except:
            return None
    
    def is_valid_username(self, username: str) -> bool:
        """Validate username or email"""
        username = username.strip()
        
        # Basic validation
        if not username or len(username) < 1 or len(username) > 200:
            return False
        
        # Skip obviously malformed usernames
        if username.startswith(('http', 'www.', '//', 'android://', 'ftp://')):
            return False
        
        # Skip usernames that look like URLs or paths
        if '://' in username or username.startswith('/'):
            return False
        
        # If it contains @, validate as email
        if '@' in username:
            return self.is_valid_email(username)
        
        # For regular usernames, check for reasonable characters
        if not re.match(r'^[a-zA-Z0-9._+-]+$', username):
            # Allow some special characters but not too many
            special_chars = sum(1 for c in username if not c.isalnum())
            if special_chars > len(username) * 0.3:  # More than 30% special chars
                return False
        
        return True
    
    def is_valid_email(self, email: str) -> bool:
        """Validate email address"""
        email = email.strip().lower()
        
        # Basic email format check
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False
        
        # Split into local and domain parts
        try:
            local, domain = email.split('@', 1)
        except:
            return False
        
        # Validate local part
        if not local or len(local) > 64:
            return False
        
        # Validate domain part
        if not domain or len(domain) > 255:
            return False
        
        # Domain must have at least one dot
        if '.' not in domain:
            return False
        
        # Check domain format
        domain_parts = domain.split('.')
        if len(domain_parts) < 2:
            return False
        
        # Each domain part must be valid
        for part in domain_parts:
            if not part or len(part) > 63:
                return False
            if not re.match(r'^[a-zA-Z0-9-]+$', part):
                return False
            if part.startswith('-') or part.endswith('-'):
                return False
        
        # TLD validation
        tld = domain_parts[-1].lower()
        if len(tld) < 2 or len(tld) > 10:
            return False
        
        return True
    
    def is_valid_password(self, password: str) -> bool:
        """Validate password"""
        password = password.strip()
        
        # Basic validation
        if not password or len(password) < 1 or len(password) > 200:
            return False
        
        # Skip obviously malformed passwords
        if password.startswith(('http', 'www.', '//', 'android://', 'ftp://')):
            return False
        
        # Skip passwords that look like URLs
        if '://' in password:
            return False
        
        return True
    
    def parse_combo_line(self, line: str) -> Optional[Tuple[str, str, str]]:
        """Parse a single combo line using reverse parsing logic"""
        line = line.strip()
        if not line or line.startswith('#'):
            return None
        
        # Count colons
        colon_count = line.count(':')
        
        if colon_count < 2:
            return None
        
        # Find the last two colons
        # This handles cases where URL or password contain colons
        last_colon_pos = line.rfind(':')
        if last_colon_pos == -1:
            return None
        
        # Extract password (everything after last colon)
        password = line[last_colon_pos + 1:]
        remaining = line[:last_colon_pos]
        
        # Find second-to-last colon
        second_last_colon_pos = remaining.rfind(':')
        if second_last_colon_pos == -1:
            return None
        
        # Extract username (between second-to-last and last colon)
        username = remaining[second_last_colon_pos + 1:]
        url = remaining[:second_last_colon_pos]
        
        # Extract domain from URL
        domain = self.extract_domain(url)
        if not domain:
            return None
        
        # Validate username
        if not self.is_valid_username(username):
            return None
        
        # Validate password
        if not self.is_valid_password(password):
            return None
        
        return (domain, username, password)
    
    def flush_batch(self):
        """Flush batch data to database"""
        if not self.batch_data:
            return

        try:
            # Acquire lock before database operations
            lock_file = self.acquire_lock()
            if not lock_file:
                raise Exception("Could not acquire database lock")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Use INSERT OR IGNORE to handle duplicates efficiently
            cursor.executemany('''
                INSERT OR IGNORE INTO combos (url, username, password)
                VALUES (?, ?, ?)
            ''', self.batch_data)

            added = cursor.rowcount
            conn.commit()
            conn.close()

            # Release lock after database operations
            self.release_lock(lock_file)

            logger.info(f"Batch processed: {len(self.batch_data)} entries, {added} new entries added")
            self.batch_data = []

        except Exception as e:
            # Release lock in case of error
            if 'lock_file' in locals() and lock_file:
                self.release_lock(lock_file)
            logger.error(f"Error flushing batch: {e}")
            self.batch_data = []
    
    def add_batch_combo(self, url: str, username: str, password: str):
        """Add combo to batch for processing"""
        self.batch_data.append((url, username, password))
        
        if len(self.batch_data) >= self.batch_size:
            self.flush_batch()
    
    def parse_file(self, file_path: str) -> Tuple[int, int]:
        """Parse a combo file, remove processed lines, and return (total_lines, valid_combos)"""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return (0, 0)
        
        total_lines = 0
        valid_combos = 0
        remaining_lines = []
        
        try:
            # Read all lines from the file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()
            
            for line in lines:
                total_lines += 1
                original_line = line.rstrip('\n\r')
                
                combo = self.parse_combo_line(original_line)
                if combo:
                    url, username, password = combo
                    self.add_batch_combo(url, username, password)
                    valid_combos += 1
                    # Don't add processed lines to remaining_lines (effectively deleting them)
                    logger.debug(f"Processed and removed: {original_line[:50]}...")
                else:
                    # Keep unprocessed/invalid lines in the file
                    remaining_lines.append(line)
                
                # Progress logging for large files
                if total_lines % 10000 == 0:
                    logger.info(f"Processed {total_lines} lines from {file_path}")
            
            # Flush any remaining batch data
            self.flush_batch()
            
            # Write back only the remaining (unprocessed) lines
            if remaining_lines:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.writelines(remaining_lines)
                logger.info(f"File updated: {file_path} - {len(remaining_lines)} lines remaining")
            else:
                # If no lines remain, delete the file
                os.remove(file_path)
                logger.info(f"File completely processed and deleted: {file_path}")
            
            logger.info(f"File parsing complete: {file_path}")
            logger.info(f"Total lines: {total_lines}, Valid combos: {valid_combos}, Remaining lines: {len(remaining_lines)}")
            
            return (total_lines, valid_combos)
            
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return (total_lines, valid_combos)
    
    def parse_directory(self, directory_path: str) -> None:
        """Parse all combo files in a directory"""
        directory = Path(directory_path)
        
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory_path}")
            return
        
        # Find all potential combo files
        combo_files = []
        for pattern in ['*.txt', '*.log', '*.dat']:
            combo_files.extend(directory.glob(pattern))
        
        # Also look for files with 'combo' in the name
        for file_path in directory.iterdir():
            if file_path.is_file() and 'combo' in file_path.name.lower():
                if file_path not in combo_files:
                    combo_files.append(file_path)
        
        if not combo_files:
            logger.warning(f"No combo files found in directory: {directory_path}")
            return
        
        logger.info(f"Found {len(combo_files)} combo files to process")
        
        total_processed = 0
        total_added = 0
        
        for file_path in combo_files:
            logger.info(f"Processing file: {file_path}")
            processed, added = self.parse_file(str(file_path))
            total_processed += processed
            total_added += added
        
        logger.info(f"Directory processing complete!")
        logger.info(f"Total processed: {total_processed}, Total added: {total_added}")

    def get_stats(self) -> dict:
        """Get database statistics"""
        try:
            # Acquire lock before database operations
            lock_file = self.acquire_lock()
            if not lock_file:
                raise Exception("Could not acquire database lock")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total combos
            cursor.execute("SELECT COUNT(*) FROM combos")
            total_combos = cursor.fetchone()[0]
            
            # Unique domains
            cursor.execute("SELECT COUNT(DISTINCT url) FROM combos")
            unique_domains = cursor.fetchone()[0]
            
            # Unique usernames
            cursor.execute("SELECT COUNT(DISTINCT username) FROM combos")
            unique_usernames = cursor.fetchone()[0]
            
            # Top domains
            cursor.execute("""
                SELECT url, COUNT(*) as count 
                FROM combos 
                GROUP BY url 
                ORDER BY count DESC 
                LIMIT 10
            """)
            top_domains = cursor.fetchall()
            
            conn.close()
            
            # Release lock after database operations
            self.release_lock(lock_file)
            
            return {
                'total_combos': total_combos,
                'unique_domains': unique_domains,
                'unique_usernames': unique_usernames,
                'top_domains': top_domains
            }
            
        except Exception as e:
            # Release lock in case of error
            if 'lock_file' in locals() and lock_file:
                self.release_lock(lock_file)
            logger.error(f"Error getting stats: {e}")
            return {}

    def search_by_domain(self, domain: str, limit: int = 50) -> List[Tuple[str, str, str]]:
        """Search combos by domain"""
        try:
            # Acquire lock before database operations
            lock_file = self.acquire_lock()
            if not lock_file:
                raise Exception("Could not acquire database lock")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT url, username, password 
                FROM combos 
                WHERE url LIKE ? 
                ORDER BY url, username 
                LIMIT ?
            """, (f'%{domain}%', limit))
            
            results = cursor.fetchall()
            conn.close()
            
            # Release lock after database operations
            self.release_lock(lock_file)
            
            return results
            
        except Exception as e:
            # Release lock in case of error
            if 'lock_file' in locals() and lock_file:
                self.release_lock(lock_file)
            logger.error(f"Error searching by domain: {e}")
            return []

    def search_by_username(self, username: str, limit: int = 50) -> List[Tuple[str, str, str]]:
        """Search combos by username"""
        try:
            # Acquire lock before database operations
            lock_file = self.acquire_lock()
            if not lock_file:
                raise Exception("Could not acquire database lock")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT url, username, password 
                FROM combos 
                WHERE username LIKE ? 
                ORDER BY url, username 
                LIMIT ?
            """, (f'%{username}%', limit))
            
            results = cursor.fetchall()
            conn.close()
            
            # Release lock after database operations
            self.release_lock(lock_file)
            
            return results
            
        except Exception as e:
            # Release lock in case of error
            if 'lock_file' in locals() and lock_file:
                self.release_lock(lock_file)
            logger.error(f"Error searching by username: {e}")
            return []

    def export_to_csv(self, output_file: str = "combos_export.csv") -> None:
        """Export combos to CSV file"""
        try:
            # Acquire lock before database operations
            lock_file = self.acquire_lock()
            if not lock_file:
                raise Exception("Could not acquire database lock")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT url, username, password FROM combos")
            
            import csv
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Domain', 'Username', 'Password'])  # Header
                
                for row in cursor:
                    writer.writerow(row)
            
            conn.close()
            
            # Release lock after database operations
            self.release_lock(lock_file)
            
            logger.info(f"Data exported to {output_file}")
            
        except Exception as e:
            # Release lock in case of error
            if 'lock_file' in locals() and lock_file:
                self.release_lock(lock_file)
            logger.error(f"Error exporting to CSV: {e}")

    def display_results(self, results: List[Tuple[str, str, str]], title: str):
        """Display search results in a formatted way"""
        if not results:
            print(f"\nNo results found for {title}")
            return
        
        print(f"\n{title} ({len(results)} results):")
        print("-" * 80)
        for i, (url, username, password) in enumerate(results, 1):
            print(f"{i:3d}. {url:30s} | {username:25s} | {password[:20]}...")
        print("-" * 80)

    def get_top_domains(self, limit: int = 20):
        """Get and display top domains by combo count"""
        try:
            # Acquire lock before database operations
            lock_file = self.acquire_lock()
            if not lock_file:
                raise Exception("Could not acquire database lock")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT url, COUNT(*) as count 
                FROM combos 
                GROUP BY url 
                ORDER BY count DESC 
                LIMIT ?
            """, (limit,))
            
            results = cursor.fetchall()
            conn.close()
            
            # Release lock after database operations
            self.release_lock(lock_file)
            
            if results:
                print(f"\nTop {len(results)} domains by combo count:")
                print("-" * 50)
                for i, (domain, count) in enumerate(results, 1):
                    print(f"{i:3d}. {domain:30s} ({count:,} combos)")
                print("-" * 50)
            else:
                print("No domains found")
                
        except Exception as e:
            # Release lock in case of error
            if 'lock_file' in locals() and lock_file:
                self.release_lock(lock_file)
            logger.error(f"Error getting top domains: {e}")

    def test_parsing(self, test_lines: List[str]):
        """Test the parsing logic with sample lines"""
        print("\nTesting combo parsing logic:")
        print("-" * 60)
        
        for i, line in enumerate(test_lines, 1):
            result = self.parse_combo_line(line)
            if result:
                domain, username, password = result
                print(f"{i:2d}. ✓ {line[:40]:40s} -> {domain} | {username} | {password[:10]}...")
            else:
                print(f"{i:2d}. ✗ {line[:40]:40s} -> INVALID")
        
        print("-" * 60)


def main():
    """Main function to handle command line arguments"""
    parser = argparse.ArgumentParser(description='Combo Parser and Search Tool')
    parser.add_argument('command', nargs='?', choices=['parse', 'stats', 'top', 'domain', 'user', 'export', 'test'],
                       help='Command to execute')
    parser.add_argument('query', nargs='?', help='Search query (for domain/user commands)')
    parser.add_argument('--limit', type=int, default=50, help='Limit number of results')
    parser.add_argument('--output', default='combos_export.csv', help='Output file for export')
    parser.add_argument('--db', default='combos.db', help='Database file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    combo_parser = ComboParser(args.db)
    
    if args.command == 'parse':
        # Parse combo files in 'combos' directory
        combos_dir = 'combos'
        if not os.path.exists(combos_dir):
            logger.error(f"Directory '{combos_dir}' not found. Please create it and add combo files.")
            return
        combo_parser.parse_directory(combos_dir)
        
    elif args.command == 'stats':
        stats = combo_parser.get_stats()
        if stats:
            print(f"\nDatabase Statistics:")
            print(f"Total combos: {stats['total_combos']:,}")
            print(f"Unique domains: {stats['unique_domains']:,}")
            print(f"Unique usernames: {stats['unique_usernames']:,}")
            
            if stats['top_domains']:
                print(f"\nTop domains:")
                for domain, count in stats['top_domains']:
                    print(f"  {domain:30s} ({count:,} combos)")
        
    elif args.command == 'top':
        combo_parser.get_top_domains(args.limit)
        
    elif args.command == 'domain':
        if not args.query:
            print("Please provide a domain to search for")
            return
        results = combo_parser.search_by_domain(args.query, args.limit)
        combo_parser.display_results(results, f"Domain search: {args.query}")
        
    elif args.command == 'user':
        if not args.query:
            print("Please provide a username to search for")
            return
        results = combo_parser.search_by_username(args.query, args.limit)
        combo_parser.display_results(results, f"Username search: {args.query}")
        
    elif args.command == 'export':
        combo_parser.export_to_csv(args.output)
        
    elif args.command == 'test':
        # Test parsing with sample lines
        test_lines = [
            "https://example.com:user@example.com:password123",
            "facebook.com:john.doe@gmail.com:mypassword",
            "google.com:testuser:secretpass",
            "invalid:line",
            "https://site.com:user:pass:with:colons",
            "android://com.app.name:username:password",
            "192.168.1.1:admin:admin123"
        ]
        combo_parser.test_parsing(test_lines)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Combo Parser and Search Tool")
        print("Usage:")
        print("  python combo.py parse                    - Parse combo files in 'combos' directory")
        print("  python combo.py stats                    - Show database statistics")
        print("  python combo.py top [--limit N]          - Show top domains")
        print("  python combo.py domain <domain_name>     - Search by domain")
        print("  python combo.py user <username>          - Search by username/email")
        print("  python combo.py export                   - Export to CSV")
        print("  python combo.py test                     - Test parsing logic")
        print()
        print("Examples:")
        print("  python combo.py parse")
        print("  python combo.py stats")
        print("  python combo.py top --limit 15")
        print("  python combo.py domain google.com")
        print("  python combo.py domain facebook")
        print("  python combo.py user john@gmail.com")
        print("  python combo.py export --output my_combos.csv")
    else:
        main()
# XTools FFI Integration
import json

def process_file_ffi(file_path: str) -> str:
    """Process combo file via FFI"""
    try:
        if not os.path.exists(file_path):
            return json.dumps({"success": False, "error": f"File not found: {file_path}"})
        
        # Read and analyze
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        return json.dumps({
            "success": True,
            "total": len(lines),
            "unique": len(set(lines))
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(process_file_ffi(sys.argv[1]))
