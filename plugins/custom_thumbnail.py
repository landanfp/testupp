import os
import asyncio
import logging
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

# Import Config (assuming it's accessible or needs to be imported)
from config import Config

logger = logging.getLogger(__name__)

# Async function to safely delete temporary files
async def delete_temp_file(path):
    if os.path.exists(path):
        try:
            await asyncio.to_thread(os.remove, path)
            logger.info(f"Deleted temp file: {path}")
        except Exception as e:
            logger.warning(f"Error deleting temp file {path}: {e}")

# Function to get video metadata (width, height, duration)
async def Mdata01(file_path):
    try:
        # Use asyncio.to_thread for blocking I/O operations
        metadata = await asyncio.to_thread(extractMetadata, createParser(file_path))
        if metadata:
            width = metadata.get('width', 0)
            height = metadata.get('height', 0)
            duration = metadata.get('duration').seconds if metadata.has('duration') else 0
            return width, height, duration
        return 0, 0, 0
    except Exception as e:
        logger.error(f"Error in Mdata01 for {file_path}: {e}")
        return 0, 0, 0

# Function to get video message metadata (width, duration)
async def Mdata02(file_path):
    try:
        metadata = await asyncio.to_thread(extractMetadata, createParser(file_path))
        if metadata:
            width = metadata.get('width', 0)
            duration = metadata.get('duration').seconds if metadata.has('duration') else 0
            return width, duration
        return 0, 0
    except Exception as e:
        logger.error(f"Error in Mdata02 for {file_path}: {e}")
        return 0, 0

# Function to get audio file metadata (duration)
async def Mdata03(file_path):
    try:
        metadata = await asyncio.to_thread(extractMetadata, createParser(file_path))
        if metadata:
            duration = metadata.get('duration').seconds if metadata.has('duration') else 0
            return duration
        return 0
    except Exception as e:
        logger.error(f"Error in Mdata03 for {file_path}: {e}")
        return 0

# Function to get a generic thumbnail (e.g., user-uploaded custom thumbnail)
async def Gthumb01(bot, update):
    user_id = update.from_user.id
    # Assuming custom thumbnail is stored in a specific path
    thumb_path = os.path.join(Config.TECH_VJ_DOWNLOAD_LOCATION, str(user_id), "thumbnail.jpg")
    if os.path.exists(thumb_path):
        return thumb_path
    return None # Return None if no custom thumbnail found

# Function to generate a video thumbnail using FFmpeg
# This function requires FFmpeg to be installed on your system
async def Gthumb02(bot, update, duration, file_path):
    user_id = update.from_user.id
    thumb_dir = os.path.join(Config.TECH_VJ_DOWNLOAD_LOCATION, str(user_id))
    os.makedirs(thumb_dir, exist_ok=True) # Ensure directory exists
    thumb_path = os.path.join(thumb_dir, f"video_thumb_{os.path.basename(file_path)}.jpg")

    try:
        # Use ffmpeg to extract a frame as thumbnail
        # -ss: seek to position (e.g., middle of video)
        # -vframes 1: extract only one frame
        # -s 320x180: resize thumbnail (optional)
        # -y: overwrite if exists
        command = [
            "ffmpeg", "-i", file_path, "-ss", str(duration // 2),
            "-vframes", "1", "-s", "320x180", "-y", thumb_path
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg thumbnail generation failed for {file_path}. Error: {stderr.decode()}")
            return None
        
        logger.info(f"Thumbnail generated: {thumb_path}")
        return thumb_path
    except FileNotFoundError:
        logger.error("FFmpeg not found. Please install FFmpeg to enable video thumbnail generation.")
        return None
    except Exception as e:
        logger.error(f"Error in Gthumb02 for {file_path}: {e}")
        return None
