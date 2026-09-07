"""
تنظیمات ربات - این مقادیر رو حتماً قبل از اجرا پر کن
"""

import os

# توکن ربات که از @BotFather گرفتی
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

# آیدی عددی خودت (ادمین) - از @userinfobot بگیر
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# آیدی عددی کانال خصوصی که فایل‌ها توش ذخیره میشن (ربات باید توش ادمین باشه)
# فرمتش معمولاً یه عدد منفی طولانیه، مثل: -1001234567890
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", "0"))

# نام فایل دیتابیس SQLite
DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")

# یوزرنیم ربات بدون @ (برای ساخت لینک) - مثلاً "MyUploaderBot"
BOT_USERNAME = os.getenv("BOT_USERNAME", "PUT_YOUR_BOT_USERNAME_HERE")
