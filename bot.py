import os
import json
import uuid
import random
import logging
import auction
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    ChatMemberHandler,
)

BOT_TOKEN = "8337172181:AAGUqm1uJvGQp4SJbSuGRPEHQSLTINmlJGU"
DATA_FILE = "/mnt/data/auction_bot_data.json"
if not os.path.exists(DATA_FILE):
    DATA_FILE = "auction_bot_data.json"

ADMINS = {1766243373, 7995262033, 5609353982, 8387898150, 7879993882}
FUN_ZONE_ID = -1002273742602
FUN_ZONE_USERNAME = "CLG_fun_zone"
MANAGEMENT_GROUP_ID = -1002922201045
MANAGEMENT_GROUP_LINK = "https://t.me/+qzPLCtIuLaA4ZjQ9"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        base = {
            "tournaments": {},
            "started_users": {},
            "known_groups": {},
            "mg_map": {},
            "management_chat_id": None,
            "admin_add_tmp": {},
            "pending_remove": {},
            "reset_tokens": {},
            "last_broadcast": None,
        }
        save_data(base)
        return base
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            base = {
                "tournaments": {},
                "started_users": {},
                "known_groups": {},
                "mg_map": {},
                "management_chat_id": None,
                "admin_add_tmp": {},
                "pending_remove": {},
                "reset_tokens": {},
                "last_broadcast": None,
            }
            save_data(base)
            return base

def save_data(data: dict):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)

DATA = load_data()

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in ADMINS:
            try:
                await (update.effective_message or update.message).reply_text("⚠️ You are not authorized to use this command.")
            except Exception:
                pass
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

async def record_start_user(user):
    if not user:
        return
    DATA.setdefault("started_users", {})[str(user.id)] = {
        "id": user.id,
        "first_name": user.first_name or "",
        "username": user.username or ""
    }
    save_data(DATA)

async def record_group(chat):
    if not chat:
        return
    DATA.setdefault("known_groups", {})[str(chat.id)] = {"id": chat.id, "title": chat.title or str(chat.id)}
    save_data(DATA)

def generate_unique_code() -> str:
    existing = set()
    for t in DATA.get("tournaments", {}).values():
        for r in t.get("registrations", []):
            if r.get("player_code"):
                existing.add(r.get("player_code"))
    for _ in range(1000):
        code = f"{random.randint(0, 999):03d}"
        if code not in existing:
            return code
    return f"{random.randint(0,999):03d}"

def find_posted_tournament():
    for tid, t in DATA.get("tournaments", {}).items():
        if t.get("is_posted"):
            return t
    last = DATA.get("last_broadcast")
    if last:
        tid = last.get("tournament_id")
        if tid:
            t = DATA.get("tournaments", {}).get(tid)
            if t:
                return t
        tmp_id = "__auto_posted__"
        if tmp_id not in DATA.get("tournaments", {}):
            DATA.setdefault("tournaments", {})[tmp_id] = {
                "id": tmp_id,
                "name": last.get("title") or "Broadcast Tournament",
                "spots": last.get("spots", 100),
                "owner_token": last.get("owner_token"),
                "register_token": last.get("register_token"),
                "owner_chat_id": None,
                "registrations": [],
                "pending": {},
                "is_posted": True,
                "registration_open": False
            }
            save_data(DATA)
        return DATA["tournaments"][tmp_id]
    return None

