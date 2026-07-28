import os
import asyncio
import logging
import glob
import requests
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


def search_kisskh(query: str):
    """جستجو در KissKH"""
    url = f"https://kisskh.nl/api/DramaList/Search?q={query}&type=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://kisskh.nl/",
    }
    try:
        r = requests.get(url, headers=headers, proxies=PROXIES, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋\n\n"
        "دستورات:\n"
        "/search payback — جستجوی سریال\n"
        "لینک مستقیم KissKH + شماره قسمت:\n"
        "`https://kisskh.do/Drama/Payback--UNCUT-/?id=12822 9 sub`\n\n"
        "mode ها: `sub` `video` `all`",
        parse_mode="Markdown"
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جستجوی سریال"""
    if not context.args:
        await update.message.reply_text("بنویس: /search اسم سریال")
        return
    
    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 در حال جستجو برای: `{query}`...", parse_mode="Markdown")
    
    results = search_kisskh(query)
    
    if not results:
        await update.message.reply_text("❌ نتیجه‌ای پیدا نشد! لینک مستقیم بفرست.")
        return
    
    # نمایش نتایج با دکمه
    keyboard = []
    for item in results[:8]:
        title = item.get("title", "Unknown")
        drama_id = item.get("id", "")
        btn_text = f"{title}"
        callback = f"select_{drama_id}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("نتایج:", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندل کردن دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("select_"):
        drama_id = data.replace("select_", "")
        # نمایش دکمه‌های انتخاب قسمت و mode
        keyboard = [
            [
                InlineKeyboardButton("زیرنویس همه قسمت‌ها", callback_data=f"dl_{drama_id}_all_sub"),
            ],
            [
                InlineKeyboardButton("قسمت ۱", callback_data=f"ep_{drama_id}_1"),
                InlineKeyboardButton("قسمت ۲", callback_data=f"ep_{drama_id}_2"),
                InlineKeyboardButton("قسمت ۳", callback_data=f"ep_{drama_id}_3"),
            ],
            [
                InlineKeyboardButton("قسمت ۴", callback_data=f"ep_{drama_id}_4"),
                InlineKeyboardButton("قسمت ۵", callback_data=f"ep_{drama_id}_5"),
                InlineKeyboardButton("قسمت ۶", callback_data=f"ep_{drama_id}_6"),
            ],
            [
                InlineKeyboardButton("قسمت ۷", callback_data=f"ep_{drama_id}_7"),
                InlineKeyboardButton("قسمت ۸", callback_data=f"ep_{drama_id}_8"),
                InlineKeyboardButton("قسمت ۹", callback_data=f"ep_{drama_id}_9"),
            ],
            [
                InlineKeyboardButton("قسمت ۱۰", callback_data=f"ep_{drama_id}_10"),
                InlineKeyboardButton("قسمت ۱۱", callback_data=f"ep_{drama_id}_11"),
                InlineKeyboardButton("قسمت ۱۲", callback_data=f"ep_{drama_id}_12"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("کدوم قسمت؟", reply_markup=reply_markup)
    
    elif data.startswith("ep_"):
        parts = data.split("_")
        drama_id = parts[1]
        ep_num = parts[2]
        
        keyboard = [
            [
                InlineKeyboardButton("زیرنویس", callback_data=f"dl_{drama_id}_{ep_num}_sub"),
                InlineKeyboardButton("ویدیو", callback_data=f"dl_{drama_id}_{ep_num}_video"),
                InlineKeyboardButton("هر دو", callback_data=f"dl_{drama_id}_{ep_num}_all"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"قسمت {ep_num} — چی می‌خوای؟", reply_markup=reply_markup)
    
    elif data.startswith("dl_"):
        parts = data.split("_")
        drama_id = parts[1]
        ep_num = parts[2]
        mode = parts[3]
        
        await query.edit_message_text(f"⏳ در حال دانلود قسمت {ep_num}...")
        
        if ep_num == "all":
            link = f"https://kisskh.do/Drama/?id={drama_id}"
            episode_args = ""
        else:
            link = f"https://kisskh.do/Drama/?id={drama_id}"
            episode_args = f"-f {ep_num} -l {ep_num}"
        
        await run_download(query, link, episode_args, mode)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # پارس mode
    parts = text.rsplit(" ", 1)
    mode = "sub"
    if len(parts) == 2 and parts[1].lower() in ["sub", "video", "all"]:
        query_text = parts[0].strip()
        mode = parts[1].lower()
    else:
        query_text = text
    
    # اگه لینک مستقیم بود
    if query_text.startswith("https://kisskh") or query_text.startswith("http://kisskh"):
        # بررسی شماره قسمت
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
        "برای جستجو بنویس:\n`/search اسم سریال`\n\n"
        "یا لینک مستقیم KissKH بفرست.",
        parse_mode="Markdown"
    )


async def run_download(msg, query: str, episode_args: str, mode: str):
    """اجرای kisskh downloader"""
    
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
