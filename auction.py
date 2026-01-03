import asyncio
import json
import os
import re
import sqlite3
import time
import uuid
import random
from typing import Dict, Any, Optional, Tuple, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Message, InputMediaVideo
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler, ApplicationBuilder

DB_PATH = "auction_bot_data.json"
USERNAMES_DB_PREFERRED = "/mnt/data/usernames.db"
DEFAULT_COUNTDOWN = 30

BOT_NAME = "ᎪᏟᎬᏴᏬᎠᎠᎽ"

START_IMAGE_URL = "https://graph.org/file/5625ef0ddc921f51bdb8f-5f4ada8ed080305cc4.jpg"
AUCTION_DONE_IMAGE = "https://graph.org/file/aa16a08f9ce82a852a258-a6f185008a91f636bd.jpg"
END_CLOSED_IMAGE = "https://graph.org/file/991ffca40c0e65077c220-4e7794de8254f40cd7.jpg"

OWNER_TELEGRAM_ID = 1766243373

NEW_PLAYER_VIDEO_IDS = [
    "BAACAgUAAxkBAAIEXmlXjM8aBqxYfkyrFi4eyMS_JmtaAAL6HwACpRG5Vo5lAjaFM0HvOAQ"
]

UNSOLD_VIDEO_IDS = [
    "BAACAgUAAxkBAAIEVWlXjJryn4pSOgoIX1L_YfSgInHCAAL2HwACpRG5Vkc2TZihwuMQOAQ"
]

BID_CONFIRMED_VIDEO_IDS = [
    "BAACAgUAAxkBAAIEamlXjYCTmcKoQgAB6BUx9LH_0M7ZoAADIAACpRG5VhnAGuu26iK2OAQ",
    "BAACAgUAAxkBAAIEV2lXjJpS6r-OfmvYX0grtBT7aJKVAAL4HwACpRG5Vj55fI-melFWOAQ",
    "BAACAgUAAxkBAAIEVGlXjJr3Gp-dTacAAS-vd4uct-y0mAAC9R8AAqURuVZFOtVu8Im4NjgE"
]

SOLD_VIDEO_IDS = [
    "BAACAgUAAxkBAAIEaGlXjU30Oga-CFnUjFsVmnlAMHn2AAL9HwACpRG5Vnokq3gSi8QTOAQ",
    "BAACAgUAAxkBAAIEVmlXjJoRJKNsgARDUZgVVmYaGLPWAAL3HwACpRG5VnvL32nMoX3KOAQ"
]

def _ensure_json_db():
    global DB_PATH
    dirpath = os.path.dirname(DB_PATH)
    if dirpath and not os.path.exists(dirpath):
        try:
            os.makedirs(dirpath, exist_ok=True)
        except Exception:
            DB_PATH = os.path.join(os.getcwd(), "auction_bot_data.json")
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_db() -> Dict[str, Any]:
    _ensure_json_db()
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f) or {}
            except Exception:
                return {}
    except Exception:
        try:
            with open(DB_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)
        except Exception:
            pass
        return {}

def save_db(data: Dict[str, Any]) -> None:
    _ensure_json_db()
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_PATH)

def _choose_usernames_db_path() -> str:
    try:
        pref_dir = os.path.dirname(USERNAMES_DB_PREFERRED) or "/"
        if pref_dir and not os.path.exists(pref_dir):
            os.makedirs(pref_dir, exist_ok=True)
        test_path = os.path.join(pref_dir, ".write_test")
        with open(test_path, "w", encoding="utf-8") as t:
            t.write("ok")
        os.remove(test_path)
        return USERNAMES_DB_PREFERRED
    except Exception:
        fallback = os.path.join(os.getcwd(), "usernames.db")
        return fallback

USERNAMES_DB_PATH = _choose_usernames_db_path()

def get_session(chat_id: int) -> Dict[str, Any]:
    db = load_db()
    sessions = db.get("auction_sessions", {})
    key = str(chat_id)
    if key not in sessions:
        sessions[key] = {
            "active": False,
            "message_key": None,
            "host_id": None,
            "host_name": None,
            "tables": None,
            "teams": {},
            "team_budgets": {},
            "budget": None,
            "players_list": [],
            "current_slot": None,
            "paused": False,
            "pause_start": None,
            "last_table_msg_key": None,
            "logs": [],
            "current_run_id": None,
            "assistants": {},
            "access_users": [],
            "min_buy": None,
            "max_buy": None,
            "min_choice_key": None,
            "max_choice_key": None,
            "completed": False,
            "countdown_seconds": DEFAULT_COUNTDOWN,
            "auto_mode": False,
            "auto_set_number": None,
            "auto_set_list": [],
            "auto_set_index": 0,
            "loaded_sets": [],
            "pending_load_origin": None,
            "auto_sequence": [],
            "pending_slots": {},
            "last_sent_slot_key": None,
            "processing_unsold": False
        }
        db["auction_sessions"] = sessions
        save_db(db)
    return sessions[key]

def save_session(chat_id: int, session: Dict[str, Any]) -> None:
    db = load_db()
    sessions = db.get("auction_sessions", {})
    sessions[str(chat_id)] = session
    db["auction_sessions"] = sessions
    save_db(db)

def start_new_run(chat_id: int, session: Dict[str, Any]) -> str:
    db = load_db()
    history = db.get("auction_history", {})
    run_id = str(int(time.time())) + "-" + uuid.uuid4().hex[:8]
    run = {
        "run_id": run_id,
        "chat_id": chat_id,
        "started_at": int(time.time()),
        "ended_at": None,
        "host_id": session.get("host_id"),
        "host_name": session.get("host_name"),
        "tables": session.get("tables"),
        "teams": {},
        "budget": session.get("budget"),
        "players_loaded": len(session.get("players_list") or []),
        "current_slot": None,
        "sold_players": [],
        "unsold_players": [],
        "logs": [],
        "attempts": {}
    }
    if str(chat_id) not in history:
        history[str(chat_id)] = []
    history[str(chat_id)].append(run)
    db["auction_history"] = history
    save_db(db)
    session["current_run_id"] = run_id
    save_session(chat_id, session)
    return run_id

def get_run(chat_id: int, run_id: str) -> Optional[Dict[str, Any]]:
    db = load_db()
    history = db.get("auction_history", {})
    runs = history.get(str(chat_id), [])
    for r in runs:
        if r.get("run_id") == run_id:
            return r
    return None

def save_run(chat_id: int, run: Dict[str, Any]) -> None:
    db = load_db()
    history = db.get("auction_history", {})
    runs = history.get(str(chat_id), [])
    for i in range(len(runs)):
        if runs[i].get("run_id") == run.get("run_id"):
            runs[i] = run
            break
    history[str(chat_id)] = runs
    db["auction_history"] = history
    save_db(db)

def append_run_log(chat_id: int, run_id: str, log: Dict[str, Any]) -> None:
    run = get_run(chat_id, run_id)
    if not run:
        return
    run_logs = run.get("logs", [])
    run_logs.append(log)
    run["logs"] = run_logs
    save_run(chat_id, run)

def build_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("I am a host", callback_data="auction_host:claim"), InlineKeyboardButton("Cancel auction", callback_data="auction_host:cancel")]])

def build_table_keyboard():
    buttons = [InlineKeyboardButton(str(n), callback_data=f"auction_table_choice:{n}") for n in range(2, 21)]
    rows = [buttons[i:i+5] for i in range(0, len(buttons), 5)]
    return InlineKeyboardMarkup(rows)

def build_load_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Internal load", callback_data="auction_load:internal"), InlineKeyboardButton("Load players", callback_data="auction_load:external")]])

def build_end_confirm(host_id: int):
    return InlineKeyboardMarkup([[InlineKeyboardButton("Yes — End Auction", callback_data=f"end_confirm:yes:{host_id}"), InlineKeyboardButton("No — Continue", callback_data=f"end_confirm:no:{host_id}")]])

def build_increase_tables_keyboard(current: int):
    buttons = [InlineKeyboardButton(str(n), callback_data=f"auction_table_change:{n}") for n in range(current+1, 21)]
    rows = [buttons[i:i+5] for i in range(0, len(buttons), 5)]
    return InlineKeyboardMarkup(rows)

def build_time_confirm_keyboard(host_id: int):
    return InlineKeyboardMarkup([[InlineKeyboardButton("Yes — Set time", callback_data=f"time_confirm:yes:{host_id}"), InlineKeyboardButton("Default (30s)", callback_data=f"time_confirm:default:{host_id}")]])

def build_start_player_keyboard(player_key: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("Start Auction", callback_data=f"auto_start:{player_key}")]])

def build_auto_mode_choice(loaded_from_text: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("AUTO MODE", callback_data=f"auction_mode:auto:{loaded_from_text}"), InlineKeyboardButton("HOST MODE", callback_data=f"auction_mode:host:{loaded_from_text}")]
    ])

def ensure_usernames_table(conn: sqlite3.Connection):
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, username_lower TEXT UNIQUE, added_at TEXT)")
    conn.commit()

countdown_tasks: Dict[int, asyncio.Task] = {}

async def _send_message(bot, chat_id: int, text: str, reply_markup=None, parse_mode=ParseMode.HTML):
    try:
        return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def _format_player_name_link(player: Dict[str, Any]) -> str:
    pid = player.get("user_id")
    display = player.get("profile_fullname") or player.get("name") or player.get("username") or "Unknown"
    if pid:
        try:
            return f"<a href='tg://user?id={int(pid)}'>{display}</a>"
        except:
            return display
    return display

async def _prefetch_profile_for_player(chat_id: int, context: ContextTypes.DEFAULT_TYPE, player: Dict[str, Any]):
    try:
        if player.get("user_id"):
            tg_id = int(player.get("user_id"))
            try:
                tg_obj = await context.bot.get_chat(tg_id)
                profile_username = getattr(tg_obj, "username", None)
                first = getattr(tg_obj, "first_name", "") or ""
                last = getattr(tg_obj, "last_name", "") or ""
                profile_fullname = f"{first} {last}".strip() if (first or last) else None
                if profile_username:
                    player["profile_username"] = profile_username.lstrip("@")
                if profile_fullname:
                    player["profile_fullname"] = profile_fullname
            except Exception:
                pass
        else:
            if player.get("username"):
                uname = str(player.get("username")).lstrip("@")
                try:
                    tg_obj = await context.bot.get_chat(f"@{uname}")
                    if getattr(tg_obj, "id", None):
                        profile_username = getattr(tg_obj, "username", None)
                        first = getattr(tg_obj, "first_name", "") or ""
                        last = getattr(tg_obj, "last_name", "") or ""
                        profile_fullname = f"{first} {last}".strip() if (first or last) else None
                        if profile_username:
                            player["profile_username"] = profile_username.lstrip("@")
                        if profile_fullname:
                            player["profile_fullname"] = profile_fullname
                        if not player.get("user_id") and getattr(tg_obj, "id", None):
                            player["user_id"] = getattr(tg_obj, "id")
                except Exception:
                    pass
    except Exception:
        pass
    return player

async def send_new_player_slot_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE, player: Dict[str, Any], base_price):
    session = get_session(chat_id)
    player_key = uuid.uuid4().hex
    session_pending = session.get("pending_slots", {}) or {}
    pcopy = dict(player)
    if pcopy.get("profile_fullname") is None or pcopy.get("profile_username") is None:
        await _prefetch_profile_for_player(chat_id, context, pcopy)
    pcopy["set_base_price"] = base_price if base_price is not None else pcopy.get("base_price") or session.get("budget") or 0
    session_pending[player_key] = pcopy
    session["pending_slots"] = session_pending
    session["last_sent_slot_key"] = player_key
    save_session(chat_id, session)
    name_link = await _format_player_name_link(pcopy)
    profile_username = pcopy.get("profile_username") or pcopy.get("username") or ""
    caption = ("⟦ New Player Slot ⟧\n\n"
               f"Player Name  : {name_link}\n"
               f"User Name    : @{(profile_username or '')}\n"
               f"Player Type  : {pcopy.get('role') or 'None'}\n"
               f"Base Price   : {pcopy.get('set_base_price')}\n\n"
               "Hey host, please click on the start auction button below to begin this player bidding.")
    try:
        sent = None
        vid = random.choice(NEW_PLAYER_VIDEO_IDS) if NEW_PLAYER_VIDEO_IDS else None
        if vid:
            try:
                sent = await context.bot.send_video(chat_id=chat_id, video=vid, caption=caption, parse_mode=ParseMode.HTML, reply_markup=build_start_player_keyboard(player_key))
            except Exception:
                sent = await _send_message(context.bot, chat_id, caption, reply_markup=build_start_player_keyboard(player_key))
        else:
            sent = await _send_message(context.bot, chat_id, caption, reply_markup=build_start_player_keyboard(player_key))
        try:
            if sent and getattr(sent, "message_id", None):
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id, disable_notification=True)
                except Exception:
                    pass
        except Exception:
            pass
        return sent
    except Exception:
        try:
            return await _send_message(context.bot, chat_id, caption, reply_markup=build_start_player_keyboard(player_key))
        except Exception:
            return None

async def start_player_slot(chat_id: int, context: ContextTypes.DEFAULT_TYPE, player: Dict[str, Any], start_price: float, by_host: bool = False, existing_msg: Optional[Message] = None):
    session = get_session(chat_id)
    if session.get("current_slot"):
        return False
    deadline = int(time.time()) + get_countdown(session)
    pcopy = dict(player)
    if pcopy.get("profile_fullname") is None or pcopy.get("profile_username") is None:
        await _prefetch_profile_for_player(chat_id, context, pcopy)
    slot = {"player": pcopy, "start_price": start_price, "deadline": deadline, "highest": None, "last_bid": None, "mg_message": None, "started_at": int(time.time()), "announced": {}}
    session["current_slot"] = slot
    save_session(chat_id, session)
    run_id = session.get("current_run_id") or start_new_run(chat_id, session)
    run = get_run(chat_id, run_id)
    if run:
        run["current_slot"] = {"player": pcopy, "start_price": start_price, "deadline": deadline, "highest": None, "started_at": int(time.time())}
        save_run(chat_id, run)
    name_link = await _format_player_name_link(pcopy)
    caption = ("📊 NEW PLAYER FOR AUCTION\n"
               "━━━━━━━━━━━━━━━━━━━━━\n"
               f"⭐️ Name.        : {name_link}\n"
               f"🏏 Role Type : {pcopy.get('role') or 'None'}\n"
               f"⚡️ Base Price : {start_price} Cr\n"
               "━━━━━━━━━━━━━━━━━━━━━\n"
               f"You have {get_countdown(session)} seconds to place your bid on this player.\n"
               f"Send your bid: /bid amount\n")
    try:
        if existing_msg:
            try:
                await existing_msg.edit_caption(caption, parse_mode=ParseMode.HTML)
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=existing_msg.message_id, disable_notification=True)
                except Exception:
                    pass
                session["current_slot"]["mg_message"] = f"{chat_id}:{existing_msg.message_id}"
                save_session(chat_id, session)
            except Exception:
                sent = await _send_message(context.bot, chat_id, caption, parse_mode=ParseMode.HTML)
                session["current_slot"]["mg_message"] = f"{chat_id}:{sent.message_id}"
                save_session(chat_id, session)
        else:
            vid = random.choice(NEW_PLAYER_VIDEO_IDS) if NEW_PLAYER_VIDEO_IDS else None
            if vid:
                sent = await context.bot.send_video(chat_id=chat_id, video=vid, caption=caption, parse_mode=ParseMode.HTML)
                session["current_slot"]["mg_message"] = f"{chat_id}:{sent.message_id}"
                save_session(chat_id, session)
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id, disable_notification=True)
                except Exception:
                    pass
            else:
                sent = await _send_message(context.bot, chat_id, caption, parse_mode=ParseMode.HTML)
                session["current_slot"]["mg_message"] = f"{chat_id}:{sent.message_id}"
                save_session(chat_id, session)
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id, disable_notification=True)
                except Exception:
                    pass
    except Exception:
        sent = await _send_message(context.bot, chat_id, caption)
        session["current_slot"]["mg_message"] = f"{chat_id}:{sent.message_id}"
        save_session(chat_id, session)
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id, disable_notification=True)
        except Exception:
            pass
    task = asyncio.create_task(slot_countdown(chat_id, context))
    countdown_tasks[chat_id] = task
    return True

