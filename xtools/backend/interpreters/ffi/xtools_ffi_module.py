#!/usr/bin/env python3
"""
XTools FFI Module - Aggregates all tools for FFI access
"""

import json
import os
import sys
import importlib.util

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'combo-database'))

def load_module_from_file(module_name, file_path):
    """Load a module from a file path"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None

# Import all tools
try:
    from sort import process_file_ffi as sort_process
except Exception as e:
    sort_process = None

try:
    from filter import process_file_ffi as filter_process
except Exception as e:
    filter_process = None

try:
    from dedup import process_file_ffi as dedup_process
except Exception as e:
    dedup_process = None

try:
    from split import process_file_ffi as split_process
except Exception as e:
    split_process = None

try:
    from remove import process_file_ffi as remove_process
except Exception as e:
    remove_process = None

try:
    from gofile import upload_file as gofile_upload
except Exception as e:
    gofile_upload = None

try:
    from combo import process_file_ffi as combo_process
except Exception as e:
    combo_process = None

# Discord bot (file has hyphen)
try:
    discord_module = load_module_from_file(
        "discord_bot",
        os.path.join(os.path.dirname(__file__), "discord-mail-bot/Mail-bot.py")
    )
    discord_start = discord_module.start_bot_ffi if discord_module else None
    discord_stop = discord_module.stop_bot_ffi if discord_module else None
except Exception as e:
    discord_start = None
    discord_stop = None

# Telegram bot (file has hyphen)
try:
    telegram_module = load_module_from_file(
        "telegram_bot",
        os.path.join(os.path.dirname(__file__), "tele-forward-bot/tele.py")
    )
    telegram_start = telegram_module.start_bot_ffi if telegram_module else None
    telegram_stop = telegram_module.stop_bot_ffi if telegram_module else None
except Exception as e:
    telegram_start = None
    telegram_stop = None

# Scraper
try:
    scraper_module = load_module_from_file(
        "scraper",
        os.path.join(os.path.dirname(__file__), "tele-scrapper/main.py")
    )
    scraper_run = scraper_module.run_scraper if scraper_module else None
except Exception as e:
    scraper_run = None

# Captcha
try:
    captcha_module = load_module_from_file(
        "captcha",
        os.path.join(os.path.dirname(__file__), "captcha-solver/__main__.py")
    )
    captcha_solve = captcha_module.solve_captcha if captcha_module else None
except Exception as e:
    captcha_solve = None

# Exported functions for C FFI
def gofile_upload_func(file_path: str) -> str:
    if gofile_upload:
        return gofile_upload(file_path)
    return json.dumps({"success": False, "error": "Gofile not available"})

def run_sort(file_path: str) -> str:
    if sort_process:
        return sort_process(file_path)
    return json.dumps({"success": False, "error": "Sort not available"})

def run_filter(file_path: str) -> str:
    if filter_process:
        return filter_process(file_path)
    return json.dumps({"success": False, "error": "Filter not available"})

def run_dedup(file_path: str) -> str:
    if dedup_process:
        return dedup_process(file_path)
    return json.dumps({"success": False, "error": "Dedup not available"})

def run_split(file_path: str) -> str:
    if split_process:
        return split_process(file_path)
    return json.dumps({"success": False, "error": "Split not available"})

def run_remove(file_path: str, pattern: str) -> str:
    if remove_process:
        return remove_process(file_path, pattern)
    return json.dumps({"success": False, "error": "Remove not available"})

def discord_bot(token: str, imap_host: str, imap_user: str, imap_pass: str, channel_id: str) -> str:
    if discord_start:
        return discord_start(token, {'host': imap_host, 'user': imap_user, 'pass': imap_pass}, channel_id)
    return json.dumps({"success": False, "error": "Discord bot not available"})

def telegram_bot(api_id: str, api_hash: str, phone: str) -> str:
    if telegram_start:
        return telegram_start(api_id, api_hash, phone)
    return json.dumps({"success": False, "error": "Telegram bot not available"})

def run_scraper(url: str) -> str:
    if scraper_run:
        return scraper_run(url)
    return json.dumps({"success": False, "error": "Scraper not available"})

def run_combo(file_path: str) -> str:
    if combo_process:
        return combo_process(file_path)
    return json.dumps({"success": False, "error": "Combo not available"})

def run_captcha(image_path: str) -> str:
    if captcha_solve:
        return captcha_solve(image_path)
    return json.dumps({"success": False, "error": "Captcha not available"})

if __name__ == "__main__":
    if len(sys.argv) > 2:
        tool = sys.argv[1]
        args = sys.argv[2:]
        
        functions = {
            'sort': lambda: run_sort(args[0]),
            'filter': lambda: run_filter(args[0]),
            'dedup': lambda: run_dedup(args[0]),
            'split': lambda: run_split(args[0]),
            'remove': lambda: run_remove(args[0], args[1] if len(args) > 1 else ''),
            'combo': lambda: run_combo(args[0]),
            'gofile': lambda: gofile_upload_func(args[0]),
            'scraper': lambda: run_scraper(args[0]),
            'captcha': lambda: run_captcha(args[0]),
        }
        
        if tool in functions:
            print(functions[tool]())
        else:
            print(json.dumps({"success": False, "error": f"Unknown tool: {tool}"}))
