import configparser
import os
import asyncio
import argparse
import sys
from scraper import run_scraper, get_channels
from generator import run_generator

def log(message):
    print(f"[LOG] {message}")

def load_config():
    config = configparser.ConfigParser()
    path = 'config/config.ini'
    if os.path.exists(path):
        config.read(path)
        return config
    else:
        log("config.ini not found in config/ directory.")
        return None

def get_config_values(config):
    try:
        api_id = config.get('Telegram', 'api_id', fallback=None)
        api_hash = config.get('Telegram', 'api_hash', fallback=None)
        phone = config.get('Telegram', 'phone_number', fallback=None)
        
        channels_str = config.get('Channels', '', fallback='')
        # Channels in ini are stored as key = value
        channels = dict(config.items('Channels')) if 'Channels' in config else {}
        
        keywords_str = config.get('Keywords', 'keywords', fallback='')
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
        
        return api_id, api_hash, phone, channels, keywords
    except Exception as e:
        log(f"Error parsing config: {e}")
        return None

async def main():
    parser = argparse.ArgumentParser(description="Combolist Scraper CLI")
    parser.add_argument('--fetch', action='store_true', help='Fetch and list available Telegram channels')
    parser.add_argument('--scrape', action='store_true', help='Start the scraping process')
    parser.add_argument('--generate', action='store_true', help='Generate wordlist from scraped data')
    
    args = parser.parse_args()
    
    # Ensure Windows compatibility for asyncio
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config()
    if not config:
        sys.exit(1)

    auth = get_config_values(config)
    if not auth[0] or not auth[1]:
        log("Error: API_ID and API_HASH must be set in config.ini")
        sys.exit(1)

    api_id, api_hash, phone, channels, keywords = auth

    # --- ACTION: FETCH CHANNELS ---
    if args.fetch:
        log("Fetching channels...")
        available_channels = await get_channels(api_id, api_hash, phone, log)
        print("\n--- Available Channels ---")
        for name, cid in available_channels.items():
            print(f"{name}: {cid}")
        print("\nCopy these into your config.ini under [Channels] to use them.")

    # --- ACTION: SCRAPE ---
    elif args.scrape:
        if not channels or not keywords:
            log("Error: No channels or keywords found in config.ini")
            return
        log("Starting Scraper...")
        await run_scraper(api_id, api_hash, phone, channels, keywords, log)
        log("Scraping completed.")

    # --- ACTION: GENERATE ---
    elif args.generate:
        log("Generating wordlist...")
        try:
            run_generator(log)
            log("Wordlist generation finished.")
        except Exception as e:
            log(f"Error during generation: {e}")

    else:
        parser.print_help()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")

# XTools FFI Integration
import json

def run_scraper(url: str) -> str:
    """Run scraper via FFI"""
    try:
        # Would need actual scraping implementation
        return json.dumps({
            "success": True,
            "message": "Scraping would happen here",
            "url": url,
            "data": "placeholder"
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(run_scraper(sys.argv[1]))
