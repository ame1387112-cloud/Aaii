import asyncio
import logging
import os
import io
import subprocess
import traceback
from telegram import Update, InputFile, InputMediaPhoto, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import perchance
from PIL import Image

# --- 1. تنظیمات اولیه ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get('PORT', 8443))

# --- 2. دیکشنری سبک‌ها ---
STYLES = {
    "انیمه": "anime, cinematic, detailed",
    "واقعی": "photorealistic, high quality, 8k",
    "نقاشی": "oil painting, classic art, detailed",
    "سه‌بعدی": "3d render, octane, detailed",
    "کارتونی": "cartoon, disney style, colorful",
    "سایبرپانک": "cyberpunk, neon lights, futuristic",
    "فانتزی": "fantasy art, ethereal, magical",
    "پیکسلی": "pixel art,16-bit, retro"
}

# --- 3. تابع نصب مرورگر ---
def install_playwright_browser():
    try:
        logger.info("در حال بررسی نصب بودن مرورگر Playwright...")
        subprocess.run(["playwright", "install", "chromium"], check=True, capture_output=True, text=True)
        logger.info("مرورگر Playwright با موفقیت آماده به کار شد.")
    except FileNotFoundError:
        logger.error("دستور playwright پیدا نشد. آیا کتابخانه به درستی نصب شده؟")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"خطا هنگام نصب مرورگر: {e.stderr}")
        raise

# --- 4. توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    style_list = "\n".join([f"• {key}" for key in STYLES.keys()])
    await update.message.reply_text(
        "به ربات تولید عکس پیشرفته خوش آمدی! 🎨\n\n"
        "این ربات **صبور** است و برای تولید ۴ عکس کمی زمان می‌برد.\n\n"
        "برای ساخت ۴ عکس، پیامت رو اینجوری بنویس:\n"
        "`موضوع عکس (به انگلیسی) | کلید سبک`\n\n"
        f"کلیدهای سبک موجود:\n{style_list}\n\n"
        "مثال:\n"
        "`a futuristic city | سایبرپانک`"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    
    if '|' not in user_message:
        await update.message.reply_text(
            "لطفاً پیامت رو با فرمت درست بنویس.\n"
            "مثال: `a futuristic city | سایبرپانک`"
        )
        return
        
    prompt, style_key = user_message.split('|', 1)
    prompt = prompt.strip()
    style_key = style_key.strip()
    
    if not prompt or not style_key:
        await update.message.reply_text(
            "هم موضوع و هم کلید سبک رو باید مشخص کنی.\n"
            "مثال: `a futuristic city | سایبرپانک`"
        )
        return

    if style_key not in STYLES:
        await update.message.reply_text(
            f"کلید سبک '{style_key}' معتبر نیست. لطفاً از کلیدهای موجود استفاده کن."
        )
        return

    # ارسال پیام فوری و شروع کار در پس‌زمینه
    await update.message.reply_text(f"درخواست ساخت ۴ تصویر با سبک '{style_key}' ثبت شد. لطفاً صبر کنید... 🎨")
    
    # این کلیدی‌ترین خط است: کار رو به پس‌زمینه می‌فرسته
    asyncio.create_task(
        generate_and_send_images_in_background(
            chat_id=update.effective_chat.id,
            prompt=prompt,
            style_key=style_key
        )
    )

# این تابع جدید تمام کار سنگین رو در پس‌زمینه انجام میده
async def generate_and_send_images_in_background(chat_id: int, prompt: str, style_key: str):
    """این تابع در پس‌زمینه اجرا می‌شه و زمان زیادی می‌بره."""
    style_prompt = STYLES[style_key]
    full_prompt = f"{prompt}, {style_prompt}"
    
    media_group = []
    try:
        # یک نمونه جدید از ربات می‌سازیم تا بتونیم پیام بفرستیم
        bot = Bot(token=TOKEN)
        gen = perchance.ImageGenerator()
        
        for i in range(4):
            async with await gen.image(full_prompt) as result:
                binary = await result.download()
                image = Image.open(binary)
                
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                media_group.append(InputMediaPhoto(media=InputFile(img_byte_arr, filename=f"image_{i}.png")))

        # وقتی همه چیز آماده شد، عکس‌ها رو می‌فرستیم
        await bot.send_media_group(
            chat_id=chat_id,
            media=media_group,
            caption=f"✅ ۴ تصویر برای «{prompt}» با سبک «{style_key}» آماده شد."
        )
            
    except Exception as e:
        logger.error(f"خطا در تولید تصویر در پس‌زمینه: {e}")
        logger.error(traceback.format_exc())
        
        # در صورت خطا هم به کاربر اطلاع می‌دیم
        bot = Bot(token=TOKEN)
        await bot.send_message(
            chat_id=chat_id,
            text="متأسفانه در تولید تصویر مشکلی پیش آمد. لطفاً کمی بعد دوباره تلاش کنید."
        )

# --- 5. تابع اصلی ---
def main() -> None:
    install_playwright_browser()
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    webhook_url = os.getenv("RENDER_EXTERNAL_URL")
    if not webhook_url:
        logger.error("متغیر RENDER_EXTERNAL_URL تنظیم نشده است.")
        return

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook"
    )

if __name__ == "__main__":
    main()
