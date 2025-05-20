# main.py

import logging
import asyncio
import os
import time
from datetime import datetime
import uuid # <<<--- اضافه کنید
# import json # برای دیتابیس ساده JSON در صورت نیاز به پایداری بیشتر از رم
# import shelve # یا shelve برای دیتابیس ساده key-value

# Pyrogram imports
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import MessageNotModified
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

# For yt-dlp
import yt_dlp as youtube_dl

# Import configurations and translations
from config import Config
from translation import Translation

# Import custom thumbnail and metadata functions
from plugins.custom_thumbnail import Mdata01, Mdata02, Mdata03, Gthumb01, Gthumb02, delete_temp_file

# --- Logging setup ---
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# --- GLOBAL STORAGE FOR TEMPORARY URLs (IN-MEMORY) ---
# NOTE: This will clear upon bot restart. For persistence, use a database (SQLite, Redis, etc.)
temp_url_storage = {}

# --- Helper functions for progress display ---
# ... (humanbytes, TimeFormatter, progress_for_pyrogram, yt_dlp_progress_hook - same as before)
async def progress_for_pyrogram(
    current,
    total,
    ud_type,
    message,
    start_time
):
    now = time.time()
    diff = now - start_time
    if round(diff % 5.00) == 0 or current == total:
        if diff == 0: # Avoid division by zero
            return
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time_str = TimeFormatter(elapsed_time)
        estimated_total_time_str = TimeFormatter(estimated_total_time)

        current_message = f"{ud_type}\n" \
                          f"**حجم:** {humanbytes(current)} از {humanbytes(total)}\n" \
                          f"**پیشرفت:** {percentage:.2f}%\n" \
                          f"**سرعت:** {humanbytes(speed)}/s\n" \
                          f"**ETA:** {estimated_total_time_str}"

        try:
            await message.edit_text(current_message)
        except MessageNotModified:
            pass # Ignore if message content hasn't changed
        except Exception as e:
            logger.warning(f"Error updating progress message: {e}")

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
          ((str(hours) + "h, ") if hours else "") + \
          ((str(minutes) + "m, ") if minutes else "") + \
          ((str(seconds) + "s, ") if seconds else "") + \
          ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2]


# --- Button Class (If you have a main menu, keep this) ---
class Button(object):
      BUTTONS01 = InlineKeyboardMarkup( [ [ InlineKeyboardButton(text="📁 YTS", callback_data='00'),
                                            InlineKeyboardButton(text="🔍 ꜱᴇᴀʀᴄʜ", switch_inline_query_current_chat="1 ") ],
                                          [ InlineKeyboardButton(text="📁 Anime", callback_data='00'),
                                            InlineKeyboardButton(text="🔍 ꜱᴇᴀʀᴄʜ", switch_inline_query_current_chat="2 ") ],
                                          [ InlineKeyboardButton(text="📁 1337x", callback_data='00'),
                                            InlineKeyboardButton(text="🔍 ꜱᴇᴀʀᴄʜ", switch_inline_query_current_chat="3 " ) ],
                                          [ InlineKeyboardButton(text="📁 ThePirateBay", callback_data='00'),
                                            InlineKeyboardButton(text="🔍 ꜱᴇᴀʀᴄʜ", switch_inline_query_current_chat="4 ") ],
                                          [ InlineKeyboardButton(text="❌", callback_data="X0") ] ] )