async def start_auction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)

    set_arg = None
    set_text = None
    unsold_base_price = None
    if context.args and len(context.args) >= 1:
        a0 = str(context.args[0]).strip()
        if re.fullmatch(r"\d+", a0):
            set_arg = int(a0)
        else:
            set_text = a0.lower()
            if len(context.args) >= 2:
                maybe_price = str(context.args[1]).strip()
                try:
                    unsold_base_price = float(maybe_price)
                except:
                    unsold_base_price = None

    if set_arg is not None:
        sets = session.get("loaded_sets", []) or []
        if not sets:
            await msg.reply_text("No sets are loaded. Load a set first using /load set <base_price> (reply to a username list).")
            return
        if set_arg < 1 or set_arg > len(sets):
            await msg.reply_text(f"Invalid set number. Available sets: 1 — {len(sets)}.\nTo start: /start_auction <set_number>\nExample: /start_auction 1")
            return
        if session.get("current_slot"):
            await msg.reply_text("A player is currently on auction. Finalize the current slot first before starting a set auction.")
            return
        chosen_set = sets[set_arg - 1]
        players_original = [dict(p) for p in chosen_set.get("players", [])] or []
        if not players_original:
            await msg.reply_text("Selected set has no players.")
            return
        unique = []
        seen = set()
        for p in players_original:
            key = str(p.get("user_id") or p.get("username") or p.get("name") or "").strip()
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        auto_sequence = unique.copy()
        random.shuffle(auto_sequence)
        for p in auto_sequence:
            if p.get("set_base_price") is None:
                p["set_base_price"] = p.get("base_price") or session.get("budget") or 0
        for p in auto_sequence:
            await _prefetch_profile_for_player(chat_id, context, p)
        session["auto_mode"] = True
        session["auto_set_number"] = set_arg
        session["auto_set_list"] = auto_sequence
        session["auto_sequence"] = [str((p.get("user_id") or p.get("username") or "")).strip() for p in auto_sequence]
        session["auto_set_index"] = 0
        session["active"] = True
        session["processing_unsold"] = False
        save_session(chat_id, session)
        announcement = (f"<b>AUCTION SET {set_arg} IS STARTING NOW</b>\n\n"
                        "Captains, steel your nerves — slots will drop one-by-one from the set, randomly. Prepare your bids.\n\n"
                        "The first player will be placed up for auction shortly.")
        try:
            await _send_message(context.bot, chat_id, announcement)
        except:
            pass

        async def delayed_first_player():
            await asyncio.sleep(2)
            sess = get_session(chat_id)
            players = sess.get("auto_set_list") or []
            if not players:
                await _send_message(context.bot, chat_id, "No players available in the selected set.")
                return
            player = players.pop(0)
            sess["auto_set_list"] = players
            save_session(chat_id, sess)
            base_price = player.get("set_base_price") if player.get("set_base_price") is not None else session.get("budget") or player.get("base_price") or 0
            try:
                await send_new_player_slot_message(chat_id, context, player, base_price)
            except Exception:
                try:
                    await _send_message(context.bot, chat_id, "Failed to send new player slot automatically.")
                except:
                    pass

        asyncio.create_task(delayed_first_player())
        return

    if set_text and set_text in ("unsold", "unsold_set", "unsoldplayers", "unsold_players"):
        run_id = session.get("current_run_id")
        run = get_run(chat_id, run_id) if run_id else None
        if not run:
            await msg.reply_text("No previous run found with unsold players.")
            return
        unsold = run.get("unsold_players", []) or []
        if not unsold:
            await msg.reply_text("There are no unsold players in this run.")
            return

        players = []
        original_unsold = []
        for u in unsold:
            original_unsold.append(u)
        run["unsold_players"] = []
        save_run(chat_id, run)

        for u in original_unsold:
            p = {
                "user_id": u.get("player_id"),
                "username": (u.get("player_username") or "") or None,
                "name": u.get("player_name") or "",
                "role": None,
                "player_code": None,
                "set_base_price": (u.get("base_price") if u.get("base_price") is not None else session.get("budget") or 0),
                "base_price": (u.get("base_price") if u.get("base_price") is not None else session.get("budget") or 0)
            }
            if unsold_base_price is not None:
                p["set_base_price"] = unsold_base_price
                p["base_price"] = unsold_base_price
            await _prefetch_profile_for_player(chat_id, context, p)
            players.append(p)

        unique = []
        seen = set()
        for p in players:
            key = str(p.get("user_id") or p.get("username") or p.get("name") or "").strip()
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        random.shuffle(unique)

        session["auto_mode"] = True
        session["auto_set_number"] = "unsold"
        session["auto_set_list"] = unique
        session["auto_sequence"] = [str((p.get("user_id") or p.get("username") or "")).strip() for p in unique]
        session["auto_set_index"] = 0
        session["active"] = True
        session["processing_unsold"] = True
        save_session(chat_id, session)
        announcement = ("<b>UNSOLD PLAYERS AUCTION IS STARTING NOW</b>\n\n"
                        "Captains, unsold players from previous rounds will be placed up for auction randomly. Prepare your bids.")
        try:
            await _send_message(context.bot, chat_id, announcement)
        except:
            pass

        async def delayed_unsold_first():
            await asyncio.sleep(2)
            sess = get_session(chat_id)
            players_local = sess.get("auto_set_list") or []
            if not players_local:
                await _send_message(context.bot, chat_id, "No unsold players available.")
                sess["processing_unsold"] = False
                save_session(chat_id, sess)
                return
            player = players_local.pop(1 if len(players_local) > 1 else 0)
            sess["auto_set_list"] = players_local
            save_session(chat_id, sess)
            base_price = player.get("set_base_price") if player.get("set_base_price") is not None else session.get("budget") or player.get("base_price") or 0
            try:
                await send_new_player_slot_message(chat_id, context, player, base_price)
            except Exception:
                try:
                    await _send_message(context.bot, chat_id, "Failed to send unsold player slot automatically.")
                except:
                    pass

        asyncio.create_task(delayed_unsold_first())
        return

    if session.get("active"):
        title = getattr(chat, "title", str(chat_id))
        await msg.reply_text(f"Auction has already started in {title}.")
        return

    session["active"] = False
    session["host_id"] = None
    session["host_name"] = None
    session["tables"] = None
    session["teams"] = {}
    session["team_budgets"] = {}
    session["budget"] = None
    session["players_list"] = []
    session["current_slot"] = None
    session["paused"] = False
    session["pause_start"] = None
    session["last_table_msg_key"] = None
    session["logs"] = []
    session["current_run_id"] = None
    session["assistants"] = {}
    session["access_users"] = []
    session["min_buy"] = None
    session["max_buy"] = None
    session["min_choice_key"] = None
    session["max_choice_key"] = None
    session["completed"] = False
    session["countdown_seconds"] = DEFAULT_COUNTDOWN
    session["auto_mode"] = False
    session["auto_set_number"] = None
    session["auto_set_list"] = []
    session["auto_set_index"] = 0
    session["auto_sequence"] = []
    session["pending_slots"] = {}
    session["last_sent_slot_key"] = None
    session["processing_unsold"] = False
    save_session(chat_id, session)

    text = (f"⟦ {BOT_NAME} HAS STARTED THE AUCTION ⟧\n\n"
            "The auction has officially begun!\n"
            "Get ready for fast bids, intense moments, and game-changing signings.\n\n"
            "To access full controls and manage the auction flow,\n"
            "please click on the \"I’m a Host\" button.")

    if START_IMAGE_URL:
        try:
            sent = await context.bot.send_photo(
                chat_id=chat_id,
                photo=START_IMAGE_URL,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=build_start_keyboard()
            )
            session["message_key"] = f"{chat_id}:{sent.message_id}"
        except Exception:
            sent = await _send_message(
                context.bot,
                chat_id,
                text,
                reply_markup=build_start_keyboard()
            )
            session["message_key"] = f"{chat_id}:{sent.message_id}"
    else:
        sent = await _send_message(
            context.bot,
            chat_id,
            text,
            reply_markup=build_start_keyboard()
        )
        session["message_key"] = f"{chat_id}:{sent.message_id}"

    save_session(chat_id, session)

