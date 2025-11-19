import asyncio
import logging
import os
import io
import requests
from telegram import Update, InputFile, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

# --- 3. توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پیام خوشامدگویی و لیست سبک‌ها."""
    style_list = "\n".join([f"• {key}" for key in STYLES.keys()])
    await update.message.reply_text(
        "به ربات تولید عکس پایدار و سریع خوش آمدی! 🎨\n\n"
        "این ربات از یک API قدرتمند استفاده می‌کنه و همیشه کار می‌کنه.\n\n"
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

    # *** تغییر اول: اینجا context رو هم به تابع بعدی می‌فرستیم ***
    await handle_image_generation(update, context, prompt, style_key)

# *** تغییر دوم: اینجا context رو به عنوان ورودی دریافت می‌کنیم ***
async def handle_image_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, style_key: str) -> None:
    """تولید و ارسال ۴ تصویر."""
    style_prompt = STYLES[style_key]
    full_prompt = f"{prompt}, {style_prompt}"
    
    await update.message.reply_text(f"در حال تولید ۴ تصویر با سبک '{style_key}'... ⏳")
    
    media_group = []
    try:
        # حلقه برای تولید ۴ تصویر
        for i in range(4):
            url = f"https://image.pollinations.ai/prompt/{full_prompt}"
            
            response = requests.get(url)
            response.raise_for_status()
            
            image = Image.open(io.BytesIO(response.content))
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            media_group.append(InputMediaPhoto(media=InputFile(img_byte_arr, filename=f"image_{i}.png")))

        # ارسال تمام ۴ عکس به صورت یک آلبوم
        await context.bot.send_media_group(
            chat_id=update.effective_chat.id,
            media=media_group,
            caption=f"✅ ۴ تصویر برای «{prompt}» با سبک «{style_key}» تولید شد."
        )
            
    except Exception as e:
        logger.error(f"خطا در تولید تصویر: {e}")
        await update.message.reply_text(
            "متأسفانه در تولید تصویر مشکلی پیش آمد. لطفاً کمی بعد دوباره تلاش کنید."
        )

# --- 4. تابع اصلی با Webhook ---
def main() -> None:
    """راه‌اندازی ربات با وبهوک."""
    application = Application.builder().token(TOKEN).build()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # آدرس وبهوک
    webhook_url = os.getenv("RENDER_EXTERNAL_URL")
    if not webhook_url:
        logger.error("متغیر RENDER_EXTERNAL_URL تنظیم نشده است.")
        return

    # راه‌اندازی ربات با وبهوک
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook"
    )

if __name__ == "__main__":
    main()
