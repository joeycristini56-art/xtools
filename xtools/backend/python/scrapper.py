#!/usr/bin/env python3
"""
NoHide.io Scraper
Scrapes nohide.io for file hosting links (gofile, mediafire, upload.ee, etc.)
Downloads files and extracts Gmail/Microsoft email:password combos to combos.txt
Uses cookie authentication for access to hidden content
"""

import requests
import re
import subprocess
import os
import urllib3
import datetime
import threading
import time
import sys
import json
import tempfile
import zipfile
import rarfile
import py7zr
from bs4 import BeautifulSoup
from colorama import Fore, Back, Style, init
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Set, List, Tuple

# Initialize colorama and disable SSL warnings
init(autoreset=True)
urllib3.disable_warnings()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
agent = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
scraped_combos = 0
stats_lock = threading.Lock()
combo_file_lock = threading.Lock()

# Site statistics
site_stats = {
    'nohide.space': {'posts': 0, 'combos': 0, 'status': 'Waiting'}
}

class FileTypeHandler:
    """Handle different file types and extract archives"""
    
    @staticmethod
    def detect_file_type(content_bytes, filename=None):
        """Detect file type from content or filename"""
        if not content_bytes:
            return 'empty'
        
        # Check magic bytes for common archive formats
        if content_bytes.startswith(b'Rar!'):
            return 'rar'
        elif content_bytes.startswith(b'PK'):
            return 'zip'
        elif content_bytes.startswith(b'7z\xbc\xaf\x27\x1c'):
            return '7z'
        elif content_bytes.startswith(b'\x1f\x8b'):
            return 'gzip'
        
        # Check filename extension if available
        if filename:
            ext = filename.lower().split('.')[-1]
            if ext in ['rar', 'zip', '7z', 'gz', 'tar']:
                return ext
            elif ext in ['txt', 'log', 'list']:
                return 'text'
        
        # Try to decode as text
        try:
            content_bytes.decode('utf-8')
            return 'text'
        except:
            try:
                content_bytes.decode('latin-1')
                return 'text'
            except:
                return 'binary'
    
    @staticmethod
    def extract_archive_content(content_bytes, file_type, filename=None):
        """Extract content from archive files"""
        extracted_content = ""
        
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content_bytes)
                temp_file.flush()
                
                if file_type == 'rar':
                    try:
                        with rarfile.RarFile(temp_file.name) as rf:
                            for member in rf.infolist():
                                if not member.is_dir() and member.filename.lower().endswith(('.txt', '.log', '.list')):
                                    try:
                                        data = rf.read(member)
                                        extracted_content += data.decode('utf-8', errors='ignore')
                                    except:
                                        try:
                                            extracted_content += data.decode('latin-1', errors='ignore')
                                        except:
                                            continue
                    except Exception as e:
                        logger.debug(f"RAR extraction failed: {e}")
                        
                elif file_type == 'zip':
                    try:
                        with zipfile.ZipFile(temp_file.name) as zf:
                            for member in zf.infolist():
                                if not member.is_dir() and member.filename.lower().endswith(('.txt', '.log', '.list')):
                                    try:
                                        data = zf.read(member)
                                        extracted_content += data.decode('utf-8', errors='ignore')
                                    except:
                                        try:
                                            extracted_content += data.decode('latin-1', errors='ignore')
                                        except:
                                            continue
                    except Exception as e:
                        logger.debug(f"ZIP extraction failed: {e}")
                        
                elif file_type == '7z':
                    try:
                        with py7zr.SevenZipFile(temp_file.name, mode='r') as sz:
                            for member in sz.getnames():
                                if member.lower().endswith(('.txt', '.log', '.list')):
                                    try:
                                        data = sz.read([member])[member].read()
                                        extracted_content += data.decode('utf-8', errors='ignore')
                                    except:
                                        try:
                                            extracted_content += data.decode('latin-1', errors='ignore')
                                        except:
                                            continue
                    except Exception as e:
                        logger.debug(f"7Z extraction failed: {e}")
                        
        except Exception as e:
            logger.debug(f"Archive extraction error: {e}")
        finally:
            try:
                os.unlink(temp_file.name)
            except:
                pass
                
        return extracted_content
    
    @staticmethod
    def process_file_content(content_bytes, filename=None, host="unknown"):
        """Process file content based on type and extract combos"""
        if not content_bytes:
            return 0
            
        file_type = FileTypeHandler.detect_file_type(content_bytes, filename)
        
        if file_type in ['rar', 'zip', '7z']:
            # Extract archive and process contents
            logger.info(f"Extracting {file_type} archive from {host}")
            extracted_content = FileTypeHandler.extract_archive_content(content_bytes, file_type, filename)
            if extracted_content:
                return FileHandler.save_combos_to_log(extracted_content, host)
            else:
                logger.warning(f"No extractable content found in {file_type} archive from {host}")
                return 0
        elif file_type == 'text':
            # Process as text content
            try:
                text_content = content_bytes.decode('utf-8', errors='ignore')
            except:
                text_content = content_bytes.decode('latin-1', errors='ignore')
            return FileHandler.save_combos_to_log(text_content, host)
        else:
            # Try to process as text anyway (fallback)
            try:
                text_content = content_bytes.decode('utf-8', errors='ignore')
                return FileHandler.save_combos_to_log(text_content, host)
            except:
                logger.warning(f"Could not process binary file from {host}")
                return 0

