import logging

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from handlers import (
    start,
    split_command,
    merge_command,
    done_command,
    cancel_command,
    button_handler,
    video_handler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("split", split_command))
    app.add_handler(CommandHandler("merge", merge_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # Button clicks
    app.add_handler(CallbackQueryHandler(button_handler))

    # Video/File handler
    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.Document.VIDEO,
            video_handler,
        )
    )

    logger.info("Bot Started...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
