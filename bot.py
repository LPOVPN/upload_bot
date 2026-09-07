"""
ربات آپلودر با لینک اختصاصی + پنل ادمین + جوین اجباری
اجرا: python bot.py
پیش‌نیاز: config.py رو پر کرده باشی
"""

import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


# ---------------------------------------------------------------------------
# /start  -  هم برای کاربر عادی (با کد لینک) هم بدون کد
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if not args:
        if is_admin(user.id):
            await update.message.reply_text(
                "سلام ادمین 👋\nبرای مدیریت ربات از /panel استفاده کن."
            )
        else:
            await update.message.reply_text(
                "سلام 👋 برای دریافت فایل باید از یه لینک مخصوص وارد بشی."
            )
        return

    code = args[0]
    context.user_data["pending_code"] = code
    await deliver_or_ask_join(update, context, code)


async def deliver_or_ask_join(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    user_id = update.effective_user.id
    chat = update.effective_chat

    not_joined = await get_unjoined_channels(context, user_id)

    if not_joined:
        buttons = []
        for ch in not_joined:
            link = ch["invite_link"] or f"https://t.me/{ch['channel_id'].lstrip('@')}"
            buttons.append([InlineKeyboardButton(f"عضویت در {ch['title']}", url=link)])
        buttons.append([InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data=f"check:{code}")])
        await chat.send_message(
            "برای دریافت فایل، اول باید عضو کانال(های) زیر بشی:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await send_file_to_user(context, chat.id, code)


async def get_unjoined_channels(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    channels = db.list_force_channels()
    not_joined = []
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
        except TelegramError:
            # اگه ربات نتونه چک کنه (مثلاً ادمین نیست) به‌عنوان احتیاط، الزامی درنظر می‌گیریم
            not_joined.append(ch)
    return not_joined


async def send_file_to_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, code: str):
    file_row = db.get_file(code)
    if not file_row:
        await context.bot.send_message(chat_id, "این لینک معتبر نیست یا فایل حذف شده.")
        return
    try:
        await context.bot.copy_message(
            chat_id=chat_id,
            from_chat_id=config.STORAGE_CHANNEL_ID,
            message_id=file_row["storage_message_id"],
        )
    except TelegramError as e:
        logger.error(f"خطا در ارسال فایل: {e}")
        await context.bot.send_message(chat_id, "خطا در ارسال فایل، بعداً دوباره امتحان کن.")


async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]

    not_joined = await get_unjoined_channels(context, query.from_user.id)
    if not_joined:
        await query.answer("هنوز عضو همه کانال‌ها نشدی!", show_alert=True)
        return

    await query.edit_message_text("✅ عضویت تایید شد، فایل رو می‌فرستم...")
    await send_file_to_user(context, query.message.chat_id, code)


# ---------------------------------------------------------------------------
# پنل ادمین
# ---------------------------------------------------------------------------

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 آپلود فایل جدید", callback_data="admin:upload")],
        [InlineKeyboardButton("📁 لیست فایل‌ها / حذف", callback_data="admin:files:0")],
        [InlineKeyboardButton("🔒 مدیریت جوین اجباری", callback_data="admin:channels")],
    ])


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    context.user_data.clear()
    await update.message.reply_text("پنل مدیریت ربات:", reply_markup=admin_menu_keyboard())


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("دسترسی نداری.", show_alert=True)
        return
    await query.answer()
    data = query.data

    if data == "admin:upload":
        context.user_data["awaiting"] = "upload_file"
        await query.edit_message_text(
            "فیلم یا فایل موردنظر رو الان برام بفرست.\n"
            "می‌تونی توضیح (کپشن) هم براش بذاری."
        )

    elif data.startswith("admin:files:"):
        offset = int(data.split(":")[2])
        await show_files_page(query, offset)

    elif data.startswith("admin:delete:"):
        code = data.split(":", 2)[2]
        db.delete_file(code)
        await query.edit_message_text(f"فایل با کد {code} حذف شد. ✅")

    elif data == "admin:channels":
        await show_channels_menu(query)

    elif data == "admin:channels:add":
        context.user_data["awaiting"] = "add_channel"
        await query.edit_message_text(
            "یه پیام از کانال موردنظر رو برام فوروارد کن\n"
            "(یادت نره ربات باید توی اون کانال ادمین باشه)."
        )

    elif data.startswith("admin:channels:remove:"):
        channel_id = data.split(":", 3)[3]
        db.remove_force_channel(channel_id)
        await show_channels_menu(query, edit=True)

    elif data == "admin:back":
        await query.edit_message_text("پنل مدیریت ربات:", reply_markup=admin_menu_keyboard())


