import os
import sys
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, DocumentAttributeVideo, DocumentAttributeFilename
import time
import hashlib
import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("HikakuGrabber")

API_ID = int(os.getenv("TELEGRAM_API_ID", "33864339"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "7a12002bdba42778b2068c88bb64072c")
SESSION_NAME = os.getenv("TELEGRAM_SESSION", "hikaku_userbot_session")

TEMP_DIR = "/tmp/hikaku_grabber"
os.makedirs(TEMP_DIR, exist_ok=True)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def download_and_send_media(event, message, destination="me"):
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

b2_auth_token = None
b2_api_url = None
b2_auth_exp = 0

B2_KEY_ID = os.getenv("B2_KEY_ID", "005562e6b2bafd40000000002")
B2_APP_KEY = os.getenv("B2_APP_KEY", "K005qO8gFPWarHPO4nEZATyOvJcQ6o4")
B2_BUCKET_ID = os.getenv("B2_BUCKET_ID", "ce45d5be80bb5e9122ff0010")
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://cdn.hikaku.uz")

async def get_b2_auth():
    global b2_auth_token, b2_api_url, b2_auth_exp
    if b2_auth_token and time.time() < b2_auth_exp:
        return b2_auth_token, b2_api_url

    auth = aiohttp.BasicAuth(B2_KEY_ID, B2_APP_KEY)
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.backblazeb2.com/b2api/v2/b2_authorize_account", auth=auth) as resp:
            data = await resp.json()
            b2_auth_token = data["authorizationToken"]
            b2_api_url = data["apiUrl"]
            b2_auth_exp = time.time() + 82800
            return b2_auth_token, b2_api_url

async def upload_file_to_b2(file_path: str, b2_file_name: str, content_type: str = "video/mp4") -> bool:
    token, api_url = await get_b2_auth()
    headers = {"Authorization": token}
    payload = {"bucketId": B2_BUCKET_ID}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{api_url}/b2api/v2/b2_get_upload_url", json=payload, headers=headers) as resp:
            up_info = await resp.json()
            upload_url = up_info["uploadUrl"]
            upload_token = up_info["authorizationToken"]

    sha1_hash = hashlib.sha1()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha1_hash.update(chunk)
    sha1_hex = sha1_hash.hexdigest()

    file_size = os.path.getsize(file_path)
    up_headers = {
        "Authorization": upload_token,
        "X-Bz-File-Name": b2_file_name,
        "Content-Type": content_type,
        "Content-Length": str(file_size),
        "X-Bz-Content-Sha1": sha1_hex
    }

    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            async with session.post(upload_url, data=f, headers=up_headers) as resp:
                return resp.status == 200

async def delete_file_from_b2(b2_file_name: str) -> int:
    token, api_url = await get_b2_auth()
    headers = {"Authorization": token}
    payload = {
        "bucketId": B2_BUCKET_ID,
        "startFileName": b2_file_name,
        "prefix": b2_file_name,
        "maxFileCount": 10
    }
    deleted = 0
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{api_url}/b2api/v2/b2_list_file_versions", json=payload, headers=headers) as resp:
            data = await resp.json()
            files = data.get("files", [])
            for f in files:
                if f["fileName"] == b2_file_name:
                    del_payload = {"fileId": f["fileId"], "fileName": f["fileName"]}
                    async with session.post(f"{api_url}/b2api/v2/b2_delete_file_version", json=del_payload, headers=headers) as del_resp:
                        if del_resp.status == 200:
                            deleted += 1
    return deleted

@client.on(events.NewMessage(pattern=r"^/(?:del|remove|delete)(?:\s+(.*))?$", outgoing=True))
async def handle_delete_b2(event):
    args = event.pattern_match.group(1)
    if not args:
        await event.reply("❌ Iltimos, o'chirilishi kerak bo'lgan havolani yozing:\nMisol: <code>/del https://cdn.hikaku.uz/videos/anime_123.mp4</code>", parse_mode="html")
        return

    target = args.strip()
    clean_name = target.replace(CDN_BASE_URL, "").lstrip("/")

    status = await event.reply(f"⏳ <b>Backblaze B2 dan o'chirilmoqda:</b> <code>{clean_name}</code>...", parse_mode="html")
    count = await delete_file_from_b2(clean_name)
    if count == 0:
        await status.edit(f"⚠️ <code>{clean_name}</code> fayli B2 omboridan topilmadi yoki allaqachon o'chirilgan.", parse_mode="html")
    else:
        await status.edit(f"✅ <b>Backblaze B2 omboridan butunlay o'chirildi!</b>\n\n📁 Fayl: <code>{clean_name}</code>\n🗑 O'chirilgan versiyalar soni: <b>{count} ta</b>", parse_mode="html")

@client.on(events.NewMessage(pattern=r"^/(?:upload|b2)(?:\s+(.*))?$", outgoing=True))
async def handle_upload_direct(event):
    reply_to = await event.get_reply_message()
    if not (reply_to and reply_to.media):
        await event.reply("❌ Iltimos, B2 ga yuklamoqchi bo'lgan videoga javob (reply) qilib <code>/upload</code> deb yozing!", parse_mode="html")
        return

    status = await event.reply("⏳ <b>1/2: Telegramdan video serverga yuklab olinmoqda...</b>", parse_mode="html")
    
    file_name = "anime_video.mp4"
    if isinstance(reply_to.media, MessageMediaDocument):
        for attr in reply_to.media.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_name = attr.file_name

    clean_base = os.path.splitext(file_name)[0].replace(" ", "_")
    ext = os.path.splitext(file_name)[1] or ".mp4"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    b2_name = f"videos/{clean_base}_{timestamp}{ext}"
    local_path = os.path.join(TEMP_DIR, f"{clean_base}_{timestamp}{ext}")

    try:
        start_t = time.time()
        await client.download_media(reply_to, file=local_path)
        
        await status.edit("☁️ <b>2/2: Backblaze B2 bulut omboriga yuklanmoqda...</b>", parse_mode="html")
        success = await upload_file_to_b2(local_path, b2_name)
        elapsed = round(time.time() - start_t, 1)

        if not success:
            await status.edit("❌ Backblaze B2 ga yuklashda xatolik yuz berdi!", parse_mode="html")
            return

        cdn_url = f"{CDN_BASE_URL}/{b2_name}"
        file_size_mb = round(os.path.getsize(local_path) / (1024 * 1024), 2)

        caption = (
            f"✅ <b>Backblaze B2 ga to'g'ridan-to'g'ri yuklandi!</b>\n\n"
            f"🔗 <b>CDN Havolasi:</b>\n<code>{cdn_url}</code>\n\n"
            f"📦 Hajmi: <b>{file_size_mb} MB</b>\n"
            f"⚡️ Ketgan vaqt: <b>{elapsed}s</b>\n\n"
            f"💡 <i>Admin panelga yoki pleerga shu havolani nusxalab qo'yishingiz mumkin!</i>"
        )
        await status.edit(caption, parse_mode="html")

    except Exception as e:
        logger.error(f"Error direct uploading: {e}")
        await status.edit(f"❌ Xatolik: {e}", parse_mode="html")
    finally:
        if os.path.exists(local_path):
            try: os.remove(local_path)
            except: pass

@client.on(events.NewMessage(pattern=r"^/grab(?:\s+(.*))?$", outgoing=True))
async def handle_grab(event):
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
        "1. Himoyalangan videoga javob (reply) qilib: <code>/grab</code> (Saved Messagesga saqlash)\n"
        "2. To'g'ridan-to'g'ri B2 ga yuklash uchun reply qilib: <code>/upload</code>\n"
        "3. B2 dan link orqali o'chirish uchun: <code>/del &lt;cdn_havolasi&gt;</code>",
        parse_mode="html"
    )

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        logger.error("❌ Userbot sessiyasi avtorizatsiyadan o'tmagan!")
        return
    me = await client.get_me()
    logger.info(f"🚀 Hikaku MTProto Userbot ishga tushdi: {me.first_name} (@{me.username} - ID: {me.id})")
    await client.run_until_disconnected()

if __name__ == "__main__":
    logger.info("Hikaku Telegram MTProto Grabber Userbot ulanmoqda...")
    client.loop.run_until_complete(main())
