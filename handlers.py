# File 4: handlers.py

import os

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from config import (
    OWNER_ID,
    DOWNLOAD_DIR,
    MERGE_DIR,
)

# user states
USER_STATE = {}
MERGE_FILES = {}


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    USER_STATE[update.effective_user.id] = {
        "mode": None,
        "duration": None,
    }

    await update.message.reply_text(
        "Video Tool Bot Ready ✅\n\n"
        "/split - Split Video\n"
        "/merge - Merge Videos"
    )


async def split_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    keyboard = [
        [
            InlineKeyboardButton("5 sec", callback_data="split_5"),
            InlineKeyboardButton("10 sec", callback_data="split_10"),
        ],
        [
            InlineKeyboardButton("20 sec", callback_data="split_20"),
            InlineKeyboardButton("30 sec", callback_data="split_30"),
        ],
        [
            InlineKeyboardButton("Custom", callback_data="split_custom"),
        ],
    ]

    await update.message.reply_text(
        "Select Clip Duration",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def merge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    user = update.effective_user.id

    USER_STATE[user] = {
        "mode": "merge",
    }

    MERGE_FILES[user] = []

    await update.message.reply_text(
        "Send all clips.\n\n"
        "When finished send /done"
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    await update.message.reply_text(
        "Merge module will start here."
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return

    user = update.effective_user.id

    USER_STATE.pop(user, None)
    MERGE_FILES.pop(user, None)

    await update.message.reply_text("Cancelled.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user.id

    if not is_owner(user):
        return

    data = query.data

    if data.startswith("split_"):

        duration = data.replace("split_", "")

        USER_STATE[user] = {
            "mode": "split",
            "duration": duration,
        }

        if duration == "custom":
            await query.edit_message_text(
                "Send duration in seconds.\nExample:\n17"
            )
            return

        await query.edit_message_text(
            f"Duration : {duration} sec\n\nNow send video."
        )


async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_owner(update.effective_user.id):
        return

    user = update.effective_user.id

    state = USER_STATE.get(user)

    if not state:
        await update.message.reply_text(
            "Use /split or /merge first."
        )
        return

    file = (
        update.message.video
        or update.message.document
    )

    tg_file = await file.get_file()

    save_path = os.path.join(
        DOWNLOAD_DIR,
        f"{file.file_unique_id}.mp4"
    )

    await tg_file.download_to_drive(save_path)

    if state["mode"] == "split":

        await update.message.reply_text(
            "Video received.\nSplit module will start..."
        )

    elif state["mode"] == "merge":

        MERGE_FILES[user].append(save_path)

        await update.message.reply_text(
            f"Clip Added : {len(MERGE_FILES[user])}"
  )
