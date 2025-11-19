import asyncio
import logging
import os
import io
import subprocess
import traceback
from collections import defaultdict
from datetime import datetime, timedelta
from telegram import Update, InputFile, InputMediaPhoto, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import perchance
from PIL import Image

# --- 1. تنظیمات اولیه ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
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

# --- 3. محدودیت استفاده ---
user_requests = defaultdict(list)

def is_rate_limited(user_id: int) -> bool:
    """بررسی آیا کاربر درخواست زیادی فرستاده"""
    now = datetime.now()
    # حذف درخواست‌های قدیمی (بیشتر از ۵ دقیقه)
    user_requests[user_id] = [req_time for req_time in user_requests[user_id] 
                             if now - req_time < timedelta(minutes=5)]
    
    if len(user_requests[user_id]) >= 3:  # حداکثر ۳ درخواست در ۵ دقیقه
        return True
    
    user_requests[user_id].append(now)
    return False

# --- 4. تابع نصب مرورگر ---
def install_playwright_browser():
    """این تابع تمام مرورگرهای مورد نیاز Playwright رو نصب می‌کنه."""
    try:
        logger.info("در حال نصب تمام مرورگرهای Playwright (شامل فایرفاکس)...")
        subprocess.run(["playwright", "install"], check=True, capture_output=True, text=True)
        logger.info("تمام مرورگرهای Playwright با موفقیت نصب شدند.")
    except FileNotFoundError:
        logger.error("دستور playwright پیدا نشد. آیا کتابخانه به درستی نصب شده؟")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"خطا هنگام نصب مرورگرها: {e.stderr}")
        raise

