import os
import asyncio
import logging
import glob
import requests
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
PROXY = os.environ.get("PROXY", "")
DOWNLOAD_DIR = "/tmp/subtitles"

if PROXY:
    os.environ["HTTP_PROXY"] = PROXY
    os.environ["HTTPS_PROXY"] = PROXY
    os.environ["ALL_PROXY"] = PROXY
    os.environ["http_proxy"] = PROXY
    os.environ["https_proxy"] = PROXY

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
PROXIES = {"http": PROXY, "https": PROXY} if PROXY else {}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://kisskh.nl/",
}


def to_int(val):
    try:
        f = float(str(val))
        return int(f) if f == int(f) else str(val)
    except:
        return str(val)


def search_kisskh(query):
    url = f"https://kisskh.nl/api/DramaList/Search?q={query}&type=0"
    try:
        r = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


def get_drama_detail(drama_id):
    url = f"https://kisskh.nl/api/DramaList/Drama/{drama_id}?isq=true"
    try:
        r = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Drama detail error: {e}")
        return None


def download_image(url):
    try:
        r = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=15)
        if r.status_code == 200:
            return BytesIO(r.content)
    except Exception as e:
        logger.error(f"Image download error: {e}")
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋\n\n"
        "برای جستجو:\n"
        "`/search Payback`\n\n"
        "یا لینک مستقیم:\n"
        "`https://kisskh.do/Drama/Payback--UNCUT-/?id=12822 9 sub`",
        parse_mode="Markdown"
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("بنویس: /search اسم سریال")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 جستجو برای: `{query}`...", parse_mode="Markdown")
    results = search_kisskh(query)

    if not results:
        await msg.edit_text("❌ نتیجه‌ای پیدا نشد!")
        return

    keyboard = []
    for item in results[:8]:
        title = item.get("title", "Unknown")
        drama_id = item.get("id", "")
        ep_count = item.get("episodesCount", "?")
        keyboard.append([InlineKeyboardButton(f"🎬 {title} ({ep_count} ep)", callback_data=f"select_{drama_id}")])

    await msg.edit_text("نتایج جستجو:", reply_markup=InlineKeyboardMarkup(keyboard))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("select_"):
        drama_id = data.replace("select_", "")
        await query.edit_message_text("⏳ در حال دریافت اطلاعات...")

        detail = get_drama_detail(drama_id)
        if not detail:
            await query.edit_message_text("❌ خطا در دریافت اطلاعات!")
            return

        title = detail.get("title", "Unknown")
        episodes = detail.get("episodes", [])
        thumbnail = detail.get("thumbnail", "")

        # ارسال عکس — دانلود مستقیم
        if thumbnail:
            img_data = download_image(thumbnail)
            if img_data:
                try:
                    await query.message.reply_photo(
                        photo=img_data,
                        caption=f"🎬 *{title}*\n📺 {len(episodes)} قسمت",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Photo send error: {e}")

        if not episodes:
            await query.edit_message_text(f"❌ قسمتی برای {title} پیدا نشد!")
            return

        # ساخت دکمه‌ها
        keyboard = []
        row = []
        for ep in episodes:
            ep_num = to_int(ep.get("number", "?"))
            ep_id = ep.get("id", "")
            # استفاده از sub field داخل episodes
            sub_available = ep.get("sub", 0) or ep.get("subCount", 0)
            icon = "✅" if sub_available else "⏳"
            row.append(InlineKeyboardButton(f"{icon}{ep_num}", callback_data=f"ep_{drama_id}_{ep_id}_{ep_num}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("📥 زیرنویس همه قسمت‌ها", callback_data=f"dlall_{drama_id}")])

        await query.edit_message_text(
            f"🎬 *{title}*\n✅ = زیرنویس دارد | ⏳ = هنوز نیامده\n\nقسمت رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("ep_"):
        parts = data.split("_")
        drama_id = parts[1]
        ep_id = parts[2]
        ep_num = parts[3]

        keyboard = [[
            InlineKeyboardButton("📄 زیرنویس", callback_data=f"dl_{drama_id}_{ep_id}_{ep_num}_sub"),
            InlineKeyboardButton("🎬 ویدیو", callback_data=f"dl_{drama_id}_{ep_id}_{ep_num}_video"),
            InlineKeyboardButton("📦 هر دو", callback_data=f"dl_{drama_id}_{ep_id}_{ep_num}_all"),
        ]]
        await query.edit_message_text(
            f"قسمت {ep_num} — چی می‌خوای؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("dlall_"):
        drama_id = data.replace("dlall_", "")
        await query.edit_message_text("⏳ در حال دانلود همه زیرنویس‌ها...")
        link = f"https://kisskh.do/Drama/?id={drama_id}"
        await run_download(query.message, link, "", "sub")

    elif data.startswith("dl_"):
        parts = data.split("_")
        drama_id = parts[1]
        ep_id = parts[2]
        ep_num = parts[3]
        mode = parts[4]

        await query.edit_message_text(f"⏳ در حال دانلود قسمت {ep_num}...")
        ep_int = to_int(ep_num)
        link = f"https://kisskh.do/Drama/?id={drama_id}"
        episode_args = f"-f {ep_int} -l {ep_int}"
        await run_download(query.message, link, episode_args, mode)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    parts = text.rsplit(" ", 1)
    mode = "sub"
    if len(parts) == 2 and parts[1].lower() in ["sub", "video", "all"]:
        query_text = parts[0].strip()
        mode = parts[1].lower()
    else:
        query_text = text

    if query_text.startswith("https://kisskh") or query_text.startswith("http://kisskh"):
        link_parts = query_text.rsplit(" ", 1)
        episode_args = ""
        link = query_text

        if len(link_parts) == 2 and link_parts[1].isdigit():
            link = link_parts[0].strip()
            ep_num = link_parts[1]
            episode_args = f"-f {ep_num} -l {ep_num}"

        await update.message.reply_text("⏳ در حال دانلود...")
        await run_download(update.message, link, episode_args, mode)
        return

    await update.message.reply_text(
        "برای جستجو بنویس:\n`/search اسم سریال`",
        parse_mode="Markdown"
    )


async def run_download(msg, query, episode_args, mode):
    for f in glob.glob(f"{DOWNLOAD_DIR}/**/*", recursive=True):
        if os.path.isfile(f):
            os.remove(f)

    if mode == "sub":
        cmd = f'kisskh dl "{query}" {episode_args} -so -s all -o {DOWNLOAD_DIR}'
    elif mode == "video":
        cmd = f'kisskh dl "{query}" {episode_args} -q 720p -o {DOWNLOAD_DIR}'
    else:
        cmd = f'kisskh dl "{query}" {episode_args} -s all -q 720p -o {DOWNLOAD_DIR}'

    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

        if process.returncode != 0:
            error = stderr.decode()
            await msg.reply_text(f"❌ خطا:\n```{error[-500:]}```", parse_mode="Markdown")
            return

        files = glob.glob(f"{DOWNLOAD_DIR}/**/*", recursive=True)
        files = [f for f in files if os.path.isfile(f)]

        if not files:
            await msg.reply_text("❌ فایلی پیدا نشد!")
            return

        await msg.reply_text(f"✅ {len(files)} فایل آماده شد!")

        for file_path in files:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)

            if file_size > 50 * 1024 * 1024:
                await msg.reply_text(f"⚠️ `{file_name}` خیلی بزرگه ({file_size//1024//1024}MB)", parse_mode="Markdown")
                continue

            with open(file_path, "rb") as f:
                await msg.reply_document(document=f, filename=file_name, caption=f"📄 {file_name}")

    except asyncio.TimeoutError:
        await msg.reply_text("⏰ timeout! خیلی طول کشید.")
    except Exception as e:
        await msg.reply_text(f"❌ خطا: {str(e)}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
