module.exports = {
  apps: [
    {
      name: "hikaku-b2-uploader",
      cwd: "./b2-uploader-bot",
      script: "python3",
      args: "bot.py",
      env: {
        TELEGRAM_BOT_TOKEN: "8950963003:AAEMACsSbEz8WXj5TD3n6VNflPhtcoWg3G8",
        TELEGRAM_API_ID: "33864339",
        TELEGRAM_API_HASH: "7a12002bdba42778b2068c88bb64072c",
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
        COMPRESSOR_BOT_TOKEN: "8815124197:AAE6zG_54LOh5ja-DxlrGFF8-2cQplEQ5fA",
        TELEGRAM_API_ID: "33864339",
        TELEGRAM_API_HASH: "7a12002bdba42778b2068c88bb64072c"
      },
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "hikaku-userbot-grabber-1",
      cwd: "./telegram-grabber-userbot",
      script: "python3",
      args: "userbot.py",
      env: {
        TELEGRAM_API_ID: "33864339",
        TELEGRAM_API_HASH: "7a12002bdba42778b2068c88bb64072c",
        TELEGRAM_SESSION: "hikaku_userbot_session"
      },
      autorestart: true,
      max_restarts: 10
    },
    {
      name: "hikaku-userbot-grabber-2",
      cwd: "./telegram-grabber-userbot",
      script: "python3",
      args: "userbot.py",
      env: {
        TELEGRAM_API_ID: "33864339",
        TELEGRAM_API_HASH: "7a12002bdba42778b2068c88bb64072c",
        TELEGRAM_SESSION: "userbot_2"
      },
      autorestart: true,
      max_restarts: 10
    }
  ]
};