async def show_files_page(query, offset: int):
    files = db.list_files(limit=10, offset=offset)
    total = db.count_files()

    if not files:
        await query.edit_message_text(
            "هنوز فایلی آپلود نشده.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ برگشت", callback_data="admin:back")]]),
        )
        return

    buttons = []
    for f in files:
        label = f["file_name"] or f["code"]
        buttons.append([
            InlineKeyboardButton(f"🗑 {label[:25]}", callback_data=f"admin:delete:{f['code']}")
        ])

    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin:files:{max(0, offset - 10)}"))
    if offset + 10 < total:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"admin:files:{offset + 10}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("⬅️ برگشت به منو", callback_data="admin:back")])

    await query.edit_message_text(
        f"لیست فایل‌ها ({total} فایل) - برای حذف روی فایل بزن:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_channels_menu(query, edit: bool = False):
    channels = db.list_force_channels()
    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(
                f"❌ حذف {ch['title']}", callback_data=f"admin:channels:remove:{ch['channel_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("➕ افزودن کانال", callback_data="admin:channels:add")])
    buttons.append([InlineKeyboardButton("⬅️ برگشت", callback_data="admin:back")])

    text = "کانال‌های جوین اجباری فعلی:" if channels else "هنوز کانالی برای جوین اجباری تنظیم نشده."
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ---------------------------------------------------------------------------
# دریافت پیام‌های ادمین (آپلود فایل / افزودن کانال با فوروارد)
# ---------------------------------------------------------------------------

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    awaiting = context.user_data.get("awaiting")
    msg = update.message

    if awaiting == "upload_file":
        if not (msg.video or msg.document or msg.photo or msg.audio):
            await msg.reply_text("این پیام فایل/فیلم نیست. یه فایل بفرست.")
            return

        sent = await context.bot.copy_message(
            chat_id=config.STORAGE_CHANNEL_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
        )

        file_name = None
        if msg.video:
            file_name = msg.video.file_name or "video"
        elif msg.document:
            file_name = msg.document.file_name
        elif msg.audio:
            file_name = msg.audio.file_name or "audio"
        else:
            file_name = "photo"

        code = db.add_file(sent.message_id, msg.caption or "", file_name)
        link = f"https://t.me/{config.BOT_USERNAME}?start={code}"

        context.user_data["awaiting"] = None
        await msg.reply_text(
            f"فایل ذخیره شد ✅\nلینک اختصاصی:\n{link}",
            reply_markup=admin_menu_keyboard(),
        )

    elif awaiting == "add_channel":
        if not msg.forward_from_chat:
            await msg.reply_text("باید یه پیام رو از کانال موردنظر فوروارد کنی.")
            return

        chat = msg.forward_from_chat
        channel_id = f"@{chat.username}" if chat.username else str(chat.id)

        try:
            invite_link = await context.bot.export_chat_invite_link(chat.id)
        except TelegramError:
            invite_link = ""

        db.add_force_channel(channel_id, chat.title or channel_id, invite_link)
        context.user_data["awaiting"] = None
        await msg.reply_text(
            f"کانال «{chat.title}» به لیست جوین اجباری اضافه شد ✅",
            reply_markup=admin_menu_keyboard(),
        )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    db.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern=r"^check:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, admin_message_handler))

    logger.info("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
