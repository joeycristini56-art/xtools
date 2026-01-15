import asyncio
import os
import argparse
import sys
import time
import re
import traceback
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError

# Hardcoded API credentials and channel IDs
api_id = 27268740
api_hash = "6c136b494051dab421a67e4752e64a93"


source_channels = {
    -1003119168922: ['fwd'],
    -1003426008955: ['fwd'],
    -1002997403984: ['fwd'],
    -1003175895368: ['fwd'],
    -1003065952961: ['fwd'],
    -1003213622391: ['fwd'],
    -1002381039539: ['fwd'],
    -1003205592218: ['fwd'],
    -1003354427043: ['fwd'],
    -1002956497329: ['fwd'],
    -1002877967453: ['fwd'],
    -1003092013419: ['fwd'],
    -1002594930749: ['fwd'],
    -1002512737317: ['fwd'],
    -1003327967130: ['fwd'],
    -1002804433440: ['fwd'],
    -1002738044231: ['fwd'],
    -1003222102036: ['fwd'],
    -1002822478602: ['fwd'],
    -1003314217349: ['fwd'],
    -1002652871773: ['fwd'],
    -1001839502111: ['fwd'],
    -1003413264918: ['fwd'],
    -1002889928680: ['fwd'],
    -1003468791912: ['fwd'],
    -1003001420482: ['fwd'],
    -1003480208247: ['fwd'],
    -1002337990504: ['fwd'],
    -1003472051043: ['fwd'],
    -1003414402913: ['fwd'],
    -1003446642125: ['fwd'],
    -1003178167267: ['fwd'],
    -1003357597522: ['fwd'],
    -1002326905328: ['fwd'],
    -1002939597453: ['fwd'],
    -1003285721752: ['fwd'],
    -1002846535548: ['fwd'],
    -1002709551131: ['fwd'],
    -1003351815066: ['fwd'],
    -1002925149644: ['fwd'],
    -1002485126141: ['fwd'],
    -1001945647265: ['fwd'],
    -1002550035996: ['fwd'],
    -1002816006701: ['fwd'],
    -1002790861499: ['fwd'],
    -1002326298282: ['fwd']
}


# Destination chat ID
destination_chat = -1003408671919

# Initialize the client with a different session name
client = TelegramClient('forward_session', api_id, api_hash)

# Global set to track forwarded messages
forwarded_messages = set()
accessible_channels = set()

def has_fwd_flag(channel_id):
    """Check if a channel has the 'fwd' flag (forward new messages only)"""
    channel_config = source_channels.get(channel_id, [])
    return 'fwd' in channel_config

def get_file_extension(file_name):
    """Get file extension from filename"""
    if not file_name or not isinstance(file_name, str):
        return None
    
    # Remove any path components and get just the filename
    file_name = file_name.split('/')[-1].split('\\')[-1]
    
    # Check if there's a dot and get extension
    if '.' in file_name:
        extension = file_name.split('.')[-1].lower().strip()
        # Ensure extension is not empty and contains only valid characters
        if extension and extension.isalnum():
            return extension
    return None

def should_forward_file(file_name, allowed_extensions):
    """Check if file should be forwarded based on extension - 'fwd' flag only allows .txt and .zip files"""
    if not file_name or not allowed_extensions:
        return False

    extension = get_file_extension(file_name)
    if not extension:
        print(f"❌ No valid extension found for file: {file_name}")
        return False

    # Filter out 'fwd' flag from extensions for file checking
    file_extensions = [ext for ext in allowed_extensions if ext != 'fwd']
    
    # If only 'fwd' flag was present (no specific extensions), only allow .txt and .zip files
    if not file_extensions and 'fwd' in allowed_extensions:
        allowed_fwd_extensions = ['txt', 'zip']
        is_allowed = extension in allowed_fwd_extensions
        if is_allowed:
            print(f"✅ Channel has 'fwd' flag - forwarding allowed file type '{extension}': {file_name}")
        else:
            print(f"❌ Channel has 'fwd' flag - file type '{extension}' not allowed (only .txt and .zip): {file_name}")
        return is_allowed
    
    # Check specific extensions
    is_allowed = extension in file_extensions
    if is_allowed:
        print(f"✅ File extension '{extension}' is allowed for: {file_name}")
    else:
        print(f"❌ File extension '{extension}' not in allowed list {file_extensions} for: {file_name}")
    
    return is_allowed