async def check_in_fun_zone(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(FUN_ZONE_ID, user_id)
        status = (member.status or "").lower()
        if status in ("member", "administrator", "creator", "restricted"):
            return True
    except Exception:
        pass
    urec = DATA.get("started_users", {}).get(str(user_id))
    uname = urec.get("username") if urec else None
    if uname:
        try:
            chat = await context.bot.get_chat("@" + uname.lstrip("@"))
            if getattr(chat, "id", None):
                try:
                    m = await context.bot.get_chat_member(FUN_ZONE_ID, chat.id)
                    if (m.status or "").lower() in ("member", "administrator", "creator", "restricted"):
                        return True
                except Exception:
                    pass
        except Exception:
            pass
    for gid_str in list(DATA.get("known_groups", {}).keys()):
        try:
            gid = int(gid_str)
        except Exception:
            continue
        try:
            cm = await context.bot.get_chat_member(gid, user_id)
            if (cm.status or "").lower() in ("member", "administrator", "creator", "restricted"):
                if gid == FUN_ZONE_ID:
                    return True
        except Exception:
            continue
    return False

BOT_NAME = "ᎪᏟᎬᏴᏬᎠᎠᎽ"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await record_start_user(user)
    text = (
        f'👋 Hey <a href="tg://user?id={user.id}">{user.first_name}</a>, welcome to the 🌟 <b>{BOT_NAME}</b> 🌟!\n\n'
        "🏏 This bot is made for the <b>upcoming & ongoing Legacy Cricket Tournament registrations</b> 🎟️\n\n"
        "🔥 Step into the legacy journey — where passion meets cricket and dreams turn into history ✨\n\n"
        "📢 Stay updated with match schedules, team line-ups & thrilling tournament moments 📅\n\n"
        "⚡️ Experience the spirit of cricket like never before — pure excitement, pure legacy 🏆\n\n"
        "🌍 Connect with players, teams & fans across the cricket community 🤝\n\n"
        "🚀 Get ready to start your unforgettable journey in the <b>Legacy Cricket Tournament</b> 🌟"
    )
    await update.message.reply_text(text, parse_mode="HTML")

@admin_only
async def broad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    if msg.reply_to_message:
        orig = msg.reply_to_message
        for gid_str in list(DATA.get("known_groups", {}).keys()):
            try:
                gid = int(gid_str)
            except Exception:
                continue
            try:
                await context.bot.copy_message(chat_id=gid, from_chat_id=orig.chat.id, message_id=orig.message_id)
            except Exception:
                continue
        try:
            await context.bot.copy_message(chat_id=FUN_ZONE_ID, from_chat_id=orig.chat.id, message_id=orig.message_id)
        except Exception:
            try:
                chat = await context.bot.get_chat(FUN_ZONE_USERNAME)
                if getattr(chat, "id", None):
                    await context.bot.copy_message(chat_id=chat.id, from_chat_id=orig.chat.id, message_id=orig.message_id)
            except Exception:
                pass
        try:
            await context.bot.copy_message(chat_id=MANAGEMENT_GROUP_ID, from_chat_id=orig.chat.id, message_id=orig.message_id)
        except Exception:
            try:
                stored = DATA.get("management_chat_id")
                if stored:
                    await context.bot.copy_message(chat_id=int(stored), from_chat_id=orig.chat.id, message_id=orig.message_id)
            except Exception:
                pass
        for uid_str in list(DATA.get("started_users", {}).keys()):
            try:
                uid = int(uid_str)
            except Exception:
                continue
            try:
                await context.bot.copy_message(chat_id=uid, from_chat_id=orig.chat.id, message_id=orig.message_id)
            except Exception:
                try:
                    text = orig.text or (orig.caption or "")
                    if text:
                        await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
                except Exception:
                    continue
        last = {
            "chat_id": orig.chat.id,
            "message_id": orig.message_id,
            "title": (orig.text or "").split("\n",1)[0] if getattr(orig, "text", None) else "Broadcast",
        }
        matched_tid = None
        search_text = (orig.text or "").lower() if getattr(orig, "text", None) else ""
        for tid, t in DATA.get("tournaments", {}).items():
            if t.get("name") and t.get("name").lower() in search_text:
                matched_tid = tid
                t["is_posted"] = True
                DATA["last_broadcast"] = {**last, "tournament_id": tid}
                save_data(DATA)
                break
        if not matched_tid:
            DATA["last_broadcast"] = last
            save_data(DATA)
        try:
            await msg.reply_text("✅ Broadcast posted everywhere (attempted).")
        except Exception:
            pass
        return
    parts = (msg.text or "").split(" ", 1)
    content = parts[1] if len(parts) > 1 else ""
    if not content:
        await msg.reply_text("Usage: reply to a message with /broad or run /broad <text>")
        return
    for gid_str in list(DATA.get("known_groups", {}).keys()):
        try:
            gid = int(gid_str)
        except Exception:
            continue
        try:
            await context.bot.send_message(chat_id=gid, text=content, parse_mode="HTML")
        except Exception:
            continue
    try:
        await context.bot.send_message(chat_id=FUN_ZONE_ID, text=content, parse_mode="HTML")
    except Exception:
        try:
            chat = await context.bot.get_chat(FUN_ZONE_USERNAME)
            if getattr(chat, "id", None):
                await context.bot.send_message(chat_id=chat.id, text=content, parse_mode="HTML")
        except Exception:
            pass
    try:
        await context.bot.send_message(chat_id=MANAGEMENT_GROUP_ID, text=content, parse_mode="HTML")
    except Exception:
        try:
            stored = DATA.get("management_chat_id")
            if stored:
                await context.bot.send_message(chat_id=int(stored), text=content, parse_mode="HTML")
        except Exception:
            pass
    for uid_str in list(DATA.get("started_users", {}).keys()):
        try:
            uid = int(uid_str)
        except Exception:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=content, parse_mode="HTML")
        except Exception:
            continue
    DATA["last_broadcast"] = {"title": content[:120]}
    save_data(DATA)
    await msg.reply_text("✅ Broadcast sent.")

@admin_only
async def start_reg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    tourn = find_posted_tournament()
    if not tourn:
        await msg.reply_text("⚠️ No posted tournament found. Use /broad (reply to tournament post) first.")
        return
    tourn["registration_open"] = True
    save_data(DATA)
    notify = (
        "🎉 <b>REGISTRATION OPEN — LET THE AUCTION BEGIN!</b> 🎉\n\n"
        f"🏷️ Tournament: <b>{tourn.get('name','Tournament')}</b>\n\n"
        "🔔 Registration is now OPEN. Head to your bot DM and use /register to join the tournament now! Good luck and happy bidding! 🏏💰"
    )
    for uid_str in list(DATA.get("started_users", {}).keys()):
        try:
            uid = int(uid_str)
        except Exception:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=notify, parse_mode="HTML")
        except Exception:
            continue
    await msg.reply_text("✅ Registration started and all known users notified (attempted).")

@admin_only
async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    tourn = find_posted_tournament()
    if not tourn:
        await msg.reply_text("No posted tournament found.")
        return
    tourn["registration_open"] = False
    save_data(DATA)
    await msg.reply_text("⛔ Registration closed.")

@admin_only
async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    tourn = find_posted_tournament()
    if not tourn:
        await msg.reply_text("No posted tournament found.")
        return
    tourn["registration_open"] = True
    save_data(DATA)
    await msg.reply_text("▶️ Registration resumed.")

