import asyncio
import logging
import os
import io
from flask import Flask
from threading import Thread
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import perchance
from PIL import Image

# --- 1. تنظیمات اولیه ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
TOKEN = os.getenv("BOT_TOKEN")

# --- 2. سیستم Keep Alive برای Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 3. توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ارسال پیام خوشامدگویی و راهنمایی نهایی."""
    await update.message.reply_text(
        "به ربات تولید عکس آزاد خوش آمدی! 🎨\n\n"
        "برای ساخت عکس، پیامت رو اینجوری بنویس:\n"
        "`موضوع عکس (به انگلیسی) | سبک عکس (به انگلیسی)`\n\n"
        "مثال:\n"
        "`a space cat on mars | anime, cinematic`\n\n"
        "🔥 نکته مهم: برای بهترین نتیجه، هم موضوع و هم سبک عکس رو به زبان انگلیسی بنویسید."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش پیام کاربر و تولید عکس."""
    user_message = update.message.text
    
    # جدا کردن موضوع و سبک با استفاده از کاراکتر |
    if '|' not in user_message:
        await update.message.reply_text(
            "لطفاً پیامت رو با فرمت درست بنویس.\n"
            "مثال: `a space cat on mars | anime, cinematic`"
        )
        return
        
    prompt, style = user_message.split('|', 1)
    prompt = prompt.strip()
    style = style.strip()
    
    if not prompt or not style:
        await update.message.reply_text(
            "هم موضوع و هم سبک عکس رو باید مشخص کنی.\n"
            "مثال: `a space cat on mars | anime, cinematic`"
        )
        return

    await handle_image_generation(update, prompt, style)

async def handle_image_generation(update: Update, prompt: str, style: str) -> None:
    """تولید و ارسال تصویر."""
    full_prompt = f"{prompt}, {style}"
    
    await update.message.reply_text("در حال تولید تصویر... ⏳")
    
    try:
        gen = perchance.ImageGenerator()
        async with await gen.image(full_prompt) as result:
            binary = await result.download()
            image = Image.open(binary)
            
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            await update.message.reply_photo(
                photo=InputFile(img_byte_arr, filename=f"{prompt[:20]}.png"),
                caption=f"تصویر «{prompt}» با سبک «{style}» تولید شد."
            )
            
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        await update.message.reply_text(
            "متأسفانه در تولید تصویر مشکلی پیش آمد. لطفاً کمی بعد دوباره تلاش کنید."
        )

def main() -> None:
    keep_alive()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