class EmailFilter:
    """Email filtering functionality from sort.py"""
    
    @staticmethod
    def get_gmail_domains() -> Set[str]:
        """Returns a set of Gmail domain patterns."""
        return {
            'gmail.com',
            'googlemail.com'
        }

    @staticmethod
    def get_microsoft_domains() -> Set[str]:
        """Returns a set of Microsoft domain patterns."""
        return {
            'hotmail.com', 'hotmail.co.uk', 'hotmail.fr', 'hotmail.de', 'hotmail.es',
            'hotmail.it', 'hotmail.ca', 'hotmail.com.au', 'hotmail.co.jp', 'hotmail.co.in',
            'hotmail.com.br', 'hotmail.com.mx', 'hotmail.com.ar', 'hotmail.nl', 'hotmail.be',
            'hotmail.ch', 'hotmail.at', 'hotmail.dk', 'hotmail.se', 'hotmail.no',
            'hotmail.fi', 'hotmail.pl', 'hotmail.cz', 'hotmail.hu', 'hotmail.gr',
            'hotmail.pt', 'hotmail.ru', 'hotmail.com.tr', 'hotmail.co.za', 'hotmail.sg',
            'hotmail.my', 'hotmail.ph', 'hotmail.th', 'hotmail.vn', 'hotmail.co.kr',
            'hotmail.com.tw', 'hotmail.hk', 'hotmail.co.nz', 'hotmail.ie', 'hotmail.co.il',
            'outlook.com', 'outlook.co.uk', 'outlook.fr', 'outlook.de', 'outlook.es',
            'outlook.it', 'outlook.ca', 'outlook.com.au', 'outlook.co.jp', 'outlook.co.in',
            'outlook.com.br', 'outlook.com.mx', 'outlook.com.ar', 'outlook.nl', 'outlook.be',
            'outlook.ch', 'outlook.at', 'outlook.dk', 'outlook.se', 'outlook.no',
            'outlook.fi', 'outlook.pl', 'outlook.cz', 'outlook.hu', 'outlook.gr',
            'outlook.pt', 'outlook.ru', 'outlook.com.tr', 'outlook.co.za', 'outlook.sg',
            'outlook.my', 'outlook.ph', 'outlook.th', 'outlook.vn', 'outlook.co.kr',
            'outlook.com.tw', 'outlook.hk', 'outlook.co.nz', 'outlook.ie', 'outlook.co.il',
            'live.com', 'live.co.uk', 'live.fr', 'live.de', 'live.es', 'live.it',
            'live.ca', 'live.com.au', 'live.co.jp', 'live.co.in', 'live.com.br',
            'live.com.mx', 'live.com.ar', 'live.nl', 'live.be', 'live.ch', 'live.at',
            'live.dk', 'live.se', 'live.no', 'live.fi', 'live.pl', 'live.cz',
            'live.hu', 'live.gr', 'live.pt', 'live.ru', 'live.com.tr', 'live.co.za',
            'live.sg', 'live.my', 'live.ph', 'live.th', 'live.vn', 'live.co.kr',
            'live.com.tw', 'live.hk', 'live.co.nz', 'live.ie', 'live.co.il',
            'msn.com', 'msn.co.uk', 'msn.fr', 'msn.de', 'msn.es', 'msn.it',
            'msn.ca', 'msn.com.au', 'msn.co.jp', 'msn.co.in', 'msn.com.br',
            'msn.com.mx', 'msn.com.ar', 'msn.nl', 'msn.be', 'msn.ch', 'msn.at',
            'msn.dk', 'msn.se', 'msn.no', 'msn.fi', 'msn.pl', 'msn.cz',
            'msn.hu', 'msn.gr', 'msn.pt', 'msn.ru', 'msn.com.tr', 'msn.co.za',
            'msn.sg', 'msn.my', 'msn.ph', 'msn.th', 'msn.vn', 'msn.co.kr',
            'msn.com.tw', 'msn.hk', 'msn.co.nz', 'msn.ie', 'msn.co.il'
        }

    @staticmethod
    def is_valid_email_format(email: str) -> bool:
        """Check if the email has a valid format."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None

    @staticmethod
    def is_target_email(email: str) -> bool:
        """Check if email is from Gmail or Microsoft domains."""
        if not EmailFilter.is_valid_email_format(email):
            return False
        
        domain = email.split('@')[-1].lower()
        gmail_domains = EmailFilter.get_gmail_domains()
        microsoft_domains = EmailFilter.get_microsoft_domains()
        return domain in gmail_domains or domain in microsoft_domains

class FileHandler:
    """File handling functionality from gen.py"""
    
    @staticmethod
    def save_combos_to_log(output, host):
        """Save filtered combos efficiently (thread-safe)"""
        global scraped_combos
        
        if not output or len(output.strip()) == 0:
            return 0

        # Fast regex for email:pass format (optimized)
        email_pattern = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}:[^\s\n\r]+)', re.IGNORECASE)
        matches = email_pattern.findall(output)
        
        if not matches:
            return 0

        # Filter for Gmail/Microsoft emails only (optimized)
        valid_combos = []
        target_domains = {'gmail.com', 'hotmail.com', 'outlook.com', 'live.com', 'msn.com'}
        
        for combo in matches:
            if ':' in combo and len(combo) <= 64:
                try:
                    email_part = combo.split(':', 1)[0].lower()
                    domain = email_part.split('@')[-1]
                    if domain in target_domains:
                        valid_combos.append(combo)
                except:
                    continue

        if valid_combos:
            # Thread-safe file writing
            with combo_file_lock:
                with open('combos.txt', 'a', encoding='utf-8') as f:
                    for combo in valid_combos:
                        f.write(combo + '\n')

            scraped_combos += len(valid_combos)

            # Update site statistics
            with stats_lock:
                for site in site_stats:
                    if site in host:
                        site_stats[site]['combos'] += len(valid_combos)
                        break

            print(f"💾 Saved {len(valid_combos)} valid combos from {host} | Total: {scraped_combos:,}")
            return len(valid_combos)
        return 0

    @staticmethod
    def gofile(link, thread):
        """Handle GoFile downloads using proper API"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Extract content ID from URL
                content_id = link.split("/")[-1] if "/" in link else link
                
                # Create account and get token
                session = requests.Session()
                session.headers.update(agent)
                
                # Get account token with retry logic
                response = session.post("https://api.gofile.io/accounts", timeout=10)
                if response.status_code != 200:
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
                        continue
                    logger.error(f"Failed to create GoFile account for {link} after {max_retries} attempts")
                    return
                    
                account_data = response.json()
                if account_data["status"] != "ok":
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
                        continue
                    logger.error(f"GoFile account creation failed for {link} after {max_retries} attempts")
                    return
                    
                token = account_data["data"]["token"]
                
                # Set authorization headers
                session.cookies.set("accountToken", token)
                session.headers.update({"Authorization": f"Bearer {token}"})
                
                # Get content information
                api_url = f"https://api.gofile.io/contents/{content_id}?wt=4fd6sg89d7s6&cache=true&sortField=createTime&sortDirection=1"
                content_response = session.get(api_url, timeout=10)
                
                if content_response.status_code != 200:
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
                        continue
                    logger.error(f"Failed to get GoFile content for {link} after {max_retries} attempts")
                    return
                    
                content_data = content_response.json()
                if content_data["status"] != "ok":
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
                        continue
                    logger.error(f"GoFile API returned error for {link} after {max_retries} attempts")
                    return
                    
                data = content_data["data"]
                
                # Check if password protected
                if "password" in data and "passwordStatus" in data and data["passwordStatus"] != "passwordOk":
                    logger.error(f"GoFile content is password protected: {link}")
                    return
                
                # Handle single file
                if data["type"] != "folder":
                    download_url = data["link"]
                    file_response = session.get(download_url, timeout=15, stream=True)
                    
                    # Download as bytes to handle all file types
                    content_bytes = b""
                    for chunk in file_response.iter_content(chunk_size=8192):
                        if chunk:
                            content_bytes += chunk
                            # Limit content size to prevent memory issues
                            if len(content_bytes) > 20 * 1024 * 1024:  # 20MB limit
                                break
                    
                    # Get filename from GoFile data
                    filename = data.get("name", None)
                    FileTypeHandler.process_file_content(content_bytes, filename, "gofile.io")
                    return
                
                # Handle folder - process all files
                if "children" in data:
                    for child_id, child_data in data["children"].items():
                        if child_data["type"] == "file":
                            download_url = child_data["link"]
                            file_response = session.get(download_url, timeout=15, stream=True)
                            
                            # Download as bytes to handle all file types
                            content_bytes = b""
                            for chunk in file_response.iter_content(chunk_size=8192):
                                if chunk:
                                    content_bytes += chunk
                                    # Limit content size to prevent memory issues
                                    if len(content_bytes) > 20 * 1024 * 1024:  # 20MB limit
                                        break
                            
                            # Get filename from GoFile data
                            filename = child_data.get("name", None)
                            FileTypeHandler.process_file_content(content_bytes, filename, "gofile.io")
                        elif child_data["type"] == "folder":
                            # Recursively handle subfolders
                            FileHandler.gofile(f"https://gofile.io/d/{child_id}", thread)
                
                return  # Success, exit retry loop
                            
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
                    continue
                logger.error(f"Error processing GoFile {link} after {max_retries} attempts: {str(e)}")

    # Class-level thread pool for non-blocking file processing
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="FileDownloader")
    _active_downloads = set()
    _download_lock = threading.Lock()

    @staticmethod
    def handle_file_link(link, thread):
        """Handle various file hosting sites with non-blocking processing"""
        print(f"🔄 Processing file: {link}")
        
        # Submit to thread pool for non-blocking processing
        future = FileHandler._executor.submit(FileHandler._process_file_blocking, link, thread)
        
        # Don't wait for completion - let it run in background
        # This prevents freezing and allows multiple files to process simultaneously
        return future

    @staticmethod
    def _process_file_blocking(link, thread):
        """Internal method to process files (runs in thread pool)"""
        
        # Check if already processing this file
        with FileHandler._download_lock:
            if link in FileHandler._active_downloads:
                return
            FileHandler._active_downloads.add(link)
        
        try:
            if 'upload.ee/files/' in link:
                FileHandler._process_upload_ee_fast(link)
                
            elif 'mediafire.com/file/' in link:
                FileHandler._process_mediafire_fast(link)
                
            elif 'pixeldrain.com/u/' in link:
                FileHandler._process_pixeldrain_fast(link)
                
            elif 'sendspace.com/file/' in link:
                FileHandler._process_sendspace_fast(link)
                    
            elif 'gofile.io/d/' in link:
                FileHandler.gofile(link, thread)
                
        except Exception as e:
            logger.error(f"File processing error for {link}: {str(e)}")
        finally:
            # Remove from active downloads
            with FileHandler._download_lock:
                FileHandler._active_downloads.discard(link)

    @staticmethod
    def _process_upload_ee_fast(link):
        """Fast upload.ee processing with timeout"""
        try:
            response = requests.get(link, headers=agent, timeout=8)
            f = BeautifulSoup(response.text, 'html.parser')
            download = f.find('a', id='d_l')
            if download:
                download_url = download.get('href')
                content_response = requests.get(download_url, headers=agent, timeout=15, stream=True)
                
                # Download as bytes to handle all file types
                content_bytes = b""
                for chunk in content_response.iter_content(chunk_size=8192):
                    if chunk:
                        content_bytes += chunk
                        # Limit content size to prevent memory issues
                        if len(content_bytes) > 20 * 1024 * 1024:  # 20MB limit
                            break
                
                # Extract filename from URL for file type detection
                filename = None
                try:
                    filename_match = re.search(r'/files/\d+/([^/]+)', link)
                    if filename_match:
                        filename = filename_match.group(1)
                        if filename.endswith('.html'):
                            filename = filename[:-5]  # Remove .html suffix
                except:
                    pass
                
                FileTypeHandler.process_file_content(content_bytes, filename, "upload.ee")
        except Exception as e:
            logger.error(f"Upload.ee error: {str(e)}")

    @staticmethod
    def _process_mediafire_fast(link):
        """Fast mediafire processing with timeout"""
        try:
            # Add retry logic for connection issues
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(link, headers=agent, timeout=8)
                    f = BeautifulSoup(response.text, 'html.parser')
                    download = f.find('a', id='downloadButton')
                    if download:
                        download_url = download.get('href')
                        content_response = requests.get(download_url, headers=agent, timeout=15, stream=True)
                        
                        # Download as bytes to handle all file types
                        content_bytes = b""
                        for chunk in content_response.iter_content(chunk_size=8192):
                            if chunk:
                                content_bytes += chunk
                                # Limit content size to prevent memory issues
                                if len(content_bytes) > 20 * 1024 * 1024:  # 20MB limit
                                    break
                        
                        # Extract filename from URL for file type detection
                        filename = None
                        try:
                            filename_match = re.search(r'/file/[^/]+/([^/]+)/', link)
                            if filename_match:
                                filename = filename_match.group(1)
                        except:
                            pass
                        
                        FileTypeHandler.process_file_content(content_bytes, filename, "mediafire.com")
                        return  # Success, exit retry loop
                    break  # No download button found, exit retry loop
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if attempt < max_retries - 1:
                        time.sleep(1)  # Wait before retry
                        continue
                    else:
                        raise e
        except Exception as e:
            logger.error(f"MediaFire error: {str(e)}")

    @staticmethod
    def _process_pixeldrain_fast(link):
        """Fast pixeldrain processing with timeout"""
        try:
            download_url = link.replace("/u/", "/api/file/") + "?download"
            content_response = requests.get(download_url, headers=agent, timeout=15, stream=True)
            
            # Download as bytes to handle all file types
            content_bytes = b""
            for chunk in content_response.iter_content(chunk_size=8192):
                if chunk:
                    content_bytes += chunk
                    # Limit content size to prevent memory issues
                    if len(content_bytes) > 20 * 1024 * 1024:  # 20MB limit
                        break
            
            # Try to get filename from response headers
            filename = None
            try:
                content_disposition = content_response.headers.get('content-disposition', '')
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('"')
            except:
                pass
            
            FileTypeHandler.process_file_content(content_bytes, filename, "pixeldrain.com")
        except Exception as e:
            logger.error(f"PixelDrain error: {str(e)}")

    @staticmethod
    def _process_sendspace_fast(link):
        """Fast sendspace processing with timeout"""
        try:
            response = requests.get(link, headers=agent, timeout=8)
            soup = BeautifulSoup(response.text, 'html.parser')
            download_link = soup.find('a', {'id': 'download_button'})
            if download_link:
                download_url = download_link['href']
                content_response = requests.get(download_url, verify=False, headers=agent, timeout=15, stream=True)
                
                # Download as bytes to handle all file types
                content_bytes = b""
                for chunk in content_response.iter_content(chunk_size=8192):
                    if chunk:
                        content_bytes += chunk
                        # Limit content size to prevent memory issues
                        if len(content_bytes) > 20 * 1024 * 1024:  # 20MB limit
                            break
                
                # Try to get filename from response headers or URL
                filename = None
                try:
                    content_disposition = content_response.headers.get('content-disposition', '')
                    if 'filename=' in content_disposition:
                        filename = content_disposition.split('filename=')[1].strip('"')
                    else:
                        # Extract from URL path
                        filename_match = re.search(r'/file/([^/]+)', link)
                        if filename_match:
                            filename = filename_match.group(1)
                except:
                    pass
                
                FileTypeHandler.process_file_content(content_bytes, filename, "sendspace.com")
        except Exception as e:
            logger.error(f"SendSpace error: {str(e)}")