start_auction_handler = CommandHandler("start_auction", start_auction)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    user = query.from_user
    chat = query.message.chat if query.message else update.effective_chat
    if not chat:
        try:
            await query.answer("Cannot determine chat", show_alert=True)
        except:
            pass
        return
    chat_id = chat.id
    session = get_session(chat_id)
    try:
        if data.startswith("auction_host:"):
            action = data.split(":",1)[1]
            if action == "claim":
                if session.get("host_id"):
                    try:
                        await query.answer("A host is already assigned", show_alert=True)
                    except:
                        pass
                    return
                session["host_id"] = user.id
                session["host_name"] = getattr(user, "full_name", None) or f"{getattr(user,'first_name','') or ''} {getattr(user,'last_name','') or ''}".strip()
                session["active"] = True
                save_session(chat_id, session)
                if not session.get("current_run_id"):
                    start_new_run(chat_id, session)
                new_text = ("⟦ HOST ACCESS ENABLED ⟧\n\n"
                            f"Hello {getattr(user,'first_name','')}, you are now recognized as the host for this auction.\n\n"
                            "For the full auction manual and command list,\n"
                            "please send: /help")
                try:
                    if query.message:
                        try:
                            await query.message.delete()
                        except:
                            pass
                    sent = await context.bot.send_photo(chat_id=chat_id, photo=START_IMAGE_URL, caption=new_text, parse_mode=ParseMode.HTML)
                    session["message_key"] = f"{chat_id}:{sent.message_id}"
                except Exception:
                    try:
                        await _send_message(context.bot, chat_id, new_text)
                    except:
                        pass
                save_session(chat_id, session)
                try:
                    await query.answer("You are now the auction host.")
                except:
                    pass
                return
            if action == "cancel":
                if session.get("host_id"):
                    try:
                        await query.answer("Host already assigned, cannot cancel", show_alert=True)
                    except:
                        pass
                    return
                session["active"] = False
                save_session(chat_id, session)
                try:
                    if query.message:
                        try:
                            await query.message.delete()
                            try:
                                await _send_message(context.bot, chat_id, "Auction cancelled by admin.")
                            except:
                                pass
                        except Exception:
                            try:
                                await query.message.edit_text("Auction cancelled by admin.")
                            except Exception:
                                await _send_message(context.bot, chat_id, "Auction cancelled by admin.")
                    else:
                        await _send_message(context.bot, chat_id, "Auction cancelled by admin.")
                except Exception:
                    try:
                        await _send_message(context.bot, chat_id, "Auction cancelled by admin.")
                    except:
                        pass
                try:
                    await query.answer("Auction cancelled")
                except:
                    pass
                return

        if data.startswith("auto_start:"):
            _, pkey = data.split(":",1)
            if session.get("host_id") and session.get("host_id") != user.id and user.id not in session.get("access_users", []):
                try:
                    await query.answer("Only the host (or authorized user) can start this auction", show_alert=True)
                except:
                    pass
                return
            session_pending = session.get("pending_slots", {}) or {}
            player = session_pending.get(pkey)
            if not player:
                try:
                    await query.answer("This player slot is no longer available or already started.", show_alert=True)
                except:
                    pass
                return
            try:
                base_price = player.get("set_base_price") if player.get("set_base_price") is not None else session.get("budget") or player.get("base_price") or 0
                try:
                    session_pending.pop(pkey, None)
                    session["pending_slots"] = session_pending
                    save_session(chat_id, session)
                except:
                    pass
                existing_msg = None
                try:
                    if query.message:
                        existing_msg = query.message
                except:
                    existing_msg = None
                started = await start_player_slot(chat_id, context, player, base_price, by_host=True, existing_msg=existing_msg)
                if not started:
                    try:
                        await query.answer("Failed to start slot: another slot active", show_alert=True)
                    except:
                        pass
                    return
                try:
                    await query.answer("Slot started")
                except:
                    pass
            except Exception:
                try:
                    await query.answer("Failed to start slot", show_alert=True)
                except:
                    pass
                return
            return

        if data.startswith("auction_table_choice:"):
            _, num_s = data.split(":",1)
            try:
                n = int(num_s)
            except:
                try:
                    await query.answer("Invalid number", show_alert=True)
                except:
                    pass
                return
            if session.get("host_id") != user.id:
                try:
                    await query.answer("Only the host can choose tables", show_alert=True)
                except:
                    pass
                return
            try:
                if query.message:
                    await query.message.delete()
            except Exception:
                pass
            session["tables"] = n
            save_session(chat_id, session)
            run_id = session.get("current_run_id") or start_new_run(chat_id, session)
            run = get_run(chat_id, run_id)
            if run:
                run["tables"] = n
                save_run(chat_id, run)
            txt = f"✅ Auction tables confirmed ({n}).\n\nNow set minimum buying limit for all teams:"
            min_buttons = [InlineKeyboardButton(str(x), callback_data=f"min_buy:{x}") for x in range(3,13)]
            kb_rows = [min_buttons[i:i+5] for i in range(0, len(min_buttons), 5)]
            sent = await _send_message(context.bot, chat_id, txt, reply_markup=InlineKeyboardMarkup(kb_rows))
            session["min_choice_key"] = f"{chat_id}:{sent.message_id}"
            save_session(chat_id, session)
            try:
                await query.answer("Tables set - choose minimum buying")
            except:
                pass
            return

        if data.startswith("auction_table_change:"):
            _, num_s = data.split(":",1)
            try:
                n = int(num_s)
            except:
                try:
                    await query.answer("Invalid number", show_alert=True)
                except:
                    pass
                return
            if session.get("host_id") != user.id:
                try:
                    await query.answer("Only host can change tables", show_alert=True)
                except:
                    pass
                return
            old = session.get("tables") or 0
            session["tables"] = n
            save_session(chat_id, session)
            run_id = session.get("current_run_id") or start_new_run(chat_id, session)
            run = get_run(chat_id, run_id)
            if run:
                run["tables"] = n
                save_run(chat_id, run)
            try:
                if query.message:
                    await query.message.edit_text(f"Auction tables changing\n\nOld tables {old}/{old}\nNew tables {old}/{n}\n\nAuction table changed to {n}")
            except:
                pass
            try:
                await query.answer(f"Tables updated to {n}")
            except:
                pass
            return

        if data.startswith("auction_table_change_confirm:"):
            _, choice = data.split(":",1)
            if session.get("host_id") != user.id:
                try:
                    await query.answer("Only host can confirm", show_alert=True)
                except:
                    pass
                return
            if choice == "yes":
                old = session.get("tables") or 0
                if old >= 20:
                    try:
                        await query.answer("Maximum tables already set to 20", show_alert=True)
                    except:
                        pass
                    try:
                        await _send_message(context.bot, chat_id, "<b>MAXIMUM TABLES ALREADY SET TO 20 — YOU CAN'T INCREASE MORE TABLES.</b>")
                    except:
                        pass
                    return
                kb = build_increase_tables_keyboard(old)
                try:
                    if query.message:
                        await query.message.edit_text(f"Auction tables changing\n\nCurrent tables {old}/{old}\n\nPlease select new auction tables:", reply_markup=kb)
                    else:
                        await _send_message(context.bot, chat_id, f"Auction tables changing\n\nCurrent tables {old}/{old}\n\nPlease select new auction tables:", reply_markup=kb)
                    try:
                        await query.answer()
                    except:
                        pass
                except:
                    pass
                return
            else:
                try:
                    if query.message:
                        await query.message.edit_text("Table change cancelled.")
                    else:
                        await _send_message(context.bot, chat_id, "Table change cancelled.")
                except:
                    pass
                try:
                    await query.answer("No change")
                except:
                    pass
                return

        if data.startswith("auction_load:"):
            _, mode = data.split(":",1)
            if session.get("host_id") != user.id and user.id not in session.get("access_users", []):
                try:
                    member = await context.bot.get_chat_member(chat_id, user.id)
                    if member.status not in ("administrator", "creator"):
                        await query.answer("Only the auction host (or a chat admin) can load players", show_alert=True)
                        return
                except Exception:
                    try:
                        await query.answer("Only the auction host (or a chat admin) can load players", show_alert=True)
                    except:
                        pass
                    return
            try:
                await query.answer()
            except:
                pass
            try:
                if query.message:
                    try:
                        await query.message.delete()
                    except:
                        pass
            except:
                pass
            if mode == "internal":
                session["pending_load_origin"] = "internal"
                save_session(chat_id, session)
                try:
                    await _send_message(context.bot, chat_id, "CHOOSE AUCTION MODE\n\nAUTO MODE: The bot will automatically bring players from the given set for auction\n\nHOST MODE: The host will have to send players up for auction from the internal player list.", reply_markup=build_auto_mode_choice("internal"))
                except:
                    pass
                try:
                    await query.answer()
                except:
                    pass
                return
            else:
                session["pending_load_origin"] = "external"
                save_session(chat_id, session)
                try:
                    await _send_message(context.bot, chat_id, "CHOOSE AUCTION MODE\n\nAUTO MODE: The bot will automatically bring players from the given set for auction\n\nHOST MODE: The host will have to send players up for auction from the provided player list.", reply_markup=build_auto_mode_choice("external"))
                except:
                    pass
                try:
                    await query.answer()
                except:
                    pass
                return

        if data.startswith("auction_mode:"):
            parts = data.split(":")
            if len(parts) < 3:
                try:
                    await query.answer()
                except:
                    pass
                return
            mode = parts[1]
            origin = parts[2]
            if session.get("host_id") != user.id and user.id not in session.get("access_users", []):
                try:
                    await query.answer("Only the host can choose auction mode", show_alert=True)
                except:
                    pass
                return
            try:
                if query.message:
                    try:
                        await query.message.delete()
                    except:
                        pass
            except:
                pass
            if mode == "host":
                session["pending_load_origin"] = None
                save_session(chat_id, session)
                if origin == "internal":
                    db = load_db()
                    regs = []
                    tournaments = db.get("tournaments", {})
                    for t in tournaments.values():
                        regs.extend([r for r in t.get("registrations", []) if r.get("status") == "accepted"])
                    players = []
                    for r in regs:
                        players.append({
                            "user_id": r.get("user_id"),
                            "username": (r.get("username") or "").lstrip("@"),
                            "name": r.get("name"),
                            "role": r.get("role"),
                            "player_code": r.get("player_code")
                        })
                    for p in players:
                        await _prefetch_profile_for_player(chat_id, context, p)
                    session["players_list"] = players
                    save_session(chat_id, session)
                    run_id = session.get("current_run_id") or start_new_run(chat_id, session)
                    run = get_run(chat_id, run_id)
                    if run:
                        run["players_loaded"] = len(players)
                        save_run(chat_id, run)
                    try:
                        await _send_message(context.bot, chat_id, f"✅ All set — players loaded from registered list ({len(players)} players). Hey host {session.get('host_name')}, you can now start auction by sending /next <player_identifier> <base_price>")
                    except:
                        pass
                    try:
                        await query.answer("Players loaded (internal)")
                    except:
                        pass
                    return
                else:
                    try:
                        await _send_message(context.bot, chat_id, "Reply now to the message containing the player list and run /load.\nAcceptable formats:\n1) Comma-separated: @u1, @u2\n2) Newline-separated:\n@u1\n@u2\nThen reply to that message with /load (as host).")
                    except:
                        pass
                    try:
                        await query.answer("Host mode - reply with list and use /load")
                    except:
                        pass
                    return
            if mode == "auto":
                session["pending_load_origin"] = origin
                save_session(chat_id, session)
                try:
                    await _send_message(context.bot, chat_id, "Auto mode selected\n\nNow please reply your set list like this (reply to the message that contains the player list):\n\n/load set 1\n\nThis number shows your minimum price of your set (base price). The reply message list can be comma-separated or newline-separated and can contain @usernames or Telegram IDs. The bot will create a new auction set from this list and use it for auto-auction.")
                except:
                    pass
                try:
                    await query.answer("Auto mode selected")
                except:
                    pass
                return

        if data.startswith("end_confirm:"):
            parts = data.split(":")
            if len(parts) < 3:
                try:
                    await query.answer()
                except:
                    pass
                return
            choice = parts[1]
            host_token = int(parts[2]) if parts[2].isdigit() else None
            if host_token != session.get("host_id"):
                try:
                    await query.answer("Only the host can confirm", show_alert=True)
                except:
                    pass
                return
            if choice == "yes":
                task = countdown_tasks.get(chat_id)
                if task and not task.done():
                    task.cancel()
                run_id = session.get("current_run_id")
                run = get_run(chat_id, run_id) if run_id else None
                teams_snapshot = session.get("teams", {})
                logs_snapshot = session.get("logs", []) or []
                host_id_snapshot = session.get("host_id")
                host_name_snapshot = session.get("host_name") or ""
                try:
                    try:
                        await query.message.delete()
                    except Exception:
                        pass
                except Exception:
                    pass
                caption = ("⟦ AUCTION CLOSED SUCCESSFULLY ⟧\n\n"
                           "The auction has been officially concluded.  \n"
                           "All bids are locked, all players are finalized, and no further actions remain.\n\n"
                           "Your final team squad has been sent to your DM.")
                if OWNER_TELEGRAM_ID:
                    try:
                        owner_chat = await context.bot.get_chat(OWNER_TELEGRAM_ID)
                        owner_name = ((getattr(owner_chat, "first_name", "") or "") + (" " + getattr(owner_chat, "last_name", "") if getattr(owner_chat, "last_name", None) else "")).strip()
                        if not owner_name:
                            owner_name = getattr(owner_chat, "username", "") or f"User {OWNER_TELEGRAM_ID}"
                    except Exception:
                        owner_name = f"User {OWNER_TELEGRAM_ID}"
                    caption += f"\n\nMade by: <a href='tg://user?id={OWNER_TELEGRAM_ID}'>{owner_name}</a>"
                try:
                    sent = await context.bot.send_photo(chat_id=chat_id, photo=END_CLOSED_IMAGE, caption=caption, parse_mode=ParseMode.HTML)
                except Exception:
                    await _send_message(context.bot, chat_id, caption)
                if teams_snapshot:
                    for tname, members in (teams_snapshot or {}).items():
                        if not members:
                            continue
                        owner_id = members[0]
                        if not owner_id:
                            continue
                        team_players = []
                        total_spent = 0
                        for l in logs_snapshot:
                            if l.get("buyer_id") and ( (l.get("buyer_id") in (members or [])) or ( ( (getattr(session.get("assistants"),'items',None)) and (session.get("assistants") and list(session.get("assistants").values()) and l.get("buyer_id") in list(session.get("assistants").values()))) ) ):
                                if l.get("price"):
                                    team_players.append({"name": l.get("player_name"), "username": (l.get("player_username") or ""), "price": l.get("price")})
                                    total_spent += int(l.get("price") or 0)
                        total_players = len(team_players)
                        lines = []
                        idx = 1
                        for p in team_players:
                            lines.append(f"Player Name: {p.get('name')}\nUsername   : @{(p.get('username') or '')}\nBuy At     : Cr.{p.get('price')}\n")
                            idx += 1
                        squad_caption = f"⟦ YOUR FINAL TEAM SQUAD — {tname} ⟧\n\nTotal Players : {total_players}\n\nPlayers:\n\n"
                        if lines:
                            squad_caption += "\n".join(lines)
                        else:
                            squad_caption += "No players bought.\n\n"
                        squad_caption += f"\nTotal Spent : Cr.{total_spent}\n\n— End of Squad —\n\nI hope your tournament goes well. Wishing you all the best!"
                        try:
                            await context.bot.send_message(chat_id=owner_id, text=squad_caption)
                        except Exception:
                            pass
                try:
                    db = load_db()
                    sessions = db.get("auction_sessions", {})
                    sessions.pop(str(chat_id), None)
                    db["auction_sessions"] = sessions
                    save_db(db)
                except Exception:
                    try:
                        session["active"] = False
                        session["host_id"] = None
                        session["current_slot"] = None
                        save_session(chat_id, session)
                    except:
                        pass
                try:
                    await query.answer("Auction closed and data cleared")
                except:
                    pass
                return
            else:
                try:
                    await query.answer("Auction end cancelled")
                except:
                    pass
                return

        if data.startswith("min_buy:"):
            _, val = data.split(":",1)
            try:
                chosen = int(val)
            except:
                try:
                    await query.answer("Invalid choice", show_alert=True)
                except:
                    pass
                return
            if session.get("host_id") != user.id:
                try:
                    await query.answer("Only host can choose", show_alert=True)
                except:
                    pass
                return
            session["min_buy"] = chosen
            save_session(chat_id, session)
            try:
                await query.message.edit_text(f"Minimum buying per team set to {chosen}. Now choose maximum buying per team:")
            except:
                pass
            max_buttons = [InlineKeyboardButton(str(x), callback_data=f"max_buy:{x}") for x in range(8,27)]
            kb_rows = [max_buttons[i:i+5] for i in range(0, len(max_buttons), 5)]
            try:
                sent = await _send_message(context.bot, chat_id, "Choose maximum buying per team:", reply_markup=InlineKeyboardMarkup(kb_rows))
                session["max_choice_key"] = f"{chat_id}:{sent.message_id}"
                save_session(chat_id, session)
            except:
                pass
            try:
                await query.answer(f"Minimum set to {chosen}")
            except:
                pass
            return

        if data.startswith("max_buy:"):
            _, val = data.split(":",1)
            try:
                chosen = int(val)
            except:
                try:
                    await query.answer("Invalid choice", show_alert=True)
                except:
                    pass
                return
            if session.get("host_id") != user.id:
                try:
                    await query.answer("Only host can choose", show_alert=True)
                except:
                    pass
                return
            session["max_buy"] = chosen
            save_session(chat_id, session)
            try:
                if query.message:
                    await query.message.edit_text(f"Maximum buying per team set to {chosen}. Min: {session.get('min_buy')}, Max: {session.get('max_buy')}")
            except:
                pass
            try:
                await query.answer(f"Maximum set to {chosen}")
            except:
                pass
            try:
                sent = await _send_message(context.bot, chat_id, "Do you want to set auction bidding time now?", reply_markup=build_time_confirm_keyboard(session.get("host_id") or 0))
                session["time_choice_msg"] = f"{chat_id}:{sent.message_id}"
                save_session(chat_id, session)
            except:
                pass
            return

        if data.startswith("time_confirm:"):
            parts = data.split(":")
            if len(parts) < 3:
                try:
                    await query.answer()
                except:
                    pass
                return
            choice = parts[1]
            host_token = int(parts[2]) if parts[2].isdigit() else None
            if host_token != session.get("host_id"):
                try:
                    await query.answer("Only the host can set time", show_alert=True)
                except:
                    pass
                return
            if choice == "default":
                session["countdown_seconds"] = DEFAULT_COUNTDOWN
                save_session(chat_id, session)
                try:
                    await query.message.edit_text(f"Auction bidding time set to default {DEFAULT_COUNTDOWN} seconds.")
                except:
                    pass
                try:
                    await query.answer("Time set to default")
                except:
                    pass
                return
            else:
                try:
                    await query.message.edit_text("Please send /time <seconds> (15-30). Example: /time 20")
                except:
                    pass
                try:
                    await query.answer("Send /time <seconds>")
                except:
                    pass
                return

        await query.answer()
    except Exception:
        try:
            await query.answer("Internal error", show_alert=True)
        except:
            pass

callback_handler = CallbackQueryHandler(callback_router)

async def set_table_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not msg or not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if session.get("host_id") != user.id and user.id not in session.get("access_users", []):
        await msg.reply_text("Only the auction host can set the number of tables.")
        return
    current = session.get("tables")
    if current:
        if current >= 20:
            await _send_message(context.bot, chat_id, "<b>MAXIMUM TABLES ALREADY SET TO 20 — YOU CAN'T INCREASE MORE TABLES.</b>")
            return
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yes I want", callback_data="auction_table_change_confirm:yes"), InlineKeyboardButton("No okay", callback_data="auction_table_change_confirm:no")]])
        text = f"The current auction table is {current}. Do you want to change tables?"
        sent = await _send_message(context.bot, chat_id, text, reply_markup=kb, parse_mode=ParseMode.HTML)
        session["last_table_msg_key"] = f"{chat_id}:{sent.message_id}"
        save_session(chat_id, session)
        return
    sent = await _send_message(context.bot, chat_id, "Please choose number of auction table between 2 - 20:", reply_markup=build_table_keyboard())
    session["last_table_msg_key"] = f"{chat_id}:{sent.message_id}"
    save_session(chat_id, session)

set_table_handler = CommandHandler("set_table", set_table_cmd)