# --- 5. توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    style_list = "\n".join([f"• {key}" for key in STYLES.keys()])
    await update.message.reply_text(
        "به ربات تولید عکس پیشرفته خوش آمدی! 🎨\n\n"
        "این ربات **صبور** است و برای تولید ۴ عکس کمی زمان می‌برد.\n\n"
        "برای ساخت ۴ عکس، پیامت رو اینجوری بنویس:\n"
        "`موضوع عکس (به انگلیسی) | کلید سبک`\n\n"
        f"کلیدهای سبک موجود:\n{style_list}\n\n"
        "مثال:\n"
        "`a futuristic city | سایبرپانک`\n\n"
        "برای راهنمایی بیشتر /help را تایپ کن."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    style_list = "\n".join([f"• {key}" for key in STYLES.keys()])
    await update.message.reply_text(
        "📖 راهنمای استفاده:\n\n"
        "فرمت دستور:\n"
        "`موضوع عکس (به انگلیسی) | سبک`\n\n"
        f"سبک‌های موجود:\n{style_list}\n\n"
        "مثال‌ها:\n"
        "`a beautiful sunset over mountains | واقعی`\n"
        "`a magical forest with fairies | فانتزی`\n"
        "`a robot in a city | سایبرپانک`\n\n"
        "⚠️ توجه:\n"
        "• تولید ۴ عکس حدود ۲-۳ دقیقه زمان می‌برد\n"
        "• حداکثر ۳ درخواست در ۵ دقیقه مجاز است\n"
        "• موضوع تصویر باید به انگلیسی باشد"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # بررسی محدودیت استفاده
    if is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ برای جلوگیری از سوء استفاده، فقط ۳ درخواست در ۵ دقیقه مجاز است.\n"
            "لطفاً ۵ دقیقه دیگر دوباره تلاش کنید."
        )
        return
        
    user_message = update.message.text
    
    if '|' not in user_message:
        await update.message.reply_text(
            "❌ لطفاً پیامت رو با فرمت درست بنویس.\n"
            "مثال: `a futuristic city | سایبرپانک`\n\n"
            "برای راهنمایی بیشتر /help را بفرستید."
        )
        return
        
    prompt, style_key = user_message.split('|', 1)
    prompt = prompt.strip()
    style_key = style_key.strip()
    
    if not prompt or not style_key:
        await update.message.reply_text(
            "❌ هم موضوع و هم سبک رو باید مشخص کنی.\n"
            "مثال: `a futuristic city | سایبرپانک`"
        )
        return

    if style_key not in STYLES:
        style_list = "\n".join([f"• {key}" for key in STYLES.keys()])
        await update.message.reply_text(
            f"❌ سبک '{style_key}' معتبر نیست.\n\n"
            f"سبک‌های موجود:\n{style_list}\n\n"
            "برای راهنمایی بیشتر /help را بفرستید."
        )
        return

    await update.message.reply_text(
        f"🎨 درخواست ساخت ۴ تصویر ثبت شد!\n"
        f"📝 موضوع: {prompt}\n"
        f"🎭 سبک: {style_key}\n\n"
        "⏳ لطفاً ۲-۳ دقیقه صبر کنید... در حال تولید تصاویر"
    )
    
    asyncio.create_task(
        generate_and_send_images_in_background(
            chat_id=update.effective_chat.id,
            prompt=prompt,
            style_key=style_key
        )
    )

async def generate_and_send_images_in_background(chat_id: int, prompt: str, style_key: str):
    """این تابع در پس‌زمینه اجرا می‌شه و زمان زیادی می‌بره."""
    bot = Bot(token=TOKEN)
    
    try:
        # ارسال پیام "در حال تولید"
        status_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"🔄 در حال تولید ۴ تصویر با سبک '{style_key}'...\nلطفاً شکیبا باشید."
        )
        
        style_prompt = STYLES[style_key]
        full_prompt = f"{prompt}, {style_prompt}"
        media_group = []
        
        gen = perchance.ImageGenerator()
        successful_images = 0
        
        for i in range(4):
            try:
                logger.info(f"تولید تصویر {i+1} از ۴")
                
                async with await gen.image(full_prompt) as result:
                    binary = await result.download()
                    image = Image.open(binary)
                    
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    
                    media_group.append(InputMediaPhoto(media=InputFile(img_byte_arr, filename=f"image_{i}.png")))
                    successful_images += 1
                    
            except Exception as e:
                logger.error(f"خطا در تولید تصویر {i+1}: {e}")
                # ادامه با تصاویر باقی مانده
                continue
        
        if media_group:
            await bot.send_media_group(
                chat_id=chat_id,
                media=media_group,
                caption=f"✅ {successful_images} تصویر برای «{prompt}» با سبک «{style_key}» آماده شد.\n\n"
                       f"برای ساخت تصاویر بیشتر، پیام جدید بفرستید."
            )
            logger.info(f"ارسال {successful_images} تصویر به کاربر")
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ متأسفانه هیچ تصویری تولید نشد.\n"
                     "ممکن است مشکل موقتی در سرویس وجود داشته باشد.\n"
                     "لطفاً چند دقیقه دیگر دوباره تلاش کنید."
            )
            
        # حذف پیام "در حال تولید"
        try:
            await bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
        except Exception as e:
            logger.warning(f"نتوانست پیام وضعیت را حذف کند: {e}")
            
    except asyncio.TimeoutError:
        await bot.send_message(
            chat_id=chat_id,
            text="⏰ زمان تولید تصاویر به پایان رسید.\n"
                 "لطفاً دوباره تلاش کنید."
        )
    except Exception as e:
        logger.error(f"خطا در تولید تصویر در پس‌زمینه: {e}")
        logger.error(traceback.format_exc())
        
        await bot.send_message(
            chat_id=chat_id,
            text="❌ متأسفانه در تولید تصویر مشکلی پیش آمد.\n"
                 "لطفاً چند دقیقه دیگر دوباره تلاش کنید.\n"
                 "اگر مشکل ادامه داشت، با پشتیبانی تماس بگیرید."
        )

# --- 6. تابع اصلی ---
def main() -> None:
    # بررسی وجود توکن
    if not TOKEN:
        logger.error("❌ متغیر محیطی BOT_TOKEN تنظیم نشده!")
        print("لطفاً متغیر محیطی BOT_TOKEN را تنظیم کنید.")
        return
    
    # نصب مرورگر با مدیریت خطا
    try:
        logger.info("در حال نصب مرورگرهای Playwright...")
        install_playwright_browser()
    except Exception as e:
        logger.warning(f"⚠️ نصب مرورگر ناموفق بود: {e}. ادامه می‌دهیم...")
    
    # ساخت اپلیکیشن
    application = Application.builder().token(TOKEN).build()
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    webhook_url = os.getenv("RENDER_EXTERNAL_URL")
    
    if webhook_url:
        logger.info("🚀 اجرا در حالت وب‌هوک...")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="webhook",
            webhook_url=f"{webhook_url}/webhook"
        )
    else:
        logger.info("🔍 اجرا در حالت پولینگ...")
        application.run_polling()

if __name__ == "__main__":
    main()