class NoHideScraper:
    """NoHide.io scraper functionality from gen.py"""
    
    @staticmethod
    def load_nohide_cookies():
        """Load cookies from cookie.txt for nohide.io authentication"""
        session = requests.Session()
        session.headers.update(agent)
        
        try:
            with open('cookie.txt', 'r') as f:
                cookie_data = json.load(f)
            
            cookies = cookie_data.get('cookies', [])
            print(f"🍪 Loading {len(cookies)} cookies for nohide.io")
            
            for cookie in cookies:
                session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain', 'nohide.io'),
                    path=cookie.get('path', '/'),
                    secure=cookie.get('secure', False)
                )
            
            print("✅ nohide.io cookies loaded successfully")
            return session
            
        except FileNotFoundError:
            print("⚠️ cookie.txt not found - using regular session")
            return session
        except Exception as e:
            print(f"❌ Error loading cookies: {str(e)}")
            return session
    
    @staticmethod
    def scrape_nohide(max_pages=3):
        """Scrape nohide.io for combo files"""
        print(f"🔍 Starting nohide.io scraping ({max_pages} pages)")
        
        # Load authenticated session with cookies
        session = NoHideScraper.load_nohide_cookies()
        
        with stats_lock:
            site_stats['nohide.space']['status'] = 'Running'
        
        dupe = []
        try:
            for page in range(1, max_pages + 1):
                print(f"📄 Processing nohide.io page {page}")
                req = session.get(f"https://nohide.io/forums/free-databases.3/page-{page}?order=post_date&direction=desc")
                soup = BeautifulSoup(req.text, 'html.parser')
                target_div = soup.find('div', class_='structItemContainer-group js-threadList')
                
                if target_div:
                    links = target_div.find_all('a')
                    print(f"Found {len(links)} links on page {page}")
                    with stats_lock:
                        site_stats['nohide.space']['posts'] += len(links)
                    
                    thread_count = 0
                    for link in links:
                        href = link.get('href')
                        if href and "/threads/" in href:
                            href = href.strip('latest').rsplit('page-', 1)[0]
                            if href not in dupe:
                                dupe.append(href)
                                thread_count += 1
                                thread_url = "https://nohide.io" + href
                                print(f"🔗 Processing thread {thread_count}: {thread_url}")
                                
                                s = BeautifulSoup(session.get(thread_url).text, 'html.parser')
                                file_links_found = 0
                                for ele in s.find_all('div', class_='bbWrapper'):
                                    link_el = ele.find_all('a', href=True)
                                    for url in link_el:
                                        file_url = url['href']
                                        if any(site in file_url for site in ['gofile.io', 'mediafire.com', 'pixeldrain.com', 'sendspace.com', 'upload.ee']):
                                            print(f"📎 Found file link: {file_url}")
                                            file_links_found += 1
                                            FileHandler.handle_file_link(file_url, thread_url)
                                
                                if file_links_found == 0:
                                    print(f"   No file hosting links found in this thread")
                else:
                    print(f"No target div found on page {page}")
                
                # Page completion message
                print(f"✅ Page {page} completed | Current total: {scraped_combos:,} combos")
                                            
        except Exception as e:
            pass
        
        with stats_lock:
            site_stats['nohide.space']['status'] = 'Completed'
        
        print("✅ nohide.io scraping completed")





