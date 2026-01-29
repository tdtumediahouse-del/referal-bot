import telebot
from telebot import types
import sqlite3
import logging
import os

# ==========================================
# SOZLAMALAR (RAILWAY UCHUN ENV O'ZGARUVCHILAR)
# ==========================================
BOT_TOKEN = os.getenv("8205914721:AAFkrlLErg2JOxG4z_iFVSipNuMQrcxZ0oU")  # Railwayda buni Variables bo'limiga yozasiz
ADMIN_ID = int(os.getenv("5390578467", "0")) 
CHANNEL_ID = int(os.getenv("-1001611294866", "0")) # Masalan: -100123456789
CHANNEL_USERNAME = os.getenv("@mirsoat_club") # Masalan: @kanal_useri

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
logging.basicConfig(level=logging.INFO)

# ==========================================
# BAZA BILAN ISHLASH (SQLITE)
# ==========================================
def db_connect():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    return conn

def init_db():
    conn = db_connect()
    cursor = conn.cursor()
    # Users jadvali: user_id, referrer_id (kim chaqirdi), status (active/left/pending)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            status TEXT DEFAULT 'pending',
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Bot ishga tushganda bazani yaratish
init_db()

# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        return False

def get_referral_count(user_id):
    conn = db_connect()
    cursor = conn.cursor()
    # Faqat 'active' (kanalda bor) bo'lgan referallarni sanaymiz
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ? AND status = 'active'", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ==========================================
# START HANDLER
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    conn = db_connect()
    cursor = conn.cursor()
    
    # Foydalanuvchini bazaga qo'shish yoki tekshirish
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        referrer_id = 0
        if len(args) > 1 and args[1].isdigit():
            potential_referrer = int(args[1])
            if potential_referrer != user_id:
                referrer_id = potential_referrer
        
        # Yangi foydalanuvchi - status 'pending' (kutilmoqda)
        cursor.execute("INSERT INTO users (user_id, referrer_id, status) VALUES (?, ?, ?)", 
                       (user_id, referrer_id, 'pending'))
        conn.commit()
        if referrer_id != 0:
            logging.info(f"{user_id} ni {referrer_id} taklif qildi (hali tasdiqlanmadi)")
    
    conn.close()
    
    # Kanalga a'zolikni tekshirish oynasi
    check_membership(message)

def check_membership(message):
    if is_subscribed(message.from_user.id):
        user_menu(message)
    else:
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")
        btn2 = types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")
        markup.add(btn1)
        markup.add(btn2)
        
        bot.send_message(message.chat.id, 
                         f"👋 Assalomu alaykum!\n\nBotdan foydalanish uchun {CHANNEL_USERNAME} kanaliga a'zo bo'ling va <b>Tekshirish</b> tugmasini bosing.",
                         reply_markup=markup)

# ==========================================
# MENU VA REFERAL
# ==========================================
def user_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔗 Referal havola", "📊 Statistika")
    if message.from_user.id == ADMIN_ID:
        markup.add("👑 Admin Panel")
        
    bot.send_message(message.chat.id, "✅ Siz muvaffaqiyatli ro'yxatdan o'tdingiz! Bo'limni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check(call):
    user_id = call.from_user.id
    if is_subscribed(user_id):
        # Bazadagi statusni yangilash
        conn = db_connect()
        cursor = conn.cursor()
        
        # Kim taklif qilganini olamiz
        cursor.execute("SELECT referrer_id, status FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            referrer_id, current_status = result
            # Agar oldin tasdiqlanmagan bo'lsa, endi 'active' qilamiz
            if current_status != 'active':
                cursor.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))
                conn.commit()
                
                # Taklif qilgan odamga xabar
                if referrer_id != 0:
                    try:
                        bot.send_message(referrer_id, f"👏 Tabriklaymiz! Sizning referalingiz ({call.from_user.first_name}) kanalga a'zo bo'ldi.")
                    except: pass
        
        conn.close()
        bot.delete_message(call.message.chat.id, call.message.message_id)
        user_menu(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

# ==========================================
# TUGMALAR
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🔗 Referal havola")
def referral_link(message):
    link = f"https://t.me/{bot.get_me().username}?start={message.from_user.id}"
    count = get_referral_count(message.from_user.id)
    bot.send_message(message.chat.id, 
                     f"🔗 <b>Sizning shaxsiy havolangiz:</b>\n{link}\n\n"
                     f"👥 <b>Tasdiqlangan referallaringiz:</b> {count} ta\n"
                     f"⚠️ <i>Eslatma: Agar taklif qilgan odamingiz kanaldan chiqib ketsa, hisobingizdan ayriladi.</i>")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def my_stats(message):
    count = get_referral_count(message.from_user.id)
    bot.send_message(message.chat.id, f"Siz jami <b>{count}</b> ta faol odam chaqirgansiz.")

# ==========================================
# ADMIN PANEL
# ==========================================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = db_connect()
    cursor = conn.cursor()
    
    # Umumiy statistika
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
    active_refs = cursor.fetchone()[0]
    
    # TOP 10 Referalchilar
    cursor.execute('''
        SELECT referrer_id, COUNT(*) as count 
        FROM users 
        WHERE status = 'active' AND referrer_id != 0 
        GROUP BY referrer_id 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    top_list = cursor.fetchall()
    
    text = f"📊 <b>ADMIN STATISTIKA</b>\n\n"
    text += f"👤 Jami bot foydalanuvchilari: {total_users}\n"
    text += f"✅ Faol referallar: {active_refs}\n\n"
    text += "🏆 <b>TOP 10 REFERALCHILAR:</b>\n"
    
    for idx, (uid, count) in enumerate(top_list, 1):
        text += f"{idx}. ID: <code>{uid}</code> — {count} ta\n"
        
    conn.close()
    bot.send_message(message.chat.id, text)

# ==========================================
# CHIQIB KETISHNI ANIQLASH (ANTI-CHEAT)
# ==========================================
@bot.chat_member_handler()
def track_exit(update: types.ChatMemberUpdated):
    if update.chat.id != CHANNEL_ID:
        return

    user_id = update.from_user.id
    new_status = update.new_chat_member.status
    old_status = update.old_chat_member.status

    # Agar a'zo bo'lsa (Pending -> Active)
    if new_status in ["member", "administrator", "creator"] and old_status not in ["member", "administrator", "creator"]:
        conn = db_connect()
        cursor = conn.cursor()
        
        # Statusni active ga o'zgartiramiz
        cursor.execute("UPDATE users SET status = 'active' WHERE user_id = ?", (user_id,))
        
        # Refererni topamiz
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if res and res[0] != 0:
            try:
                bot.send_message(res[0], "➕ Bitta referalingiz kanalga a'zo bo'ldi!")
            except: pass
        
        conn.commit()
        conn.close()

    # Agar chiqib ketsa (Active -> Left/Kicked)
    elif new_status in ["left", "kicked"] and old_status in ["member", "administrator", "creator"]:
        conn = db_connect()
        cursor = conn.cursor()
        
        # Statusni left ga o'zgartiramiz
        cursor.execute("UPDATE users SET status = 'left' WHERE user_id = ?", (user_id,))
        
        # Refererni topamiz va ogohlantiramiz
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if res and res[0] != 0:
            referrer_id = res[0]
            try:
                bot.send_message(referrer_id, "➖ Referalingiz kanaldan chiqib ketdi! U endi hisoblanmaydi.")
            except: pass
            
        conn.commit()
        conn.close()

bot.infinity_polling(allowed_updates=['message', 'callback_query', 'chat_member'])

