import logging
import asyncio
import os
import time
from datetime import datetime
import uuid

# Pyrogram imports
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import MessageNotModified, FloodWait, RPCError
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

# For yt-dlp
import yt_dlp as youtube_dl

# Import configurations and translations
from config import Config
from translation import Translation

# Import custom thumbnail and metadata functions
from plugins.custom_thumbnail import Mdata01, Mdata02, Mdata03, Gthumb01, Gthumb02, delete_temp_file

# --- Logging setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("yt_dlp").setLevel(logging.WARNING)

# --- GLOBAL STORAGE FOR TEMPORARY URLs (IN-MEMORY) ---
temp_url_storage = {}

# --- Helper functions for progress display ---
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
        if diff == 0:
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
            pass
        except FloodWait as e:
            logger.warning(f"FloodWait encountered while updating progress: {e.value} seconds. Waiting...")
            await asyncio.sleep(e.value)
        except RPCError as e:
            logger.error(f"Pyrogram RPCError during progress update: {e}")
        except Exception as e:
            logger.warning(f"General error updating progress message: {e}")

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

# --- Button Class (Example, can be removed if not used) ---
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
            'format': 'bestvideo+bestaudio/best',
            'cachedir': False,
            'dump_single_json': True,
            'extract_flat': True,
            'force_empty_metadata': True,
            'no_warnings': True,
            'noplaylist': True,
            'logger': logger
        }
        
        info_dict = await asyncio.to_thread(lambda: youtube_dl.YoutubeDL(ydl_opts).extract_info(url, download=False))

        if 'entries' in info_dict and info_dict['entries']:
            info_dict = info_dict['entries'][0]

        formats = info_dict.get('formats', [])
        if not formats:
            await sent_message.edit_text("فرمت قابل دانلودی برای این URL یافت نشد.")
            return
        
        temp_key = f"{message.chat.id}_{message.id}"
        temp_url_storage[temp_key] = url
        logger.info(f"Stored URL {url} with key {temp_key}")

        available_qualities = {}
        for f in formats:
            format_id = f.get('format_id')
            ext = f.get('ext')
            height = f.get('height')
            fps = f.get('fps')
            filesize = f.get('filesize') or f.get('filesize_approx')
            vcodec = f.get('vcodec')
            acodec = f.get('acodec')

            if (vcodec != 'none' and acodec != 'none' and height) and ext in ['mp4', 'mkv', 'webm']:
                quality_label = f"{height}p"
                if fps:
                    quality_label += f"@{int(fps)}fps"
                quality_label += f" ({ext})"
                if filesize:
                    quality_label += f" [{humanbytes(filesize)}]"
                else:
                    quality_label += " [اندازه نامشخص]"

                callback_data = f"dl_q={format_id}={ext}={temp_key}"
                
                if len(callback_data.encode('utf-8')) > 64:
                    logger.warning(f"Callback data too long ({len(callback_data.encode('utf-8'))} bytes) for format {format_id}. Skipping.")
                    continue

                available_qualities[quality_label] = callback_data

        if not available_qualities:
            await sent_message.edit_text("فرمت‌های ویدیویی مناسب برای این URL یافت نشد.")
            return

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
        logger.error(f"General error processing URL {url}: {e}", exc_info=True)
        await sent_message.edit_text(f"هنگام پردازش لینک شما خطایی رخ داد: {e}")

