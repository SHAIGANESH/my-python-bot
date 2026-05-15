import telebot
import requests
from telebot import types
import threading
import time
import re
import io
import json
from datetime import datetime, timedelta

# --- CONFIGURATION ---
TOKEN = "8408246872:AAGF_n3wkBbeF9YeIuhJ9_efVuUhnYEKPEE"
ADMIN_PASSWORD = "Sold@9819"
ADMIN_CHAT_ID = "8481566006"
CHANNEL_ID = "https://t.me/paidnmms"
OWNER_USERNAME = "@dinamic80"
OWNER_NAME = "NO RECORD"

# APIs
USER_API = "https://tg-number-api.vercel.app/?userid="
NUM_API = "https://toxic-num-info.vercel.app/?number="
INSTA_API = "https://instagraminfo.anshapi.workers.dev/info?username="
TG_TO_NUM_API = "https://jahangirdev.xo.je/tginfo.php?id="
TG_TO_NUM_BACKUP_API = "https://rootx-osint.in/?type=tg_num&key=Al704&query="
NUM_TO_INFO_API = "https://movements-invoice-amanda-victoria.trycloudflare.com/search/number?number={}&key=mysecretkey123"
NEW_NUM_API = "https://movements-invoice-amanda-victoria.trycloudflare.com/search/number?number={}&key=mysecretkey123"

bot = telebot.TeleBot(TOKEN)

# Data stores
users = set()
banned_users = set()
user_daily_searches = {}  # user_id -> {"count": int, "date": str}
user_premium = {}  # user_id -> {"type": "day"/"month"/"lifetime", "expiry": datetime}
admin_logged_in = set()  # Store admin sessions

# --- HELPER FUNCTIONS ---
def is_admin(user_id):
    return str(user_id) == ADMIN_CHAT_ID and user_id in admin_logged_in

def admin_required(func):
    """Decorator to check if user is logged in as admin"""
    def wrapper(message):
        if str(message.chat.id) == ADMIN_CHAT_ID:
            if message.chat.id in admin_logged_in:
                return func(message)
            else:
                bot.send_message(message.chat.id, "🔐 **Access Denied!**\nUse `/admin <password>` to login.", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "❌ You are not authorized to use admin commands.")
        return None
    return wrapper

def is_subscribed(user_id):
    try:
        channel = CHANNEL_ID.replace("https://t.me/", "").replace("@", "")
        status = bot.get_chat_member(f"@{channel}", user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

def clean_number(text):
    nums = re.sub(r'\D', '', text)
    return nums[-10:] if len(nums) >= 10 else nums

def get_daily_search_count(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_daily_searches or user_daily_searches[user_id]["date"] != today:
        user_daily_searches[user_id] = {"count": 0, "date": today}
    return user_daily_searches[user_id]["count"]

def increment_daily_search(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in user_daily_searches or user_daily_searches[user_id]["date"] != today:
        user_daily_searches[user_id] = {"count": 1, "date": today}
    else:
        user_daily_searches[user_id]["count"] += 1

def can_search(user_id):
    if user_id in user_premium:
        premium = user_premium[user_id]
        if premium["type"] == "lifetime":
            return True
        elif premium["type"] in ["day", "month"]:
            if datetime.now() < premium["expiry"]:
                return True
            else:
                del user_premium[user_id]
    return get_daily_search_count(user_id) < 5

def get_remaining_searches(user_id):
    if user_id in user_premium:
        return "∞ (Premium)"
    return f"{5 - get_daily_search_count(user_id)}/5"

def notify_admin_new_user(user_id, username, first_name):
    try:
        user_info = bot.get_chat(user_id)
        name = user_info.first_name or ""
        if user_info.last_name:
            name += f" {user_info.last_name}"
        username_str = f"@{user_info.username}" if user_info.username else "No username"

        msg = (
            f"🆕 **NEW USER JOINED THE BOT!**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👤 **Name:** `{name}`\n"
            f"🔗 **Username:** `{username_str}`\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"📅 **Joined:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        )
        bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Error sending admin notification: {e}")

# ========== PER BUTTON DISPLAY MARKUP ==========
def get_main_menu_markup():
    """Main menu with all buttons visible per request"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 USER SEARCH", callback_data="menu_user"),
        types.InlineKeyboardButton("📱 NUM OSINT", callback_data="menu_num"),
        types.InlineKeyboardButton("📸 INSTAGRAM INFO", callback_data="menu_insta"),
        types.InlineKeyboardButton("📊 STATS", callback_data="menu_stats"),
        types.InlineKeyboardButton("👑 OWNER", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")
    )
    return markup

def get_user_search_markup():
    """User search submenu"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Search by Username/ID", callback_data="search_user"),
        types.InlineKeyboardButton("📱 Find Number from TG ID", callback_data="search_tg_to_num"),
        types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")
    )
    return markup

def get_num_search_markup():
    """Number search submenu"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📱 Search Number Info", callback_data="search_num"),
        types.InlineKeyboardButton("🔍 Advanced Number Lookup", callback_data="search_num_adv"),
        types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")
    )
    return markup

def get_insta_search_markup():
    """Instagram search submenu"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📸 Profile Info", callback_data="search_insta"),
        types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")
    )
    return markup

