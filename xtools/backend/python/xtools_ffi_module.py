#!/usr/bin/env python3
"""
XTools FFI Module - Production-grade aggregation of all tools for FFI access
Provides unified interface for all Python-based tools in the XTools suite.
"""

import json
import os
import sys
import importlib.util
import traceback
from typing import Optional, Callable, Any, Dict, List

# Add backend paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, 'combo-database'))
sys.path.insert(0, os.path.join(BACKEND_DIR, 'captcha-solver'))
sys.path.insert(0, os.path.join(BACKEND_DIR, 'discord-mail-bot'))
sys.path.insert(0, os.path.join(BACKEND_DIR, 'tele-forward-bot'))
sys.path.insert(0, os.path.join(BACKEND_DIR, 'tele-scrapper'))


def load_module_from_file(module_name: str, file_path: str) -> Optional[Any]:
    """Load a Python module from a file path."""
    try:
        if not os.path.exists(file_path):
            return None
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
    except Exception:
        pass
    return None


def safe_json_response(success: bool, **kwargs) -> str:
    """Create a safe JSON response string."""
    response = {"success": success}
    response.update(kwargs)
    return json.dumps(response)


def handle_exception(func_name: str, e: Exception) -> str:
    """Handle exceptions and return JSON error response."""
    return safe_json_response(False, error=f"{func_name} failed: {str(e)}", traceback=traceback.format_exc())


# Import all tools with proper error handling
sort_process = None
filter_process = None
dedup_process = None
split_process = None
remove_process = None
gofile_upload = None
combo_process = None
discord_start = None
discord_stop = None
telegram_start = None
telegram_stop = None
scraper_run = None
captcha_solve = None
web_scraper_run = None

try:
    from sort import process_file_ffi as sort_process
except Exception:
    pass

try:
    from filter import process_file_ffi as filter_process
except Exception:
    pass

try:
    from dedup import process_file_ffi as dedup_process
except Exception:
    pass

try:
    from split import process_file_ffi as split_process
except Exception:
    pass

try:
    from remove import process_file_ffi as remove_process
except Exception:
    pass

try:
    from gofile import upload_file as gofile_upload
except Exception:
    pass

try:
    from combo import process_file_ffi as combo_process
except Exception:
    pass

# Discord bot
try:
    discord_module = load_module_from_file(
        "discord_mail_bot",
        os.path.join(BACKEND_DIR, "discord-mail-bot/Mail-bot.py")
    )
    if discord_module:
        discord_start = getattr(discord_module, 'start_bot_ffi', None)
        discord_stop = getattr(discord_module, 'stop_bot_ffi', None)
except Exception:
    pass

# Telegram bot
try:
    telegram_module = load_module_from_file(
        "telegram_forward_bot",
        os.path.join(BACKEND_DIR, "tele-forward-bot/tele.py")
    )
    if telegram_module:
        telegram_start = getattr(telegram_module, 'start_bot_ffi', None)
        telegram_stop = getattr(telegram_module, 'stop_bot_ffi', None)
except Exception:
    pass

# Telegram scraper
try:
    scraper_module = load_module_from_file(
        "telegram_scraper",
        os.path.join(BACKEND_DIR, "tele-scrapper/main.py")
    )
    if scraper_module:
        scraper_run = getattr(scraper_module, 'run_scraper_ffi', None)
except Exception:
    pass

# Web scraper
try:
    web_scraper_module = load_module_from_file(
        "web_scraper",
        os.path.join(BACKEND_DIR, "scrapper.py")
    )
    if web_scraper_module:
        web_scraper_run = getattr(web_scraper_module, 'scrape_url_ffi', None)
except Exception:
    pass

# Captcha solver
try:
    captcha_module = load_module_from_file(
        "captcha_solver",
        os.path.join(BACKEND_DIR, "captcha-solver/__main__.py")
    )
    if captcha_module:
        captcha_solve = getattr(captcha_module, 'solve_captcha_ffi', None)
except Exception:
    pass


# ============================================================================
# FFI EXPORTED FUNCTIONS - These are called from the C FFI layer
# ============================================================================

