import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Environment variables
    TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    APP_ID = int(os.environ.get("APP_ID", 1234567)) # Your API ID
    API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH_HERE") # Your API Hash

    # Download location
    TECH_VJ_DOWNLOAD_LOCATION = os.environ.get("DOWNLOAD_LOCATION", "./downloads/")

    # Maximum file size for Telegram (approx. 2 GB - 2 * 1024 * 1024 * 1024)
    TECH_VJ_TG_MAX_FILE_SIZE = int(os.environ.get("TG_MAX_FILE_SIZE", 2147483648))

    # Maximum timeout for processing (downloading) links (in seconds)
    TECH_VJ_PROCESS_MAX_TIMEOUT = int(os.environ.get("PROCESS_TIMEOUT", 3600)) # 1 hour

    # Chunk size for direct download (if still used, though yt-dlp handles this)
    TECH_VJ_CHUNK_SIZE = 1024 * 1024 # 1MB
