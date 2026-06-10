import re
import logging

from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from pyrogram.errors import RPCError

from config import API_ID, API_HASH, BOT_TOKEN, SESSION_STRING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

GROUP_ID = -1003758688231

GANG_PATTERN = re.compile(r"^(?:/)?gang(?:@\w+)?(?:\s+(.*))?$", re.IGNORECASE)
LIST_PATTERN = re.compile(r"^(?:/)?list(?:@\w+)?$", re.IGNORECASE)

bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user = Client(
    "user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

playing_data = {}
picker_data = {}


def get_display_name(tg_user) -> str:
    first = (tg_user.first_name or "").strip()
    last = (tg_user.last_name or "").strip()

    full_name = " ".join(part for part in [first, last] if part).strip()
    if full_name:
        return full_name

    if tg_user.username:
        return tg_user.username.strip()

    return f"User {tg_user.id}"


def build_playing_text(data: dict) -> str:
    text = "PLAYING MEMBERS\n\n"

    if data["in"]:
        for index, member in enumerate(data["in"].values(), start=1):
            text += f"{index}. {member}\n"
    else:
        text += "No members\n"

    text += "\nOUT MEMBERS\n\n"

    if data["out"]:
        for index, member in enumerate(data["out"].values(), start=1):
            text += f"{index}. {member}\n"
    else:
        text += "No members\n"

    return text


def build_picker_text(data: dict) -> str:
    selected_usernames = []

    for user_id in data["selected"]:
        member = data["members"].get(user_id)
        if member and member["username"]:
            selected_usernames.append(f"@{member['username']}")

    if not selected_usernames:
        return "Selected usernames:\n\nNo usernames selected yet."

    text = "Selected usernames:\n\n"
    for index, username in enumerate(selected_usernames, start=1):
        text += f"{index}. {username}\n"

    return text.rstrip()


def build_picker_keyboard(message_id: int, data: dict) -> InlineKeyboardMarkup:
    rows = []

    for user_id, member in data["members"].items():
        label = member["name"]
        if user_id in data["selected"]:
            label = f"✅ {label}"

        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"pick:{message_id}:{user_id}"
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "📋 FINAL LIST",
                callback_data=f"pickfinal:{message_id}"
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


async def send_group_usernames(message: Message, prefix_text: str, usernames: list[str]) -> None:
    if not usernames:
        if prefix_text:
            await message.reply_text(
                f"{prefix_text}\n\nNo usernames found."
            )
        else:
            await message.reply_text("No usernames found.")
        return

    lines = []

    if prefix_text:
        lines.append(prefix_text)
        lines.append("")

    for index, username in enumerate(usernames, start=1):
        lines.append(f"{index}. @{username}")

    result = "\n".join(lines)

    if len(result) > 4000:
        chunks = [
            result[i:i + 4000]
            for i in range(0, len(result), 4000)
        ]

        for chunk in chunks:
            await message.reply_text(chunk, disable_web_page_preview=True)
    else:
        await message.reply_text(result, disable_web_page_preview=True)


async def get_group_members_for_picker() -> list[dict]:
    members = []
    seen = set()

    async for member in user.get_chat_members(GROUP_ID):
        tg_user = member.user

        if not tg_user:
            continue

        if tg_user.is_bot:
            continue

        username = (tg_user.username or "").strip().lstrip("@")
        if not username:
            continue

        if tg_user.id in seen:
            continue

        seen.add(tg_user.id)

        members.append(
            {
                "id": tg_user.id,
                "name": get_display_name(tg_user),
                "username": username
            }
        )

    return members


@bot.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    await message.reply_text(
        "Hello!\n\n"
        "I am online and ready.\n"
        "Use:\n"
        "/gang\n"
        "/gang hello\n"
        "/makeplaying\n"
        "/list"
    )


@bot.on_message(filters.group & filters.text)
async def gang_text_router(client, message: Message):
    text = (message.text or "").strip()
    match = GANG_PATTERN.fullmatch(text)

    if not match:
        return

    prefix_text = (match.group(1) or "").strip()

    try:
        usernames = []
        seen = set()

        async for member in user.get_chat_members(message.chat.id):
            usr = member.user

            if not usr:
                continue

            if usr.is_bot:
                continue

            if not usr.username:
                continue

            username = usr.username.strip()

            if username.lower() in seen:
                continue

            seen.add(username.lower())
            usernames.append(username)

        await send_group_usernames(message, prefix_text, usernames)

    except RPCError as e:
        await message.reply_text(f"Telegram Error:\n{e}")

    except Exception as e:
        await message.reply_text(f"Error:\n{e}")


@bot.on_message(filters.group & filters.command("makeplaying"))
async def makeplaying_cmd(client, message: Message):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ I AM IN", callback_data="playing_in"),
                InlineKeyboardButton("❌ I AM OUT", callback_data="playing_out")
            ],
            [
                InlineKeyboardButton("📋 GET LIST", callback_data="playing_list")
            ]
        ]
    )

    sent = await message.reply_text(
        "Choose your status:",
        reply_markup=keyboard
    )

    playing_data[sent.id] = {
        "message_id": sent.id,
        "chat_id": sent.chat.id,
        "in": {},
        "out": {}
    }