def gofile_upload_func(file_path: str) -> str:
    """Upload file to GoFile.io"""
    try:
        if not os.path.exists(file_path):
            return safe_json_response(False, error=f"File not found: {file_path}")
        if gofile_upload:
            return gofile_upload(file_path)
        return safe_json_response(False, error="GoFile module not available")
    except Exception as e:
        return handle_exception("gofile_upload", e)


def run_sort(file_path: str, domains: str = "") -> str:
    """Sort/extract emails by domain from combo file."""
    try:
        if not os.path.exists(file_path):
            return safe_json_response(False, error=f"File not found: {file_path}")
        if sort_process:
            if domains:
                domain_list = [d.strip() for d in domains.split(',') if d.strip()]
                return sort_process(file_path, domain_list)
            return sort_process(file_path)
        return safe_json_response(False, error="Sort module not available")
    except Exception as e:
        return handle_exception("run_sort", e)


def run_filter(file_path: str) -> str:
    """Filter/deduplicate lines in a file."""
    try:
        if not os.path.exists(file_path):
            return safe_json_response(False, error=f"File not found: {file_path}")
        if filter_process:
            return filter_process(file_path)
        return safe_json_response(False, error="Filter module not available")
    except Exception as e:
        return handle_exception("run_filter", e)


def run_dedup(file_path: str) -> str:
    """Deduplicate and consolidate valid files."""
    try:
        if not os.path.exists(file_path):
            return safe_json_response(False, error=f"File not found: {file_path}")
        if dedup_process:
            return dedup_process(file_path)
        return safe_json_response(False, error="Dedup module not available")
    except Exception as e:
        return handle_exception("run_dedup", e)


def run_split(file_path: str) -> str:
    """Filter for CC/PayPal accounts."""
    try:
        if not os.path.exists(file_path):
            return safe_json_response(False, error=f"File/directory not found: {file_path}")
        if split_process:
            return split_process(file_path)
        return safe_json_response(False, error="Split module not available")
    except Exception as e:
        return handle_exception("run_split", e)


def run_remove(file_path: str, pattern: str) -> str:
    """Remove lines matching a pattern."""
    try:
        if not os.path.exists(file_path):
            return safe_json_response(False, error=f"File not found: {file_path}")
        if not pattern:
            return safe_json_response(False, error="Pattern is required")
        if remove_process:
            return remove_process(file_path, pattern)
        return safe_json_response(False, error="Remove module not available")
    except Exception as e:
        return handle_exception("run_remove", e)


def discord_bot(config_json: str) -> str:
    """Start Discord bot with configuration."""
    try:
        config = json.loads(config_json)
        token = config.get('token', '')
        imap_config = {
            'host': config.get('imap_host', ''),
            'user': config.get('imap_user', ''),
            'pass': config.get('imap_pass', '')
        }
        channel_id = config.get('channel_id', '')
        
        if not token:
            return safe_json_response(False, error="Discord token is required")
        
        if discord_start:
            return discord_start(token, imap_config, channel_id)
        return safe_json_response(False, error="Discord bot module not available")
    except json.JSONDecodeError:
        return safe_json_response(False, error="Invalid JSON configuration")
    except Exception as e:
        return handle_exception("discord_bot", e)


def discord_bot_stop() -> str:
    """Stop Discord bot."""
    try:
        if discord_stop:
            return discord_stop()
        return safe_json_response(False, error="Discord bot module not available")
    except Exception as e:
        return handle_exception("discord_bot_stop", e)


def telegram_bot(config_json: str) -> str:
    """Start Telegram bot with configuration."""
    try:
        config = json.loads(config_json)
        api_id = config.get('api_id', '')
        api_hash = config.get('api_hash', '')
        phone = config.get('phone', '')
        channel_ids = config.get('channel_ids', [])
        dropbox_config = config.get('dropbox', {})
        
        if not all([api_id, api_hash, phone]):
            return safe_json_response(False, error="API ID, API Hash, and Phone are required")
        
        if telegram_start:
            return telegram_start(api_id, api_hash, phone, channel_ids, dropbox_config)
        return safe_json_response(False, error="Telegram bot module not available")
    except json.JSONDecodeError:
        return safe_json_response(False, error="Invalid JSON configuration")
    except Exception as e:
        return handle_exception("telegram_bot", e)