@admin_only
async def registered_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    tourn = find_posted_tournament()
    if not tourn:
        await msg.reply_text("No posted tournament.")
        return
    regs = tourn.get("registrations", [])
    visible = [r for r in regs if r.get("status") in ("accepted", "accepted_pending", "requested")]
    per_page = 10
    total = len(visible)
    pages = max(1, (total + per_page - 1) // per_page)
    page = 1
    start = (page - 1) * per_page
    end = start + per_page
    chunk = visible[start:end]
    lines = ["📋 <b>Tournament Registration List</b>\n"]
    for i, r in enumerate(chunk, start=start + 1):
        uname = f"@{r.get('username')}" if r.get('username') else "-"
        pc = r.get("player_code") or "-"
        tid = r.get("user_id") or "-"
        lines.append(f"({i})\nName: {r.get('name')}\nUsername: {uname}\nTelegram ID: {tid}\nRole: {r.get('role')}\nBase Price: {r.get('price')}\nPlayerCode: {pc}\n")
    lines.append(f"\n✅ Total Players Registered: {total}")
    kb = []
    prev_cb = InlineKeyboardButton("◀ Previous", callback_data=f"reglist|{tourn.get('id')}|{max(1,page-1)}")
    stats_cb = InlineKeyboardButton("Status", callback_data=f"regstats|{tourn.get('id')}|{page}")
    next_cb = InlineKeyboardButton("Next ▶", callback_data=f"reglist|{tourn.get('id')}|{min(pages,page+1)}")
    kb.append([prev_cb, stats_cb, next_cb])
    kb.append([InlineKeyboardButton("Close", callback_data=f"reglist_close|{tourn.get('id')}")])
    await msg.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def reglist_cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    if data.startswith("reglist_close|"):
        try:
            await cq.edit_message_text("Closed.")
        except Exception:
            pass
        return
    if data.startswith("regstats|"):
        parts = data.split("|")
        if len(parts) < 3:
            await cq.answer("Invalid.")
            return
        _, tid, page_str = parts[0], parts[1], parts[2]
        tourn = DATA.get("tournaments", {}).get(tid) or find_posted_tournament()
        if not tourn:
            await cq.edit_message_text("Tournament not found.")
            return
        regs = tourn.get("registrations", [])
        visible = [r for r in regs if r.get("status") in ("accepted", "accepted_pending", "requested")]
        role_counts = {}
        country_counts = {}
        for r in visible:
            role = r.get("role") or "Unknown"
            role_counts[role] = role_counts.get(role, 0) + 1
            country = r.get("country")
            if country:
                country_counts[country] = country_counts.get(country, 0) + 1
        lines = ["📊 <b>Registration Status Summary</b>\n"]
        lines.append("<b>By Role:</b>")
        for k, v in role_counts.items():
            lines.append(f"{k} → {v}")
        if country_counts:
            lines.append("\n<b>By Country:</b>")
            for k, v in country_counts.items():
                lines.append(f"{k} → {v}")
        else:
            lines.append("\nCountry data not available.")
        try:
            await cq.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to list", callback_data=f"reglist|{tourn.get('id')}|1")]]))
        except Exception:
            pass
        return
    parts = data.split("|")
    if len(parts) < 3:
        await cq.answer("Invalid.")
        return
    _, tid, page_str = parts[0], parts[1], parts[2]
    try:
        page = int(page_str)
    except Exception:
        page = 1
    tourn = DATA.get("tournaments", {}).get(tid) or find_posted_tournament()
    if not tourn:
        await cq.edit_message_text("Tournament not found.")
        return
    regs = tourn.get("registrations", [])
    visible = [r for r in regs if r.get("status") in ("accepted", "accepted_pending", "requested")]
    per_page = 10
    total = len(visible)
    pages = max(1, (total + per_page - 1) // per_page)
    if page < 1:
        page = 1
    if page > pages:
        page = pages
    start = (page - 1) * per_page
    end = start + per_page
    chunk = visible[start:end]
    lines = ["📋 <b>Tournament Registration List</b>\n"]
    for i, r in enumerate(chunk, start=start + 1):
        uname = f"@{r.get('username')}" if r.get('username') else "-"
        pc = r.get("player_code") or "-"
        tidv = r.get("user_id") or "-"
        lines.append(f"({i})\nName: {r.get('name')}\nUsername: {uname}\nTelegram ID: {tidv}\nRole: {r.get('role')}\nBase Price: {r.get('price')}\nPlayerCode: {pc}\n")
    lines.append(f"\n✅ Total Players Registered: {total}\nPage {page}/{pages}")
    prev_page = max(1, page - 1)
    next_page = min(pages, page + 1)
    prev_cb = InlineKeyboardButton("◀ Previous", callback_data=f"reglist|{tourn.get('id')}|{prev_page}")
    stats_cb = InlineKeyboardButton("Status", callback_data=f"regstats|{tourn.get('id')}|{page}")
    next_cb = InlineKeyboardButton("Next ▶", callback_data=f"reglist|{tourn.get('id')}|{next_page}")
    kb = [[prev_cb, stats_cb, next_cb], [InlineKeyboardButton("Close", callback_data=f"reglist_close|{tourn.get('id')}")]]
    try:
        await cq.edit_message_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
    except Exception:
        pass

async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        try:
            await update.message.reply_text("Please use /register in a private chat with the bot.")
        except Exception:
            pass
        return
    user = update.effective_user
    if not user:
        return
    await record_start_user(user)
    tourn = find_posted_tournament()
    if not tourn:
        await update.message.reply_text("❌ No active posted tournament. Please wait for admin /broad.")
        return
    if not tourn.get("registration_open"):
        await update.message.reply_text("⏳ Registration is not open currently.")
        return
    def has_active(u_id: int, tournament: dict):
        for r in tournament.get("registrations", []):
            if r.get("user_id") == u_id and r.get("status") not in ("declined", "removed"):
                return r
        for r in tournament.get("pending", {}).values():
            if r.get("user_id") == u_id:
                return r
        return None
    existing = has_active(user.id, tourn)
    if existing:
        status = existing.get("status", "unknown")
        await update.message.reply_text(f"⚠️ You have already registered (status: {status}). You cannot register again.", parse_mode="HTML")
        return
    in_group = await check_in_fun_zone(user.id, context)
    if not in_group:
        text = ('❗ Sorry, you must join our main group to register.\n\n' f'👉 <a href="https://t.me/{FUN_ZONE_USERNAME}">Join Fun Zone</a>')
        await update.message.reply_text(text, parse_mode="HTML")
        return
    name = user.full_name or (user.first_name or "NoName")
    username = (user.username or "").lstrip("@")
    reg_id = uuid.uuid4().hex[:8]
    reg = {
        "id": reg_id,
        "user_id": user.id,
        "name": name,
        "username": username,
        "role": None,
        "price": None,
        "status": "draft",
        "player_code": None,
    }
    tourn.setdefault("pending", {})[reg_id] = reg
    save_data(DATA)
    def build_text(r):
        uname_display = f"@{r['username']}" if r['username'] else "-"
        role_disp = r['role'] if r['role'] else "— not selected —"
        price_disp = r['price'] if r['price'] else "— not selected —"
        return ("<b>Registration Preview</b>\n\n" f"Name: {r['name']}\n" f"Username: {uname_display}\n" f"Role: {role_disp}\n" f"Base Price: {price_disp}\n\n" "Choose role and base price below:")
    kb_roles = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Batsman", callback_data=f"role|{reg_id}|Batsman"),
            InlineKeyboardButton("Bowler", callback_data=f"role|{reg_id}|Bowler"),
            InlineKeyboardButton("All-Rounder", callback_data=f"role|{reg_id}|All-Rounder")
        ]
    ])
    await update.message.reply_text(build_text(reg), parse_mode="HTML", reply_markup=kb_roles)