def main():
    """Main execution function"""
    print("NOHIDE.IO SCRAPER")
    print("=" * 30)
    
    max_pages = 3  # Fixed to 5 pages as requested
    start_time = datetime.datetime.now()
    
    # Initialize output file
    with open('combos.txt', 'w', encoding='utf-8') as f:
        f.write(f"# Combo scraping started at {start_time}\n")
    
    # Start scraping nohide.io only
    try:
        NoHideScraper.scrape_nohide(max_pages)
        
        # Wait for background file processing to complete
        print(f"\n🔄 Waiting for background downloads to complete...")
        FileHandler._executor.shutdown(wait=True)
        
        # Count final results
        final_count = 0
        try:
            with open('combos.txt', 'r', encoding='utf-8') as f:
                final_count = sum(1 for line in f if not line.startswith('#'))
        except:
            final_count = scraped_combos
        
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        
        print(f"\n" + "=" * 50)
        print(f"✅ SCRAPING COMPLETED SUCCESSFULLY!")
        print(f"=" * 50)
        print(f"📊 FINAL RESULTS:")
        print(f"   • Total combos found: {final_count:,}")
        print(f"   • Pages processed: {max_pages}")
        print(f"   • Time taken: {duration}")
        print(f"   • Output file: combos.txt")
        print(f"   • Average: {final_count/max_pages:.0f} combos per page")
        print(f"=" * 50)
        
    except KeyboardInterrupt:
        # Count partial results
        partial_count = 0
        try:
            with open('combos.txt', 'r', encoding='utf-8') as f:
                partial_count = sum(1 for line in f if not line.startswith('#'))
        except:
            partial_count = scraped_combos
            
        print(f"\n⚠️ Scraping interrupted by user")
        print(f"🔄 Stopping background downloads...")
        FileHandler._executor.shutdown(wait=False)
        print(f"\n📊 PARTIAL RESULTS:")
        print(f"   • Combos saved so far: {partial_count:,}")
        print(f"   • Output file: combos.txt")

