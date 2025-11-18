import asyncio
import logging
import os
import io
from flask import Flask, request
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import perchance
from PIL import Image

# --- 1. تنظیمات اولیه ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get('PORT', 8080))

# --- 2. ساخت اپلیکیشن Flask برای Keep Alive و Webhook ---
app = Flask(__name__)

@app.route('/')
def home():
    """برای اینکه Render فکر کنه سرویس زنده است."""
    return "Bot is alive!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """این مسیر پیام‌ها رو از تلگرام دریافت می‌کنه."""
    application = Application.builder().token(TOKEN).build()
    update = Update.de_json(request.get_json(force=True), application.bot)
    # اینجا باید منطق پردازش پیام رو فراخوانی کنیم
    # اما روش بهتر، استفاده از قابلیت داخلی کتابخانه است
    # پس این تابع رو خالی میذاریم و کتابخانه کار رو انجام میده
    return "ok"


# --- 3. توابع اصلی ربات (بدون تغییر) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "به ربات تولید عکس آزاد خوش آمدی! 🎨\n\n"
        "برای ساخت عکس، پیامت رو اینجوری بنویس:\n"
        "`موضوع عکس (به انگلیسی) | سبک عکس (به انگلیسی)`\n\n"
        "مثال:\n"
        "`a space cat on mars | anime, cinematic`\n\n"
        "🔥 نکته مهم: برای بهترین نتیجه، هم موضوع و هم سبک عکس رو به زبان انگلیسی بنویسید."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    
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

# --- 4. تابع اصلی با Webhook ---
def main() -> None:
    # ساخت اپلیکیشن تلگرام و اتصالش به اپلیکیشن Flask
    application = Application.builder().token(TOKEN).build()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # آدرس وبهوک
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL')}/webhook"
    
    # راه‌اندازی ربات با وبهوک
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    main()