async def role_cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 3:
        await cq.edit_message_text("Invalid selection.")
        return
    _, reg_id, role_selected = parts[0], parts[1], parts[2]
    tourn = find_posted_tournament()
    if not tourn:
        await cq.edit_message_text("Tournament not found.")
        return
    reg = tourn.setdefault("pending", {}).get(reg_id)
    if not reg:
        await cq.edit_message_text("Registration not found or expired.")
        return
    reg["role"] = role_selected
    save_data(DATA)
    def build_text(r):
        uname_display = f"@{r['username']}" if r['username'] else "-"
        role_disp = r['role'] if r['role'] else "— not selected —"
        price_disp = r['price'] if r['price'] else "— not selected —"
        return ("<b>Registration Preview</b>\n\n" f"Name: {r['name']}\n" f"Username: {uname_display}\n" f"Role: {role_disp}\n" f"Base Price: {price_disp}\n\n" "Choose base price:")
    kb_price = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 CR", callback_data=f"price|{reg_id}|1 CR"),
            InlineKeyboardButton("2 CR", callback_data=f"price|{reg_id}|2 CR"),
            InlineKeyboardButton("3 CR", callback_data=f"price|{reg_id}|3 CR")
        ]
    ])
    await cq.edit_message_text(build_text(reg), parse_mode="HTML", reply_markup=kb_price)

async def price_cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 3:
        await cq.edit_message_text("Invalid selection.")
        return
    _, reg_id, price_selected = parts[0], parts[1], parts[2]
    tourn = find_posted_tournament()
    if not tourn:
        await cq.edit_message_text("Tournament not found.")
        return
    reg = tourn.setdefault("pending", {}).get(reg_id)
    if not reg:
        await cq.edit_message_text("Registration not found or expired.")
        return
    reg["price"] = price_selected
    save_data(DATA)
    def build_text(r):
        uname_display = f"@{r['username']}" if r['username'] else "-"
        role_disp = r['role'] if r['role'] else "— not selected —"
        price_disp = r['price'] if r['price'] else "— not selected —"
        return ("<b>Registration Preview</b>\n\n" f"Name: {r['name']}\n" f"Username: {uname_display}\n" f"Role: {role_disp}\n" f"Base Price: {price_disp}\n\n" "Are you sure you want to submit your registration?")
    kb_confirm = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Submit", callback_data=f"submit|{reg_id}|yes"), InlineKeyboardButton("✏️ Edit", callback_data=f"submit|{reg_id}|edit"), InlineKeyboardButton("❌ Cancel", callback_data=f"submit|{reg_id}|no")]
    ])
    await cq.edit_message_text(build_text(reg), parse_mode="HTML", reply_markup=kb_confirm)

async def submit_cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 3:
        await cq.edit_message_text("Invalid action.")
        return
    _, reg_id, action = parts[0], parts[1], parts[2]
    tourn = find_posted_tournament()
    if not tourn:
        await cq.edit_message_text("Tournament not found.")
        return
    pending = tourn.setdefault("pending", {})
    reg = pending.get(reg_id)
    if not reg:
        await cq.edit_message_text("Registration not found or expired.")
        return
    if action == "no":
        pending.pop(reg_id, None)
        save_data(DATA)
        await cq.edit_message_text("❌ Registration cancelled.")
        return
    if action == "edit":
        kb_roles = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Batsman", callback_data=f"role|{reg_id}|Batsman"),
                InlineKeyboardButton("Bowler", callback_data=f"role|{reg_id}|Bowler"),
                InlineKeyboardButton("All-Rounder", callback_data=f"role|{reg_id}|All-Rounder")
            ]
        ])
        await cq.edit_message_text("<b>Edit Registration</b>\n\nChoose role:", parse_mode="HTML", reply_markup=kb_roles)
        return
    for r in tourn.get("registrations", []):
        if r.get("user_id") == reg["user_id"] and r.get("status") not in ("declined", "removed"):
            pending.pop(reg_id, None)
            save_data(DATA)
            await cq.edit_message_text("⚠️ You already have an active registration.")
            return
    reg["status"] = "requested"
    tourn.setdefault("registrations", []).append(reg)
    pending.pop(reg_id, None)
    save_data(DATA)
    mg_text = ("<b>🆕 New Registration Request</b>\n\n"
               f"Name: {reg['name']}\n"
               f"Username: @{reg['username'] if reg['username'] else '-'}\n"
               f"Telegram ID: {reg['user_id']}\n"
               f"Role: {reg['role']}\n"
               f"Base Price: {reg['price']}\n\n"
               "⤵️ Actions:")
    mg_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Accept", callback_data=f"mg_accept|{reg['id']}|{reg['user_id']}"), InlineKeyboardButton("❌ Decline", callback_data=f"mg_decline|{reg['id']}|{reg['user_id']}")]
    ])
    sent = await send_registration_to_management(context, reg, mg_text, mg_kb)
    try:
        await context.bot.send_message(chat_id=int(reg["user_id"]), text="✅ Your registration request was sent to management. You will be notified after review.", parse_mode="HTML")
    except Exception:
        pass
    if sent:
        await cq.edit_message_text("✅ Registration submitted to management. Management will review it shortly.")
    else:
        await cq.edit_message_text("⚠️ Registration submitted locally but failed to notify management groups. Please contact admins.")

async def send_registration_to_management(context: ContextTypes.DEFAULT_TYPE, reg: dict, mg_text: str, mg_kb: InlineKeyboardMarkup) -> int:
    sent = 0
    try:
        sent_msg = await context.bot.send_message(chat_id=MANAGEMENT_GROUP_ID, text=mg_text, parse_mode="HTML", reply_markup=mg_kb)
        key = f"{sent_msg.chat.id}:{sent_msg.message_id}"
        DATA.setdefault("mg_map", {})[key] = {"user_id": reg["user_id"], "reg_id": reg["id"]}
        DATA["management_chat_id"] = MANAGEMENT_GROUP_ID
        save_data(DATA)
        sent += 1
        return sent
    except Exception:
        pass
    try:
        stored = DATA.get("management_chat_id")
        if stored:
            sent_msg = await context.bot.send_message(chat_id=int(stored), text=mg_text, parse_mode="HTML", reply_markup=mg_kb)
            key = f"{sent_msg.chat.id}:{sent_msg.message_id}"
            DATA.setdefault("mg_map", {})[key] = {"user_id": reg["user_id"], "reg_id": reg["id"]}
            save_data(DATA)
            sent += 1
            return sent
    except Exception:
        pass
    for gid_str in list(DATA.get("known_groups", {}).keys()):
        try:
            gid = int(gid_str)
        except Exception:
            continue
        try:
            sent_msg = await context.bot.send_message(chat_id=gid, text=mg_text, parse_mode="HTML", reply_markup=mg_kb)
            key = f"{sent_msg.chat.id}:{sent_msg.message_id}"
            DATA.setdefault("mg_map", {})[key] = {"user_id": reg["user_id"], "reg_id": reg["id"]}
            save_data(DATA)
            sent += 1
        except Exception:
            continue
    return sent

