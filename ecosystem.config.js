module.exports = {
  apps: [
    {
      name: "hikaku-b2-uploader",
      cwd: "./b2-uploader-bot",
      script: "./b2-uploader-bot",
      env: {
        TELEGRAM_BOT_TOKEN: "8491783785:AAH02Aj6dckq1yk9NYtt1yJ7_TBibi_hrBE",
        B2_KEY_ID: "005562e6b2bafd40000000002",
        B2_APP_KEY: "K005qO8gFPWarHPO4nEZATyOvJcQ6o4",
        B2_BUCKET_NAME: "iskurama",
        B2_BUCKET_ID: "ce45d5be80bb5e9122ff0010",
        CDN_BASE_URL: "https://cdn.hikaku.uz"
      },
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "hikaku-video-compressor",
      cwd: "./video-compressor-bot",
      script: "python3",
      args: "bot.py",
      env: {
        COMPRESSOR_BOT_TOKEN: "8491783785:AAH02Aj6dckq1yk9NYtt1yJ7_TBibi_hrBE",
        TELEGRAM_API_ID: "33864339",
        TELEGRAM_API_HASH: "7a12002bdba42778b2068c88bb64072c"
      },
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "hikaku-userbot-grabber",
      cwd: "./telegram-grabber-userbot",
      script: "python3",
      args: "userbot.py",
      autorestart: true,
      max_restarts: 5
    }
  ]
};
