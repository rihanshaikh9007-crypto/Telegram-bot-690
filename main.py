import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import random
import string
import os
import time
from datetime import datetime
from flask import Flask
import threading

# Yahan apna bot token dalein
TOKEN = '8579040508:AAH10pdTGv8OARL0ECXsT5xgxtJpZT-pdww'
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# Aapki Admin ID aur Approval Channel
ADMIN_ID = 1484173564
APPROVAL_CHANNEL = "@ValiModes_key" # Yahan approval requests aayengi

# ================= DATABASE SETUP =================
conn = sqlite3.connect('webseries_bot.db', check_same_thread=False)
c = conn.cursor()

# All Required Tables
c.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id TEXT, link TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS join_reqs (user_id INTEGER, channel_id TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, join_date TEXT, coins INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS pending_refs (user_id INTEGER PRIMARY KEY, referrer_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS completed_refs (user_id INTEGER PRIMARY KEY, referrer_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS vip_keys (key_code TEXT PRIMARY KEY, duration INTEGER, status TEXT DEFAULT 'UNUSED', used_by INTEGER)''')

# 🔗 Naya Table: Link change karne ke liye settings
c.execute('''CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT)''')
c.execute("INSERT OR IGNORE INTO settings (name, value) VALUES ('key_link', 'https://www.mediafire.com/file/if3uvvwjbj87lo2/DRIPCLIENT_v6.2_GLOBAL_AP.apks/file')")
conn.commit()

# ================= SECURITY / ANTI-SPAM =================
user_last_msg = {}

def flood_check(user_id):
    now = time.time()
    if user_id in user_last_msg and now - user_last_msg[user_id] < 1.0:
        return True
    user_last_msg[user_id] = now
    return False

def is_user_banned(user_id):
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    return res and res[0] == 1

# ================= FLASK WEB SERVER =================
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running perfectly on Render!"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


# ================= 💰 ADMIN ADD COINS COMMAND =================
@bot.message_handler(commands=['addcoins'])
def add_coins(message):
    if message.chat.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ <b>Galat Format!</b>\nAise likho: <code>/addcoins USER_ID COINS</code>\nExample: <code>/addcoins 123456789 20</code>")
            return
            
        target_user = int(parts[1])
        amount = int(parts[2])
        
        # Check agar user database me hai
        c.execute("SELECT * FROM users WHERE user_id=?", (target_user,))
        if not c.fetchone():
            bot.reply_to(message, "❌ User database mein nahi mila! Sayad usne bot start nahi kiya hai.")
            return
            
        # Add coins to user
        c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, target_user))
        conn.commit()
        
        bot.reply_to(message, f"✅ <b>Success!</b>\nUser <code>{target_user}</code> ke account mein <b>{amount} Coins</b> add kar diye gaye hain.")
        
        # User ko notification bhejna
        try:
            bot.send_message(target_user, f"🎁 <b>Surprise!</b>\nAdmin ne aapke account mein <b>{amount} Coins</b> bheje hain! Apne account me check karein.")
        except:
            pass # Agar user ne bot block kar diya ho toh error nahi aayega
            
    except ValueError:
        bot.reply_to(message, "❌ User ID aur Coins sirf numbers hone chahiye!")


# ================= 🔗 LINK CHANGER COMMAND =================
@bot.message_handler(commands=['change'])
def change_link(message):
    if message.chat.id != ADMIN_ID: return
    try:
        new_link = message.text.replace('/change', '').strip()
        if new_link == "":
            bot.reply_to(message, "❌ Link khali nahi ho sakta!")
            return
            
        c.execute("UPDATE settings SET value=? WHERE name='key_link'", (new_link,))
        conn.commit()
        bot.reply_to(message, f"✅ <b>Link Updated!</b>\nAb users ko key ke niche ye link dikhega:\n{new_link}")
    except Exception as e:
        bot.reply_to(message, "❌ <b>Galat Format!</b>\nAise likho: <code>/change naya_link_yaha_dalo</code>")


# ================= ADMIN PANEL =================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID: return 
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("➕ Add Channel", callback_data="add_channel"),
               InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel"))
    markup.add(InlineKeyboardButton("📋 View Added Channels", callback_data="view_channels"))
    markup.add(InlineKeyboardButton("📊 Stats & Users", callback_data="adm_stats"),
               InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"))
    markup.add(InlineKeyboardButton("🚫 Ban User", callback_data="adm_ban"),
               InlineKeyboardButton("✅ Unban User", callback_data="adm_unban"))
    markup.add(InlineKeyboardButton("🔑 Gen 1-Day VIP", callback_data="adm_key1"),
               InlineKeyboardButton("🔑 Gen 7-Day VIP", callback_data="adm_key7"))
    
    bot.send_message(message.chat.id, "👨‍💻 <b>Admin Panel</b>\n\nKya karna chahte ho?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["add_channel", "remove_channel", "view_channels"] or call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.message.chat.id != ADMIN_ID: return

    if call.data == "add_channel":
        msg = bot.send_message(call.message.chat.id, "🤖 Pehle bot ko channel me Admin banao!\n\nPhir mujhe sirf Channel ID send karo (Example: <code>-100123456789</code>):")
        bot.register_next_step_handler(msg, process_add_channel)
    elif call.data == "view_channels":
        c.execute("SELECT channel_id, link FROM channels")
        channels = c.fetchall()
        if not channels:
            bot.send_message(call.message.chat.id, "❌ Koi channel added nahi hai.")
            return
        text = "📋 <b>Added Channels:</b>\n\n"
        for ch in channels: text += f"ID: <code>{ch[0]}</code>\nLink: {ch[1]}\n\n"
        bot.send_message(call.message.chat.id, text, disable_web_page_preview=True)
    elif call.data == "remove_channel":
        msg = bot.send_message(call.message.chat.id, "🗑️ Jisko remove karna hai uska Channel ID send karo:")
        bot.register_next_step_handler(msg, process_remove_channel)
    elif call.data == "adm_stats":
        c.execute("SELECT COUNT(*) FROM users")
        tot = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
        ban = c.fetchone()[0]
        bot.send_message(call.message.chat.id, f"📊 <b>BOT STATS</b>\n\n👥 Total Users: {tot}\n🟢 Active Users: {tot-ban}\n🔴 Banned Users: {ban}")
    elif call.data == "adm_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 Bhejo jo message sabko send karna hai:")
        bot.register_next_step_handler(msg, process_broadcast)
    elif call.data == "adm_ban":
        msg = bot.send_message(call.message.chat.id, "🚫 User ID bhejo jise BAN karna hai:")
        bot.register_next_step_handler(msg, lambda m: toggle_ban(m, 1))
    elif call.data == "adm_unban":
        msg = bot.send_message(call.message.chat.id, "✅ User ID bhejo jise UNBAN karna hai:")
        bot.register_next_step_handler(msg, lambda m: toggle_ban(m, 0))
    elif call.data in ["adm_key1", "adm_key7"]:
        days = 1 if call.data == "adm_key1" else 7
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        c.execute("INSERT INTO vip_keys (key_code, duration) VALUES (?, ?)", (code, days))
        conn.commit()
        bot.send_message(call.message.chat.id, f"✅ <b>{days}-Day VIP Key:</b>\n<code>{code}</code>")

def process_add_channel(message):
    ch_id = message.text.strip()
    try:
        bot_member = bot.get_chat_member(ch_id, bot.get_me().id)
        if bot_member.status != 'administrator':
            bot.send_message(message.chat.id, "❌ Bot is channel me Admin nahi hai!")
            return
        invite_link = bot.create_chat_invite_link(ch_id, creates_join_request=True)
        c.execute("INSERT INTO channels (channel_id, link) VALUES (?, ?)", (ch_id, invite_link.invite_link))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Channel <code>{ch_id}</code> add ho gaya!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

def process_remove_channel(message):
    c.execute("DELETE FROM channels WHERE channel_id=?", (message.text.strip(),))
    conn.commit()
    bot.send_message(message.chat.id, "✅ Channel remove kar diya gaya hai!")

def process_broadcast(message):
    bot.send_message(message.chat.id, "⏳ Broadcasting started...")
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    sent, failed = 0, 0
    for u in users:
        try:
            bot.copy_message(u[0], message.chat.id, message.message_id)
            sent += 1
            time.sleep(0.05)
        except: failed += 1
    bot.send_message(message.chat.id, f"✅ <b>Broadcast Done!</b>\nSuccess: {sent} | Failed: {failed}")

def toggle_ban(message, status):
    try:
        uid = int(message.text.strip())
        c.execute("UPDATE users SET is_banned=? WHERE user_id=?", (status, uid))
        conn.commit()
        bot.reply_to(message, f"✅ Done!")
    except: bot.reply_to(message, "❌ Invalid ID.")


# ================= JOIN REQUEST & FORCE SUB =================
@bot.chat_join_request_handler()
def handle_join_request(message: telebot.types.ChatJoinRequest):
    c.execute("INSERT INTO join_reqs (user_id, channel_id) VALUES (?, ?)", (message.from_user.id, str(message.chat.id)))
    conn.commit()

@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = message.from_user.id
    if flood_check(uid) or is_user_banned(uid): return

    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    if not c.fetchone():
        date = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO users (user_id, username, join_date) VALUES (?, ?, ?)", (uid, message.from_user.username or "Unknown", date))
        
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != uid:
                c.execute("SELECT * FROM completed_refs WHERE user_id=?", (uid,))
                if not c.fetchone():
                    c.execute("INSERT OR IGNORE INTO pending_refs (user_id, referrer_id) VALUES (?, ?)", (uid, ref_id))
        conn.commit()
    send_force_sub(message.chat.id, uid)

def check_user_status(user_id):
    c.execute("SELECT channel_id FROM channels")
    channels = c.fetchall()
    if not channels: return True 
    for ch in channels:
        joined = False
        try:
            if bot.get_chat_member(ch[0], user_id).status in ['member', 'administrator', 'creator']: joined = True
        except: pass
        if not joined:
            c.execute("SELECT * FROM join_reqs WHERE user_id=? AND channel_id=?", (user_id, ch[0]))
            if not c.fetchone(): return False 
    return True

def send_force_sub(chat_id, user_id):
    if check_user_status(user_id):
        send_main_menu(chat_id)
        return
        
    markup = InlineKeyboardMarkup()
    c.execute("SELECT link FROM channels")
    for i, ch in enumerate(c.fetchall()): markup.add(InlineKeyboardButton(f"🔔 Join Channel {i+1}", url=ch[0]))
    markup.add(InlineKeyboardButton("✅ VERIFY", callback_data="verify_channels"))
    
    bot.send_photo(chat_id, "https://files.catbox.moe/wcfmqd.jpg", caption="𝗛ᴇʟʟᴏ 𝗨ꜱᴇʀ 👻 𝐁𝐎𝐓\n\nALL CHANNEL JOIN 🥰\n\n👻 Sab channels join karo phir VERIFY dabao", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "verify_channels")
def verify_callback(call):
    uid = call.from_user.id
    if is_user_banned(uid): return
    if check_user_status(uid):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        c.execute("SELECT referrer_id FROM pending_refs WHERE user_id=?", (uid,))
        ref = c.fetchone()
        if ref:
            referrer_id = ref[0]
            c.execute("UPDATE users SET coins = coins + 2 WHERE user_id=?", (referrer_id,))
            c.execute("DELETE FROM pending_refs WHERE user_id=?", (uid,))
            c.execute("INSERT INTO completed_refs (user_id, referrer_id) VALUES (?, ?)", (uid, referrer_id))
            conn.commit()
            try: bot.send_message(referrer_id, "🎉 <b>Congrats!</b>\nA referral verified successfully. <b>+2 Coins</b> Added!")
            except: pass
            
        send_main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ Aapne abhi tak channels me Join Request nahi bheji hai!", show_alert=True)


# ================= MAIN MENU & GET KEY LOGIC =================
def send_main_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("👤 My Account"), KeyboardButton("🔗 Refer & Earn"))
    markup.add(KeyboardButton("🎁 Get Key (15 Coins)"), KeyboardButton("🔑 Use VIP Key"))
    bot.send_message(chat_id, "✅ Use the menu below to navigate:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def text_commands(message):
    uid = message.from_user.id
    if flood_check(uid) or is_user_banned(uid): return
    
    c.execute("SELECT coins FROM users WHERE user_id=?", (uid,))
    res = c.fetchone()
    if not res: return
    coins = res[0]
    text = message.text

    if text == "👤 My Account":
        bot.send_message(uid, f"👤 <b>Account Stats</b>\n\n🆔 User ID: <code>{uid}</code>\n💰 Coins: <b>{coins}</b>")
        
    elif text == "🔗 Refer & Earn":
        bot_usr = bot.get_me().username
        bot.send_message(uid, f"📢 <b>REFER & EARN</b>\n\nInvite friends & get <b>2 Coins</b>!\n\n🔗 Your Link:\nhttps://t.me/{bot_usr}?start={uid}\n\n<i>*Coins are given ONLY when your friend verifies channel joins.</i>")
        
    elif text == "🎁 Get Key (15 Coins)":
        if coins >= 15:
            # 15 coins deduct karo aur approval request bhejo
            c.execute("UPDATE users SET coins = coins - 15 WHERE user_id=?", (uid,))
            conn.commit()
            
            req_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            username = message.from_user.username
            user_mention = f"@{username}" if username else f"User ID: {uid}"

            req_text = (
                f"🆕 <b>New Key Request</b>\n\n"
                f"👤 <b>User:</b> {user_mention}\n"
                f"🆔 <b>ID:</b> <code>{uid}</code>\n"
                f"⏰ <b>Time:</b> {req_time}"
            )

            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("✅ APPROVAL", callback_data=f"approve_{uid}"),
                InlineKeyboardButton("❌ REJECTED", callback_data=f"reject_{uid}")
            )

            try:
                bot.send_message(APPROVAL_CHANNEL, req_text, reply_markup=markup)
                bot.send_message(uid, "⏳ <b>Request Sent!</b>\nAapki request admin channel me bhej di gayi hai. Approval milte hi aapko key mil jayegi.")
            except Exception as e:
                # Agar channel me message nahi gaya, toh coins wapas kar do
                c.execute("UPDATE users SET coins = coins + 15 WHERE user_id=?", (uid,))
                conn.commit()
                bot.send_message(uid, f"❌ Error: Admin ne abhi tak bot ko {APPROVAL_CHANNEL} me admin nahi banaya hai. (Coins refunded)")

        else:
            bot.send_message(uid, f"❌ <b>Coins Kam Hain!</b>\n\nKey lene ke liye <b>15 Coins</b> chahiye.\nAapke paas abhi sirf <b>{coins} Coins</b> hain. Doston ko refer karo!")

    elif text == "🔑 Use VIP Key":
        msg = bot.send_message(uid, "Send your generated VIP Key here:")
        bot.register_next_step_handler(msg, process_vip_key)

def process_vip_key(message):
    key = message.text.strip()
    uid = message.from_user.id
    c.execute("SELECT duration FROM vip_keys WHERE key_code=? AND status='UNUSED'", (key,))
    res = c.fetchone()
    if res:
        c.execute("UPDATE vip_keys SET status='USED', used_by=? WHERE key_code=?", (uid, key))
        conn.commit()
        bot.send_message(uid, f"✅ <b>VIP Key Activated!</b>\nYou now have VIP Access for {res[0]} days.")
    else:
        bot.send_message(uid, "❌ <b>Invalid or Used Key!</b>")


# ================= APPROVE / REJECT LOGIC =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_approval(call):
    # Sirf ADMIN hi in buttons pe click kar sakta hai
    if call.fromuser.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Only Admin can do this!", show_alert=True)
        return

    action, uid_str = call.data.split("_")
    uid = int(uid_str)

    if action == "approve":
        bot.edit_message_text(f"{call.message.text}\n\n✅ <b>STATUS: APPROVED</b>", chat_id=call.message.chat.id, message_id=call.message.message_id)
        send_dynamic_key(uid)
        
        try:
            bot.send_message(uid, "🎉 <b>Congratulations!</b>\nAapki request Admin ne Approve kar di hai. Upar aapki key aur link mil jayega 👆")
        except:
            pass

    elif action == "reject":
        bot.edit_message_text(f"{call.message.text}\n\n❌ <b>STATUS: REJECTED</b>", chat_id=call.message.chat.id, message_id=call.message.message_id)
        
        # User ke 15 coins usko wapas de do
        c.execute("UPDATE users SET coins = coins + 15 WHERE user_id=?", (uid,))
        conn.commit()
        
        try:
            bot.send_message(uid, "❌ <b>Request Rejected!</b>\nAdmin ne aapki request reject kar di hai. Aapke 15 coins wapas account me daal diye gaye hain.")
        except:
            pass


# ================= DYNAMIC KEY GENERATOR =================
def send_dynamic_key(chat_id):
    key = f"{random.randint(1000000000, 9999999999)}"
    
    # Database se naya link fetch karega jo /change se dala gaya tha
    c.execute("SELECT value FROM settings WHERE name='key_link'")
    dynamic_link = c.fetchone()[0]
    
    text = (
        f"Key - <code>{key}</code>\n\n"
        f"<a href='https://t.me/+MkNcxGuk-w43MzBl'>DRIP SCINET APK - {dynamic_link}</a>"
    )
    bot.send_message(chat_id, text, disable_web_page_preview=True)


# ================= START SYSTEM =================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Bot is running...")
    bot.infinity_polling(allowed_updates=telebot.util.update_types)