def telegram_bot_stop() -> str:
    """Stop Telegram bot."""
    try:
        if telegram_stop:
            return telegram_stop()
        return safe_json_response(False, error="Telegram bot module not available")
    except Exception as e:
        return handle_exception("telegram_bot_stop", e)


def run_scraper(config_json: str) -> str:
    """Run web or Telegram scraper."""
    try:
        config = json.loads(config_json)
        scraper_type = config.get('type', 'web')
        
        if scraper_type == 'telegram':
            if scraper_run:
                return scraper_run(config)
            return safe_json_response(False, error="Telegram scraper module not available")
        else:
            url = config.get('url', '')
            if not url:
                return safe_json_response(False, error="URL is required for web scraping")
            if web_scraper_run:
                return web_scraper_run(url)
            return safe_json_response(False, error="Web scraper module not available")
    except json.JSONDecodeError:
        return safe_json_response(False, error="Invalid JSON configuration")
    except Exception as e:
        return handle_exception("run_scraper", e)


def run_combo(file_path: str) -> str:
    """Process combo file into database."""
    try:
        if not os.path.exists(file_path):
            return safe_json_response(False, error=f"File not found: {file_path}")
        if combo_process:
            return combo_process(file_path)
        return safe_json_response(False, error="Combo module not available")
    except Exception as e:
        return handle_exception("run_combo", e)


def run_captcha(config_json: str) -> str:
    """Solve CAPTCHA with configuration."""
    try:
        config = json.loads(config_json)
        captcha_type = config.get('type', 'image')
        
        if captcha_solve:
            return captcha_solve(config)
        return safe_json_response(False, error="Captcha solver module not available")
    except json.JSONDecodeError:
        return safe_json_response(False, error="Invalid JSON configuration")
    except Exception as e:
        return handle_exception("run_captcha", e)


def get_tool_status() -> str:
    """Get status of all available tools."""
    status = {
        "success": True,
        "tools": {
            "sort": sort_process is not None,
            "filter": filter_process is not None,
            "dedup": dedup_process is not None,
            "split": split_process is not None,
            "remove": remove_process is not None,
            "gofile": gofile_upload is not None,
            "combo": combo_process is not None,
            "discord_bot": discord_start is not None,
            "telegram_bot": telegram_start is not None,
            "telegram_scraper": scraper_run is not None,
            "web_scraper": web_scraper_run is not None,
            "captcha": captcha_solve is not None,
        }
    }
    return json.dumps(status)


# ============================================================================
# CLI INTERFACE
# ============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(safe_json_response(False, error="Usage: python xtools_ffi_module.py <tool> [args...]"))
        sys.exit(1)
    
    tool = sys.argv[1]
    args = sys.argv[2:]
    
    functions = {
        'sort': lambda: run_sort(args[0], args[1] if len(args) > 1 else ''),
        'filter': lambda: run_filter(args[0]),
        'dedup': lambda: run_dedup(args[0]),
        'split': lambda: run_split(args[0]),
        'remove': lambda: run_remove(args[0], args[1] if len(args) > 1 else ''),
        'combo': lambda: run_combo(args[0]),
        'gofile': lambda: gofile_upload_func(args[0]),
        'scraper': lambda: run_scraper(args[0]),
        'captcha': lambda: run_captcha(args[0]),
        'discord': lambda: discord_bot(args[0]),
        'telegram': lambda: telegram_bot(args[0]),
        'status': lambda: get_tool_status(),
    }
    
    if tool in functions:
        if tool != 'status' and len(args) < 1:
            print(safe_json_response(False, error=f"Tool '{tool}' requires at least one argument"))
        else:
            print(functions[tool]())
    else:
        print(safe_json_response(False, error=f"Unknown tool: {tool}. Available: {', '.join(functions.keys())}"))
