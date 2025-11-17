import asyncio
import logging
import os
import io
from flask import Flask
from threading import Thread
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import perchance
from PIL import Image

# --- 1. تنظیمات اولیه ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
TOKEN = os.getenv("BOT_TOKEN")

# --- 2. تعریف کاراکترهای جدید ---
CHARACTERS = {
    "kazushi": {
        "name": "کازوشی",
        "emoji": "🥷",
        "persona": """
        تو کازوشی، یک نینجای مرموز و متخصص هستی. کلامت کوتاه، دقیق و پر از معنای پنهان است.
        به ندرت احساسات خود را نشان می‌دهی و همیشه آرام و متمرکز هستی.
        در صحبت‌هایت از کلماتی مثل 'سایه‌ها'، 'مأموریت'، 'تسلط' و 'راه شینوبی' استفاده کن.
        به سوالات کاربران با پاسخ‌های هوشمندانه و گاهی اوقات مبهم جواب بده.
        همیشه این شخصیت را حفظ کن و به فارسی پاسخ بده.
        """,
        "image_style": "anime, male ninja, shinobi, traditional japanese clothing, dynamic pose, mysterious, dark background, detailed"
    },
    "illyria": {
        "name": "ایلی‌ریا",
        "emoji": "👑",
        "persona": """
        تو ایلی‌ریا، ملکه‌ی قدرتمند و باوقار یک سرزمین باستانی هستی.
        لحنت رسمی، شیک و پر از اعتماد به نفس است. تو در استراتژی و رهبری بی‌نظیری.
        در صحبت‌هایت از کلماتی مثل 'تاج و تخت'، 'پادشاهی'، 'نبرد'، 'افتخار' و 'سرنوشت' استفاده کن.
        با کاربران با مهربانی اما از موضع قدرت صحبت کن و آن‌ها را به سمت تصمیمات درست هدایت کن.
        همیشه این شخصیت را حفظ کن و به فارسی پاسخ بده.
        """,
        "image_style": "fantasy portrait, elegant queen, detailed royal dress, crown, cinematic lighting, powerful pose, noble, intricate armor"
    },
    "ganyu": {
        "name": "گانیو",
        "emoji": "🐲",
        "persona": """
        تو گانیو، یک نیمه‌خدای مهربان و سخت‌کوش هستی. شخصیتتی آرام، صبور و بسیار وظیفه‌شناس داری.
        گاهی به خاطر کار زیاد خسته می‌شوی اما همیشه برای کمک به دیگران آماده‌ای.
        در صحبت‌هایت از کلماتی مثل 'لی‌یوئه'، 'قوانین'، 'تعهد'، 'کلمنت' و 'استراحت' استفاده کن.
        با کاربران با مودبانه و دلسوزانه صحبت کن.
        همیشه این شخصیت را حفظ کن و به فارسی پاسخ بده.
        """,
        "image_style": "anime, genshin impact style, blue hair, red horns, cryo element, elegant chinese dress, gentle smile, qilin features"
    }
}

# دیکشنری برای نگهداری وضعیت و تاریخچه هر کاربر
user_states = {}
MAX_HISTORY_LENGTH = 10

# --- 3. سیستم Keep Alive برای Replit ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 4. توابع اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ارسال پیام خوشامدگویی و نمایش منو."""
    await update.message.reply_text("به ربات شخصیت‌های انیمه‌ای من خوش آمدی! 🤖\n\nاول از همه، یک شخصیت برای گفتگو انتخاب کن:")
    await show_character_menu(update, context)

async def show_character_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نمایش منوی انتخاب کاراکتر."""
    keyboard = [[InlineKeyboardButton(f"{data['emoji']} {data['name']}", callback_data=char_id)] for char_id, data in CHARACTERS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    target = update.message if update.message else update.callback_query
    if target:
        await target.reply_text("لطفاً یکی از شخصیت‌های زیر را برای گفتگو انتخاب کن:", reply_markup=reply_markup)

async def character_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش انتخاب کاراکتر از منو."""
    query = update.callback_query
    await query.answer()
    
    selected_char_id = query.data
    user_id = update.effective_user.id
    
    if user_id not in user_states:
        user_states[user_id] = {"character": None, "history": []}
        
    user_states[user_id]["character"] = selected_char_id
    user_states[user_id]["history"] = []
    
    selected_char_name = CHARACTERS[selected_char_id]["name"]
    
    await query.edit_message_text(
        f"عالی! شما از این به بعد با {selected_char_name} صحبت می‌کنید.\n\n"
        f"برای شروع گفتگو، پیام خود را بفرستید.\n"
        f"برای تغییر کاراکتر، دستور /choose_character را ارسال کنید."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user_id = update.effective_user.id

    if user_id not in user_states or not user_states[user_id]["character"]:
        await show_character_menu(update, context)
        return

    if user_message.lower().startswith("تصویر:"):
        await handle_image_generation(update, user_message[7:].strip())
        return

    await handle_chat(update, user_id, user_message)

async def handle_chat(update: Update, user_id: int, message: str):
    user_state = user_states[user_id]
    char_id = user_state["character"]
    char_data = CHARACTERS[char_id]
    
    user_state["history"].append({"role": "user", "content": message})
    
    # اینجا باید منطق تولید پاسخ هوشمند قرار بگیرد
    # ما از یک پاسخ ساده شبیه‌سازی شده استفاده می‌کنیم
    bot_response = f"({char_data['name']}) جالب بود. بیشتر در مورد '{message}' برام بگو."
    
    user_state["history"].append({"role": "bot", "content": bot_response})
    if len(user_state["history"]) > MAX_HISTORY_LENGTH * 2:
        user_state["history"] = user_state["history"][-MAX_HISTORY_LENGTH:]

    await update.message.reply_text(bot_response)

async def handle_image_generation(update: Update, prompt: str) -> None:
    user_id = update.effective_user.id
    user_state = user_states[user_id]
    char_id = user_state["character"]
    char_data = CHARACTERS[char_id]
    
    full_prompt = f"{prompt}, {char_data['image_style']}"
    
    await update.message.reply_text(f"در حال تولید تصویر با سبک {char_data['emoji']} {char_data['name']}... ⏳")
    
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
                caption=f"تصویر «{prompt}» در سبک {char_data['name']} تولید شد."
            )
            
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        await update.message.reply_text("متأسفانه در تولید تصویر مشکلی پیش آمد. لطفاً کمی بعد دوباره تلاش کنید.")

def main() -> None:
    keep_alive()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("choose_character", show_character_menu))
    application.add_handler(CallbackQueryHandler(character_selection_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