async def table_reply_handler_func(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.reply_to_message or not msg.text:
        return
    chat = update.effective_chat or (msg.chat if msg else None)
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    last_key = session.get("last_table_msg_key")
    if not last_key:
        return
    try:
        last_chat, last_msg_id = last_key.split(":")
        last_msg_id = int(last_msg_id)
    except:
        return
    if msg.reply_to_message.message_id != last_msg_id:
        return
    try:
        n = int(msg.text.strip().split()[0])
    except:
        await msg.reply_text("Please reply with a number between 2 and 20.")
        return
    if n < 2 or n > 20:
        await msg.reply_text("Please reply with a number between 2 and 20.")
        return
    session["tables"] = n
    save_session(chat_id, session)
    run_id = session.get("current_run_id") or start_new_run(chat_id, session)
    run = get_run(chat_id, run_id)
    if run:
        run["tables"] = n
        save_run(chat_id, run)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=last_msg_id)
    except Exception:
        pass
    txt = f"✅ Auction tables confirmed ({n}).\n\nNow set minimum buying limit for all teams:"
    min_buttons = [InlineKeyboardButton(str(x), callback_data=f"min_buy:{x}") for x in range(3,13)]
    kb_rows = [min_buttons[i:i+5] for i in range(0, len(min_buttons), 5)]
    sent = await _send_message(context.bot, chat_id, txt, reply_markup=InlineKeyboardMarkup(kb_rows))
    session["min_choice_key"] = f"{chat_id}:{sent.message_id}"
    save_session(chat_id, session)
    return

table_reply_handler = MessageHandler(filters.TEXT & filters.REPLY & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP), table_reply_handler_func)

def _extract_username_from_entities(text: str, entities: Optional[list]) -> Optional[str]:
    if not text or not entities:
        return None
    for ent in entities:
        try:
            ent_type = ent.type if not isinstance(ent, dict) else ent.get("type")
            offset = ent.offset if not isinstance(ent, dict) else ent.get("offset")
            length = ent.length if not isinstance(ent, dict) else ent.get("length")
        except:
            continue
        if ent_type == "mention":
            try:
                return text[offset:offset+length].lstrip("@")
            except Exception:
                continue
    return None

def _find_registration_by_username_or_code(db: Dict[str, Any], identifier: str) -> Optional[Dict[str, Any]]:
    if not identifier:
        return None
    tournaments = db.get("tournaments", {})
    for t in tournaments.values():
        for r in t.get("registrations", []) or []:
            if (r.get("username") or "").lstrip("@").lower() == identifier.lstrip("@").lower():
                return r
            if r.get("player_code") and str(r.get("player_code")) == str(identifier):
                return r
            if r.get("user_id") and str(r.get("user_id")) == str(identifier):
                return r
    return None

def _recursive_find_userid_by_username(obj: Any, username: str) -> Optional[int]:
    if not obj:
        return None
    uname_l = username.lstrip("@").lower()
    if isinstance(obj, dict):
        u = obj.get("username") or obj.get("user") or obj.get("user_name")
        uid = obj.get("user_id") or obj.get("id") or obj.get("tg_id")
        if u and isinstance(u, str) and uid:
            if u.lstrip("@").lower() == uname_l:
                try:
                    return int(uid)
                except:
                    return None
        for k, v in obj.items():
            found = _recursive_find_userid_by_username(v, username)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _recursive_find_userid_by_username(item, username)
            if found:
                return found
    return None

async def _extract_target_from_message(message: Message) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not message:
        return None, "no message"
    if getattr(message, "from_user", None):
        u = message.from_user
        return {"user_id": getattr(u, "id", None), "first_name": getattr(u, "first_name", ""), "last_name": getattr(u, "last_name", ""), "full_name": getattr(u, "full_name", None) or f"{getattr(u,'first_name','') or ''} {getattr(u,'last_name','') or ''}".strip()}, None
    if getattr(message, "forward_from", None):
        f = message.forward_from
        return {"user_id": getattr(f, "id", None), "first_name": getattr(f, "first_name", ""), "last_name": getattr(f, "last_name", ""), "full_name": getattr(f, "full_name", None) or f"{getattr(f,'first_name','') or ''} {getattr(f,'last_name','') or ''}".strip()}, None
    if getattr(message, "sender_chat", None):
        return None, "message is from a channel/sender_chat (anonymous)"
    text = message.text or message.caption or ""
    ent_username = _extract_username_from_entities(text, getattr(message, "entities", None))
    if ent_username:
        db = load_db()
        reg = _find_registration_by_username_or_code(db, ent_username)
        if reg:
            return {"user_id": reg.get("user_id"), "first_name": reg.get("name") or reg.get("username") or ent_username}, None
        return {"user_id": None, "first_name": ent_username, "last_name": ""}, None
    return None, "could not identify target user from replied message"

def _is_host_or_access(session: Dict[str, Any], user_id: int) -> bool:
    if not session:
        return False
    if session.get("host_id") == user_id:
        return True
    access = session.get("access_users") or []
    if user_id in access:
        return True
    return False

def _is_team_owner(session: Dict[str, Any], user_id: int, team_name: Optional[str] = None) -> Optional[str]:
    teams = session.get("teams", {}) or {}
    if team_name:
        members = teams.get(team_name) or []
        if members and members[0] == user_id:
            return team_name
        return None
    for tname, members in teams.items():
        if members and members[0] == user_id:
            return tname
    return None

def _get_team_of_user(session: Dict[str, Any], user_id: int) -> Optional[str]:
    """
    Returns the team name for a user id.
    Checks team members (owner & other members) and assistants mapping.
    """
    teams = session.get("teams", {}) or {}
    for tname, members in teams.items():
        if members and user_id in members:
            return tname
    assistants = session.get("assistants", {}) or {}
    for tname, aid in assistants.items():
        try:
            if aid and int(aid) == int(user_id):
                return tname
        except:
            continue
    return None

async def team_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not msg or not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if not _is_host_or_access(session, user.id) and _is_team_owner(session, user.id) is None:
        await msg.reply_text("Only the auction host can assign or remove teams.")
        return
    raw = (msg.text or "").strip()
    if not raw:
        await msg.reply_text("Usage: /team <TeamName> (reply to user message) OR /team remove <TeamName> OR /team <TeamName> @username")
        return
    if raw.lower().startswith("/team"):
        remainder = raw.split(maxsplit=1)
        remainder = remainder[1].strip() if len(remainder) > 1 else ""
    else:
        remainder = raw
    tokens = remainder.split()
    if tokens and tokens[0].lower() == "remove" and len(tokens) >= 2:
        team_name = " ".join(tokens[1:]).strip()
        teams = session.get("teams", {}) or {}
        found_key = None
        for k in teams.keys():
            if k.lower() == team_name.lower():
                found_key = k
                break
        if not found_key:
            await msg.reply_text("Team not found.")
            return
        members = teams.pop(found_key, None)
        session["teams"] = teams
        save_session(chat_id, session)
        await msg.reply_text(f"Team slot '{found_key}' removed. The total table count remains {session.get('tables')}. You can reassign a team to this slot.")
        return
    if msg.reply_to_message:
        if not remainder:
            await msg.reply_text("Usage: reply to a user's message with /team <TeamName>")
            return
        team_name = remainder
        reply_msg = msg.reply_to_message
        target_info, reason = await _extract_target_from_message(reply_msg)
        if not target_info:
            text_reason = reason or "unknown"
            await msg.reply_text(f"Could not identify the target user. Reason: {text_reason}.")
            return
        target_id = target_info.get("user_id")
        target_name = target_info.get("full_name") or f"{target_info.get('first_name','') or ''} {target_info.get('last_name','') or ''}".strip()
    else:
        if not remainder:
            await msg.reply_text("When not replying, include the username or user id after the team name. Example: /team RCB @username")
            return
        parts = remainder.split(maxsplit=1)
        team_name = parts[0] if parts else remainder
        arg = parts[1].strip() if len(parts) > 1 else ""
        if not arg:
            await msg.reply_text("When not replying, include the username or user id after the team name. Example: /team RCB @username")
            return
        candidate = arg.lstrip("@")
        target_id = None
        target_name = None
        session_players = session.get("players_list") or []
        for p in session_players:
            if p and p.get("username") and p.get("username").lstrip("@").lower() == candidate.lower():
                target_id = p.get("user_id")
                target_name = p.get("name") or p.get("username")
                break
            if p and p.get("player_code") and str(p.get("player_code")) == candidate:
                target_id = p.get("user_id")
                target_name = p.get("name") or p.get("username")
                break
            if p and p.get("user_id") and str(p.get("user_id")) == candidate:
                target_id = p.get("user_id")
                target_name = p.get("name") or p.get("username")
                break
        if not target_id:
            db = load_db()
            reg = _find_registration_by_username_or_code(db, candidate)
            if reg:
                target_id = reg.get("user_id")
                target_name = reg.get("name") or reg.get("username") or candidate
        if not target_id:
            try:
                maybe_id = int(candidate)
                target_id = maybe_id
                target_name = candidate
            except:
                target_id = None
                target_name = candidate
    if not team_name:
        await msg.reply_text("Team name missing.")
        return
    teams = session.get("teams", {})
    existing_key = None
    for k in teams.keys():
        if k.lower() == team_name.lower():
            existing_key = k
            break
    key = existing_key or team_name
    if key not in teams:
        if session.get("tables") is None:
            await msg.reply_text("Please set auction tables first (/set_table).")
            return
        current_assigned = len([t for t, m in (teams.items()) if m and m[0]])
        if current_assigned >= (session.get("tables") or 0):
            await msg.reply_text(f"Cannot assign more teams. Maximum tables reached ({session.get('tables')}). If you want to increase tables, run /set_table again.")
            return
        teams[key] = []
    if target_id in sum([v for v in teams.values()], []):
        for tname, members in teams.items():
            if members and target_id in members and tname.lower() != key.lower():
                await msg.reply_text(f"This player has already assigned as team {tname}.")
                return
    if target_id not in teams[key]:
        teams[key].append(target_id)
    session["teams"] = teams
    if session.get("budget") and key not in session.get("team_budgets", {}):
        tb = session.get("team_budgets", {})
        tb[key] = session.get("budget")
        session["team_budgets"] = tb
    save_session(chat_id, session)
    run_id = session.get("current_run_id") or start_new_run(chat_id, session)
    run = get_run(chat_id, run_id)
    if run:
        run_teams = run.get("teams", {})
        if key not in run_teams:
            run_teams[key] = []
        if target_id not in run_teams[key]:
            run_teams[key].append(target_id)
        run["teams"] = run_teams
        save_run(chat_id, run)
        append_run_log(chat_id, run.get("run_id"), {"event": "team_assigned", "team": key, "user_id": target_id, "user_name": target_name or "", "ts": int(time.time())})
    try:
        db = load_db()
        if not db.get("owners"):
            db["owners"] = {}
        if not db.get("username_to_owner"):
            db["username_to_owner"] = {}
        if target_id:
            stored_username = None
            try:
                tg_chat = await context.bot.get_chat(target_id)
                stored_username = getattr(tg_chat, "username", None)
                stored_fullname = (getattr(tg_chat, "first_name", "") or "") + (" " + getattr(tg_chat, "last_name", "") if getattr(tg_chat, "last_name", None) else "")
                db["owners"][str(target_id)] = {"username": (stored_username or "").lstrip("@") if stored_username else "", "team": key, "name": stored_fullname.strip() or target_name or ""}
                if stored_username:
                    db["username_to_owner"][stored_username.lstrip("@").lower()] = target_id
            except Exception:
                db["owners"][str(target_id)] = {"username": "", "team": key, "name": target_name or ""}
        save_db(db)
    except Exception:
        pass
    tables_total = session.get("tables") or 0
    assigned_count = len([t for t, m in (teams.items()) if m and m[0]])
    if target_id:
        reply_text = (f"✅ {target_name} has been assigned to team {key}.\n\n" f"Teams set: {assigned_count} / {tables_total}\n")
    else:
        reply_text = (f"✅ {target_name} has been assigned to team {key} (no numeric user_id available).\n\n" f"Teams set: {assigned_count} / {tables_total}\n")
    await _send_message(context.bot, chat_id, reply_text)
    if assigned_count >= tables_total and tables_total > 0:
        await _send_message(context.bot, chat_id, f"All team tables set now ({assigned_count}). Please set the budget using /budget <number>.")
    return

team_handler = CommandHandler("team", team_cmd)

async def budget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if not _is_host_or_access(session, user.id):
        await msg.reply_text("Only the auction host can set the budget.")
        return
    run_id = session.get("current_run_id")
    run = get_run(chat_id, run_id) if run_id else None
    if run and (session.get("current_slot") or (run.get("sold_players") or []) or (run.get("unsold_players") or [])):
        await msg.reply_text(f"Budget has already set to {session.get('budget') or 0} or auction already started. Cannot change now.")
        return
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply_text("Usage: /budget <number>")
        return
    try:
        amt = int(parts[1].replace(",", "").strip())
    except:
        await msg.reply_text("Please provide a valid integer amount.")
        return
    session["budget"] = amt
    tb = session.get("team_budgets", {}) or {}
    for k in (session.get("teams") or {}).keys():
        tb.setdefault(k, amt)
    session["team_budgets"] = tb
    save_session(chat_id, session)
    run_id = session.get("current_run_id") or start_new_run(chat_id, session)
    run = get_run(chat_id, run_id)
    if run:
        run["budget"] = amt
        save_run(chat_id, run)
    await _send_message(context.bot, chat_id, f"✅ Budget set to {amt} for all teams.\nNow choose player load method: internal or load from provided list.", reply_markup=build_load_keyboard())
    return

budget_handler = CommandHandler("budget", budget_cmd)