def should_forward_url(message_text, allowed_extensions):
    """Check if URL should be forwarded - only if 'url' is explicitly allowed or channel has 'fwd' flag only"""
    if not message_text:
        return False
        
    # Filter out 'fwd' flag from extensions for URL checking
    url_extensions = [ext for ext in allowed_extensions if ext != 'fwd']
    
    # If only 'fwd' flag was present (no specific extensions), allow all URLs
    if not url_extensions and 'fwd' in allowed_extensions:
        text_lower = message_text.lower().strip()
        
        # More precise URL detection - must start with http/https or www.
        url_patterns = [
            r'\bhttps?://[^\s]+',  # http:// or https:// URLs
            r'\bwww\.[^\s]+',      # www. URLs
            r'\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s]*'  # domain.tld URLs
        ]
        
        for pattern in url_patterns:
            if re.search(pattern, text_lower):
                print(f"✅ Channel has 'fwd' flag only - forwarding all URLs")
                return True
        
        print(f"❌ No valid URL pattern found in message")
        return False
    
    # Check if 'url' is explicitly allowed
    if 'url' not in url_extensions:
        return False
    
    text_lower = message_text.lower().strip()
    
    # More precise URL detection - must start with http/https or www.
    url_patterns = [
        r'\bhttps?://[^\s]+',  # http:// or https:// URLs
        r'\bwww\.[^\s]+',      # www. URLs
        r'\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\s]*'  # domain.tld URLs
    ]
    
    for pattern in url_patterns:
        if re.search(pattern, text_lower):
            print(f"✅ URL detected in message, forwarding allowed")
            return True
    
    print(f"❌ No valid URL pattern found in message")
    return False

def should_forward_text(message_text, allowed_extensions):
    """Check if plain text message should be forwarded - DISABLED: 'txt' means .txt files only, not plain text"""
    if not message_text:
        return False
    
    # Plain text messages are NEVER forwarded - 'txt' extension means .txt files only
    print(f"❌ Plain text message blocked - 'txt' extension means .txt files only, not plain text messages")
    return False

async def check_channel_access():
    """Check which channels are accessible"""
    print("Checking channel access...")
    for channel_id in source_channels.keys():
        try:
            # Try to get channel info
            entity = await client.get_entity(channel_id)
            accessible_channels.add(channel_id)
            print(f"✅ Channel {channel_id} is accessible")
        except (ChannelPrivateError, ChatAdminRequiredError, ValueError) as e:
            print(f"❌ Channel {channel_id} is not accessible: {e}")
        except Exception as e:
            print(f"⚠️ Error checking channel {channel_id}: {e}")

    print(f"Total accessible channels: {len(accessible_channels)}")