def get_stats_markup():
    """Stats display with back button"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 Refresh", callback_data="menu_stats"),
        types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")
    )
    return markup

def get_premium_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 USER SEARCH", callback_data="search_user"),
        types.InlineKeyboardButton("📱 NUM OSINT", callback_data="search_num"),
        types.InlineKeyboardButton("📸 INSTAGRAM INFO", callback_data="search_insta"),
        types.InlineKeyboardButton("📊 STATS", callback_data="show_stats"),
        types.InlineKeyboardButton("👑 OWNER", url=f"https://t.me/{OWNER_USERNAME.replace('@','')}")
    )
    return markup

def get_admin_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 DB STATS", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 BAN USER", callback_data="admin_ban"),
        types.InlineKeyboardButton("✅ UNBAN USER", callback_data="admin_unban")
    )
    markup.add(
        types.InlineKeyboardButton("👤 GET USER INFO", callback_data="admin_userinfo"),
        types.InlineKeyboardButton("📄 EXPORT USERS", callback_data="admin_export")
    )
    markup.add(
        types.InlineKeyboardButton("⭐ GIVE PREMIUM", callback_data="admin_give_premium"),
        types.InlineKeyboardButton("📊 USER SEARCH LOGS", callback_data="admin_user_logs"),
        types.InlineKeyboardButton("🚪 LOGOUT", callback_data="admin_logout")
    )
    return markup

def advanced_animation(chat_id, action_text):
    bot.send_chat_action(chat_id, 'typing')
    time.sleep(0.5)
    sent_msg = bot.send_message(chat_id, "📡 `[■□□□□□□□□□] 10% - Connecting...`", parse_mode="Markdown")
    frames = [
        f"⏳ `[■■■□□□□□□□] 30% - Locating {action_text}...`",
        f"🔎 `[■■■■■□□□□□] 50% - Scanning Database...`",
        f"📂 `[■■■■■■■□□□] 70% - Fetching Records...`",
        f"⚙️ `[■■■■■■■■■□] 90% - Formatting Data...`",
        f"✅ `[■■■■■■■■■■] 100% - Displaying Results...`"
    ]
    for frame in frames:
        time.sleep(0.5)
        try:
            bot.edit_message_text(frame, chat_id, sent_msg.message_id, parse_mode="Markdown")
        except:
            pass
    return sent_msg.message_id

def format_osint_data(data_list, source="general"):
    if not isinstance(data_list, list):
        data_list = [data_list]

    unique_results = []
    seen = set()

    for entry in data_list:
        entry_str = str(entry)
        if entry_str not in seen:
            unique_results.append(entry)
            seen.add(entry_str)

    final_text = ""
    for i, item in enumerate(unique_results, 1):
        final_text += f"👤 **RESULT #{i}**\n"
        final_text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        for key, val in item.items():
            if val and str(val).strip() and val != "None":
                display_key = key.replace('_', ' ').title()
                if 'aadhar' in key.lower():
                    final_text += f"🔹 **{display_key}:** `{val}`\n"
                else:
                    final_text += f"🔹 **{display_key}:** `{val}`\n"
        final_text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    return final_text if final_text else "❌ No data found in database."

def format_instagram_data(data):
    if not data or "error" in data:
        return "❌ Instagram user not found or API error."

    text = (
        f"📸 **INSTAGRAM PROFILE INFO**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👤 **Username:** `{data.get('username', 'N/A')}`\n"
        f"📝 **Full Name:** `{data.get('full_name', 'N/A')}`\n"
        f"📜 **Bio:** `{data.get('bio', 'N/A')}`\n"
        f"👥 **Followers:** `{data.get('followers', 'N/A'):,}`\n"
        f"👣 **Following:** `{data.get('following', 'N/A'):,}`\n"
        f"🔒 **Private:** `{'Yes' if data.get('is_private') else 'No'}`\n"
        f"✅ **Verified:** `{'Yes' if data.get('is_verified') else 'No'}`\n"
        f"🆔 **User ID:** `{data.get('id', 'N/A')}`\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🖼️ **Profile Image:** [Link]({data.get('profile_image', '#')})"
    )
    return text

def format_tg_to_num_data(data):
    if not data.get("success"):
        return "❌ Telegram user not found."

    info = data.get("data", {})
    basic = info.get("BASIC_INFO", {})
    number = info.get("NUMBER_INFO", {})
    activity = info.get("ACTIVITY_INFO", {})

    text = (
        f"📡 **TELEGRAM TO NUMBER OSINT**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👤 **Name:** `{basic.get('FIRST_NAME', 'N/A')}`\n"
        f"🆔 **User ID:** `{basic.get('ID', 'N/A')}`\n"
        f"📱 **Phone:** `+{number.get('COUNTRY_CODE', '')}{number.get('NUMBER', '')}`\n"
        f"🌍 **Country:** `{number.get('COUNTRY', 'N/A')}`\n"
        f"📊 **Total Groups:** `{activity.get('TOTAL_GROUPS', 0)}`\n"
        f"💬 **Total Messages:** `{activity.get('TOTAL_MSG_COUNT', 0)}`\n"
        f"🕐 **First Seen:** `{activity.get('FIRST_MSG_DATE', 'N/A')[:10]}`\n"
        f"⚡ **Active:** `{'Yes' if info.get('STATUS_INFO', {}).get('IS_ACTIVE') else 'No'}`\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🔗 **API By:** `{data.get('API BY', 'Unknown')}`"
    )
    return text

def format_tg_num_backup(data):
    try:
        results = data.get("results", {}).get("results", {})
        if results:
            text = (
                f"📞 **TELEGRAM TO NUMBER (BACKUP)**\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                f"📱 **Number:** `{results.get('n', 'N/A')}`\n"
                f"🌍 **Country:** `{results.get('c', 'N/A')}`\n"
                f"🔢 **Country Code:** `{results.get('cc', 'N/A')}`\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
            )
            return text
        return "❌ No data found."
    except:
        return "❌ Backup API error."

def format_num_to_info(data):
    if not data or not isinstance(data, list):
        return "❌ No information found for this number."
    return format_osint_data(data, "number")

def send_stats_message(chat_id):
    total_users = len(users)
    banned_count = len(banned_users)
    premium_count = len(user_premium)

    lifetime = sum(1 for p in user_premium.values() if p["type"] == "lifetime")
    month = sum(1 for p in user_premium.values() if p["type"] == "month")
    day = sum(1 for p in user_premium.values() if p["type"] == "day")

    stats_text = (
        f"📊 **BEELZEBUB OSINT STATISTICS**\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👥 **Total Users:** `{total_users}`\n"
        f"🚫 **Banned Users:** `{banned_count}`\n"
        f"⭐ **Premium Users:** `{premium_count}`\n"
        f"   ├─ Lifetime: `{lifetime}`\n"
        f"   ├─ Monthly: `{month}`\n"
        f"   └─ Daily: `{day}`\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"👑 **Owner:** {OWNER_NAME}\n"
        f"🔗 **Channel:** {CHANNEL_ID}"
    )
    bot.send_message(chat_id, stats_text, parse_mode="Markdown")

# --- ADMIN COMMANDS ---
@bot.message_handler(commands=['admin'])
def admin_login(message):
    user_id = message.chat.id
    if str(user_id) != ADMIN_CHAT_ID:
        bot.send_message(user_id, "❌ You are not authorized to use admin commands.")
        return

    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(user_id, "🔐 **Admin Login**\nUsage: `/admin <password>`", parse_mode="Markdown")
        return

    password = parts[1]
    if password == ADMIN_PASSWORD:
        admin_logged_in.add(user_id)
        bot.send_message(
            user_id,
            "✅ **Admin Login Successful!**\n\n"
            "🛡️ **BEELZEBUB ADMIN PANEL**\n"
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            "Welcome back, Admin.\n"
            "Use the buttons below to manage the bot:",
            reply_markup=get_admin_markup(),
            parse_mode="Markdown"
        )
    else:
        bot.send_message(user_id, "❌ **Invalid Password!** Access Denied.", parse_mode="Markdown")

@bot.message_handler(commands=['logout'])
def admin_logout(message):
    user_id = message.chat.id
    if user_id in admin_logged_in:
        admin_logged_in.discard(user_id)
        bot.send_message(user_id, "🔒 **Logged out successfully.**", parse_mode="Markdown")
    else:
        bot.send_message(user_id, "❌ You are not logged in as admin.")

# --- USER BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.chat.id
    if uid in banned_users:
        return bot.send_message(uid, "🚫 **Access Denied.** You have been banned from using this bot.")

    is_new = uid not in users
    users.add(uid)

    if is_new:
        username = message.from_user.username or "No username"
        first_name = message.from_user.first_name or ""
        notify_admin_new_user(uid, username, first_name)

    if is_subscribed(uid):
        remaining = get_remaining_searches(uid)
        welcome_text = (
            f"🦋 **WELCOME TO BEELZEBUB OSINT v5**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👑 **Owner:** {OWNER_NAME}\n"
            f"🔗 **Channel:** {CHANNEL_ID}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📊 **Free Searches Left:** `{remaining}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"Select a search method below:"
        )
        bot.send_message(uid, welcome_text, reply_markup=get_main_menu_markup(), parse_mode="Markdown")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_ID))
        markup.add(types.InlineKeyboardButton("✅ Verify Join", callback_data="verify_join"))
        bot.send_message(uid, "⚠️ **ACCESS LOCKED**\n\nJoin our channel to use the OSINT tools.", reply_markup=markup, parse_mode="Markdown")

# ========== PER BUTTON DISPLAY CALLBACK ROUTER ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    uid = call.message.chat.id

    # Handle admin callbacks
    if str(uid) == ADMIN_CHAT_ID and uid in admin_logged_in:
        if call.data.startswith("admin_"):
            handle_admin_callbacks(call)
            return

    # ===== PER BUTTON DISPLAY SECTION =====

    # Back to main menu
    if call.data == "back_menu":
        remaining = get_remaining_searches(uid)
        welcome_text = (
            f"🦋 **BEELZEBUB OSINT MAIN MENU**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📊 **Free Searches Left:** `{remaining}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"Select a search method below:"
        )
        try:
            bot.edit_message_text(welcome_text, uid, call.message.message_id, 
                                reply_markup=get_main_menu_markup(), parse_mode="Markdown")
        except:
            bot.send_message(uid, welcome_text, reply_markup=get_main_menu_markup(), parse_mode="Markdown")
        bot.answer_callback_query(call.id, "🏠 Main Menu")
        return

    # USER SEARCH BUTTON DISPLAY
    elif call.data == "menu_user":
        text = (
            f"🔍 **USER SEARCH OPTIONS**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📌 **Search by Username/ID** - Find user details\n"
            f"📌 **Find Number from TG ID** - Get phone from Telegram ID\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"💡 Choose an option below:"
        )
        try:
            bot.edit_message_text(text, uid, call.message.message_id,
                                reply_markup=get_user_search_markup(), parse_mode="Markdown")
        except:
            bot.send_message(uid, text, reply_markup=get_user_search_markup(), parse_mode="Markdown")
        bot.answer_callback_query(call.id, "🔍 User Search")
        return

    # NUMBER SEARCH BUTTON DISPLAY
    elif call.data == "menu_num":
        text = (
            f"📱 **NUMBER OSINT OPTIONS**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📌 **Search Number Info** - Basic number lookup\n"
            f"📌 **Advanced Number Lookup** - Deep number search\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"💡 Choose an option below:"
        )
        try:
            bot.edit_message_text(text, uid, call.message.message_id,
                                reply_markup=get_num_search_markup(), parse_mode="Markdown")
        except:
            bot.send_message(uid, text, reply_markup=get_num_search_markup(), parse_mode="Markdown")
        bot.answer_callback_query(call.id, "📱 Number OSINT")
        return

    # INSTAGRAM SEARCH BUTTON DISPLAY
    elif call.data == "menu_insta":
        text = (
            f"📸 **INSTAGRAM INFO OPTIONS**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📌 **Profile Info** - Get Instagram profile details\n"
            f"📌 Username, Bio, Followers, Following, Verified status\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"💡 Choose an option below:"
        )
        try:
            bot.edit_message_text(text, uid, call.message.message_id,
                                reply_markup=get_insta_search_markup(), parse_mode="Markdown")
        except:
            bot.send_message(uid, text, reply_markup=get_insta_search_markup(), parse_mode="Markdown")
        bot.answer_callback_query(call.id, "📸 Instagram Info")
        return

    # STATS BUTTON DISPLAY
    elif call.data == "menu_stats":
        total_users = len(users)
        banned_count = len(banned_users)
        premium_count = len(user_premium)
        lifetime = sum(1 for p in user_premium.values() if p["type"] == "lifetime")
        month = sum(1 for p in user_premium.values() if p["type"] == "month")
        day = sum(1 for p in user_premium.values() if p["type"] == "day")
        remaining = get_remaining_searches(uid)

        text = (
            f"📊 **BOT STATISTICS**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👥 **Total Users:** `{total_users}`\n"
            f"🚫 **Banned Users:** `{banned_count}`\n"
            f"⭐ **Premium Users:** `{premium_count}`\n"
            f"   ├─ Lifetime: `{lifetime}`\n"
            f"   ├─ Monthly: `{month}`\n"
            f"   └─ Daily: `{day}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📊 **Your Searches Left:** `{remaining}`\n"
            f"👑 **Owner:** {OWNER_NAME}\n"
            f"🔗 **Channel:** {CHANNEL_ID}"
        )
        try:
            bot.edit_message_text(text, uid, call.message.message_id,
                                reply_markup=get_stats_markup(), parse_mode="Markdown")
        except:
            bot.send_message(uid, text, reply_markup=get_stats_markup(), parse_mode="Markdown")
        bot.answer_callback_query(call.id, "📊 Stats")
        return

    # Handle verify join
    elif call.data == "verify_join":
        if is_subscribed(uid):
            bot.answer_callback_query(call.id, "✅ Access Granted")
            bot.delete_message(uid, call.message.message_id)
            start_handler(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)
        return

    # ===== ORIGINAL SEARCH HANDLERS =====
    elif call.data == "search_user":
        if not can_search(uid):
            bot.answer_callback_query(call.id, "⚠️ Daily limit reached! Get premium for unlimited searches.", show_alert=True)
            return
        msg = bot.send_message(uid, "🆔 **Enter Username or Chat ID:**\n*(Example: @username or 123456789)*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_user_search)

    elif call.data == "search_tg_to_num":
        if not can_search(uid):
            bot.answer_callback_query(call.id, "⚠️ Daily limit reached! Get premium for unlimited searches.", show_alert=True)
            return
        msg = bot.send_message(uid, "🆔 **Enter Telegram User ID:**\n*(Example: 123456789)*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_tg_to_num_search)

    elif call.data == "search_num":
        if not can_search(uid):
            bot.answer_callback_query(call.id, "⚠️ Daily limit reached! Get premium for unlimited searches.", show_alert=True)
            return
        msg = bot.send_message(uid, "📱 **Enter Mobile Number:**\n*(No country code needed, 10 digits)*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_num_search)

    elif call.data == "search_num_adv":
        if not can_search(uid):
            bot.answer_callback_query(call.id, "⚠️ Daily limit reached! Get premium for unlimited searches.", show_alert=True)
            return
        msg = bot.send_message(uid, "📱 **Enter Mobile Number (Advanced):**\n*(No country code needed, 10 digits)*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_num_search)

    elif call.data == "search_insta":
        if not can_search(uid):
            bot.answer_callback_query(call.id, "⚠️ Daily limit reached! Get premium for unlimited searches.", show_alert=True)
            return
        msg = bot.send_message(uid, "📸 **Enter Instagram Username:**\n*(Without @ symbol)*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_insta_search)

    elif call.data == "show_stats":
        send_stats_message(uid)

def handle_admin_callbacks(call):
    cid = call.message.chat.id

    if call.data == "admin_stats":
        total_users = len(users)
        banned_count = len(banned_users)
        premium_count = len(user_premium)

        lifetime = sum(1 for p in user_premium.values() if p["type"] == "lifetime")
        month = sum(1 for p in user_premium.values() if p["type"] == "month")
        day = sum(1 for p in user_premium.values() if p["type"] == "day")

        text = (
            f"📈 **LIVE DATABASE STATS**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👥 **Total Users:** `{total_users}`\n"
            f"🚫 **Blacklisted:** `{banned_count}`\n"
            f"⭐ **Premium Users:** `{premium_count}`\n"
            f"   ├─ Lifetime: `{lifetime}`\n"
            f"   ├─ Monthly: `{month}`\n"
            f"   └─ Daily: `{day}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        )
        bot.edit_message_text(text, cid, call.message.message_id, parse_mode="Markdown", reply_markup=get_admin_markup())

    elif call.data == "admin_broadcast":
        msg = bot.send_message(cid, "📝 **Enter the message to broadcast:**\n*(Markdown supported)*", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_admin_broadcast)

    elif call.data == "admin_ban":
        msg = bot.send_message(cid, "🚫 **Enter User ID to BAN:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: process_ban_logic(m, True))

    elif call.data == "admin_unban":
        msg = bot.send_message(cid, "✅ **Enter User ID to UNBAN:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: process_ban_logic(m, False))

    elif call.data == "admin_userinfo":
        msg = bot.send_message(cid, "👤 **Enter Target User ID:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_fetch_user_info)

    elif call.data == "admin_export":
        if not users:
            bot.edit_message_text("❌ Database is currently empty.", cid, call.message.message_id, reply_markup=get_admin_markup())
            return
        db_content = f"BEELZEBUB OSINT USERS EXPORT\nExported: {datetime.now()}\n\n" + "\n".join(str(u) for u in users)
        file = io.BytesIO(db_content.encode('utf-8'))
        file.name = f"Beelzebub_Users_{datetime.now().strftime('%Y%m%d')}.txt"
        bot.send_document(cid, file, caption="📄 **Exported User List**", parse_mode="Markdown")
        bot.send_message(cid, "✅ **Export Completed.**", reply_markup=get_admin_markup(), parse_mode="Markdown")

    elif call.data == "admin_give_premium":
        msg = bot.send_message(
            cid,
            "⭐ **GIVE PREMIUM ACCESS**\n"
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            "Send in format:\n"
            "`USER_ID TYPE`\n\n"
            "**Types:** `day`, `month`, `lifetime`\n"
            "Example: `123456789 lifetime`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_give_premium)

    elif call.data == "admin_user_logs":
        msg = bot.send_message(cid, "👤 **Enter User ID to view search logs:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_user_logs)

    elif call.data == "admin_logout":
        admin_logged_in.discard(cid)
        bot.edit_message_text("🔒 **Logged out successfully.**", cid, call.message.message_id, parse_mode="Markdown")

def process_admin_broadcast(message):
    if not is_admin(message.chat.id):
        return
    count = 0
    failed = 0
    for u in users:
        try:
            bot.send_message(u, f"🔔 **SYSTEM ALERT**\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n{message.text}", parse_mode="Markdown")
            count += 1
        except:
            failed += 1
    bot.send_message(message.chat.id, f"✅ **Broadcast Completed!**\n📨 Delivered to: `{count}` users\n❌ Failed: `{failed}`", parse_mode="Markdown", reply_markup=get_admin_markup())

def process_ban_logic(message, is_ban):
    if not is_admin(message.chat.id):
        return
    try:
        target = int(message.text.strip())
        if is_ban:
            banned_users.add(target)
            bot.send_message(message.chat.id, f"🚫 Target `{target}` successfully **BANNED**.", parse_mode="Markdown", reply_markup=get_admin_markup())
            try:
                bot.send_message(target, "🚫 You have been **BANNED** from using Beelzebub OSINT bot.")
            except:
                pass
        else:
            banned_users.discard(target)
            bot.send_message(message.chat.id, f"✅ Target `{target}` successfully **UNBANNED**.", parse_mode="Markdown", reply_markup=get_admin_markup())
            try:
                bot.send_message(target, "✅ You have been **UNBANNED** from Beelzebub OSINT bot.")
            except:
                pass
    except:
        bot.send_message(message.chat.id, "❌ **Invalid ID provided.**", parse_mode="Markdown", reply_markup=get_admin_markup())

def process_fetch_user_info(message):
    if not is_admin(message.chat.id):
        return
    try:
        target = int(message.text.strip())
        user_info = bot.get_chat(target)

        name = user_info.first_name or ""
        if user_info.last_name:
            name += f" {user_info.last_name}"
        username = f"@{user_info.username}" if user_info.username else "No Username"
        bio = user_info.bio if user_info.bio else "N/A"
        is_banned = "🔴 YES" if target in banned_users else "🟢 NO"

        premium_status = "❌ None"
        if target in user_premium:
            p = user_premium[target]
            if p["type"] == "lifetime":
                premium_status = "⭐ Lifetime"
            elif p["type"] == "month":
                expiry_str = p["expiry"].strftime("%Y-%m-%d") if p["expiry"] else "N/A"
                premium_status = f"📅 Monthly (expires: {expiry_str})"
            elif p["type"] == "day":
                expiry_str = p["expiry"].strftime("%Y-%m-%d") if p["expiry"] else "N/A"
                premium_status = f"📆 Daily (expires: {expiry_str})"

        daily_info = get_daily_search_count(target)

        info_text = (
            f"👤 **TARGET INTEL GATHERED**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🆔 **User ID:** `{target}`\n"
            f"📝 **Full Name:** `{name.strip()}`\n"
            f"🔗 **Username:** `{username}`\n"
            f"📜 **Bio:** `{bio}`\n"
            f"⚠️ **Blacklisted:** `{is_banned}`\n"
            f"⭐ **Premium:** `{premium_status}`\n"
            f"📊 **Searches Today:** `{daily_info}/5`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        )
        bot.send_message(message.chat.id, info_text, parse_mode="Markdown", reply_markup=get_admin_markup())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ **User not found.**\nError: {str(e)[:100]}", parse_mode="Markdown", reply_markup=get_admin_markup())

def process_give_premium(message):
    if not is_admin(message.chat.id):
        return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ **Invalid format!** Use: `USER_ID TYPE`", parse_mode="Markdown", reply_markup=get_admin_markup())
            return

        user_id = int(parts[0])
        premium_type = parts[1].lower()

        if premium_type not in ["day", "month", "lifetime"]:
            bot.send_message(message.chat.id, "❌ **Invalid type!** Use: `day`, `month`, or `lifetime`", parse_mode="Markdown", reply_markup=get_admin_markup())
            return

        if premium_type == "day":
            expiry = datetime.now() + timedelta(days=1)
        elif premium_type == "month":
            expiry = datetime.now() + timedelta(days=30)
        else:
            expiry = None

        user_premium[user_id] = {"type": premium_type, "expiry": expiry}

        expiry_str = "Never" if expiry is None else expiry.strftime("%Y-%m-%d %H:%M:%S")
        bot.send_message(
            message.chat.id,
            f"✅ **Premium Granted!**\n"
            f"👤 User: `{user_id}`\n"
            f"⭐ Type: `{premium_type}`\n"
            f"📅 Expires: `{expiry_str}`",
            parse_mode="Markdown", reply_markup=get_admin_markup()
        )

        try:
            bot.send_message(
                user_id,
                f"🎉 **CONGRATULATIONS!**\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                f"You have been granted **{premium_type.upper()} PREMIUM** access!\n"
                f"✨ Enjoy unlimited OSINT searches.\n"
                f"👑 Thank you for choosing Beelzebub OSINT!",
                parse_mode="Markdown"
            )
        except:
            pass

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}", parse_mode="Markdown", reply_markup=get_admin_markup())

def process_user_logs(message):
    if not is_admin(message.chat.id):
        return
    try:
        user_id = int(message.text.strip())
        searches = get_daily_search_count(user_id)
        today = datetime.now().strftime("%Y-%m-%d")

        text = (
            f"📊 **USER SEARCH LOGS**\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📅 **Date:** `{today}`\n"
            f"🔍 **Searches Used:** `{searches}/5`\n"
            f"⭐ **Premium:** `{'Yes' if user_id in user_premium else 'No'}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_admin_markup())
    except:
        bot.send_message(message.chat.id, "❌ Invalid User ID!", parse_mode="Markdown", reply_markup=get_admin_markup())

def process_user_search(message):
    uid = message.chat.id
    if uid in banned_users:
        return bot.send_message(uid, "🚫 You are banned from using this bot.")

    if not can_search(uid):
        return bot.send_message(uid, "⚠️ **Daily limit reached!** Contact owner for premium access.")

    query = message.text.replace("@", "").strip()
    increment_daily_search(uid)
    mid = advanced_animation(uid, "User Database")

    try:
        res = requests.get(f"{USER_API}{query}", timeout=15).json()
        data = res.get("result", [])

        tg_backup = requests.get(f"{TG_TO_NUM_BACKUP_API}{query}", timeout=10)
        if tg_backup.status_code == 200:
            backup_data = tg_backup.json()
            backup_text = format_tg_num_backup(backup_data)
            final_text = format_osint_data(data) + "\n" + backup_text
        else:
            final_text = format_osint_data(data)

        bot.edit_message_text(final_text, uid, mid, parse_mode="Markdown")
        remaining = get_remaining_searches(uid)
        bot.send_message(uid, f"📊 **Remaining free searches:** `{remaining}`", parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text("❌ System error or user not found.", uid, mid)

def process_tg_to_num_search(message):
    uid = message.chat.id
    if uid in banned_users:
        return bot.send_message(uid, "🚫 You are banned from using this bot.")

    if not can_search(uid):
        return bot.send_message(uid, "⚠️ **Daily limit reached!** Contact owner for premium access.")

    tg_id = message.text.strip()
    increment_daily_search(uid)
    mid = advanced_animation(uid, "Telegram to Number")

    try:
        res = requests.get(f"{TG_TO_NUM_API}{tg_id}", timeout=15)
        if res.status_code == 200:
            data = res.json()
            final_text = format_tg_to_num_data(data)
        else:
            backup = requests.get(f"{TG_TO_NUM_BACKUP_API}{tg_id}", timeout=10)
            if backup.status_code == 200:
                data = backup.json()
                final_text = format_tg_num_backup(data)
            else:
                final_text = "❌ Telegram user not found or API error."

        bot.edit_message_text(final_text, uid, mid, parse_mode="Markdown")
        remaining = get_remaining_searches(uid)
        bot.send_message(uid, f"📊 **Remaining free searches:** `{remaining}`", parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text("❌ Connection error. Try again.", uid, mid)

def process_num_search(message):
    uid = message.chat.id
    if uid in banned_users:
        return bot.send_message(uid, "🚫 You are banned from using this bot.")

    if not can_search(uid):
        return bot.send_message(uid, "⚠️ **Daily limit reached!** Contact owner for premium access.")

    num = clean_number(message.text.strip())
    increment_daily_search(uid)
    mid = advanced_animation(uid, "Number Logs")

    try:
        # Try NEW_NUM_API first
        new_api_url = NEW_NUM_API.format(num)
        res = requests.get(new_api_url, timeout=15)

        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                result_data = data.get("result", [])
                final_text = format_osint_data(result_data)
            else:
                # Fallback to NUM_API
                res2 = requests.get(f"{NUM_API}{num}", timeout=15).json()
                data2 = res2.get("result", []) if 'result' in res2 else res2
                final_text = format_osint_data(data2)
        else:
            # Fallback to NUM_API
            res2 = requests.get(f"{NUM_API}{num}", timeout=15).json()
            data2 = res2.get("result", []) if 'result' in res2 else res2
            final_text = format_osint_data(data2)

        # NEW NUM_TO_INFO_API - movements-invoice API
        backup_url = NUM_TO_INFO_API.format(num)
        backup_res = requests.get(backup_url, timeout=10)
        if backup_res.status_code == 200:
            backup_data = backup_res.json()
            if backup_data.get("status") == "success":
                backup_result = backup_data.get("result", [])
                if backup_result and isinstance(backup_result, list) and backup_result:
                    backup_text = format_osint_data(backup_result, "number_backup")
                    final_text += "\n\n📡 **ADDITIONAL NUMBER INFO**\n" + backup_text

        bot.edit_message_text(final_text, uid, mid, parse_mode="Markdown")
        remaining = get_remaining_searches(uid)
        bot.send_message(uid, f"📊 **Remaining free searches:** `{remaining}`", parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text("❌ Connection error. Try again.", uid, mid)

def process_insta_search(message):
    uid = message.chat.id
    if uid in banned_users:
        return bot.send_message(uid, "🚫 You are banned from using this bot.")

    if not can_search(uid):
        return bot.send_message(uid, "⚠️ **Daily limit reached!** Contact owner for premium access.")

    username = message.text.strip().replace("@", "")
    increment_daily_search(uid)
    mid = advanced_animation(uid, "Instagram Profile")

    try:
        res = requests.get(f"{INSTA_API}{username}", timeout=15)
        if res.status_code == 200:
            data = res.json()
            final_text = format_instagram_data(data)
        else:
            final_text = "❌ Instagram API error. User may not exist."

        bot.edit_message_text(final_text, uid, mid, parse_mode="Markdown")
        remaining = get_remaining_searches(uid)
        bot.send_message(uid, f"📊 **Remaining free searches:** `{remaining}`", parse_mode="Markdown")

    except Exception as e:
        bot.edit_message_text("❌ Connection error. Try again.", uid, mid)

if __name__ == "__main__":
    print("🚀 Starting Beelzebub OSINT Bot v5...")
    print(f"👑 Owner: {OWNER_NAME}")
    print(f"🔗 Channel: {CHANNEL_ID}")
    print(f"🔐 Admin Password: {ADMIN_PASSWORD}")
    print("✅ Bot is running!")

    bot.infinity_polling()
