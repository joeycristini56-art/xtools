import asyncio
import os
import re
from telethon import TelegramClient
from telethon.tl.types import PeerChannel, InputMessagesFilterDocument
from telethon.tl.functions.messages import GetHistoryRequest

from telethon.sessions import SQLiteSession
from telethon.errors import SessionPasswordNeededError

class TelegramScraper:
    def __init__(self, api_id, api_hash, phone_number, log_callback):
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.log = log_callback
        
        session_folder = 'sessions'
        if not os.path.exists(session_folder):
            os.makedirs(session_folder)
        
        session_path = os.path.join(session_folder, 'session.sqlite')
        self.client = TelegramClient(
            SQLiteSession(session_path), 
            self.api_id, 
            self.api_hash,
            connection_retries=5,
            retry_delay=1,
            timeout=30,
            request_retries=3
        )
        self.download_semaphore = asyncio.Semaphore(5)

    async def _ensure_connected(self):
        if not self.client.is_connected():
            await self.client.connect()

        if not await self.client.is_user_authorized():
            self.log("First run or session expired. Please check the console to log in.")
            await self.client.send_code_request(self.phone_number)
            try:
                await self.client.sign_in(self.phone_number, input("Enter Telegram code: "))
            except SessionPasswordNeededError:
                self.log("Two-step verification is enabled. Please enter your password in the console.")
                await self.client.sign_in(password=input("Enter 2FA password: "))
            except Exception as e:
                self.log(f"Error during sign in: {e}")
                raise

    async def list_channels(self):
        self.log("Fetching channel list...")
        await self._ensure_connected()
        
        channels = {}
        async for dialog in self.client.iter_dialogs():
            if dialog.is_channel:
                channels[dialog.name] = dialog.id
        
        self.log(f"Found {len(channels)} channels.")
        return channels

    async def _download_file_concurrent(self, message, file_path, file_name, file_size_mb):
        async with self.download_semaphore:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.log(f"Downloading {file_name} ({file_size_mb:.2f} MB)...")
                    
                    def progress_callback(current, total):
                        if total > 0:
                            percent = (current / total) * 100
                            if percent % 25 == 0:
                                self.log(f"Progress {file_name}: {percent:.0f}%")
                    
                    await self.client.download_media(
                        message, 
                        file=file_path,
                        progress_callback=progress_callback
                    )
                    self.log(f"✓ Completed {file_name}")
                    return
                    
                except Exception as e:
                    self.log(f"✗ Attempt {attempt + 1} failed for {file_name}: {e}")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        self.log(f"✗ All attempts failed for {file_name}")

    async def _process_channel(self, channel_name, channel_id, keywords, main_folder):
        try:
            clean_channel_path = self._clean_folder_name(channel_name, channel_id, main_folder)
            channel = await self.client.get_entity(PeerChannel(int(channel_id)))
            
            self.log(f"⚡ High-speed scan: {channel_name}...")
            
            message_count = 0
            found_files_count = 0
            download_tasks = []
            
            # API-level filter: Only fetch messages that contain files (Documents)
            # This makes the history scanning significantly faster.
            async for message in self.client.iter_messages(channel, filter=InputMessagesFilterDocument()):
                message_count += 1
                
                if message_count % 500 == 0:
                    self.log(f"[{channel_name}] Scanned {message_count} files in history...")

                if message.media and hasattr(message.media, 'document'):
                    file_name = self._get_file_name(message)
                    
                    if file_name and any(self._contains_exact_keyword(file_name, keyword) for keyword in keywords):
                        # LAZY FOLDER CREATION
                        if not os.path.exists(clean_channel_path):
                            os.makedirs(clean_channel_path)
                            self.log(f"Folder created for: {channel_name}")

                        file_size = message.media.document.size
                        final_file_name = file_name
                        
                        # PRE-DOWNLOAD CHECK: Skip if exact match, rename if different size
                        if os.path.exists(os.path.join(clean_channel_path, file_name)):
                            if self._file_exists_with_same_size(clean_channel_path, file_name, file_size):
                                continue 
                            else:
                                final_file_name = self._generate_new_file_name(clean_channel_path, file_name)
                        
                        found_files_count += 1
                        file_path = os.path.join(clean_channel_path, final_file_name)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        task = self._download_file_concurrent(message, file_path, final_file_name, file_size_mb)
                        download_tasks.append(task)

                        # Stream downloads in batches of 10 while scanning
                        if len(download_tasks) >= 10:
                            await asyncio.gather(*download_tasks, return_exceptions=True)
                            download_tasks = []

            # Finish remaining tasks
            if download_tasks:
                await asyncio.gather(*download_tasks, return_exceptions=True)

            if found_files_count == 0:
                self.log(f"Scan complete for {channel_name}. No matches found.")
            else:
                self.log(f"✅ Finished {channel_name}. Total files found: {found_files_count}")
                
        except Exception as e:
            self.log(f"[!] Error in channel {channel_name}: {e}")

    async def scrape(self, channels, keywords):
        self.log("Connecting to Telegram...")
        await self._ensure_connected()

        main_folder = "combolists"
        if not os.path.exists(main_folder):
            os.makedirs(main_folder)

        # Iterate through every group in the config
        for channel_name, channel_id in channels.items():
            await self._process_channel(channel_name, channel_id, keywords, main_folder)
        
        self.log("Finished processing all groups.")
        await self.client.disconnect()

    def _get_file_name(self, message):
        if hasattr(message.media, 'document'):
            for attribute in message.media.document.attributes:
                if hasattr(attribute, 'file_name'):
                    return attribute.file_name
        return None

    def _clean_folder_name(self, channel_name, channel_id, main_folder):
        # Folder Format: "Name - ID"
        clean_name = re.sub(r'[<>:"/\\|?*]', '', str(channel_name))
        return os.path.join(main_folder, f"{clean_name} - {channel_id}")

    def _file_exists_with_same_size(self, directory, file_name, file_size):
        file_path = os.path.join(directory, file_name)
        if os.path.exists(file_path):
            return os.path.getsize(file_path) == file_size
        return False

    def _generate_new_file_name(self, directory, file_name):
        base, ext = os.path.splitext(file_name)
        counter = 1
        new_file_name = f"{base}_{counter}{ext}"
        while os.path.exists(os.path.join(directory, new_file_name)):
            counter += 1
            new_file_name = f"{base}_{counter}{ext}"
        return new_file_name

    def _contains_exact_keyword(self, word, keyword):
        return re.search(r'\b' + re.escape(keyword) + r'\b', word, re.IGNORECASE) is not None

# --- EXTERNAL ENTRY POINTS ---

async def run_scraper(api_id, api_hash, phone_number, channels, keywords, log_callback):
    scraper = TelegramScraper(api_id, api_hash, phone_number, log_callback)
    await scraper.scrape(channels, keywords)

async def get_channels(api_id, api_hash, phone_number, log_callback):
    scraper = TelegramScraper(api_id, api_hash, phone_number, log_callback)
    return await scraper.list_channels()