# --- Handler for quality selection Callback Queries ---
@Client.on_callback_query(filters.regex(r"^dl_q="))
async def ddl_call_back(bot: Client, update: CallbackQuery):
    logger.info(f"Callback received: {update.data} from user {update.from_user.id}")
    cb_data = update.data

    try:
        _, youtube_dl_format, youtube_dl_ext, temp_key = cb_data.split("=", 3)
    except ValueError as e:
        logger.error(f"Error parsing callback data: {cb_data} - {e}", exc_info=True)
        await update.message.edit_text("خطا در پردازش اطلاعات دکمه. لطفاً دوباره امتحان کنید.")
        return

    youtube_dl_url = temp_url_storage.get(temp_key)
    if not youtube_dl_url:
        await update.message.edit_text("خطا: لینک اصلی پیدا نشد یا منقضی شده است. لطفاً دوباره امتحان کنید یا لینک جدیدی ارسال کنید.")
        logger.warning(f"URL not found in temp_url_storage for key: {temp_key}. Bot might have restarted or key expired.")
        return
    
    user = await bot.get_me()
    if user and user.mention:
        mention = user.mention
    elif user and user.first_name:
        mention = user.first_name
    else:
        mention = "ربات"
        logger.warning("Could not get bot's mention or first name. Using generic 'ربات'.")

    description = Translation.TECH_VJ_CUSTOM_CAPTION_UL_FILE.format(mention=mention)

    start_time_download = datetime.now()

    try:
        await update.message.edit_text(Translation.DOWNLOAD_START)
    except MessageNotModified:
        pass
    except RPCError as e:
        logger.error(f"Failed to edit message with DOWNLOAD_START: {e}")
        await bot.send_message(chat_id=update.message.chat.id, text=Translation.DOWNLOAD_START)


    tmp_directory_for_each_user = os.path.join(Config.TECH_VJ_DOWNLOAD_LOCATION, str(update.from_user.id))
    os.makedirs(tmp_directory_for_each_user, exist_ok=True)

    output_template = os.path.join(tmp_directory_for_each_user, '%(title)s.%(ext)s')

    # Get the event loop instance
    loop = asyncio.get_running_loop()

    ydl_opts_download = {
        'format': youtube_dl_format,
        'outtmpl': output_template,
        'cachedir': False,
        'noplaylist': True,
        'logger': logger,
        # FIX: Use run_coroutine_threadsafe to schedule the progress hook
        'progress_hooks': [lambda d: loop.call_soon_threadsafe(
            asyncio.create_task, # Create task in the main event loop
            yt_dlp_progress_hook(d, bot, update.message.chat.id, update.message.id, start_time_download.timestamp())
        )],
        'prefer_ffmpeg': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': youtube_dl_ext,
        }]
    }

    download_success = False
    downloaded_file_path = None
    try:
        with youtube_dl.YoutubeDL(ydl_opts_download) as ydl:
            # The actual download occurs here
            info_dict = await asyncio.to_thread(lambda: ydl.extract_info(youtube_dl_url, download=True))
            downloaded_file_path = await asyncio.to_thread(ydl.prepare_filename, info_dict)
            download_success = True
    except youtube_dl.DownloadError as e:
        logger.error(f"Download Error for {youtube_dl_url} (format {youtube_dl_format}): {e}", exc_info=True)
        await update.message.edit_text(f"دانلود با شکست مواجه شد: {e}")
        return
    except Exception as e:
        logger.error(f"An unexpected error occurred during download: {e}", exc_info=True)
        await update.message.edit_text(f"خطای غیرمنتظره‌ای در حین دانلود رخ داد: {e}")
        return

    if download_success and downloaded_file_path and os.path.exists(downloaded_file_path):
        end_download_time = datetime.now()
        try:
            await update.message.edit_text(Translation.UPLOAD_START)
        except MessageNotModified:
            pass
        except RPCError as e:
            logger.error(f"Failed to edit message with UPLOAD_START: {e}")
            await bot.send_message(chat_id=update.message.chat.id, text=Translation.UPLOAD_START)

        file_size = os.stat(downloaded_file_path).st_size

        if file_size > Config.TECH_VJ_TG_MAX_FILE_SIZE:
            await update.message.edit_text(
                chat_id=update.message.chat.id,
                text=Translation.TECH_VJ_RCHD_TG_API_LIMIT,
                message_id=update.message.id
            )
            try:
                await asyncio.to_thread(os.remove, downloaded_file_path)
                logger.info(f"Removed large file: {downloaded_file_path}")
            except Exception as e:
                logger.warning(f"Error removing large file {downloaded_file_path}: {e}")
            return
        else:
            upload_start_time = time.time()

            if downloaded_file_path.lower().endswith(('.mp3', '.ogg', '.wav', '.m4a')):
                tg_send_type = "audio"
            elif downloaded_file_path.lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
                tg_send_type = "video"
            else:
                tg_send_type = "file"

            thumb_image_path = None
            try:
                thumb_image_path = await Gthumb01(bot, update) 
            except Exception as e:
                logger.warning(f"Could not get custom thumbnail with Gthumb01: {e}")
                thumb_image_path = None

            thumb_vm_path = None
            thumb_video_path = None

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
                elif tg_send_type == "video":
                    width, height, duration = await Mdata01(downloaded_file_path)
                    
                    is_video_note = (width and height and width == height and duration <= 60)

                    if is_video_note:
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
                    else:
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
                logger.error(f"Error during file upload: {e}", exc_info=True)
                await update.message.edit_text(f"خطا در آپلود فایل: {e}")
                return

            end_upload_time = datetime.now()
            try:
                await delete_temp_file(downloaded_file_path)
                
                if thumb_image_path and os.path.exists(thumb_image_path):
                    await delete_temp_file(thumb_image_path)
                if thumb_vm_path and os.path.exists(thumb_vm_path):
                    await delete_temp_file(thumb_vm_path)
                if thumb_video_path and os.path.exists(thumb_video_path):
                    await delete_temp_file(thumb_video_path)

                if os.path.exists(tmp_directory_for_each_user) and not os.listdir(tmp_directory_for_each_user):
                    await asyncio.to_thread(os.rmdir, tmp_directory_for_each_user)
                    logger.info(f"Removed empty user directory: {tmp_directory_for_each_user}")

            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

            time_taken_for_download = (end_download_time - start_time_download).seconds
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

            if diff == 0:
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
                pass
            except FloodWait as e:
                logger.warning(f"FloodWait on progress update: {e.value} seconds. Waiting...")
                await asyncio.sleep(e.value)
            except RPCError as e:
                logger.error(f"Pyrogram RPCError during yt-dlp progress update: {e}")
            except Exception as e:
                logger.warning(f"General error updating yt-dlp progress message: {e}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished for {d.get('filename', 'unknown file')}")


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
    app.add_handler(CallbackQueryHandler(ddl_call_back, filters.regex(r"^dl_q=")))

    logger.info("ربات در حال شروع به کار است...")
    app.run()
    logger.info("ربات متوقف شد.")