async def mg_cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 3:
        try:
            await cq.edit_message_text("Invalid action.")
        except Exception:
            pass
        return
    action = parts[0]
    reg_id = parts[1]
    try:
        user_id = int(parts[2])
    except Exception:
        user_id = None
    found = None
    tourn = find_posted_tournament()
    if not tourn:
        await cq.edit_message_text("Tournament not found.")
        return
    for r in tourn.get("registrations", []):
        if r.get("id") == reg_id:
            found = r
            break
    if not found:
        await cq.edit_message_text("Registration not found.")
        return
    actor = cq.from_user
    if action == "mg_accept":
        if not found.get("player_code"):
            found["player_code"] = generate_unique_code()
        found["status"] = "accepted"
        save_data(DATA)
        try:
            edited = (
                "when《 Player Registration 》\n"
                f"Name: {found.get('name')}\n"
                f"Username: @{found.get('username') if found.get('username') else '-'}\n"
                f"Telegram ID: {found.get('user_id')}\n"
                f"Role: {found.get('role')}\n"
                f"Base Price: {found.get('price')}\n\n"
                f"Accepted by: <a href=\"tg://user?id={actor.id}\">{actor.full_name}</a>"
            )
            await cq.edit_message_text(edited, parse_mode="HTML")
        except Exception:
            try:
                await cq.edit_message_reply_markup(None)
            except Exception:
                pass
        try:
            await context.bot.pin_chat_message(chat_id=cq.message.chat.id, message_id=cq.message.message_id)
        except Exception:
            pass
        accept_text = (
            "🎉 <b>Registration Accepted!</b>\n\n"
            f"Name: {found.get('name')}\n"
            f"Username: @{found.get('username') if found.get('username') else '-'}\n"
            f"Role: {found.get('role')}\n"
            f"Base Price: {found.get('price')}\n\n"
            f"🔑 <b>Your Player Code:</b> <code>{found.get('player_code')}</code>\n\n"
            "Save this code — admins will use it to add/remove players."
        )
        try:
            if user_id:
                await context.bot.send_message(chat_id=int(user_id), text=accept_text, parse_mode="HTML")
        except Exception:
            pass
    elif action == "mg_decline":
        found["status"] = "declined"
        save_data(DATA)
        try:
            edited = (
                "when《 Player Registration 》\n"
                f"Name: {found.get('name')}\n"
                f"Username: @{found.get('username') if found.get('username') else '-'}\n"
                f"Telegram ID: {found.get('user_id')}\n"
                f"Role: {found.get('role')}\n"
                f"Base Price: {found.get('price')}\n\n"
                f"Declined by: <a href=\"tg://user?id={actor.id}\">{actor.full_name}</a>"
            )
            await cq.edit_message_text(edited, parse_mode="HTML")
        except Exception:
            try:
                await cq.edit_message_reply_markup(None)
            except Exception:
                pass
        try:
            await context.bot.pin_chat_message(chat_id=cq.message.chat.id, message_id=cq.message.message_id)
        except Exception:
            pass
        try:
            if user_id:
                await context.bot.send_message(chat_id=int(user_id), text="❌ Your registration request was declined by management.", parse_mode="HTML")
        except Exception:
            pass
    else:
        await cq.edit_message_text("Invalid action.")

async def mg_forward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return

@admin_only
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.chat.type != "private":
        await msg.reply_text("Please use /add in a private chat with the bot.")
        return
    admin_id = update.effective_user.id
    DATA.setdefault("admin_add_tmp", {})
    DATA["admin_add_tmp"][str(admin_id)] = {"step": "await_username"}
    save_data(DATA)
    await msg.reply_text("✅ OK — please enter the player's Telegram username (like @username) or numeric user id now. I will fetch details and show preview.")

async def _process_admin_add_text(admin_id: int, text: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    tmp = DATA.get("admin_add_tmp", {}).get(str(admin_id))
    if not tmp:
        return False
    if tmp.get("step") != "await_username":
        return False
    resolved_user = None
    user_chat = None
    if text.isdigit():
        try:
            user_chat = await context.bot.get_chat(int(text))
            resolved_user = user_chat
        except Exception:
            user_chat = None
    if not resolved_user:
        try:
            user_chat = await context.bot.get_chat(text)
            resolved_user = user_chat
        except Exception:
            user_chat = None
    if not resolved_user and not text.startswith("@"):
        try:
            user_chat = await context.bot.get_chat("@" + text)
            resolved_user = user_chat
        except Exception:
            user_chat = None
    if not resolved_user:
        for k, v in DATA.get("started_users", {}).items():
            if v.get("username") and v.get("username").lstrip("@").lower() == text.lstrip("@").lower():
                try:
                    user_chat = await context.bot.get_chat(int(k))
                    resolved_user = user_chat
                except Exception:
                    resolved_user = {"id": int(k), "username": v.get("username"), "first_name": v.get("first_name")}
                break
    if not resolved_user:
        await update.message.reply_text("❌ I couldn't fetch that Telegram user. Make sure the username is correct and the user is reachable. You can try a numeric user id.")
        return True
    if isinstance(resolved_user, dict):
        u_id = resolved_user.get("id")
        u_name = resolved_user.get("first_name") or ""
        u_un = resolved_user.get("username") or ""
    else:
        u_id = resolved_user.id
        u_name = getattr(resolved_user, "full_name", None) or (getattr(resolved_user, "first_name", "") or "")
        u_un = getattr(resolved_user, "username", "") or ""
    tmp_id = uuid.uuid4().hex[:8]
    reg = {
        "tmp_id": tmp_id,
        "user_id": u_id,
        "name": u_name,
        "username": u_un,
        "role": None,
        "price": None,
        "status": "accepted_pending",
        "player_code": None
    }
    DATA["admin_add_tmp"][str(admin_id)] = {"step": "choose_role", "reg": reg}
    save_data(DATA)
    uname_display = f"@{reg['username']}" if reg['username'] else "-"
    preview = ("<b>Add Player — Preview</b>\n\n"
               f"Name: {reg['name']}\n"
               f"Username: {uname_display}\n"
               f"Role: — not selected —\n"
               f"Base Price: — not selected —\n\n"
               "Please select the <b>type of player (role)</b>:")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Batsman", callback_data=f"add_role|{tmp_id}|Batsman"),
         InlineKeyboardButton("Bowler", callback_data=f"add_role|{tmp_id}|Bowler"),
         InlineKeyboardButton("All-Rounder", callback_data=f"add_role|{tmp_id}|All-Rounder")]
    ])
    await update.message.reply_text(preview, parse_mode="HTML", reply_markup=kb)
    return True

