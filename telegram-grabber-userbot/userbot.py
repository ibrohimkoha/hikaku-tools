import os
import sys
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, DocumentAttributeVideo, DocumentAttributeFilename

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("HikakuGrabber")

API_ID = int(os.getenv("TELEGRAM_API_ID", "28373801"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "9dd3f0e8f22fa97d8b5e91eb705886d4")
SESSION_NAME = os.getenv("TELEGRAM_SESSION", "hikaku_userbot_session")

TEMP_DIR = "/tmp/hikaku_grabber"
os.makedirs(TEMP_DIR, exist_ok=True)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def download_and_send_media(event, message, destination="me"):
    """
    Himoyalangan (Restricted) xabardan videoni sug'urib olib toza qilib yuboradi.
    """
    if not message.media:
        await event.reply("❌ Bu xabarda media (video/fayl) mavjud emas!")
        return

    status_msg = await event.reply("⏳ <b>Himoyalangan media MTProto orqali sug'urib olinmoqda...</b>", parse_mode="html")
    
    file_name = "grabbed_video.mp4"
    if isinstance(message.media, MessageMediaDocument):
        for attr in message.media.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_name = attr.file_name

    download_path = os.path.join(TEMP_DIR, file_name)

    try:
        await client.download_media(message, file=download_path)
        
        await status_msg.edit("📤 <b>Saqlangan xabarlaringizga (Saved Messages) yuborilmoqda...</b>", parse_mode="html")

        await client.send_file(
            destination,
            file=download_path,
            caption=f"✅ <b>Sug'urib olingan media:</b> <code>{file_name}</code>\nManba: {getattr(message.chat, 'title', getattr(message.chat, 'username', 'Chat'))}",
            parse_mode="html",
            supports_streaming=True
        )

        await status_msg.edit("✅ <b>Muvaffaqiyatli saqlandi!</b> (Saved Messages bo'limini tekshiring)", parse_mode="html")

    except Exception as e:
        logger.error(f"Error grabbing: {e}")
        await status_msg.edit(f"❌ Xatolik: {e}")
    finally:
        if os.path.exists(download_path):
            try: os.remove(download_path)
            except: pass

@client.on(events.NewMessage(pattern=r"^/grab(?:\s+(.*))?$", outgoing=True))
async def handle_grab(event):
    """
    1. Reply qilib: `/grab`
    2. Bot username va soni bilan: `/grab @bot_username 5`
    """
    reply_to = await event.get_reply_message()
    args = event.pattern_match.group(1)

    if reply_to and reply_to.media:
        await download_and_send_media(event, reply_to, destination="me")
        return

    if args:
        parts = args.split()
        target = parts[0]
        count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        status = await event.reply(f"🔍 <code>{target}</code> chatidan oxirgi {count} ta video qidirilmoqda...", parse_mode="html")
        try:
            chat_entity = await client.get_entity(target)
            grabbed = 0
            async for msg in client.iter_messages(chat_entity, limit=30):
                if msg.media and (msg.video or (msg.document and msg.document.mime_type.startswith("video/"))):
                    await download_and_send_media(event, msg, destination="me")
                    grabbed += 1
                    if grabbed >= count:
                        break
            
            await status.edit(f"🎉 <b>Jami {grabbed} ta video muvaffaqiyatli olindi!</b>", parse_mode="html")
        except Exception as e:
            await status.edit(f"❌ Xatolik: {e}")
        return

    await event.reply(
        "💡 <b>Qanday ishlatiladi:</b>\n"
        "1. Himoyalangan videoga javob (reply) qilib: <code>/grab</code> deb yozing.\n"
        "2. Yoki bot usernamesi va sonini yozing: <code>/grab @bot_username 3</code>",
        parse_mode="html"
    )

if __name__ == "__main__":
    logger.info("Hikaku Telegram MTProto Grabber Userbot ishga tushmoqda...")
    client.start()
    client.run_until_disconnected()