if __name__ == "__main__":
    main()

# XTools FFI Integration
def scrape_url_ffi(url: str) -> str:
    """
    Scrape a URL for combo data via FFI.
    
    Args:
        url: URL to scrape (can be a file hosting link or a page with links)
    
    Returns:
        JSON string with results
    """
    import json
    
    try:
        if not url:
            return json.dumps({"success": False, "error": "URL is required"})
        
        # Determine the type of URL and handle accordingly
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        combos_before = scraped_combos
        
        if 'gofile.io' in domain:
            FileHandler.gofile(url, "ffi")
        elif 'mediafire.com' in domain:
            FileHandler.mediafire(url, "ffi")
        elif 'upload.ee' in domain:
            FileHandler.uploadee(url, "ffi")
        elif 'anonfiles' in domain or 'anonfile' in domain:
            FileHandler.anonfiles(url, "ffi")
        elif 'nohide' in domain:
            # Scrape nohide page
            NoHideScraper.scrape_nohide(max_pages=1)
        else:
            # Try to scrape as a generic page
            session = requests.Session()
            session.headers.update(agent)
            response = session.get(url, timeout=30, verify=False)
            
            if response.status_code == 200:
                # Try to extract combos from page content
                FileHandler.save_combos_to_log(response.text, domain)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                })
        
        combos_found = scraped_combos - combos_before
        
        return json.dumps({
            "success": True,
            "url": url,
            "combos_found": combos_found,
            "total_combos": scraped_combos,
            "output_file": "combos.txt"
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})