async def safe_forward_message(message, destination_chat, max_retries=3, timeout=30):
    """Safely forward a message with rate limiting, retry logic, and timeout"""
    for attempt in range(max_retries):
        try:
            # Use asyncio.wait_for to add timeout to the forward operation
            await asyncio.wait_for(
                client.forward_messages(destination_chat, message),
                timeout=timeout
            )
            return True
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"⏳ Rate limited. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
            if wait_time > 3600:  # If wait time is more than 1 hour, skip this message
                print(f"⏰ Wait time too long ({wait_time}s), skipping message {message.id}")
                return False
            await asyncio.sleep(wait_time)
        except asyncio.TimeoutError:
            print(f"⏰ Timeout ({timeout}s) forwarding message {message.id} (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)  # Wait 5 seconds before retry
            else:
                print(f"❌ Failed to forward message {message.id} after {max_retries} attempts (timeout)")
                return False
        except Exception as e:
            print(f"❌ Error forwarding message {message.id} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)  # Wait 5 seconds before retry
            else:
                print(f"❌ Failed to forward message {message.id} after {max_retries} attempts")
                return False
    return False

@client.on(events.NewMessage(chats=list(source_channels.keys())))
async def handle_new_message(event):
    """Handle new messages in real-time with strict filtering"""
    try:
        source_chat_id = event.chat_id

        if source_chat_id not in accessible_channels:
            print(f"⚠️ Skipping message from inaccessible channel: {source_chat_id}")
            return

        allowed_extensions = source_channels.get(source_chat_id, [])
        print(f"📨 New message from channel {source_chat_id}, allowed extensions: {allowed_extensions}")

        should_forward = False
        forward_reason = ""

        # Check for file attachments first
        if event.media and hasattr(event.media, 'document') and event.media.document:
            document = event.media.document
            file_name = None
            
            # Get the filename from document attributes
            for attr in document.attributes:
                if hasattr(attr, 'file_name') and attr.file_name:
                    file_name = attr.file_name
                    break
            
            if file_name:
                if should_forward_file(file_name, allowed_extensions):
                    should_forward = True
                    forward_reason = f"File: {file_name}"
                else:
                    print(f"🚫 File {file_name} blocked - extension not allowed")
            else:
                print(f"🚫 Document without filename - blocked")

        # Check for URLs in text (only if no file was found or if file was not allowed)
        if not should_forward and event.text:
            if should_forward_url(event.text, allowed_extensions):
                should_forward = True
                forward_reason = f"URL in text: {event.text[:50]}..."
            elif should_forward_text(event.text, allowed_extensions):
                should_forward = True
                forward_reason = f"Text message: {event.text[:50]}..."
            else:
                print(f"🚫 Text message blocked - no valid URL, text not allowed")

        # Forward the message if it meets criteria
        if should_forward:
            print(f"🔄 Attempting to forward: {forward_reason}")
            success = await safe_forward_message(event.message, destination_chat, timeout=45)
            
            if success:
                forwarded_messages.add(event.message.id)
                print(f"✅ Successfully forwarded: {forward_reason} from channel {source_chat_id}")
                
                # Add 3-second delay after each successful forward
                print("⏳ Waiting 3 seconds before processing next message...")
                await asyncio.sleep(3)
            else:
                print(f"❌ Failed to forward: {forward_reason} from channel {source_chat_id}")
        else:
            print(f"🚫 Message not forwarded - doesn't match allowed criteria")

    except Exception as e:
        print(f"❌ Error handling message from channel {source_chat_id}: {e}")
        traceback.print_exc()

async def process_historical_messages():
    """Process historical messages from accessible channels (skipping 'fwd' channels) in a round-robin fashion"""
    print("\n📚 Starting historical message processing...")
    print("🔄 Processing messages from channels without 'fwd' flag in round-robin fashion...")
    
    total_processed = 0
    total_forwarded = 0
    
    # Create iterators for each accessible channel (excluding 'fwd' channels)
    channel_iterators = {}
    channel_stats = {}
    skipped_fwd_channels = []
    
    for channel_id in accessible_channels:
        try:
            allowed_extensions = source_channels.get(channel_id, [])
            
            # Skip channels with 'fwd' flag for historical processing
            if has_fwd_flag(channel_id):
                skipped_fwd_channels.append(channel_id)
                print(f"⏭️ Skipping historical processing for channel {channel_id} (has 'fwd' flag - new messages only)")
                continue
            
            print(f"🔍 Setting up iterator for channel {channel_id} (allowed: {allowed_extensions})")
            
            entity = await client.get_entity(channel_id)
            channel_iterators[channel_id] = client.iter_messages(entity, limit=None)
            channel_stats[channel_id] = {'processed': 0, 'forwarded': 0, 'allowed_extensions': allowed_extensions}
            
        except Exception as e:
            print(f"❌ Error setting up channel {channel_id}: {e}")
            continue
    
    if not channel_iterators:
        print("❌ No channel iterators could be created")
        return 0
    
    print(f"✅ Created iterators for {len(channel_iterators)} channels")
    
    # Process messages in round-robin fashion
    active_channels = list(channel_iterators.keys())
    current_channel_index = 0
    
    while active_channels:
        channel_id = active_channels[current_channel_index]
        iterator = channel_iterators[channel_id]
        allowed_extensions = channel_stats[channel_id]['allowed_extensions']
        
        try:
            # Get next message from current channel
            message = await iterator.__anext__()
            
            channel_stats[channel_id]['processed'] += 1
            total_processed += 1
            
            # Skip if message was already forwarded
            if message.id in forwarded_messages:
                # Move to next channel
                current_channel_index = (current_channel_index + 1) % len(active_channels)
                continue
            
            should_forward = False
            forward_reason = ""
            
            # Check for file attachments
            if message.media and hasattr(message.media, 'document') and message.media.document:
                document = message.media.document
                file_name = None
                
                # Get the filename from document attributes
                for attr in document.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        file_name = attr.file_name
                        break
                
                if file_name:
                    if should_forward_file(file_name, allowed_extensions):
                        should_forward = True
                        forward_reason = f"File: {file_name} (from channel {channel_id})"

            # Check for URLs in text (only if no file was found or if file was not allowed)
            if not should_forward and message.text:
                if should_forward_url(message.text, allowed_extensions):
                    should_forward = True
                    forward_reason = f"URL in text: {message.text[:50]}... (from channel {channel_id})"
                elif should_forward_text(message.text, allowed_extensions):
                    should_forward = True
                    forward_reason = f"Text message: {message.text[:50]}... (from channel {channel_id})"

            # Forward the message if it meets criteria
            if should_forward:
                success = await safe_forward_message(message, destination_chat, timeout=45)
                
                if success:
                    forwarded_messages.add(message.id)
                    channel_stats[channel_id]['forwarded'] += 1
                    total_forwarded += 1
                    print(f"✅ Forwarded: {forward_reason}")
                    
                    # Add 3-second delay after each successful forward
                    print("⏳ Waiting 3 seconds before next forward...")
                    await asyncio.sleep(3)
                else:
                    print(f"❌ Failed to forward: {forward_reason}")
            
            # Progress update every 50 total messages
            if total_processed % 50 == 0:
                print(f"📊 Progress: {total_processed} total processed, {total_forwarded} forwarded")
                for cid, stats in channel_stats.items():
                    if stats['processed'] > 0:
                        print(f"  Channel {cid}: {stats['processed']} processed, {stats['forwarded']} forwarded")
            
            # Move to next channel
            current_channel_index = (current_channel_index + 1) % len(active_channels)
            
        except StopAsyncIteration:
            # This channel is exhausted, remove it from active channels
            print(f"✅ Channel {channel_id} completed: {channel_stats[channel_id]['processed']} processed, {channel_stats[channel_id]['forwarded']} forwarded")
            active_channels.remove(channel_id)
            if current_channel_index >= len(active_channels) and active_channels:
                current_channel_index = 0
                
        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"⏳ Rate limited on channel {channel_id}. Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
            # Don't move to next channel, retry this one
            
        except Exception as e:
            print(f"❌ Error processing message from channel {channel_id}: {e}")
            # Move to next channel
            current_channel_index = (current_channel_index + 1) % len(active_channels)
            continue
    
    print(f"\n🎉 Historical processing complete!")
    print(f"📊 Final stats:")
    for channel_id, stats in channel_stats.items():
        print(f"  Channel {channel_id}: {stats['processed']} processed, {stats['forwarded']} forwarded")
    
    if skipped_fwd_channels:
        print(f"⏭️ Skipped channels (fwd flag - new messages only): {len(skipped_fwd_channels)}")
        for channel_id in skipped_fwd_channels:
            print(f"  Channel {channel_id}: skipped (will only process new messages)")
    
    print(f"📊 Total: {total_processed} messages processed, {total_forwarded} messages forwarded")
    return total_forwarded

async def main():
    """Main function with improved error handling and historical message processing"""
    try:
        print("🚀 Starting Telegram Forward Bot...")
        
        # Start client with timeout
        await asyncio.wait_for(client.start(), timeout=60)
        print("✅ Forward client started successfully!")

        # Check channel access first
        print("🔍 Checking channel accessibility...")
        await asyncio.wait_for(check_channel_access(), timeout=120)

        if not accessible_channels:
            print("❌ No accessible channels found. Exiting...")
            return

        print(f"✅ Found {len(accessible_channels)} accessible channels")
        
        # Display channel configuration
        print("\n📋 Channel Configuration:")
        for channel_id in accessible_channels:
            extensions = source_channels.get(channel_id, [])
            fwd_status = " (NEW messages only)" if has_fwd_flag(channel_id) else " (with history)"
            print(f"  Channel {channel_id}: {extensions}{fwd_status}")

        # Process historical messages
        print("\n🔄 Processing historical messages from all accessible channels...")
        print("⚠️  This may take a while depending on channel size...")
        
        try:
            forwarded_count = await process_historical_messages()
            print(f"✅ Historical processing completed. {forwarded_count} messages forwarded.")
        except Exception as e:
            print(f"❌ Error during historical processing: {e}")
            print("🔄 Continuing with real-time monitoring...")

        # Keep the client running to handle new messages
        print(f"\n👂 Now listening for NEW messages from {len(accessible_channels)} accessible channels...")
        print("🔄 Press Ctrl+C to stop the bot")
        
        # Run with periodic health checks
        while True:
            try:
                await asyncio.wait_for(client.run_until_disconnected(), timeout=3600)  # 1 hour timeout
                break  # If we reach here, client disconnected normally
            except asyncio.TimeoutError:
                print("⏰ Periodic health check - bot is still running...")
                continue
                
    except asyncio.TimeoutError:
        print("⏰ Timeout during startup. Please check your internet connection and try again.")
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error in main function: {e}")
        traceback.print_exc()
    finally:
        try:
            if client.is_connected():
                await client.disconnect()
                print("🔌 Client disconnected")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
