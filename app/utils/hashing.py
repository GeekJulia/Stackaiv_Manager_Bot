import hashlib
import requests
import os

def calculate_file_hash(bot, file_id):
    """
    Downloads a file from Telegram and calculates its SHA-256 hash.
    
    Args:
        bot: The telebot instance.
        file_id: The Telegram file_id to download.
        
    Returns:
        The SHA-256 hash of the file as a hexadecimal string.
    """
    try:
        # Get file path from Telegram
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        
        # Construct the download URL
        # Note: In pyTelegramBotAPI, download_file returns the bytes
        file_content = bot.download_file(file_path)
        
        # Calculate SHA-256 hash
        sha256_hash = hashlib.sha256()
        sha256_hash.update(file_content)
        
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"ERROR: calculate_file_hash failed for file_id {file_id} - {str(e)}")
        return None