async def load_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    host_id = session.get("host_id")
    if host_id != user.id and user.id not in session.get("access_users", []):
        try:
            member = await context.bot.get_chat_member(chat_id, user.id)
            if member.status not in ("administrator", "creator"):
                await msg.reply_text("Only the auction host (or a chat admin) can load players.")
                return
        except Exception:
            await msg.reply_text("Only the auction host (or a chat admin) can load players.")
            return
    reply_msg = msg.reply_to_message
    text = (msg.text or "").strip()
    parts = text.split()
    is_set_mode = False
    set_base_price = None
    if len(parts) >= 3 and parts[1].lower() == "set":
        try:
            set_base_price = float(parts[2])
            is_set_mode = True
        except:
            is_set_mode = False
    if not reply_msg and not is_set_mode:
        await msg.reply_text("Reply to the message containing the player list and run /load.\nAcceptable formats:\n1) Comma-separated: @u1, @u2\n2) Newline-separated:\n@u1\n@u2\nThen reply to that message with /load (as host).")
        return
    if is_set_mode and not reply_msg:
        await msg.reply_text("Reply to the message containing the player list and run /load set <base_price> to create a new set.")
        return
    source_text = ""
    if reply_msg:
        if getattr(reply_msg, "text", None):
            source_text = reply_msg.text
        elif getattr(reply_msg, "caption", None):
            source_text = reply_msg.caption
        else:
            source_text = ""
    if not source_text or not source_text.strip():
        await msg.reply_text("The replied message contains no textual usernames to parse.")
        return
    raw = source_text.strip()
    chunks = re.split(r',\s*|\n+', raw)
    players = []
    inserted = 0
    conn = None
    existing = set()
    try:
        conn = sqlite3.connect(USERNAMES_DB_PATH, timeout=10)
        ensure_usernames_table(conn)
        cur = conn.cursor()
        cur.execute("SELECT username_lower FROM users")
        existing = {r[0] for r in cur.fetchall() if r and r[0]}
    except Exception:
        existing = set()
    db = load_db()
    tournaments = db.get("tournaments", {})
    regs = []
    for t in tournaments.values():
        regs.extend(t.get("registrations", []) or [])
    reg_map = {}
    for r in regs:
        key = (r.get("username") or "").lstrip("@").lower()
        if key:
            reg_map[key] = r
        if r.get("player_code"):
            reg_map[str(r.get("player_code"))] = r
        if r.get("user_id"):
            reg_map[str(r.get("user_id"))] = r
    for chunk in chunks:
        chunk = (chunk or "").strip()
        if not chunk:
            continue
        username_match = re.search(r'@([A-Za-z0-9_]{1,64})', chunk)
        number_match = re.search(r'(\d{5,20})', chunk)
        username = None
        user_id = None
        if username_match:
            username = username_match.group(1).strip()
        if number_match:
            try:
                user_id = int(number_match.group(1))
            except:
                user_id = None
        if not username and re.fullmatch(r'\d{5,20}', chunk):
            try:
                user_id = int(chunk)
            except:
                user_id = None
        if username == "-":
            username = None
        if user_id is None and username is None:
            plain = chunk.strip()
            if plain.startswith("@"):
                plain = plain[1:]
            plain_clean = re.sub(r'[^\w\-]', '', plain)
            if plain_clean:
                if plain_clean.isdigit():
                    try:
                        user_id = int(plain_clean)
                    except:
                        user_id = None
                else:
                    username = plain_clean
        reg = None
        if username:
            reg = reg_map.get(username.lstrip("@").lower())
        if not reg and user_id:
            reg = reg_map.get(str(user_id))
        if reg:
            pentry = {
                "user_id": reg.get("user_id"),
                "username": (reg.get("username") or "").lstrip("@"),
                "name": reg.get("name"),
                "role": reg.get("role"),
                "player_code": reg.get("player_code"),
                "placeholder": False,
                "base_price": None
            }
            await _prefetch_profile_for_player(chat_id, context, pentry)
            players.append(pentry)
        else:
            if user_id:
                pentry = {
                    "user_id": user_id,
                    "username": None,
                    "name": str(user_id),
                    "role": None,
                    "player_code": None,
                    "placeholder": False,
                    "base_price": None
                }
                try:
                    tg_chat = await context.bot.get_chat(user_id)
                    profile_username = getattr(tg_chat, "username", None)
                    first = getattr(tg_chat, "first_name", "") or ""
                    last = getattr(tg_chat, "last_name", "") or ""
                    profile_fullname = f"{first} {last}".strip() if (first or last) else None
                    if profile_username:
                        pentry["username"] = profile_username.lstrip("@")
                    if profile_fullname:
                        pentry["name"] = profile_fullname
                    if profile_username:
                        try:
                            clean = profile_username.lstrip("@")
                            lower = clean.lower()
                            if lower not in existing and conn:
                                cur.execute("INSERT OR IGNORE INTO users (username, username_lower, added_at) VALUES (?, ?, ?)", ("@" + clean, lower, time.strftime("%Y-%m-%dT%H:%M:%S")))
                                conn.commit()
                                existing.add(lower)
                                inserted += 1
                        except:
                            pass
                except Exception:
                    pass
                players.append(pentry)
            elif username:
                pentry = {
                    "user_id": None,
                    "username": username.lstrip("@"),
                    "name": username.lstrip("@"),
                    "role": None,
                    "player_code": None,
                    "placeholder": True,
                    "base_price": None
                }
                try:
                    clean = pentry["username"].lstrip("@")
                    lower = clean.lower()
                    if conn and lower not in existing:
                        cur.execute("INSERT OR IGNORE INTO users (username, username_lower, added_at) VALUES (?, ?, ?)", ("@" + clean, lower, time.strftime("%Y-%m-%dT%H:%M:%S")))
                        conn.commit()
                        existing.add(lower)
                        inserted += 1
                except:
                    pass
                players.append(pentry)
            else:
                pentry = {
                    "user_id": None,
                    "username": chunk,
                    "name": chunk,
                    "role": None,
                    "player_code": None,
                    "placeholder": True,
                    "base_price": None
                }
                players.append(pentry)
    if conn:
        try:
            conn.close()
        except:
            pass
    if is_set_mode:
        set_entry = {
            "base_price": set_base_price,
            "players": []
        }
        for p in players:
            p_copy = dict(p)
            p_copy["set_base_price"] = set_base_price
            p_copy["base_price"] = set_base_price
            set_entry["players"].append(p_copy)
        loaded_sets = session.get("loaded_sets", []) or []
        loaded_sets.append(set_entry)
        session["loaded_sets"] = loaded_sets
        save_session(chat_id, session)
        set_index = len(loaded_sets)
        totals = len(set_entry["players"])
        await msg.reply_text(f"AUCTION SET {set_index} UPDATED\n\nTOTALS PLAYERS IN SET: ({str(totals).zfill(2)})\nSET BASE PRICE: ({set_base_price}) CR\n\nLOAD NEXT SET LIST WITH SAME PROCESS")
        return
    existing_players = session.get("players_list") or []
    existing_map = {}
    for p in existing_players:
        if p and p.get("username"):
            existing_map[str(p.get("username")).lstrip("@").lower()] = p
        elif p and p.get("user_id"):
            existing_map[str(p.get("user_id"))] = p
    for p in players:
        key = None
        if p.get("username"):
            key = str(p.get("username")).lstrip("@").lower()
        elif p.get("user_id"):
            key = str(p.get("user_id"))
        if not key:
            continue
        existing_map[key] = p
    merged = list(existing_map.values())
    for p in merged:
        await _prefetch_profile_for_player(chat_id, context, p)
    session["players_list"] = merged
    save_session(chat_id, session)
    run_id = session.get("current_run_id") or start_new_run(chat_id, session)
    run = get_run(chat_id, run_id)
    if run:
        run["players_loaded"] = len(merged)
        save_run(chat_id, run)
    total_usernames = len(chunks)
    loaded_player = len([p for p in players if not p.get("placeholder")])
    maths_username = inserted
    host_name = session.get("host_name") or ""
    reply = ("Players loaded\n\n" f"👥 players on list {total_usernames}\n" f"✅ players loaded: {loaded_player}\n" f"📁 Already in data: {maths_username}\n\n" f"Hey {host_name} players are loaded for auction now you can send the first player for bidding for full details send /next")
    await msg.reply_text(reply)
    return

load_handler = CommandHandler("load", load_cmd)
load_msg_handler = MessageHandler(filters.REPLY & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP), load_cmd)
load_reply_fallback_handler = load_msg_handler