async def add_role_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 3:
        await cq.edit_message_text("Invalid action.")
        return
    _, tmp_id, role = parts[0], parts[1], parts[2]
    admin_key = None
    admin_entry = None
    for k, v in DATA.get("admin_add_tmp", {}).items():
        if v.get("reg", {}).get("tmp_id") == tmp_id:
            admin_key = k
            admin_entry = v
            break
    if not admin_entry:
        await cq.edit_message_text("Temporary add session not found or expired.")
        return
    reg = admin_entry["reg"]
    reg["role"] = role
    DATA["admin_add_tmp"][admin_key]["reg"] = reg
    DATA["admin_add_tmp"][admin_key]["step"] = "choose_price"
    save_data(DATA)
    uname_display = f"@{reg['username']}" if reg['username'] else "-"
    preview = ("<b>Add Player — Preview</b>\n\n"
               f"Name: {reg['name']}\n"
               f"Username: {uname_display}\n"
               f"Role: {reg['role']}\n"
               f"Base Price: — not selected —\n\n"
               "Please choose the <b>base price</b>:")
    kb_price = InlineKeyboardMarkup([
        [InlineKeyboardButton("1 CR", callback_data=f"add_price|{tmp_id}|1 CR"),
         InlineKeyboardButton("2 CR", callback_data=f"add_price|{tmp_id}|2 CR"),
         InlineKeyboardButton("3 CR", callback_data=f"add_price|{tmp_id}|3 CR")]
    ])
    await cq.edit_message_text(preview, parse_mode="HTML", reply_markup=kb_price)

async def add_price_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 3:
        await cq.edit_message_text("Invalid action.")
        return
    _, tmp_id, price = parts[0], parts[1], parts[2]
    admin_key = None
    admin_entry = None
    for k, v in DATA.get("admin_add_tmp", {}).items():
        if v.get("reg", {}).get("tmp_id") == tmp_id:
            admin_key = k
            admin_entry = v
            break
    if not admin_entry:
        await cq.edit_message_text("Temporary add session not found or expired.")
        return
    reg = admin_entry["reg"]
    reg["price"] = price
    DATA["admin_add_tmp"][admin_key]["reg"] = reg
    DATA["admin_add_tmp"][admin_key]["step"] = "confirm_add"
    save_data(DATA)
    uname_display = f"@{reg['username']}" if reg['username'] else "-"
    preview = ("<b>Add Player — Final Preview</b>\n\n"
               f"Name: {reg['name']}\n"
               f"Username: {uname_display}\n"
               f"Role: {reg['role']}\n"
               f"Base Price: {reg['price']}\n\n"
               "Are you sure you want to add this player directly? (This will not go to management.)")
    kb_confirm = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes — Add", callback_data=f"add_submit|{tmp_id}|yes"),
         InlineKeyboardButton("❌ Cancel", callback_data=f"add_submit|{tmp_id}|no")]
    ])
    await cq.edit_message_text(preview, parse_mode="HTML", reply_markup=kb_confirm)

async def add_submit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 3:
        await cq.edit_message_text("Invalid action.")
        return
    _, tmp_id, action = parts[0], parts[1], parts[2]
    admin_key = None
    admin_entry = None
    for k, v in DATA.get("admin_add_tmp", {}).items():
        if v.get("reg", {}).get("tmp_id") == tmp_id:
            admin_key = k
            admin_entry = v
            break
    if not admin_entry:
        await cq.edit_message_text("Temporary add session not found or expired.")
        return
    reg = admin_entry["reg"]
    if action == "no":
        DATA["admin_add_tmp"].pop(admin_key, None)
        save_data(DATA)
        await cq.edit_message_text("❌ Add cancelled.")
        return
    tourn = find_posted_tournament()
    if not tourn:
        await cq.edit_message_text("No posted tournament to add into.")
        DATA["admin_add_tmp"].pop(admin_key, None)
        save_data(DATA)
        return
    for r in tourn.get("registrations", []):
        if r.get("user_id") == reg["user_id"] and r.get("status") not in ("declined", "removed"):
            await cq.edit_message_text("⚠️ This user already has an active registration. Remove it first.")
            DATA["admin_add_tmp"].pop(admin_key, None)
            save_data(DATA)
            return
    reg_rec = {
        "id": uuid.uuid4().hex[:8],
        "user_id": reg["user_id"],
        "name": reg["name"],
        "username": reg["username"],
        "role": reg["role"],
        "price": reg["price"],
        "status": "accepted",
        "player_code": generate_unique_code()
    }
    tourn.setdefault("registrations", []).append(reg_rec)
    save_data(DATA)
    DATA["admin_add_tmp"].pop(admin_key, None)
    save_data(DATA)
    accept_text = (
        "🎉 <b>Registration Accepted by Admin!</b>\n\n"
        f"Name: {reg_rec.get('name')}\n"
        f"Username: @{reg_rec.get('username') if reg_rec.get('username') else '-'}\n"
        f"Role: {reg_rec.get('role')}\n"
        f"Base Price: {reg_rec.get('price')}\n\n"
        f"🔑 <b>Your Player Code:</b> <code>{reg_rec.get('player_code')}</code>\n\n"
        "Save this code — admins will use it to add/remove players."
    )
    try:
        await context.bot.send_message(chat_id=int(reg_rec.get('user_id')), text=accept_text, parse_mode="HTML")
    except Exception:
        pass
    await cq.edit_message_text("✅ Player added & accepted. User notified privately.")