@bot.on_message(filters.private & filters.text)
async def private_list_router(client, message: Message):
    text = (message.text or "").strip()

    if not LIST_PATTERN.fullmatch(text):
        return

    try:
        members = await get_group_members_for_picker()

        if not members:
            await message.reply_text("No usernames found in the target group.")
            return

        picker_data[message.id] = {
            "members": {item["id"]: item for item in members},
            "selected": set()
        }

        await message.reply_text(
            "Tap names below to add or remove them.\n"
            "Use FINAL LIST to get usernames only.",
            reply_markup=build_picker_keyboard(message.id, picker_data[message.id])
        )

    except RPCError as e:
        await message.reply_text(f"Telegram Error:\n{e}")

    except Exception as e:
        await message.reply_text(f"Error:\n{e}")


@bot.on_callback_query()
async def callback_router(client, query: CallbackQuery):
    if not query.message:
        return

    data = query.data or ""

    if data.startswith("playing_"):
        msg_id = query.message.id

        if msg_id not in playing_data:
            await query.answer("List expired.", show_alert=True)
            return

        play_data = playing_data[msg_id]
        user_info = query.from_user

        if not user_info:
            await query.answer("User not found.", show_alert=True)
            return

        username = f"@{user_info.username}" if user_info.username else user_info.first_name

        if data == "playing_in":
            play_data["out"].pop(user_info.id, None)
            play_data["in"][user_info.id] = username

            updated_text = build_playing_text(play_data)

            await query.message.edit_text(
                updated_text,
                reply_markup=query.message.reply_markup
            )

            await query.answer("Added to playing list.")
            return

        if data == "playing_out":
            play_data["in"].pop(user_info.id, None)
            play_data["out"][user_info.id] = username

            updated_text = build_playing_text(play_data)

            await query.message.edit_text(
                updated_text,
                reply_markup=query.message.reply_markup
            )

            await query.answer("Added to out list.")
            return

        if data == "playing_list":
            text = build_playing_text(play_data)
            await query.message.reply_text(text)
            await query.answer()
            return

    if data.startswith("pick:"):
        parts = data.split(":")

        if len(parts) != 3:
            await query.answer("Invalid button.", show_alert=True)
            return

        msg_id = int(parts[1])
        user_id = int(parts[2])

        if msg_id not in picker_data:
            await query.answer("List expired.", show_alert=True)
            return

        data_obj = picker_data[msg_id]

        if user_id not in data_obj["members"]:
            await query.answer("Member not found.", show_alert=True)
            return

        if user_id in data_obj["selected"]:
            data_obj["selected"].remove(user_id)
        else:
            data_obj["selected"].add(user_id)

        await query.message.edit_text(
            build_picker_text(data_obj),
            reply_markup=build_picker_keyboard(msg_id, data_obj)
        )
        await query.answer("Updated.")
        return

    if data.startswith("pickfinal:"):
        parts = data.split(":")

        if len(parts) != 2:
            await query.answer("Invalid button.", show_alert=True)
            return

        msg_id = int(parts[1])

        if msg_id not in picker_data:
            await query.answer("List expired.", show_alert=True)
            return

        data_obj = picker_data[msg_id]

        final_usernames = []
        for user_id in data_obj["members"]:
            if user_id in data_obj["selected"]:
                username = data_obj["members"][user_id]["username"]
                if username:
                    final_usernames.append(f"@{username}")

        if not final_usernames:
            await query.answer("No usernames selected.", show_alert=True)
            return

        await query.message.reply_text("\n".join(final_usernames), disable_web_page_preview=True)
        await query.answer("Final list sent.")
        return


async def main() -> None:
    await user.start()
    await bot.start()

    try:
        await idle()
    finally:
        await bot.stop()
        await user.stop()