# --- Handler for URL messages ---
@Client.on_message(filters.regex(r"^(http|https)://[^\s/$.?#].[^\s]*$") & filters.private)
async def process_url_for_qualities(bot: Client, message: Message):
    url = message.text
    sent_message = await message.reply_text("در حال دریافت کیفیت‌های موجود، لطفاً صبر کنید...", quote=True)
    try:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best', # Default format to extract info
            'cachedir': False, # Disable cache
            'dump_single_json': True, # Return only JSON info
            'extract_flat': True, # If playlist, extract only top-level info of items
            'force_empty_metadata': True, # Force empty metadata
            'no_warnings': True, # Don't show warnings
            'noplaylist': True, # Do not process playlists (only first item)
            'logger': logger # Use custom logger
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)

        # If it's a playlist or multiple entries, select the first entry.
        if 'entries' in info_dict and info_dict['entries']:
            info_dict = info_dict['entries'][0]

        formats = info_dict.get('formats', [])
        if not formats:
            await sent_message.edit_text("فرمت قابل دانلودی برای این URL یافت نشد.")
            return
        
        # --- Store the URL in temp_url_storage and generate a short key ---
        # Using chat_id and message_id ensures uniqueness for a given message and user
        # This key will be used to retrieve the full URL later
        temp_key = f"{message.chat.id}_{message.id}"
        temp_url_storage[temp_key] = url
        logger.info(f"Stored URL {url} with key {temp_key}")

        # Filter formats and prepare for buttons
        available_qualities = {} # Dict to store (quality_label: callback_data)
        for f in formats:
            format_id = f.get('format_id')
            ext = f.get('ext')
            height = f.get('height')
            fps = f.get('fps')
            filesize = f.get('filesize') or f.get('filesize_approx') # Actual or approximate file size
            vcodec = f.get('vcodec')
            acodec = f.get('acodec')

            # Basic filtering: only video and audio formats that are mp4/mkv/webm and have a specific height.
            if vcodec != 'none' and acodec != 'none' and height and ext in ['mp4', 'mkv', 'webm']:
                quality_label = f"{height}p"
                if fps:
                    quality_label += f"@{int(fps)}fps" # Display frames per second
                quality_label += f" ({ext})"
                if filesize:
                    quality_label += f" [{humanbytes(filesize)}]" # Display file size
                else:
                    quality_label += " [اندازه نامشخص]" # If size is unknown

                # callback_data format: dl_q=FORMAT_ID=EXT=TEMP_KEY
                # 'dl_q' is a shortened prefix for 'download_quality' to save bytes
                callback_data = f"dl_q={format_id}={ext}={temp_key}"
                available_qualities[quality_label] = callback_data

        if not available_qualities:
            await sent_message.edit_text("فرمت‌های ویدیویی مناسب برای این URL یافت نشد.")
            return

        # Build inline keyboard buttons
        buttons = []
        for quality_label, callback_data in available_qualities.items():
            buttons.append([InlineKeyboardButton(text=quality_label, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(buttons)
        await sent_message.edit_text(
            "کیفیت مورد نظر را انتخاب کنید:",
            reply_markup=reply_markup
        )

    except youtube_dl.utils.DownloadError as e:
        logger.error(f"YoutubeDL Error processing URL {url}: {e}")
        await sent_message.edit_text(f"خطا در پردازش لینک (YoutubeDL): {e}")
    except Exception as e:
        logger.error(f"General error processing URL {url}: {e}")
        await sent_message.edit_text(f"هنگام پردازش لینک شما خطایی رخ داد: {e}")

# --- Handler for quality selection Callback Queries ---
@Client.on_callback_query(filters.regex(r"^dl_q=")) # <<<--- Regex changed to 'dl_q='
async def ddl_call_back(bot: Client, update: CallbackQuery):
    logger.info(f"Callback received: {update.data}")
    cb_data = update.data

    # parsing callback_data: dl_q=FORMAT_ID=EXT=TEMP_KEY
    _, youtube_dl_format, youtube_dl_ext, temp_key = cb_data.split("=", 3)

    # --- Retrieve the original URL from temp_url_storage ---
    youtube_dl_url = temp_url_storage.get(temp_key)
    if not youtube_dl_url:
        await update.message.edit_text("خطا: لینک اصلی پیدا نشد یا منقضی شده است. لطفاً دوباره امتحان کنید یا لینک جدیدی ارسال کنید.")
        return
    
    # Optional: Delete the URL from storage if you want it to be used only once
    # However, if a user might want to download multiple qualities from the same message,
    # don't delete it. Consider a scheduled cleanup or a persistent DB.
    # del temp_url_storage[temp_key] # Consider if you need to retain for other downloads

    user = await bot.get_me()
    mention = user["mention"]
    description = Translation.TECH_VJ_CUSTOM_CAPTION_UL_FILE.format(mention)
    start_time = datetime.now() # Start time for download

    await update.message.edit_text(Translation.DOWNLOAD_START)

    tmp_directory_for_each_user = os.path.join(Config.TECH_VJ_DOWNLOAD_LOCATION, str(update.from_user.id))
    if not os.path.isdir(tmp_directory_for_each_user):
        os.makedirs(tmp_directory_for_each_user)

    # Output filename template for yt-dlp
    output_template = os.path.join(tmp_directory_for_each_user, '%(title)s.%(ext)s')

    ydl_opts_download = {
        'format': youtube_dl_format, # Use the selected format_id
        'outtmpl': output_template,
        'cachedir': False,
        'noplaylist': True,
        'logger': logger,
        'progress_hooks': [lambda d: asyncio.create_task(
            yt_dlp_progress_hook(d, bot, update.message.chat.id, update.message.id, start_time.timestamp())
        )],
        'prefer_ffmpeg': True, # Prefer FFmpeg for merging (e.g., video+audio)
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': youtube_dl_ext, # Ensure correct extension after merging/conversion
        }]
    }

    download_success = False
    downloaded_file_path = None
    try:
        with youtube_dl.YoutubeDL(ydl_opts_download) as ydl:
            info_dict = ydl.extract_info(youtube_dl_url, download=True)
            downloaded_file_path = ydl.prepare_filename(info_dict)
            download_success = True
    except youtube_dl.DownloadError as e:
        logger.error(f"Download Error for {youtube_dl_url} (format {youtube_dl_format}): {e}")
        await update.message.edit_text(f"دانلود با شکست مواجه شد: {e}")
        return
    except Exception as e:
        logger.error(f"An unexpected error occurred during download: {e}")
        await update.message.edit_text(f"خطای غیرمنتظره‌ای در حین دانلود رخ داد: {e}")
        return

    if download_success and downloaded_file_path and os.path.exists(downloaded_file_path):
        end_download_time = datetime.now()
        await update.message.edit_text(Translation.UPLOAD_START)

        file_size = os.stat(downloaded_file_path).st_size

        if file_size > Config.TECH_VJ_TG_MAX_FILE_SIZE:
            await update.message.edit_text(
                chat_id=update.message.chat.id,
                text=Translation.TECH_VJ_RCHD_TG_API_LIMIT,
                message_id=update.message.id
            )
            try:
                os.remove(downloaded_file_path)
            except Exception as e:
                logger.warning(f"Error removing large file {downloaded_file_path}: {e}")
            return
        else:
            upload_start_time = time.time() # Start time for upload

            if downloaded_file_path.endswith(('.mp3', '.ogg', '.wav', '.m4a')):
                tg_send_type = "audio"
            elif downloaded_file_path.endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
                tg_send_type = "video"
            else:
                tg_send_type = "file" # Default to file if unknown

            thumb_image_path = None
            try:
                thumb_image_path = await Gthumb01(bot, update) # This function should return a valid path or None
            except Exception as e:
                logger.warning(f"Could not generate thumbnail with Gthumb01: {e}")
                thumb_image_path = None # Set to None if error occurs

            try:
                if tg_send_type == "audio":
                    duration = await Mdata03(downloaded_file_path)
                    await bot.send_audio(
                        chat_id=update.message.chat.id,
                        audio=downloaded_file_path,
                        caption=description,
                        duration=duration,
                        thumb=thumb_image_path,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.TECH_VJ_UPLOAD_START,
                            update.message,
                            upload_start_time
                        )
                    )
                elif tg_send_type == "file":
                    await bot.send_document(
                        chat_id=update.message.chat.id,
                        document=downloaded_file_path,
                        thumb=thumb_image_path,
                        caption=description,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.TECH_VJ_UPLOAD_START,
                            update.message,
                            upload_start_time
                        )
                    )
                elif tg_send_type == "vm": # Video Message (circular video)
                    width, duration = await Mdata02(downloaded_file_path)
                    thumb_vm_path = await Gthumb02(bot, update, duration, downloaded_file_path)
                    await bot.send_video_note(
                        chat_id=update.message.chat.id,
                        video_note=downloaded_file_path,
                        duration=duration,
                        length=width,
                        thumb=thumb_vm_path,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.TECH_VJ_UPLOAD_START,
                            update.message,
                            upload_start_time
                        )
                    )
                elif tg_send_type == "video":
                    width, height, duration = await Mdata01(downloaded_file_path)
                    thumb_video_path = await Gthumb02(bot, update, duration, downloaded_file_path)
                    await bot.send_video(
                        chat_id=update.message.chat.id,
                        video=downloaded_file_path,
                        caption=description,
                        duration=duration,
                        width=width,
                        height=height,
                        supports_streaming=True,
                        thumb=thumb_video_path,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.TECH_VJ_UPLOAD_START,
                            update.message,
                            upload_start_time
                        )
                    )
                else:
                    logger.info("Unknown send type. Sending file as document.")
                    await bot.send_document(
                        chat_id=update.message.chat.id,
                        document=downloaded_file_path,
                        thumb=thumb_image_path,
                        caption=description,
                        reply_to_message_id=update.message.reply_to_message.id,
                        progress=progress_for_pyrogram,
                        progress_args=(
                            Translation.TECH_VJ_UPLOAD_START,
                            update.message,
                            upload_start_time
                        )
                    )
            except Exception as e:
                logger.error(f"Error during file upload: {e}")
                await update.message.edit_text(f"خطا در آپلود فایل: {e}")
                return

            end_upload_time = datetime.now()
            # --- Cleanup ---
            try:
                os.remove(downloaded_file_path)
                # Remove thumbnail if created
                if thumb_image_path and os.path.exists(thumb_image_path):
                    await delete_temp_file(thumb_image_path) # Use async function for deletion
                # Also remove thumbnails generated by Gthumb02 if they exist
                if 'thumb_vm_path' in locals() and thumb_vm_path and os.path.exists(thumb_vm_path):
                     await delete_temp_file(thumb_vm_path)
                if 'thumb_video_path' in locals() and thumb_video_path and os.path.exists(thumb_video_path):
                     await delete_temp_file(thumb_video_path)

            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

            time_taken_for_download = (end_download_time - start_time).seconds
            time_taken_for_upload = (end_upload_time - end_download_time).seconds
            await update.message.edit_text(
                text=Translation.TECH_VJ_AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(time_taken_for_download, time_taken_for_upload),
                chat_id=update.message.chat.id,
                message_id=update.message.id,
                disable_web_page_preview=True
            )
    else:
        await update.message.edit_text(
            text=Translation.TECH_VJ_NO_VOID_FORMAT_FOUND.format("دانلود ناموفق بود یا فایل یافت نشد."),
            chat_id=update.message.chat.id,
            message_id=update.message.id,
            disable_web_page_preview=True
        )