async def perform_remove_by_key(context: ContextTypes.DEFAULT_TYPE, update: Update, key: str):
    msg = update.effective_message or update.message
    tourn = find_posted_tournament()
    if not tourn:
        await msg.reply_text("No active posted tournament.")
        return
    regs = tourn.get("registrations", [])
    visible = [r for r in regs if r.get("status") in ("accepted", "requested", "accepted_pending")]
    k = key.strip()
    if k.isdigit():
        pos = int(k)
        if 1 <= pos <= len(visible):
            targ = visible[pos - 1]
            targ["status"] = "removed"
            for mm in list(DATA.get("mg_map", {}).keys()):
                val = DATA["mg_map"].get(mm)
                if val and val.get("reg_id") == targ.get("id"):
                    DATA["mg_map"].pop(mm, None)
            save_data(DATA)
            try:
                await context.bot.send_message(chat_id=int(targ.get("user_id")), text="⚠️ You have been removed from the tournament registration by admin.", parse_mode="HTML")
            except Exception:
                pass
            await msg.reply_text(f"✅ Registration at position {pos} removed (user notified).")
            return
    targ = None
    for r in regs:
        if str(r.get("player_code")) == k or str(r.get("user_id")) == k or (r.get("username") and r.get("username").lstrip("@").lower() == k.lstrip("@").lower()):
            targ = r
            break
    if not targ:
        await msg.reply_text("❌ Registration not found for that identifier.")
        return
    targ["status"] = "removed"
    for mm in list(DATA.get("mg_map", {}).keys()):
        val = DATA["mg_map"].get(mm)
        if val and val.get("reg_id") == targ.get("id"):
            DATA["mg_map"].pop(mm, None)
    save_data(DATA)
    try:
        await context.bot.send_message(chat_id=int(targ.get("user_id")), text="⚠️ You have been removed from the tournament registration by admin.", parse_mode="HTML")
    except Exception:
        pass
    await msg.reply_text("✅ User removed from registration list.")

@admin_only
async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    args = context.args or []
    if not args:
        admin_id = update.effective_user.id
        DATA.setdefault("pending_remove", {})[str(admin_id)] = True
        save_data(DATA)
        await msg.reply_text("Please send the position number, username, player code or telegram user id to remove (send it now).")
        return
    key = args[0].strip()
    await perform_remove_by_key(context, update, key)

async def _process_admin_remove_text(admin_id: int, text: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = DATA.get("pending_remove", {}).get(str(admin_id))
    if not pending:
        return False
    await perform_remove_by_key(context, update, text.strip())
    DATA.setdefault("pending_remove", {}).pop(str(admin_id), None)
    save_data(DATA)
    return True

@admin_only
async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    caller_id = update.effective_user.id
    token = uuid.uuid4().hex[:8]
    DATA.setdefault("reset_tokens", {})[str(caller_id)] = token
    save_data(DATA)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes — Reset all data", callback_data=f"reset_confirm|yes|{caller_id}|{token}")],
        [InlineKeyboardButton("❌ No — Cancel", callback_data=f"reset_confirm|no|{caller_id}|{token}")]
    ])
    await msg.reply_text("⚠️ Are you sure you want to reset ALL data? This will permanently DELETE tournament posts, registrations and all related data. Choose an option below:", reply_markup=kb)

async def reset_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DATA
    cq = update.callback_query
    await cq.answer()
    data = (cq.data or "")
    parts = data.split("|")
    if len(parts) < 4:
        await cq.edit_message_text("Invalid action.")
        return
    _, choice, admin_id_str, token = parts[0], parts[1], parts[2], parts[3]
    try:
        admin_id = int(admin_id_str)
    except Exception:
        admin_id = None
    actor = cq.from_user
    if admin_id and actor.id != admin_id:
        await cq.edit_message_text("Only the admin who initiated the reset can confirm it.")
        return
    stored = DATA.get("reset_tokens", {}).get(str(admin_id))
    if not stored or stored != token:
        await cq.edit_message_text("This reset token is invalid or expired.")
        return
    if choice == "no":
        DATA.setdefault("reset_tokens", {}).pop(str(admin_id), None)
        save_data(DATA)
        await cq.edit_message_text("❌ Reset cancelled.")
        return
    base = {"tournaments": {}, "started_users": {}, "known_groups": {}, "mg_map": {}, "management_chat_id": None, "admin_add_tmp": {}, "pending_remove": {}, "reset_tokens": {}, "last_broadcast": None}
    save_data(base)
    DATA = load_data()
    await cq.edit_message_text("✅ All data reset successfully. All tournament posts, registrations and related data have been permanently deleted.")

async def my_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.my_chat_member or update.chat_member
    if not cm:
        return
    old_status = cm.old_chat_member.status
    new_status = cm.new_chat_member.status
    if new_status in ("member", "administrator") and old_status not in ("member", "administrator"):
        adder = cm.from_user
        chat = cm.chat
        await record_group(chat)
        if chat.id == MANAGEMENT_GROUP_ID:
            DATA["management_chat_id"] = MANAGEMENT_GROUP_ID
            save_data(DATA)

