import logging

from telegram import BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db
from config import FILES_DIR, get_bot_token
from handlers import (
    SELECT_CATEGORY,
    WAIT_CUSTOM_NAME,
    WAIT_COMMENT,
    cancel,
    category_selected,
    custom_name_received,
    comment_command,
    delete_command,
    download_command,
    error_handler,
    files_command,
    help_command,
    info_command,
    last_command,
    menu_command,
    receive_file,
    save_file_with_comment,
    search_command,
    start,
    stats_command,
    text_router,
    unknown_command,
    upload_command,
    versions_command,
    categories_command,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
async def setup_bot_commands(app):
    """Создаёт выпадающее меню команд в Telegram."""
    await app.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("menu", "Открыть меню"),
        BotCommand("help", "Показать справку"),
        BotCommand("upload", "Как загрузить файл"),
        BotCommand("files", "Показать все файлы"),
        BotCommand("categories", "Показать категории"),
        BotCommand("search", "Найти файл"),
        BotCommand("versions", "Показать версии файла"),
        BotCommand("download", "Скачать файл по ID"),
        BotCommand("delete", "Удалить файл по ID"),
        BotCommand("comment", "Изменить комментарий"),
        BotCommand("info", "Информация о файле"),
        BotCommand("last", "Последние файлы"),
        BotCommand("stats", "Статистика"),
        BotCommand("cancel", "Отменить действие"),
    ])

def main() -> None:
    """Точка входа в приложение."""
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()

    app = (
    ApplicationBuilder()
    .token(get_bot_token())
    .post_init(setup_bot_commands)
    .build()
    )

    upload_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL | filters.PHOTO, receive_file)],
        states={
            SELECT_CATEGORY: [CallbackQueryHandler(category_selected, pattern=r"^category:")],
            WAIT_CUSTOM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_name_received)],
            WAIT_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_file_with_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("files", files_command))
    app.add_handler(CommandHandler("categories", categories_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("versions", versions_command))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("comment", comment_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("last", last_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(upload_conversation)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_error_handler(error_handler)

    print("File Manager Bot запущен. Нажмите Ctrl+C для остановки.")
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