# --- Progress Hook for yt-dlp ---
async def yt_dlp_progress_hook(d: dict, bot: Client, chat_id: int, message_id: int, start_time: float):
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        downloaded_bytes = d.get('downloaded_bytes')
        speed = d.get('speed')
        eta = d.get('eta')

        if total_bytes and downloaded_bytes:
            percentage = downloaded_bytes * 100 / total_bytes
            current_time = time.time()
            diff = current_time - start_time

            if diff == 0: # Avoid division by zero
                diff = 0.001

            current_speed = humanbytes(speed) if speed else "N/A"
            estimated_time_str = TimeFormatter(eta * 1000) if eta else "N/A"

            current_message = f"**وضعیت دانلود**\n" \
                              f"**دانلود شده:** {humanbytes(downloaded_bytes)} از {humanbytes(total_bytes)}\n" \
                              f"**پیشرفت:** {percentage:.2f}%\n" \
                              f"**سرعت:** {current_speed}/s\n" \
                              f"**زمان باقیمانده (ETA):** {estimated_time_str}"
            try:
                await bot.edit_message_text(chat_id, message_id, text=current_message)
            except MessageNotModified:
                pass # Ignore if message content hasn't changed
            except Exception as e:
                logger.warning(f"Error updating yt-dlp progress message: {e}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished for {d['filename']}")


# --- Bot initialization and execution ---
if __name__ == "__main__":
    plugins_path = dict(root="plugins")

    app = Client(
        "my_bot_session",
        bot_token=Config.TG_BOT_TOKEN,
        api_id=Config.APP_ID,
        api_hash=Config.API_HASH,
        plugins=plugins_path
    )

    app.add_handler(MessageHandler(process_url_for_qualities, filters.regex(r"^(http|https)://[^\s/$.?#].[^\s]*$") & filters.private))
    app.add_handler(CallbackQueryHandler(ddl_call_back, filters.regex(r"^dl_q="))) # <<<--- Regex changed here

    logger.info("ربات در حال شروع به کار است...")
    app.run()
    logger.info("ربات متوقف شد.")