def _normalize_player_entry(p: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(p or {})
    if p.get("username"):
        p["username"] = str(p["username"]).lstrip("@")
    if p.get("user_id") is not None:
        try:
            p["user_id"] = int(p["user_id"])
        except:
            p["user_id"] = p["user_id"]
    return p

async def find_player_async(session: Dict[str, Any], identifier: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
    if not identifier:
        return None
    id_clean = str(identifier).strip()
    if id_clean.startswith("@"):
        id_clean = id_clean[1:]
    players = session.get("players_list") or []
    for p in players:
        p2 = _normalize_player_entry(p)
        uname = (p2.get("username") or "").lstrip("@")
        if uname and uname.lower() == id_clean.lower():
            db = load_db()
            try:
                found_id = _recursive_find_userid_by_username(db, uname)
            except Exception:
                found_id = None
            if found_id:
                p2["user_id"] = p2.get("user_id") or found_id
                try:
                    tg_chat = await context.bot.get_chat(int(found_id))
                    if tg_chat:
                        profile_username = getattr(tg_chat, "username", None)
                        first = getattr(tg_chat, "first_name", "") or ""
                        last = getattr(tg_chat, "last_name", "") or ""
                        profile_fullname = f"{first} {last}".strip() if (first or last) else None
                        if profile_username:
                            p2["profile_username"] = profile_username.lstrip("@")
                        if profile_fullname:
                            p2["profile_fullname"] = profile_fullname
                except Exception:
                    pass
            else:
                try:
                    tg_chat = await context.bot.get_chat(f"@{uname}")
                    if tg_chat:
                        profile_username = getattr(tg_chat, "username", None)
                        first = getattr(tg_chat, "first_name", "") or ""
                        last = getattr(tg_chat, "last_name", "") or ""
                        profile_fullname = f"{first} {last}".strip() if (first or last) else None
                        if profile_username:
                            p2["profile_username"] = profile_username.lstrip("@")
                        if profile_fullname:
                            p2["profile_fullname"] = profile_fullname
                        if getattr(tg_chat, "id", None):
                            p2["user_id"] = p2.get("user_id") or getattr(tg_chat, "id", None)
                except Exception:
                    pass
            return p2
    for p in players:
        p2 = _normalize_player_entry(p)
        if p2.get("player_code") and str(p2.get("player_code")) == id_clean:
            if p2.get("user_id"):
                try:
                    tg_chat = await context.bot.get_chat(int(p2.get("user_id")))
                    if tg_chat:
                        profile_username = getattr(tg_chat, "username", None)
                        first = getattr(tg_chat, "first_name", "") or ""
                        last = getattr(tg_chat, "last_name", "") or ""
                        p2["profile_fullname"] = f"{first} {last}".strip() if (first or last) else p2.get("name")
                        if profile_username:
                            p2["profile_username"] = profile_username.lstrip("@")
                except Exception:
                    pass
            return p2
    if re.fullmatch(r"\d+", id_clean):
        try:
            tg_id = int(id_clean)
        except:
            tg_id = None
        if tg_id:
            profile_username = None
            profile_fullname = None
            try:
                tg_user = await context.bot.get_chat(tg_id)
                profile_username = getattr(tg_user, "username", None)
                first = getattr(tg_user, "first_name", "") or ""
                last = getattr(tg_user, "last_name", "") or ""
                profile_fullname = f"{first} {last}".strip() if (first or last) else None
            except Exception:
                profile_username = None
                profile_fullname = None
            if profile_username:
                for p in players:
                    p2 = _normalize_player_entry(p)
                    if p2.get("username") and p2.get("username").lstrip("@").lower() == profile_username.lstrip("@").lower():
                        p2["profile_username"] = profile_username.lstrip("@")
                        if profile_fullname:
                            p2["profile_fullname"] = profile_fullname
                        p2["user_id"] = p2.get("user_id") or tg_id
                        return p2
            if profile_username or profile_fullname:
                return {"user_id": tg_id, "username": profile_username.lstrip("@") if profile_username else id_clean, "name": profile_fullname or profile_username or str(tg_id), "profile_username": profile_username.lstrip("@") if profile_username else None, "profile_fullname": profile_fullname}
            return None
    db = load_db()
    try:
        found_id = _recursive_find_userid_by_username(db, id_clean)
    except Exception:
        found_id = None
    if found_id:
        try:
            tg_user = await context.bot.get_chat(found_id)
            profile_username = getattr(tg_user, "username", None)
            first = getattr(tg_user, "first_name", "") or ""
            last = getattr(tg_user, "last_name", "") or ""
            profile_fullname = f"{first} {last}".strip() if (first or last) else None
        except Exception:
            profile_username = None
            profile_fullname = None
        if profile_username:
            for p in players:
                p2 = _normalize_player_entry(p)
                if p2.get("username") and p2.get("username").lstrip("@").lower() == profile_username.lstrip("@").lower():
                    p2["profile_username"] = profile_username.lstrip("@")
                    if profile_fullname:
                        p2["profile_fullname"] = profile_fullname
                    p2["user_id"] = p2.get("user_id") or found_id
                    return p2
        return {"user_id": found_id, "username": profile_username.lstrip("@") if profile_username else id_clean, "name": profile_fullname or id_clean, "profile_username": profile_username.lstrip("@") if profile_username else None, "profile_fullname": profile_fullname}
    reg = _find_registration_by_username_or_code(db, id_clean)
    if reg:
        return {"user_id": reg.get("user_id"), "username": (reg.get("username") or "").lstrip("@"), "name": reg.get("name"), "role": reg.get("role"), "player_code": reg.get("player_code")}
    return None

def _team_total_spent(session: Dict[str, Any], team_name: str) -> int:
    logs = session.get("logs", []) or []
    total = 0
    for l in logs:
        buyer_id = l.get("buyer_id")
        if not buyer_id:
            continue
        buyer_team = _get_team_of_user(session, buyer_id)
        if buyer_team == team_name and l.get("price"):
            total += int(l.get("price") or 0)
    return total

def get_countdown(session: Dict[str, Any]) -> int:
    try:
        v = int(session.get("countdown_seconds", DEFAULT_COUNTDOWN))
        if v < 15:
            return 15
        if v > 30:
            return 30
        return v
    except:
        return DEFAULT_COUNTDOWN

async def parse_next_identifier_and_price(text: str) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    if not text:
        return None, None, None
    t = text.strip()
    t = re.sub(r'^\s*/next(@[^\s]+)?\s*', '/next ', t, flags=re.IGNORECASE)
    price_match = re.search(r'(\d+(\.\d+)?)\s*$', t)
    if not price_match:
        return None, None, None
    price = float(price_match.group(1))
    before_price = t[:price_match.start()].strip()
    at_matches = list(re.finditer(r'@([A-Za-z0-9_]{1,64})', before_price))
    if at_matches:
        last = at_matches[-1]
        identifier = last.group(0)
        pre_text = before_price[:last.start()].strip()
        return identifier, price, pre_text
    numeric_match = None
    tokens = before_price.split()
    for i in range(len(tokens)-1, -1, -1):
        tok = tokens[i].strip()
        if re.fullmatch(r'\d+', tok):
            numeric_match = tok
            pre_text = " ".join(tokens[:i]).strip()
            return numeric_match, price, pre_text
    if tokens:
        identifier = tokens[-1]
        pre_text = " ".join(tokens[:-1]).strip()
        return identifier, price, pre_text
    return None, price, None

async def _try_send_next_auto(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        session = get_session(chat_id)
        if not session.get("auto_mode"):
            return
        if session.get("current_slot"):
            return
        players = session.get("auto_set_list") or []
        if not players:
            set_num = session.get("auto_set_number") or 0
            host_id = session.get("host_id")
            host_name = session.get("host_name") or "Host"
            if host_id:
                host_tag = f"<a href='tg://user?id={host_id}'>{host_name}</a>"
            else:
                host_tag = host_name
            loaded_sets = session.get("loaded_sets") or []
            if isinstance(set_num, int) and set_num:
                next_set_num = (set_num or 0) + 1
                if next_set_num <= len(loaded_sets):
                    text = (f"⟦ SET {set_num} AUCTION COMPLETED ⟧\n\n"
                            f"{host_tag}, set {set_num} auction is completed. Please start the next set auction: /start_auction {next_set_num}\n\n"
                            f"Guideline: Use /start_auction {next_set_num} to auto-start the next set. You can also run /start_auction <set_number> anytime.")
                    try:
                        await _send_message(context.bot, chat_id, text, parse_mode=ParseMode.HTML)
                    except:
                        pass
                else:
                    caption = ("⟦ AUCTION HAS OFFICIALLY COMPLETED ⟧\n\n"
                               "All bidding rounds are now closed, and no further bids will be accepted.\n"
                               "It’s time to finalize your squads and proceed with the final review.\n\n"
                               "To fully close the auction and complete all processes,\n"
                               "please send the command: /end_auction")
                    try:
                        sent = await context.bot.send_photo(chat_id=chat_id, photo=AUCTION_DONE_IMAGE, caption=caption, parse_mode=ParseMode.HTML)
                    except Exception:
                        await _send_message(context.bot, chat_id, caption)
                    session["completed"] = True
                    save_session(chat_id, session)
            else:
                caption = ("⟦ AUCTION HAS OFFICIALLY COMPLETED ⟧\n\n"
                           "All bidding rounds are now closed, and no further bids will be accepted.\n"
                           "It’s time to finalize your squads and proceed with the final review.\n\n"
                           "To fully close the auction and complete all processes,\n"
                           "please send the command: /end_auction")
                try:
                    sent = await context.bot.send_photo(chat_id=chat_id, photo=AUCTION_DONE_IMAGE, caption=caption, parse_mode=ParseMode.HTML)
                except Exception:
                    await _send_message(context.bot, chat_id, caption)
                session["completed"] = True
                save_session(chat_id, session)
            if session.get("processing_unsold"):
                session["processing_unsold"] = False
                save_session(chat_id, session)
            return
        run = None
        run_id = session.get("current_run_id")
        if run_id:
            run = get_run(chat_id, run_id)
            sold_ids = {str(s.get("player_id")) for s in (run.get("sold_players") or []) if s.get("player_id")}
            if session.get("processing_unsold"):
                unsold_ids = set()
            else:
                unsold_ids = {str(s.get("player_id")) for s in (run.get("unsold_players") or []) if s.get("player_id")}
        else:
            sold_ids = set()
            unsold_ids = set()
        next_player = None
        while players:
            candidate = players.pop(0)
            key_id = str(candidate.get("user_id") or "")
            uname = (candidate.get("username") or "").lstrip("@").lower()
            if (key_id and key_id in sold_ids):
                continue
            if (key_id and key_id in unsold_ids) and not session.get("processing_unsold"):
                continue
            if (uname and run):
                for s in (run.get("sold_players") or []):
                    if (s.get("player_username") or "").lstrip("@").lower() == uname:
                        candidate = None
                        break
                if candidate is None:
                    continue
            next_player = candidate
            break
        session["auto_set_list"] = players
        save_session(chat_id, session)
        if not next_player:
            await _try_send_next_auto(chat_id, context)
            return
        base_price = next_player.get("set_base_price") if next_player.get("set_base_price") is not None else session.get("budget") or next_player.get("base_price") or 0
        try:
            await send_new_player_slot_message(chat_id, context, next_player, base_price)
        except Exception:
            try:
                await _send_message(context.bot, chat_id, "Failed to send next auto player slot. Use /next to start manually.")
            except:
                pass
    except Exception:
        return

async def _remove_player_from_auto_and_pending(session: Dict[str, Any], player: Dict[str, Any]):
    uid = player.get("user_id")
    uname = (player.get("username") or "").lstrip("@").lower()
    new_auto = []
    for p in session.get("auto_set_list", []) or []:
        if p is None:
            continue
        if uid and p.get("user_id") and str(p.get("user_id")) == str(uid):
            continue
        if uname and p.get("username") and p.get("username").lstrip("@").lower() == uname:
            continue
        new_auto.append(p)
    session["auto_set_list"] = new_auto
    seq = [s for s in (session.get("auto_sequence") or []) if s != str(uid) and s != uname]
    session["auto_sequence"] = seq
    pending = session.get("pending_slots", {}) or {}
    keys_to_rm = []
    for k, v in pending.items():
        if not v:
            continue
        if uid and v.get("user_id") and str(v.get("user_id")) == str(uid):
            keys_to_rm.append(k)
        elif uname and v.get("username") and v.get("username").lstrip("@").lower() == uname:
            keys_to_rm.append(k)
    for k in keys_to_rm:
        pending.pop(k, None)
    session["pending_slots"] = pending

async def _finalize_current_slot(chat_id: int, context: ContextTypes.DEFAULT_TYPE, by_host: bool = False):
    session = get_session(chat_id)
    slot = session.get("current_slot")
    if not slot:
        return False, "No active slot"
    now = int(time.time())
    deadline = slot.get("deadline", now)
    if now < deadline:
        return False, "deadline extended"
    player = slot.get("player") or {}
    highest = slot.get("highest") or slot.get("last_bid")
    run_id = session.get("current_run_id")
    run = get_run(chat_id, run_id) if run_id else None
    name_link = await _format_player_name_link(player)
    if highest:
        buyer_id = highest.get("user_id")
        price = highest.get("amount")
        buyer_name = highest.get("name") or ""
        buyer_team = _get_team_of_user(session, buyer_id)
        buyer_link = f"<a href='tg://user?id={buyer_id}'>{buyer_name}</a>" if buyer_id else (buyer_name or "—")
        caption = ("🏵 PLAYER SOLD\n\n"
                   f"🔨 Sold Price  : Cr.{price}\n"
                   "━━━━━━━━━━━━━━━━━━━━━\n"
                   f"👾 Player        : {name_link}\n"
                   f"🔥 Role Type   : {player.get('role') or 'None'}\n"
                   "━━━━━━━━━━━━━━━━━━━━━\n"
                   f"👤 Buyer         : {buyer_link}\n"
                   f"🫂 Team          : {buyer_team or '—'}\n"
                   "━━━━━━━━━━━━━━━━━━━━━\n")
        try:
            vid = random.choice(SOLD_VIDEO_IDS) if SOLD_VIDEO_IDS else None
            if vid:
                sent = await context.bot.send_video(chat_id=chat_id, video=vid, caption=caption, parse_mode=ParseMode.HTML)
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id, disable_notification=True)
                except Exception:
                    pass
            else:
                sent = await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML)
        session["logs"].append({"ts": int(time.time()), "player_id": player.get("user_id"), "player_name": player.get("name"), "price": price, "buyer_id": buyer_id, "player_username": player.get("username"), "player_role": player.get("role")})
        if run:
            run_sold = run.get("sold_players", [])
            run_sold.append({"ts": int(time.time()), "player_id": player.get("user_id"), "player_name": player.get("name"), "price": price, "buyer_id": buyer_id, "player_username": player.get("username")})
            run["sold_players"] = run_sold
            run["current_slot"] = None
            append_run_log(chat_id, run.get("run_id"), {"event": "sold", "player": player, "price": price, "buyer_id": buyer_id, "ts": int(time.time())})
            save_run(chat_id, run)
        try:
            tb = session.get("team_budgets", {}) or {}
            if buyer_team:
                prev_budget = tb.get(buyer_team, session.get("budget") or 0)
                new_budget = prev_budget - price
                tb[buyer_team] = new_budget
                session["team_budgets"] = tb
                save_session(chat_id, session)
        except Exception:
            pass
    else:
        caption = ("🏵 PLAYER UNSOLD\n\n"
                   f"👾 Player        : {name_link}\n"
                   f"🔥 Role Type   : {player.get('role') or 'None'}\n\n"
                   f"Final Status: UNSOLD\n")
        try:
            vid = random.choice(UNSOLD_VIDEO_IDS) if UNSOLD_VIDEO_IDS else None
            if vid:
                sent = await context.bot.send_video(chat_id=chat_id, video=vid, caption=caption, parse_mode=ParseMode.HTML)
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=sent.message_id, disable_notification=True)
                except Exception:
                    pass
            else:
                sent = await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode=ParseMode.HTML)
        session["logs"].append({"ts": int(time.time()), "player_id": player.get("user_id"), "player_name": player.get("name"), "price": None, "buyer_id": None, "player_username": player.get("username"), "player_role": player.get("role")})
        if run:
            run_unsold = run.get("unsold_players", [])
            run_unsold.append({"ts": int(time.time()), "player_id": player.get("user_id"), "player_name": player.get("name"), "base_price": slot.get("start_price"), "player_username": player.get("username")})
            run["unsold_players"] = run_unsold
            run["current_slot"] = None
            append_run_log(chat_id, run.get("run_id"), {"event": "unsold", "player": player, "base_price": slot.get("start_price"), "ts": int(time.time())})
            save_run(chat_id, run)
    try:
        await _remove_player_from_auto_and_pending(session, player)
    except Exception:
        pass
    session["current_slot"] = None
    save_session(chat_id, session)
    try:
        t = countdown_tasks.get(chat_id)
        if t and not t.done():
            t.cancel()
    except:
        pass
    if run:
        await check_auction_completion(chat_id, session, run, context)
    try:
        asyncio.create_task(_try_send_next_auto(chat_id, context))
    except Exception:
        pass
    return True, "finalized"

def _parse_amount_token(tok: str) -> Optional[float]:
    if not tok:
        return None
    tok = tok.strip().lower().replace(" ", "")
    m = re.match(r'^(\d+(\.\d+)?)(cr)?$', tok)
    if not m:
        m = re.match(r'^(\d+(\.\d+)?)$', tok)
    if m:
        val = float(m.group(1))
        return val
    return None

async def next_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)

    if session.get("auto_mode"):
        await msg.reply_text("You cannot use /next while Auto Mode is enabled. Disable auto or use the Auto controls.")
        return

    if not _is_host_or_access(session, user.id):
        await msg.reply_text("Only the auction host can start next slot.")
        return
    parsed_identifier, parsed_price, pre_text = await parse_next_identifier_and_price(msg.text or "")
    if parsed_identifier is None or parsed_price is None:
        help_text = ("Usage examples for /next:\n\n"
                     "1) By username:\n/next @samayofficial 10\n\n"
                     "2) With extra display name before username:\n/next Virat @samayofficial 10\n\n"
                     "3) By Telegram ID:\n/next 123456789 10\n")
        await msg.reply_text(help_text)
        return
    identifier = parsed_identifier
    price = parsed_price
    if session.get("current_slot"):
        await msg.reply_text("A player is currently on auction. Wait for slot to finish or /pause + finalize.")
        return
    identifier_clean = identifier.strip()
    if identifier_clean.startswith("@"):
        identifier_clean = identifier_clean[1:]
    player = None
    try:
        player = await find_player_async(session, identifier_clean, chat_id, context)
    except Exception:
        player = None
    if not player:
        await msg.reply_text("Player not found in loaded list. If you passed a Telegram ID, ensure that ID's username is present in the loaded list or load the player first with /load.")
        return
    player = _normalize_player_entry(player)
    run_id = session.get("current_run_id") or start_new_run(chat_id, session)
    run = get_run(chat_id, run_id)
    player_key = str(player.get("user_id") or (player.get("username") or "")).strip()
    if run:
        attempts = run.get("attempts", {}) or {}
        attempts[player_key] = attempts.get(player_key, 0) + 1
        run["attempts"] = attempts
        save_run(chat_id, run)
    profile_fullname = player.get("profile_fullname") or player.get("name") or None
    if not profile_fullname and pre_text:
        profile_fullname = pre_text
    sold_already = False
    for l in session.get("logs", []) or []:
        if l.get("player_id") and player.get("user_id") and str(l.get("player_id")) == str(player.get("user_id")) and l.get("price"):
            sold_already = True
            break
    if sold_already:
        await msg.reply_text("This player has already sold.")
        return
    start_price = price
    sent_new = await send_new_player_slot_message(chat_id, context, player, start_price)
    return

next_handler = CommandHandler("next", next_cmd)

async def check_auction_completion(chat_id: int, session: Dict[str, Any], run: Optional[Dict[str, Any]], context: ContextTypes.DEFAULT_TYPE):
    if not session or not run:
        return
    players = session.get("players_list") or []
    if not players:
        return
    attempts = run.get("attempts", {}) or {}
    sold_ids = {str(s.get("player_id")) for s in (run.get("sold_players") or []) if s.get("player_id")}
    all_done = True
    for p in players:
        p2 = _normalize_player_entry(p)
        key = str(p2.get("user_id") or (p2.get("username") or "")).strip()
        if key in sold_ids:
            continue
        if attempts.get(key, 0) >= 2:
            continue
        all_done = False
        break
    if all_done and not session.get("completed"):
        caption = ("⟦ AUCTION HAS OFFICIALLY COMPLETED ⟧\n\n"
                   "All bidding rounds are now closed, and no further bids will be accepted.\n"
                   "It’s time to finalize your squads and proceed with the final review.\n\n"
                   "To fully close the auction and complete all processes,\n"
                   "please send the command: /end_auction")
        try:
            sent = await context.bot.send_photo(chat_id=chat_id, photo=AUCTION_DONE_IMAGE, caption=caption, parse_mode=ParseMode.HTML)
        except Exception:
            await _send_message(context.bot, chat_id, caption)
        session["completed"] = True
        save_session(chat_id, session)

async def slot_countdown(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        while True:
            session = get_session(chat_id)
            slot = session.get("current_slot")
            if not slot:
                return
            if session.get("paused"):
                await asyncio.sleep(1)
                continue
            now_t = int(time.time())
            deadline = slot.get("deadline", now_t)
            remaining = deadline - now_t
            if remaining <= 0:
                fresh = get_session(chat_id)
                fresh_slot = fresh.get("current_slot")
                if fresh_slot:
                    fresh_deadline = fresh_slot.get("deadline", int(time.time()))
                    if int(time.time()) < int(fresh_deadline):
                        await asyncio.sleep(1)
                        continue
                await _finalize_current_slot(chat_id, context)
                return
            if remaining == 10 and not slot.get("announced", {}).get("10"):
                try:
                    await context.bot.send_message(chat_id=chat_id, text="🔟 10 seconds remaining for bid")
                except Exception:
                    pass
                slot.setdefault("announced", {})["10"] = True
                session["current_slot"] = slot
                save_session(chat_id, session)
                await asyncio.sleep(1)
                continue
            if remaining <= 5 and remaining > 0:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=f"{remaining} second{'s' if remaining!=1 else ''} remaining for bid")
                except Exception:
                    pass
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        return
    except Exception:
        return

