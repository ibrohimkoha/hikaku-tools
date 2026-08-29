# 🛠 Hikaku Tools (Private Ecosystem)

Ushbu repozitoriy **Hikaku Anime (`anime.hikaku.uz`)** infratuzilmasi uchun maxsus ishlab chiqilgan yopiq (Private) vositalar to'plamini o'z ichiga oladi.

---

## 📦 Modullar:

### 1. ⚡ `b2-uploader-bot` (Golang)
- **Vazifasi:** Telegram orqali yuborilgan video/fayllarni to'g'ridan-to'g'ri Backblaze B2 bulutiga yuklaydi va `https://cdn.hikaku.uz/...` havolasini beradi.
- **O'chirish:** `/del <url_yoki_nom>` buyrug'i yoki xabar ostidagi `[🗑 B2 dan O'chirish]` tugmasi orqali B2 dan darhol o'chiradi.
- **Xotira:** Zero-VPS disk storage (VPS diskida joy band qilmaydi).

### 2. 🗜️ `video-compressor-bot` (Python + FFmpeg)
- **Vazifasi:** Video sifatini yo'qotmagan holda (H.264 CRF-23 + AAC 128k + Web Faststart) 50% - 80% gacha siqib beradi.
- **Qulaylik:** Siqilgan video to'g'ridan-to'g'ri brauzerda qotmasdan tez ochiladigan qilib tayyorlanadi.

### 3. 🤖 `telegram-grabber-userbot` (Python Telethon MTProto)
- **Vazifasi:** Telegramda forward / saqlash taqiqlangan (Restricted) botlar va yopiq kanallardan videolarni sug'urib oladi.
- **Foydalanish:**
  - Himoyalangan videoga javob (reply) qilib: `/grab`
  - Yoki bot username va soni bilan: `/grab @target_bot 5`

---

## 🚀 Ishga tushirish (PM2 orqali):

```bash
# 1. B2 Uploader botni kompilyatsiya qilish
cd b2-uploader-bot && go build -o b2-uploader-bot main.go && cd ..

# 2. Python kutubxonalarini o'rnatish
pip install -r video-compressor-bot/requirements.txt
pip install -r telegram-grabber-userbot/requirements.txt

# 3. PM2 orqali hammasini fon rejimida yoqish
pm2 start ecosystem.config.js
pm2 save
```
