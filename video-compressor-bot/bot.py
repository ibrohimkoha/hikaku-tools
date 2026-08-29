import asyncio
import os
import time
import subprocess
import logging
from pyrogram import Client, filters
from pyrogram.types import Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VideoCompressor")

BOT_TOKEN = os.getenv("COMPRESSOR_BOT_TOKEN", "8815124197:AAE6zG_54LOh5ja-DxlrGFF8-2cQplEQ5fA")
API_ID = int(os.getenv("TELEGRAM_API_ID", "33864339"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "7a12002bdba42778b2068c88bb64072c")
ADMIN_IDS = [5415350162, 6149114216]

TEMP_DIR = "/tmp/hikaku_compress"
os.makedirs(TEMP_DIR, exist_ok=True)

app = Client("hikaku_video_compressor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def human_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = 0
    p = float(size_bytes)
    while p >= 1024.0 and i < len(size_name) - 1:
        p /= 1024.0
        i += 1
    return f"{p:.2f} {size_name[i]}"

async def compress_video_ffmpeg(input_path: str, output_path: str, crf: int = 24) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "veryfast",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode == 0

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔️ Ushbu bot faqat Hikaku administratorlari uchun!")
        return

    text = (
        "🗜️ <b>Hikaku Smart Video Compressor Bot</b>\n\n"
        "Menga istalgan video (MP4/MKV) yoki hujjat yuboring.\n"
        "Men uning vizual sifatini yo'qotmagan holda <b>50% - 80% gacha</b> hajmini qisqartirib (siqib) beraman!\n\n"
        "⚙️ <b>Standart:</b> H.264 CRF-24 + AAC 128k + Web Faststart (2GB gacha)"
    )
    await message.reply_text(text)

@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔️ Ruxsat yo'q!")
        return

    media = message.video or message.document
    if message.document and not (media.mime_type and media.mime_type.startswith("video/")):
        await message.reply_text("❌ Iltimos, faqat video fayl yuboring!")
        return

    orig_name = media.file_name or f"video_{int(time.time())}.mp4"
    orig_size = media.file_size or 0

    status_msg = await message.reply_text(
        f"⏳ <b>Video yuklab olinmoqda...</b>\n📁 <code>{orig_name}</code> ({human_size(orig_size)})"
    )

    clean_base = os.path.splitext(orig_name)[0].replace(" ", "_")
    ext = os.path.splitext(orig_name)[1] or ".mp4"
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    in_file = os.path.join(TEMP_DIR, f"in_{clean_base}_{timestamp}{ext}")
    out_file = os.path.join(TEMP_DIR, f"out_{clean_base}_{timestamp}.mp4")

    try:
        last_edit = [0]
        async def progress(current, total):
            if time.time() - last_edit[0] > 4:
                last_edit[0] = time.time()
                pct = round((current / total) * 100, 1) if total > 0 else 0
                try:
                    await status_msg.edit_text(f"⏳ <b>Yuklab olinmoqda: {pct}%</b>\n({human_size(current)} / {human_size(total)})")
                except:
                    pass

        await message.download(file_name=in_file, progress=progress)
        await status_msg.edit_text("⚙️ <b>FFmpeg orqali sifat saqlangan holda siqilmoqda...</b>\n<i>Iltimos kuting...</i>")

        start_time = time.time()
        success = await compress_video_ffmpeg(in_file, out_file, crf=24)
        elapsed = round(time.time() - start_time, 1)

        if not success or not os.path.exists(out_file):
            await status_msg.edit_text("❌ Siqish jarayonida xatolik yuz berdi!")
            return

        new_size = os.path.getsize(out_file)
        saved_percent = round((1 - (new_size / orig_size)) * 100, 1) if orig_size > 0 else 0

        await status_msg.edit_text(f"📤 <b>Siqilgan video Telegramga yuklanmoqda...</b>\nTejaldi: <b>{saved_percent}%</b>")

        caption = (
            f"✅ <b>Video muvaffaqiyatli siqildi!</b>\n\n"
            f"📦 Asl hajm: <b>{human_size(orig_size)}</b>\n"
            f"🗜 Yangi hajm: <b>{human_size(new_size)}</b>\n"
            f"🎉 Tejalgan joy: <b>{saved_percent}%</b>\n"
            f"⚡️ Ketgan vaqt: <b>{elapsed}s</b>"
        )

        last_up = [0]
        async def up_progress(current, total):
            if time.time() - last_up[0] > 4:
                last_up[0] = time.time()
                pct = round((current / total) * 100, 1) if total > 0 else 0
                try:
                    await status_msg.edit_text(f"📤 <b>Yuklanmoqda: {pct}%</b>\n({human_size(current)} / {human_size(total)})")
                except:
                    pass

        await message.reply_video(
            video=out_file,
            caption=caption,
            supports_streaming=True,
            progress=up_progress
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error compressing: {e}")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")
    finally:
        if os.path.exists(in_file):
            try: os.remove(in_file)
            except: pass
        if os.path.exists(out_file):
            try: os.remove(out_file)
            except: pass

if __name__ == "__main__":
    logger.info("Starting Hikaku Video Compressor Bot...")
    app.run()
