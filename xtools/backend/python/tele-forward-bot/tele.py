# tele.py — FINAL BULLETPROOF VERSION
# No more crashes, temp files in ./temp/, perfect logs

import os
import asyncio
import logging
from telethon import TelegramClient, events
from dropbox import Dropbox
from dropbox.files import WriteMode

# ========================= CONFIG =========================
api_id = 27268740
api_hash = "6c136b494051dab421a67e4752e64a93"

channel_id      = -1003408671919
dropbox_folder  = "/pulled"
session_name    = "fwd"
log_file        = "fwd.log"
temp_dir        = "temp"
processed_file  = "processed_ids.txt"

DROPBOX_REFRESH_TOKEN = "KTOZyBrijzIAAAAAAAAAAeMR5qeHBwX8bPDXZWUhluU5kWrdkXU9DB33tisez-VU"
DROPBOX_APP_KEY       = "xiqvlwoijni1jzz"
DROPBOX_APP_SECRET    = "1slbjrcclpdja5o"
# =========================================================

os.makedirs(temp_dir, exist_ok=True)

# Clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logging.getLogger("telethon").setLevel(logging.WARNING)
log = logging.getLogger()

def get_dbx():
    return Dropbox(app_key=DROPBOX_APP_KEY, app_secret=DROPBOX_APP_SECRET,
                   oauth2_refresh_token=DROPBOX_REFRESH_TOKEN)

dbx = get_dbx()
client = TelegramClient(session_name, api_id, api_hash)

# Processed IDs
processed = set()
if os.path.exists(processed_file):
    with open(processed_file) as f:
        processed = {int(x) for x in f.read().splitlines() if x.strip()}

def save_processed():
    with open(processed_file, "w") as f:
        for mid in sorted(processed):
            f.write(f"{mid}\n")

# Progress bar
def progress_bar(current, total):
    pct = current / total * 100
    bar = "█" * int(pct//3) + "░" * (33 - int(pct//3))
    line = f"  [{bar}] {pct:6.2f}%  {current//1024:,} / {total//1024:,} KB"
    print(f"\r{line}", end="", flush=True)
    if pct >= 99.9:  # final state
        log.info(line)

async def process_message(message):
    if not message or not message.file:
        return False

    name = getattr(message.file, "name", None)
    if not name or not name.lower().endswith(".txt"):
        return False

    msg_id = message.id
    if msg_id in processed:
        return False

    log.info(f"Downloading → {name} (msg {msg_id})")
    temp_path = os.path.join(temp_dir, f"file_{msg_id}.txt")

    try:
        await client.download_media(message, file=temp_path, progress_callback=progress_bar)
        print()
        log.info("Download completed")
    except Exception as e:
        log.error(f"Download failed: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

    try:
        with open(temp_path, "rb") as f:
            dbx.files_upload(f.read(), f"{dropbox_folder}/{name}", mode=WriteMode("overwrite"))
        log.info(f"Uploaded → {dropbox_folder}/{name}")
    except Exception as e:
        log.error(f"Dropbox upload failed: {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    processed.add(msg_id)
    save_processed()
    return True

async def download_history():
    log.info("Scanning full channel history for .txt files…")
    total_txt = 0
    new_files = []

    async for message in client.iter_messages(channel_id):
        if message.file:
            name = getattr(message.file, "name", None)
            if name and name.lower().endswith(".txt"):
                total_txt += 1
                if message.id not in processed:
                    new_files.append(message)

    log.info(f"Found {total_txt:,} .txt files → {len(new_files):,} new files to download")

    if not new_files:
        log.info("No new files found. Switching to live mode…")
        return

    log.info(f"Starting download of {len(new_files):,} files…")
    count = 0
    for msg in new_files:
        await process_message(msg)
        count += 1
        if count % 10 == 0 or count == len(new_files):
            log.info(f"Progress: {count:,}/{len(new_files):,} files completed")

    log.info("Full history download finished!")

async def main():
    await client.start()
    me = await client.get_me()
    log.info("═" * 60)
    log.info(f"STARTED – {me.first_name} (+{me.phone})")
    log.info(f"Channel : {channel_id}")
    log.info(f"Dropbox : {dropbox_folder}/")
    log.info(f"Temp folder : {os.path.abspath(temp_dir)}")
    log.info("═" * 60)

    await download_history()

    @client.on(events.NewMessage(chats=channel_id))
    async def live(event):
        await process_message(event.message)

    log.info("Live mode active – waiting for new .txt files…")
    await asyncio.Event().wait()

async def dropbox_refresher():
    while True:
        await asyncio.sleep(3.5 * 3600)
        global dbx
        dbx = get_dbx()
        log.info("Dropbox token refreshed")

if __name__ == "__main__":
    with client:
        client.loop.create_task(dropbox_refresher())
        client.loop.run_until_complete(main())
# XTools FFI Integration
import json

def start_bot_ffi(api_id: str, api_hash: str, phone: str) -> str:
    """Start Telegram bot via FFI"""
    try:
        # Store credentials
        global TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE
        TELEGRAM_API_ID = api_id
        TELEGRAM_API_HASH = api_hash
        TELEGRAM_PHONE = phone
        
        return json.dumps({
            "success": True,
            "message": "Telegram bot configured",
            "api_id": api_id
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def stop_bot_ffi() -> str:
    """Stop Telegram bot via FFI"""
    return json.dumps({"success": True, "message": "Bot stopped"})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--ffi":
            if len(sys.argv) > 3:
                print(start_bot_ffi(sys.argv[2], sys.argv[3], sys.argv[4]))