async def private_admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    if not user or user.id not in ADMINS:
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    admin_id = user.id
    handled = False
    handled = await _process_admin_add_text(admin_id, text, update, context) or handled
    if handled:
        return
    if text.startswith("/remove"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            await perform_remove_by_key(context, update, parts[1].strip())
            return
        else:
            DATA.setdefault("pending_remove", {})[str(admin_id)] = True
            save_data(DATA)
            await update.message.reply_text("Please send the position number, username, player code or telegram user id to remove (send it now).")
            return
    handled = await _process_admin_remove_text(admin_id, text, update, context) or handled
    if handled:
        return
    if text.startswith("/reset"):
        await reset_cmd(update, context)
        return

@admin_only
async def user_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    args = context.args or []
    if not args:
        await msg.reply_text("Usage: /user_status @username  OR  /user_status <telegram_id>")
        return
    key = args[0].strip()
    seek_username = None
    seek_userid = None
    if key.startswith("@"):
        seek_username = key.lstrip("@").lower()
    elif key.isdigit():
        seek_userid = int(key)
    else:
        seek_username = key.lstrip("@").lower()
    tourn = find_posted_tournament()
    found = None
    if tourn:
        for r in tourn.get("registrations", []):
            if seek_userid and r.get("user_id") == seek_userid:
                found = r
                break
            if seek_username and r.get("username") and r.get("username").lstrip("@").lower() == seek_username:
                found = r
                break
    if found:
        uname = f"@{found.get('username')}" if found.get('username') else "-"
        pc = found.get("player_code") or "-"
        tidv = found.get("user_id") or ""
        lines = [
            "<b>User Status — Registration Info</b>",
            f"Name: {found.get('name')}",
            f"Username: {uname}",
            f"Role: {found.get('role')}",
            f"Base Price: {found.get('price')}",
            f"Telegram ID: {tidv}",
            f"Status: registered"
        ]
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
        return
    known = None
    if seek_userid:
        known = DATA.get("started_users", {}).get(str(seek_userid))
    elif seek_username:
        for k, v in DATA.get("started_users", {}).items():
            if v.get("username") and v.get("username").lstrip("@").lower() == seek_username:
                known = v
                break
    if known:
        uname = f"@{known.get('username')}" if known.get('username') else "-"
        lines = [
            "<b>User Status — Not Registered</b>",
            f"Name: {known.get('first_name')}",
            f"Username: {uname}",
            f"Telegram ID: {known.get('id')}",
            f"Status: not registered yet"
        ]
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
        return
    await msg.reply_text("User not found in registrations or known users.")

@admin_only
async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    if not os.path.exists(DATA_FILE):
        save_data(DATA)
    try:
        await msg.reply_text("Preparing backup file...")
        with open(DATA_FILE, "rb") as f:
            await context.bot.send_document(chat_id=update.effective_user.id, document=f, filename=os.path.basename(DATA_FILE))
        await msg.reply_text("✅ Backup sent to your private chat.")
    except Exception as e:
        logger.exception("Backup failed")
        await msg.reply_text(f"❌ Failed to send backup: {e}")

@admin_only
async def restore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    doc = None
    if msg.reply_to_message and msg.reply_to_message.document:
        doc = msg.reply_to_message.document
    elif msg.document:
        doc = msg.document
    if not doc:
        await msg.reply_text("Reply to a backup file (JSON) with /restore or send the backup file with /restore as reply.")
        return
    try:
        file_obj = await context.bot.get_file(doc.file_id)
        tmp_path = DATA_FILE + ".restore.tmp"
        await file_obj.download_to_drive(tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        if not isinstance(content, dict):
            await msg.reply_text("❌ Invalid backup file format (expected JSON object).")
            return
        save_data(content)
        global DATA
        DATA = load_data()
        await msg.reply_text("✅ Restore completed. Data loaded successfully.")
    except Exception as e:
        logger.exception("Restore failed")
        await msg.reply_text(f"❌ Restore failed: {e}")

async def doc_restore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    if not user or user.id not in ADMINS:
        return
    msg = update.message
    if msg and msg.document:
        await msg.reply_text("Reply to this document with /restore to restore the database, or send /backup to get a copy.")

def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("broad", broad_cmd))
    app.add_handler(CommandHandler("start_reg", start_reg_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("resume", resume_cmd))
    app.add_handler(CommandHandler("registered_list", registered_list_cmd))
    app.add_handler(CommandHandler("user_status", user_status_cmd))
    app.add_handler(CommandHandler("register", register_cmd))
    app.add_handler(CallbackQueryHandler(role_cb_handler, pattern=r"^role\|"))
    app.add_handler(CallbackQueryHandler(price_cb_handler, pattern=r"^price\|"))
    app.add_handler(CallbackQueryHandler(submit_cb_handler, pattern=r"^submit\|"))
    app.add_handler(CallbackQueryHandler(mg_cb_handler, pattern=r"^mg_(accept|decline)\|"))
    app.add_handler(MessageHandler(filters.REPLY & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP), mg_forward_handler))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, private_admin_text_handler))
    app.add_handler(CallbackQueryHandler(add_role_cb, pattern=r"^add_role\|"))
    app.add_handler(CallbackQueryHandler(add_price_cb, pattern=r"^add_price\|"))
    app.add_handler(CallbackQueryHandler(add_submit_cb, pattern=r"^add_submit\|"))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CallbackQueryHandler(reset_confirm_cb, pattern=r"^reset_confirm\|"))
    app.add_handler(ChatMemberHandler(my_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(reglist_cb_handler, pattern=r"^reglist\|"))
    app.add_handler(CallbackQueryHandler(reglist_cb_handler, pattern=r"^regstats\|"))
    app.add_handler(CallbackQueryHandler(reglist_cb_handler, pattern=r"^reglist_close\|"))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, doc_restore_handler))

    app.add_handler(CallbackQueryHandler(auction.callback_router, pattern=r"^(auction_host:|auction_table_choice:|auction_load:|end_confirm:|min_buy:|max_buy:)"))
    app.add_handler(auction.start_auction_handler)
    app.add_handler(auction.set_table_handler)
    app.add_handler(auction.table_reply_handler)
    app.add_handler(auction.team_handler)
    app.add_handler(auction.budget_handler)
    app.add_handler(auction.load_handler)
    app.add_handler(auction.load_msg_handler)
    app.add_handler(auction.load_reply_fallback_handler)
    app.add_handler(auction.next_handler)
    app.add_handler(auction.bid_handler)
    app.add_handler(auction.pause_handler)
    app.add_handler(auction.resume_handler)
    app.add_handler(auction.summary_handler)
    app.add_handler(auction.end_handler)
    app.add_handler(auction.status_handler)
    app.add_handler(auction.my_team_handler)
    app.add_handler(auction.unsold_handler)
    app.add_handler(auction.assist_handler)
    app.add_handler(auction.demote_handler)
    app.add_handler(auction.access_handler)
    app.add_handler(auction.deduct_handler)
    app.add_handler(auction.plus_handler)
    return app

if __name__ == "__main__":
    application = build_app()
    application.run_polling()