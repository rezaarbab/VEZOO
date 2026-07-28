import os
import asyncio
import logging
import subprocess
import glob
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
DOWNLOAD_DIR = "/tmp/subtitles"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋\n\n"
        "دستورات:\n"
        "`Payback 9 sub` — فقط زیرنویس\n"
        "`Payback 9 video` — ویدیو\n"
        "`Payback 9 all` — هر دو\n\n"
        "یا لینک مستقیم KissKH بفرست!",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # اگه لینک مستقیم بود
    if text.startswith("https://kisskh"):
        await process_link(update, text, "sub")
        return
    
    # پارس دستور: "Payback 9 sub"
    parts = text.rsplit(" ", 1)
    mode = "sub"
    
    if len(parts) == 2 and parts[1].lower() in ["sub", "video", "all"]:
        query = parts[0]
        mode = parts[1].lower()
    else:
        query = text
    
    await update.message.reply_text(f"🔍 در حال جستجو برای: `{query}`...", parse_mode="Markdown")
    await process_search(update, query, mode)


async def process_search(update: Update, query: str, mode: str):
    """جستجو در KissKH و دانلود"""
    
    # بررسی اگه شماره قسمت داده شده
    parts = query.rsplit(" ", 1)
    episode_args = ""
    
    if len(parts) == 2 and parts[1].isdigit():
        drama_name = parts[0]
        ep_num = int(parts[1])
        episode_args = f"-f {ep_num} -l {ep_num}"
        search_query = drama_name
    else:
        search_query = query
        episode_args = ""
    
    await run_download(update, search_query, episode_args, mode)


async def process_link(update: Update, link: str, mode: str):
    """دانلود با لینک مستقیم"""
    await update.message.reply_text("⏳ در حال دانلود...")
    await run_download(update, link, "", mode)


async def run_download(update: Update, query: str, episode_args: str, mode: str):
    """اجرای kisskh downloader"""
    
    # تمیز کردن پوشه قبلی
    for f in glob.glob(f"{DOWNLOAD_DIR}/*"):
        os.remove(f)
    
    # ساخت دستور
    if mode == "sub":
        cmd = f'kisskh dl "{query}" {episode_args} -so -s all -o {DOWNLOAD_DIR}'
    elif mode == "video":
        cmd = f'kisskh dl "{query}" {episode_args} -q 720p -o {DOWNLOAD_DIR}'
    else:  # all
        cmd = f'kisskh dl "{query}" {episode_args} -s all -q 720p -o {DOWNLOAD_DIR}'
    
    await update.message.reply_text(f"⚙️ در حال پردازش...\n`{cmd}`", parse_mode="Markdown")
    
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        
        if process.returncode != 0:
            error = stderr.decode()
            await update.message.reply_text(f"❌ خطا:\n```{error[-500:]}```", parse_mode="Markdown")
            return
        
        # ارسال فایل‌ها
        files = glob.glob(f"{DOWNLOAD_DIR}/**/*", recursive=True)
        files = [f for f in files if os.path.isfile(f)]
        
        if not files:
            await update.message.reply_text("❌ فایلی پیدا نشد!")
            return
        
        await update.message.reply_text(f"✅ {len(files)} فایل آماده شد!")
        
        for file_path in files:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            if file_size > 50 * 1024 * 1024:  # بیشتر از 50MB
                await update.message.reply_text(f"⚠️ `{file_name}` خیلی بزرگه ({file_size//1024//1024}MB)", parse_mode="Markdown")
                continue
            
            with open(file_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=file_name,
                    caption=f"📄 {file_name}"
                )
    
    except asyncio.TimeoutError:
        await update.message.reply_text("⏰ timeout! خیلی طول کشید.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {str(e)}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