async def bid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    slot = session.get("current_slot")
    if not slot:
        await msg.reply_text("No active auction slot right now.")
        return

    now_ts = int(time.time())
    slot_deadline = slot.get("deadline", now_ts)
    if now_ts >= slot_deadline:
        await _finalize_current_slot(chat_id, context)
        await msg.reply_text("Too late — bidding time ended for this player.")
        return

    teams = session.get("teams", {}) or {}
    bidder_team = None
    bidder_is_assistant = False
    for tname, members in teams.items():
        if members and user.id in members:
            bidder_team = tname
            break
    if not bidder_team:
        for tname, aid in (session.get("assistants", {}) or {}).items():
            try:
                if aid and int(aid) == user.id:
                    bidder_team = tname
                    bidder_is_assistant = True
                    break
            except:
                continue
    if not bidder_team:
        await msg.reply_text("Only assigned team owners or assistants can place bids.")
        return
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip().lower() == "end":
        if session.get("host_id") != user.id:
            await msg.reply_text("Only the host can use '/bid end'.")
            return
        ok, reason = await _finalize_current_slot(chat_id, context, by_host=True)
        if ok:
            await msg.reply_text("Slot finalized by host.")
        else:
            await msg.reply_text("No active slot to finalize.")
        return
    parts = msg.text.strip().split(maxsplit=1)
    amt = None
    if len(parts) < 2:
        budget = session.get("budget")
        if not budget:
            amt = 1
        else:
            amt = max(1, round(budget * 0.01))
    else:
        try:
            amt = float(parts[1].replace(",", "").strip())
        except:
            await msg.reply_text("Please send a valid integer or float bid.")
            return

    now_ts = int(time.time())
    slot_deadline = slot.get("deadline", now_ts)
    if now_ts >= slot_deadline:
        await _finalize_current_slot(chat_id, context)
        await msg.reply_text("Too late — bidding time ended for this player.")
        return

    if amt < slot.get("start_price", 0):
        highest = slot.get("highest")
        leading_team = _get_team_of_user(session, highest.get("user_id")) if highest and highest.get("user_id") else "—"
        await msg.reply_text(f"Your bid is lower than the current price.\nHighest bid is still held by: {leading_team}.")
        return
    highest = slot.get("highest")
    if highest:
        if highest.get("user_id") == user.id:
            leading_team = _get_team_of_user(session, highest.get("user_id")) or user.first_name or ""
            await msg.reply_text(f"Your bid is already registered for this player.\nCurrent top bidder remains: {leading_team}")
            return
        if amt <= highest.get("amount", 0):
            leading_team = _get_team_of_user(session, highest.get("user_id")) or "—"
            await msg.reply_text(f"Your bid is lower than the current price.\nHighest bid is still held by: {leading_team}.")
            return
    team_budget_map = session.get("team_budgets", {}) or {}
    team_budget = team_budget_map.get(bidder_team)
    # FIX: treat team_budgets as remaining budget (no double subtraction)
    if team_budget is not None:
        if amt > team_budget:
            await msg.reply_text(f"Insufficient budget. Remaining: {team_budget} Cr.")
            return
    purchased_count = 0
    logs = session.get("logs", []) or []
    for l in logs:
        buyer_team_for_log = _get_team_of_user(session, l.get("buyer_id")) if l.get("buyer_id") else None
        if buyer_team_for_log == bidder_team and l.get("price"):
            purchased_count += 1
    max_buy = session.get("max_buy")
    if isinstance(max_buy, int) and purchased_count >= max_buy:
        await msg.reply_text(f"Team {bidder_team} has reached the maximum purchases ({max_buy}). Cannot bid further.")
        return
    timestamp = int(time.time())
    current_deadline = slot.get("deadline", timestamp)
    if timestamp < current_deadline:
        slot["highest"] = {"user_id": user.id, "amount": amt, "name": user.first_name or "", "ts": timestamp}
        slot["last_bid"] = dict(slot["highest"])
        # reset countdown to full (bid extends to full configured countdown)
        slot["deadline"] = timestamp + get_countdown(session)
    else:
        await _finalize_current_slot(chat_id, context)
        await msg.reply_text("Too late — bidding time ended for this player.")
        return
    slot["announced"] = {}
    session["current_slot"] = slot
    save_session(chat_id, session)
    run_id = session.get("current_run_id")
    if run_id:
        run = get_run(chat_id, run_id)
        if run:
            run_current = run.get("current_slot", {})
            run_current["highest"] = slot["highest"]
            run_current["deadline"] = slot["deadline"]
            run["current_slot"] = run_current
            save_run(chat_id, run)
            append_run_log(chat_id, run_id, {"event": "bid", "user_id": user.id, "amount": amt, "player": slot.get("player"), "ts": timestamp})
    bidder_link = f'<a href="tg://user?id={user.id}">{(user.first_name or "")}</a>'
    name_link = await _format_player_name_link(slot.get("player", {}))
    text = ("🏵 Bid Confirmed Price : Cr. " + str(amt) + "\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏏 Player        : {name_link}\n"
            f"🎯 Role Type  : {((slot.get('player') or {}).get('role') or 'None')}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Bidder       : {bidder_link}\n"
            f"🫂 Team         : {bidder_team}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"You have {get_countdown(session)} seconds for the next bid.\n")
    try:
        vid = random.choice(BID_CONFIRMED_VIDEO_IDS) if BID_CONFIRMED_VIDEO_IDS else None
        if vid:
            await context.bot.send_video(chat_id=chat_id, video=vid, caption=text, parse_mode=ParseMode.HTML)
        else:
            await _send_message(context.bot, chat_id, text, parse_mode=ParseMode.HTML)
    except:
        await msg.reply_text(text)
    return

bid_handler = CommandHandler("bid", bid_cmd)

async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if not _is_host_or_access(session, user.id):
        await msg.reply_text("Only the auction host can pause.")
        return
    session["paused"] = True
    session["pause_start"] = int(time.time())
    save_session(chat_id, session)
    await msg.reply_text("⏸️ Auction paused. Countdown halted. Use /continue to resume.")
    return

pause_handler = CommandHandler("pause", pause_cmd)

async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if not _is_host_or_access(session, user.id):
        await msg.reply_text("Only the auction host can resume.")
        return
    if not session.get("paused"):
        await msg.reply_text("Auction is not paused.")
        return
    pause_start = session.get("pause_start")
    if pause_start:
        paused_seconds = int(time.time()) - pause_start
    else:
        paused_seconds = 0
    slot = session.get("current_slot")
    if slot and slot.get("deadline"):
        slot["deadline"] = slot.get("deadline", int(time.time())) + paused_seconds
        session["current_slot"] = slot
    session["paused"] = False
    session["pause_start"] = None
    save_session(chat_id, session)
    run_id = session.get("current_run_id")
    if run_id:
        run = get_run(chat_id, run_id)
        if run:
            run_current = run.get("current_slot") or {}
            if run_current.get("deadline"):
                run_current["deadline"] = run_current.get("deadline") + paused_seconds
                run["current_slot"] = run_current
                save_run(chat_id, run)
    await msg.reply_text("▶️ Auction resumed. Countdown continues.")
    return

resume_handler = CommandHandler("continue", resume_cmd)

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if not _is_host_or_access(session, user.id):
        await msg.reply_text("Only the auction host can view summary.")
        return
    tables = session.get("tables") or 0
    teams_count = len(session.get("teams", {}).keys())
    budget = session.get("budget") or 0
    players_count = len(session.get("players_list") or [])
    sold = len([l for l in session.get("logs", []) if l.get("price")])
    unsold = len([l for l in session.get("logs", []) if l.get("price") is None])
    available = players_count - sold - unsold
    txt = ("🎯 Auction Summary 🎯\n\n" f"Total Tables: {teams_count}/{tables}\n" f"Auction Budget (per team): {budget}\n" f"Total Players Loaded: {players_count}\n" f"Available for Buying: {available}\n" f"Sold Players: {sold}\n" f"Unsold Players: {unsold}\n\n" "Keep the energy up — good luck!")
    await _send_message(context.bot, chat_id, txt)
    return

summary_handler = CommandHandler("summary", summary_cmd)

async def end_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if not _is_host_or_access(session, user.id):
        await msg.reply_text("Only the auction host can end the auction.")
        return
    await _send_message(context.bot, chat_id, "Are you sure you want to end the auction?", reply_markup=build_end_confirm(user.id))
    return

end_handler = CommandHandler("end_auction", end_cmd)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not msg or not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    text = (msg.text or "").strip()
    if msg.reply_to_message:
        reply_msg = msg.reply_to_message
        target_info, reason = await _extract_target_from_message(reply_msg)
        if not target_info:
            await msg.reply_text("Could not identify the target user.")
            return
        target_username = (target_info.get("first_name") or "").strip()
        target_user_id = target_info.get("user_id")
    else:
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            candidate = parts[1].strip()
            if candidate.startswith("@"):
                candidate = candidate[1:]
            target_user_id = None
            db = load_db()
            reg = _find_registration_by_username_or_code(db, candidate)
            if reg and reg.get("user_id"):
                target_user_id = reg.get("user_id")
            else:
                try:
                    target_user_id = int(candidate)
                except:
                    target_user_id = None
            target_username = candidate
        else:
            if not _is_host_or_access(session, user.id) and _is_team_owner(session, user.id) is None:
                await msg.reply_text("Only host or team owners can use status.")
                return
            teams = session.get("teams", {}) or {}
            budget = session.get("budget")
            logs = session.get("logs", []) or []
            parts = []
            idx = 1
            for tname, members in teams.items():
                bought_count = 0
                spent = 0
                for l in logs:
                    buyer_team = _get_team_of_user(session, l.get("buyer_id")) if l.get("buyer_id") else None
                    if buyer_team == tname and l.get("price"):
                        bought_count += 1
                        spent += l.get("price", 0)
                remaining = None
                if isinstance(budget, (int, float)):
                    remaining = session.get("team_budgets", {}).get(tname, budget)
                parts.append(f"{idx} {tname}\nPlayers bought: {str(bought_count).zfill(2)}\nRemaining Budget: {str(remaining).zfill(3) if remaining is not None else 'Not set'}\n")
                idx += 1
            if not parts:
                await msg.reply_text("No teams assigned yet.")
                return
            final_text = "Teams status\n\n" + "\n".join(parts)
            await _send_message(context.bot, chat_id, final_text)
            return
    found_entry = None
    if target_user_id:
        for l in session.get("logs", []) or []:
            if l.get("player_id") and str(l.get("player_id")) == str(target_user_id):
                found_entry = l
                break
        if not found_entry:
            run_id = session.get("current_run_id")
            if run_id:
                run = get_run(chat_id, run_id)
                if run:
                    for s in (run.get("sold_players", []) or []):
                        if s.get("player_id") and str(s.get("player_id")) == str(target_user_id):
                            found_entry = {"player_name": s.get("player_name"), "price": s.get("price"), "buyer_id": s.get("buyer_id")}
                            break
    else:
        target_un = (target_username or "").lstrip("@").lower()
        for l in session.get("logs", []) or []:
            if (l.get("player_username") or "").lstrip("@").lower() == target_un:
                found_entry = l
                break
        if not found_entry:
            run_id = session.get("current_run_id")
            if run_id:
                run = get_run(chat_id, run_id)
                if run:
                    for s in (run.get("sold_players", []) or []):
                        if (s.get("player_name") or "").strip().lower() == target_un:
                            found_entry = {"player_name": s.get("player_name"), "price": s.get("price"), "buyer_id": s.get("buyer_id")}
                            break
    if found_entry:
        if found_entry.get("price"):
            buyer_team = None
            buyer_id = found_entry.get("buyer_id")
            buyer_team = _get_team_of_user(session, buyer_id)
            buyer_label = buyer_team if buyer_team else "Team Owner"
            await msg.reply_text(f"Player {found_entry.get('player_name')} has been SOLD to {buyer_label} for {found_entry.get('price')} Cr.")
            return
        else:
            await msg.reply_text(f"Player {found_entry.get('player_name')} was UNSOLD.")
            return
    else:
        for p in session.get("players_list") or []:
            p2 = _normalize_player_entry(p)
            if p2.get("user_id") and target_user_id and str(p2.get("user_id")) == str(target_user_id):
                await msg.reply_text(f"Player {p2.get('name') or p2.get('username')} is loaded but not auctioned yet.")
                return
            if p2.get("username") and (target_username or "") and p2.get("username").lstrip("@").lower() == (target_username or "").lstrip("@").lower():
                await msg.reply_text(f"Player {p2.get('name') or p2.get('username')} is loaded but not auctioned yet.")
                return
        await msg.reply_text("Player not found in loaded list or auction logs.")
        return

status_handler = CommandHandler("status", status_cmd)

async def my_team_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    user = update.effective_user
    if not msg or not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    # allow owner OR assistant to view their team
    team = _get_team_of_user(session, user.id)
    if not team:
        await msg.reply_text("You are not assigned to any team.")
        return
    budget = session.get("budget")
    logs = session.get("logs", []) or []
    team_members = session.get("teams", {}).get(team, []) or []
    team_assistant = session.get("assistants", {}).get(team)
    team_purchases = []
    total_spent = 0
    for l in logs:
        buyer_id = l.get("buyer_id")
        if not buyer_id:
            continue
        buyer_team = _get_team_of_user(session, buyer_id)
        if buyer_team == team and l.get("price"):
            total_spent += int(l.get("price") or 0)
            team_purchases.append({
                "name": l.get("player_name") or "",
                "username": l.get("player_username") or "",
                "price": l.get("price")
            })
    total_players = len(team_purchases)
    remaining = None
    if isinstance(budget, (int, float)):
        remaining = session.get("team_budgets", {}).get(team, budget)
    # Build formatted message per requested template (HTML)
    lines = []
    lines.append(f"<b>TEAM LINE UP :</b>\n")
    lines.append(f"<b>({team})</b>\n")
    lines.append(f"\n<b>👥 TOTAL PLAYERS BOUGHT: {total_players}</b>\n")
    lines.append("━━━━━━━━━━━━━━━━━━\n")
    lines.append("\n<b>🧑‍💼 PLAYERS ACQUIRED</b>\n")
    idx = 1
    for p in team_purchases:
        name = p.get("name") or "Unknown"
        uname = p.get("username") or ""
        price = p.get("price") or 0
        lines.append(
            f"\n【{idx:02d}】 {name}\n"
            f"  👤 Username: @{(uname or '')}\n"
            f"  💎 Bought At: Cr. {str(price)}\n"
        )
        idx += 1
    lines.append("━━━━━━━━━━━━━━━━━━\n")
    lines.append("\n<b>💼 FINANCIAL SUMMARY</b>\n")
    tb_value = session.get("team_budgets", {}).get(team, budget if budget is not None else 0)
    lines.append(f"◼ Total Budget        : Cr. {tb_value + total_spent}\n")
    lines.append(f"◼ Spent Balance     : Cr. {total_spent}\n")
    lines.append(f"◼ Remaining Balance : Cr. {remaining if remaining is not None else 'Not set'}\n")
    lines.append("━━━━━━━━━━━━━━━━━━\n")
    final = "\n".join(lines)
    await _send_message(context.bot, chat_id, final, parse_mode=ParseMode.HTML)
    return

my_team_handler = CommandHandler("my_team", my_team_cmd)

async def unsold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat or (msg.chat if msg else None)
    if not msg or not chat:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    run_id = session.get("current_run_id")
    run = get_run(chat_id, run_id) if run_id else None
    unsold_list = []
    if run:
        for u in (run.get("unsold_players") or []):
            unsold_list.append({"name": u.get("player_name"), "username": u.get("player_username") or "", "id": u.get("player_id"), "base_price": u.get("base_price")})
    if not unsold_list:
        await msg.reply_text("No unsold players in current auction run.")
        return
    lines = []
    idx = 1
    for u in unsold_list:
        name = u.get("name") or "Unknown"
        uname = ("@" + u.get("username")) if (u.get("username")) else "—"
        tid = u.get("id") or "None"
        bp = u.get("base_price") or "None"
        lines.append(f"{idx}. 👤 {name} | Username: {uname} | ID: {tid} | Base: Cr.{bp}")
        idx += 1
    resp = "🟦 Unsold Players (current run) 🟦\n\n" + "\n".join(lines)
    await _send_message(context.bot, chat_id, resp)
    return

unsold_handler = CommandHandler("unsold", unsold_cmd)

async def assist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    text = (msg.text or "").strip()
    args = text.split()[1:] if text else []
    target_info = None
    if msg.reply_to_message:
        target_info, _ = await _extract_target_from_message(msg.reply_to_message)
    else:
        if args:
            maybe = args[-1]
            if maybe.startswith("@"):
                maybe = maybe[1:]
            db = load_db()
            reg = _find_registration_by_username_or_code(db, maybe)
            if reg and reg.get("user_id"):
                target_info = {"user_id": reg.get("user_id"), "first_name": reg.get("name") or reg.get("username")}
            else:
                try:
                    uid = int(maybe)
                    target_info = {"user_id": uid, "first_name": str(uid)}
                except:
                    target_info = None
    if not target_info or not target_info.get("user_id"):
        await msg.reply_text("Could not identify the user to assign as assistant. Reply to the user's message or pass @username/userid.")
        return
    target_id = int(target_info.get("user_id"))
    assigned_team = None
    if _is_host_or_access(session, user.id):
        if args:
            possible_team = args[0]
            if possible_team.startswith("@"):
                possible_team = possible_team[1:]
            teams = session.get("teams", {}) or {}
            for tname in teams.keys():
                if tname.lower() == possible_team.lower():
                    assigned_team = tname
                    break
            if not assigned_team:
                await msg.reply_text("Team not found. Provide correct team name.")
                return
        else:
            await msg.reply_text("As host you must provide the team name to assign an assistant. Usage: /assist <TeamName> @username or reply to user with /assist <TeamName>")
            return
    else:
        owner_team = _is_team_owner(session, user.id)
        if not owner_team:
            await msg.reply_text("Only host or a team owner can assign an assistant.")
            return
        assigned_team = owner_team
    assistants = session.get("assistants", {}) or {}
    current_assistant = assistants.get(assigned_team)
    if current_assistant and current_assistant != target_id:
        try:
            u = await context.bot.get_chat(current_assistant)
            name = getattr(u, "first_name", "") or str(current_assistant)
        except:
            name = str(current_assistant)
        await msg.reply_text(f"This team already has an assistant: {name}. Remove them first with /dem.")
        return
    assistants[assigned_team] = target_id
    session["assistants"] = assistants
    save_session(chat_id, session)
    try:
        tgt = await context.bot.get_chat(target_id)
        name_display = getattr(tgt, "first_name", "") or str(target_id)
    except:
        name_display = str(target_id)
    await msg.reply_text(f"{name_display} is now assistant for team {assigned_team}. Assistants can bid alongside the owner.")
    return

assist_handler = CommandHandler("assist", assist_cmd)

async def dem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    text = (msg.text or "").strip()
    args = text.split()[1:] if text else []
    target_info = None
    if msg.reply_to_message:
        target_info, _ = await _extract_target_from_message(msg.reply_to_message)
    else:
        if args:
            maybe = args[-1]
            if maybe.startswith("@"):
                maybe = maybe[1:]
            db = load_db()
            reg = _find_registration_by_username_or_code(db, maybe)
            if reg and reg.get("user_id"):
                target_info = {"user_id": reg.get("user_id"), "first_name": reg.get("name") or reg.get("username")}
            else:
                try:
                    uid = int(maybe)
                    target_info = {"user_id": uid, "first_name": str(uid)}
                except:
                    target_info = None
    if not target_info or not target_info.get("user_id"):
        await msg.reply_text("Could not identify the assistant to demote. Reply to the assistant's message or pass @username/userid.")
        return
    target_id = int(target_info.get("user_id"))
    teams = session.get("teams", {}) or {}
    assistants = session.get("assistants", {}) or {}
    team_found = None
    for tname, aid in (assistants.items()):
        if aid and int(aid) == target_id:
            team_found = tname
            break
    if not team_found:
        await msg.reply_text("This user is not an assistant for any team.")
        return
    if _is_host_or_access(session, user.id):
        pass
    else:
        owner_team = _is_team_owner(session, user.id)
        if owner_team != team_found:
            await msg.reply_text("Only the host or the team owner can demote this assistant.")
            return
    assistants.pop(team_found, None)
    session["assistants"] = assistants
    save_session(chat_id, session)
    try:
        tgt = await context.bot.get_chat(target_id)
        name_display = getattr(tgt, "first_name", "") or str(target_id)
    except:
        name_display = str(target_id)
    await msg.reply_text(f"{name_display} has been demoted and removed as assistant from team {team_found}.")
    return

demote_handler = CommandHandler("dem", dem_cmd)

async def access_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if session.get("host_id") != user.id:
        await msg.reply_text("Only the host can grant access.")
        return
    target_info = None
    if msg.reply_to_message:
        target_info, _ = await _extract_target_from_message(msg.reply_to_message)
    else:
        parts = (msg.text or "").split()
        if len(parts) > 1:
            maybe = parts[1]
            if maybe.startswith("@"):
                maybe = maybe[1:]
            db = load_db()
            reg = _find_registration_by_username_or_code(db, maybe)
            if reg and reg.get("user_id"):
                target_info = {"user_id": reg.get("user_id"), "first_name": reg.get("name") or reg.get("username")}
            else:
                try:
                    uid = int(maybe)
                    target_info = {"user_id": uid, "first_name": str(uid)}
                except:
                    target_info = None
    if not target_info or not target_info.get("user_id"):
        await msg.reply_text("Could not identify the user to grant access. Reply to the user message or pass @username/userid.")
        return
    target_id = int(target_info.get("user_id"))
    access = session.get("access_users", []) or []
    if target_id in access:
        await msg.reply_text("This user already has host-level access.")
        return
    access.append(target_id)
    session["access_users"] = access
    save_session(chat_id, session)
    try:
        tgt = await context.bot.get_chat(target_id)
        name_display = getattr(tgt, "first_name", "") or str(target_id)
    except:
        name_display = str(target_id)
    await msg.reply_text(f"{name_display} has been granted host-like access. They can now run host commands.")
    return

access_handler = CommandHandler("access", access_cmd)

async def _resolve_username_to_userid(context: ContextTypes.DEFAULT_TYPE, username: str) -> Optional[int]:
    if not username:
        return None
    username = username.lstrip("@").lower()
    db = load_db()
    u2o = db.get("username_to_owner", {}) or {}
    if username in u2o:
        try:
            return int(u2o[username])
        except:
            return None
    owners = db.get("owners", {}) or {}
    for k, v in owners.items():
        uname = (v.get("username") or "").lstrip("@").lower()
        if uname and uname == username:
            try:
                return int(k)
            except:
                continue
    found = _recursive_find_userid_by_username(db, username)
    if found:
        return found
    try:
        chat = await context.bot.get_chat(f"@{username}")
        if getattr(chat, "id", None):
            return int(chat.id)
    except:
        pass
    try:
        conn = sqlite3.connect(USERNAMES_DB_PATH, timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username_lower = ?", (username,))
        row = cur.fetchone()
        conn.close()
        if row:
            return None
    except:
        pass
    return None

async def _find_team_by_owner_userid(session: Dict[str, Any], userid: int) -> Optional[str]:
    teams = session.get("teams", {}) or {}
    for tname, members in teams.items():
        if members and members[0] == userid:
            return tname
    return None

async def deduct_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if session.get("host_id") != user.id:
        await msg.reply_text("Only the host can use /deduct.")
        return
    text = (msg.text or "").strip()
    parts = text.split()[1:] if text else []
    target_team = None
    amount = None
    if msg.reply_to_message:
        target_info, _ = await _extract_target_from_message(msg.reply_to_message)
        if not target_info or not target_info.get("user_id"):
            await msg.reply_text("Could not detect the replied user to deduct from.")
            return
        target_owner_id = int(target_info.get("user_id"))
        target_team = await _find_team_by_owner_userid(session, target_owner_id)
        if not target_team:
            await msg.reply_text("Replied user is not a team owner.")
            return
        if parts:
            for i, tok in enumerate(parts):
                maybe = _parse_amount_token(tok)
                if maybe is not None:
                    amount = maybe
                    break
    else:
        if not parts:
            await msg.reply_text("Usage: /deduct <team name or @owner or owner_id> <amount>\nOr reply to the team owner with /deduct <amount>")
            return
        amount = None
        amount_idx = None
        for i, tok in enumerate(parts):
            maybe = _parse_amount_token(tok)
            if maybe is not None:
                amount = maybe
                amount_idx = i
                break
        if amount is None:
            await msg.reply_text("Amount missing or invalid. Example: /deduct RCB 20  or /deduct 20 RCB")
            return
        other_tokens = [t for idx, t in enumerate(parts) if idx != amount_idx]
        identifier = " ".join(other_tokens).strip()
        if not identifier:
            await msg.reply_text("Team identifier missing. Provide team name, @username, or owner user id.")
            return
        if identifier.startswith("@"):
            username = identifier.lstrip("@")
            uid = await _resolve_username_to_userid(context, username)
            if not uid:
                await msg.reply_text("Cannot find that username in DB.")
                return
            team = await _find_team_by_owner_userid(session, uid)
            if not team:
                await msg.reply_text("This user is not a team owner.")
                return
            target_team = team
        else:
            team = None
            teams = session.get("teams", {}) or {}
            for t in teams.keys():
                if t.lower() == identifier.lower():
                    team = t
                    break
            if team is None:
                try:
                    uid = int(identifier)
                    team = await _find_team_by_owner_userid(session, uid)
                    if team is None:
                        await msg.reply_text("Team not found for that id.")
                        return
                except:
                    await msg.reply_text("Team not found.")
                    return
            target_team = team
    if amount is None:
        await msg.reply_text("Amount missing. Usage examples:\n/deduct 5 India  or reply to owner with /deduct 5")
        return
    tb = session.get("team_budgets", {}) or {}
    prev = tb.get(target_team, session.get("budget") or 0)
    if amount > prev:
        await msg.reply_text(f"<b>INSUFFICIENT FUNDS</b>\n\nThis team does not have enough budget to deduct Cr.{amount}.\nCurrent budget: Cr.{prev}", parse_mode=ParseMode.HTML)
        return
    newv = prev - amount
    tb[target_team] = newv
    session["team_budgets"] = tb
    save_session(chat_id, session)
    await msg.reply_text(f"Previous Budget : Cr.{prev}\nNew Budget      : Cr.{newv}")
    return

deduct_handler = CommandHandler("deduct", deduct_cmd)

async def plus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if session.get("host_id") != user.id:
        await msg.reply_text("Only the host can use /plus.")
        return
    text = (msg.text or "").strip()
    parts = text.split()[1:] if text else []
    target_team = None
    amount = None
    if msg.reply_to_message:
        target_info, _ = await _extract_target_from_message(msg.reply_to_message)
        if not target_info or not target_info.get("user_id"):
            await msg.reply_text("Could not detect the replied user to add to.")
            return
        target_owner_id = int(target_info.get("user_id"))
        target_team = await _find_team_by_owner_userid(session, target_owner_id)
        if not target_team:
            await msg.reply_text("Replied user is not a team owner.")
            return
        if parts:
            for i, tok in enumerate(parts):
                maybe = _parse_amount_token(tok)
                if maybe is not None:
                    amount = maybe
                    break
    else:
        if not parts:
            await msg.reply_text("Usage: /plus <team name or @owner or owner_id> <amount>\nOr reply to the team owner with /plus <amount>")
            return
        amount = None
        amount_idx = None
        for i, tok in enumerate(parts):
            maybe = _parse_amount_token(tok)
            if maybe is not None:
                amount = maybe
                amount_idx = i
                break
        if amount is None:
            await msg.reply_text("Amount missing or invalid. Example: /plus RCB 20  or /plus 20 RCB")
            return
        other_tokens = [t for idx, t in enumerate(parts) if idx != amount_idx]
        identifier = " ".join(other_tokens).strip()
        if not identifier:
            await msg.reply_text("Team identifier missing. Provide team name, @username, or owner user id.")
            return
        if identifier.startswith("@"):
            username = identifier.lstrip("@")
            uid = await _resolve_username_to_userid(context, username)
            if not uid:
                await msg.reply_text("Cannot find that username in DB.")
                return
            team = await _find_team_by_owner_userid(session, uid)
            if not team:
                await msg.reply_text("This user is not a team owner.")
                return
            target_team = team
        else:
            team = None
            teams = session.get("teams", {}) or {}
            for t in teams.keys():
                if t.lower() == identifier.lower():
                    team = t
                    break
            if team is None:
                try:
                    uid = int(identifier)
                    team = await _find_team_by_owner_userid(session, uid)
                    if team is None:
                        await msg.reply_text("Team not found for that id.")
                        return
                except:
                    await msg.reply_text("Team not found.")
                    return
            target_team = team
    if amount is None:
        await msg.reply_text("Amount missing. Usage examples:\n/plus 5 India  or reply to owner with /plus 5")
        return
    tb = session.get("team_budgets", {}) or {}
    prev = tb.get(target_team, session.get("budget") or 0)
    newv = prev + amount
    tb[target_team] = newv
    session["team_budgets"] = tb
    save_session(chat_id, session)
    await msg.reply_text(f"Previous Budget : Cr.{prev}\nNew Budget      : Cr.{newv}")
    return

plus_handler = CommandHandler("plus", plus_cmd)

async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return
    chat_id = chat.id
    session = get_session(chat_id)
    if session.get("host_id") != user.id:
        await msg.reply_text("Only the host can set bidding time.")
        return
    parts = (msg.text or "").split()
    if len(parts) < 2:
        await msg.reply_text("Usage: /time <seconds> (between 15 and 30). Example: /time 20")
        return
    try:
        val = int(parts[1])
    except:
        await msg.reply_text("Please provide an integer value between 15 and 30.")
        return
    if val < 15 or val > 30:
        await msg.reply_text("Time must be between 15 and 30 seconds.")
        return
    if session.get("min_buy") is None or session.get("max_buy") is None:
        await msg.reply_text("Set minimum and maximum buying first.")
        return
    session["countdown_seconds"] = val
    save_session(chat_id, session)
    await msg.reply_text(f"Auction bidding time set to {val} seconds.")
    return

time_handler = CommandHandler("time", time_cmd)