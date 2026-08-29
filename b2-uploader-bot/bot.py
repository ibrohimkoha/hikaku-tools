import os
import time
import asyncio
import hashlib
import aiohttp
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("B2UploaderBot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8950963003:AAEMACsSbEz8WXj5TD3n6VNflPhtcoWg3G8")
API_ID = int(os.getenv("TELEGRAM_API_ID", "33864339"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "7a12002bdba42778b2068c88bb64072c")
ADMIN_IDS = [5415350162, 6149114216]

B2_KEY_ID = os.getenv("B2_KEY_ID", "005562e6b2bafd40000000002")
B2_APP_KEY = os.getenv("B2_APP_KEY", "K005qO8gFPWarHPO4nEZATyOvJcQ6o4")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "iskurama")
B2_BUCKET_ID = os.getenv("B2_BUCKET_ID", "ce45d5be80bb5e9122ff0010")
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://cdn.hikaku.uz")

TEMP_DIR = "/tmp/hikaku_b2_upload"
os.makedirs(TEMP_DIR, exist_ok=True)

app = Client("hikaku_b2_uploader_pyro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

b2_auth_token = None
b2_api_url = None
b2_auth_exp = 0

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

async def get_b2_upload_url():
    token, api_url = await get_b2_auth()
    headers = {"Authorization": token}
    payload = {"bucketId": B2_BUCKET_ID}
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{api_url}/b2api/v2/b2_get_upload_url", json=payload, headers=headers) as resp:
            return await resp.json()

async def upload_file_to_b2(file_path: str, b2_file_name: str, content_type: str = "video/mp4") -> bool:
    up_info = await get_b2_upload_url()
    upload_url = up_info["uploadUrl"]
    upload_token = up_info["authorizationToken"]

    sha1_hash = hashlib.sha1()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha1_hash.update(chunk)
    sha1_hex = sha1_hash.hexdigest()

    file_size = os.path.getsize(file_path)
    headers = {
        "Authorization": upload_token,
        "X-Bz-File-Name": b2_file_name,
        "Content-Type": content_type,
        "Content-Length": str(file_size),
        "X-Bz-Content-Sha1": sha1_hex
    }

    async with aiohttp.ClientSession() as session:
        with open(file_path, "rb") as f:
            async with session.post(upload_url, data=f, headers=headers) as resp:
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

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔️ Ushbu bot faqat Hikaku administratorlari uchun!")
        return

    text = (
        "⚡️ <b>Hikaku Backblaze B2 Direct Uploader (MTProto 2GB)</b>\n\n"
        "Menga istalgan <b>Video (2 GB gacha)</b> yoki <b>Hujjat</b> yuboring.\n"
        "Men uni to'g'ridan-to'g'ri Backblaze B2 bulutiga yuklab, <code>https://cdn.hikaku.uz/...</code> havolasini beraman!\n\n"
        "🗑 <b>O'chirish uchun:</b>\n"
        "• <code>/del &lt;cdn_havolasi_yoki_fayl_nomi&gt;</code>\n"
        "• Yoki xabar ostidagi [🗑 B2 dan O'chirish] tugmasini bosing."
    )
    await message.reply_text(text)

@app.on_message(filters.command("del"))
async def del_cmd(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("❌ Iltimos o'chirilishi kerak bo'lgan CDN havolasini yoki fayl nomini yozing:\nMisol: <code>/del https://cdn.hikaku.uz/videos/anime_123.mp4</code>")
        return

    target = args[1].strip()
    clean_name = target.replace(CDN_BASE_URL, "").lstrip("/")

    status = await message.reply_text("⏳ Backblaze B2 omboridan o'chirilmoqda...")
    count = await delete_file_from_b2(clean_name)
    if count == 0:
        await status.edit_text(f"⚠️ <code>{clean_name}</code> fayli B2 omboridan topilmadi yoki allaqachon o'chirilgan.")
    else:
        await status.edit_text(f"✅ <b>Muvaffaqiyatli o'chirildi!</b>\n\n📁 Fayl: <code>{clean_name}</code>\n🗑 O'chirilgan nusxalar soni: {count}")

@app.on_callback_query(filters.regex(r"^delb2_(.+)"))
async def callback_del(client: Client, callback_query):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔️ Ruxsat yo'q!", show_alert=True)
        return

    file_name = callback_query.matches[0].group(1)
    await callback_query.answer("⏳ B2 dan o'chirilmoqda...")
    count = await delete_file_from_b2(file_name)
    await callback_query.message.edit_text(
        f"🗑 <b>Fayl Backblaze B2 dan butunlay o'chirildi!</b>\n\n📁 Fayl: <code>{file_name}</code>\nSoni: {count} ta versiya"
    )

@app.on_message(filters.video | filters.document)
async def handle_media(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔️ Ruxsat yo'q!")
        return

    media = message.video or message.document
    orig_name = media.file_name or f"video_{int(time.time())}.mp4"
    orig_size = media.file_size or 0

    status_msg = await message.reply_text(
        f"⏳ <b>Telegramdan yuklab olinmoqda (MTProto 2GB)...</b>\n📁 <code>{orig_name}</code> ({human_size(orig_size)})"
    )

    clean_base = os.path.splitext(orig_name)[0].replace(" ", "_")
    ext = os.path.splitext(orig_name)[1] or ".mp4"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    b2_name = f"videos/{clean_base}_{timestamp}{ext}"

    local_path = os.path.join(TEMP_DIR, f"{clean_base}_{timestamp}{ext}")

    try:
        start_t = time.time()
        last_edit = [0]

        async def progress(current, total):
            if time.time() - last_edit[0] > 4:
                last_edit[0] = time.time()
                pct = round((current / total) * 100, 1) if total > 0 else 0
                try:
                    await status_msg.edit_text(f"⏳ <b>Telegramdan yuklab olinmoqda: {pct}%</b>\n({human_size(current)} / {human_size(total)})")
                except:
                    pass

        await message.download(file_name=local_path, progress=progress)

        await status_msg.edit_text("☁️ <b>Backblaze B2 bulutiga to'g'ridan-to'g'ri uzatilmoqda...</b>")
        success = await upload_file_to_b2(local_path, b2_name, content_type=media.mime_type or "video/mp4")
        elapsed = round(time.time() - start_t, 1)

        if not success:
            await status_msg.edit_text("❌ Backblaze B2 ga yuklashda xatolik yuz berdi!")
            return

        cdn_url = f"{CDN_BASE_URL}/{b2_name}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 B2 dan O'chirish", callback_data=f"delb2_{b2_name}")]
        ])

        caption = (
            f"✅ <b>Backblaze B2 ga muvaffaqiyatli yuklandi!</b>\n\n"
            f"🔗 <b>To'g'ridan-to'g'ri CDN Havolasi:</b>\n<code>{cdn_url}</code>\n\n"
            f"📦 Hajmi: <b>{human_size(orig_size)}</b>\n"
            f"⚡️ Ketgan vaqt: <b>{elapsed}s</b>\n\n"
            f"💡 <i>Admin panelga yoki pleerga shu havolani nusxalab qo'yishingiz mumkin!</i>"
        )
        await status_msg.edit_text(caption, reply_markup=kb)

    except Exception as e:
        logger.error(f"Error handling upload: {e}")
        await status_msg.edit_text(f"❌ Xatolik: {e}")
    finally:
        if os.path.exists(local_path):
            try: os.remove(local_path)
            except: pass

if __name__ == "__main__":
    logger.info("Starting Hikaku MTProto B2 Uploader Bot...")
    app.run()
