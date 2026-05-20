import logging
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

import database as db
from config import CATEGORIES, MAX_FILE_SIZE_MB
from keyboards import categories_keyboard, main_menu_keyboard
from utils import (
    build_storage_path,
    format_file_row,
    format_files_list,
    human_size,
    make_custom_filename,
)

logger = logging.getLogger(__name__)

SELECT_CATEGORY, WAIT_CUSTOM_NAME, WAIT_COMMENT = range(3)


async def _log(update: Update) -> None:
    if not update.effective_user:
        return
    text = ""
    if update.message:
        text = update.message.text or update.message.caption or "[file/attachment]"
    elif update.callback_query:
        text = update.callback_query.data or "[callback]"
    db.log_message(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        message_text=text,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    text = (
        "Здравствуйте! Я File Manager Bot.\n\n"
        "Я умею хранить файлы, распределять их по категориям, "
        "создавать версии, добавлять комментарии, искать, скачивать и удалять файлы.\n\n"
        "Чтобы загрузить файл, просто отправьте мне документ или фото.\n"
        "Для списка команд используйте /help."
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    text = (
        "Команды бота:\n\n"
        "/start — запуск бота\n"
        "/help — справка\n"
        "/upload — инструкция по загрузке файла\n"
        "/files — список всех файлов\n"
        "/categories — список категорий\n"
        "/search название — поиск файла\n"
        "/versions название_файла — показать версии файла\n"
        "/download ID — скачать файл по ID\n"
        "/delete ID — удалить файл по ID\n"
        "/comment ID текст — изменить комментарий\n"
        "/info ID — подробная информация о файле\n"
        "/last — последние загруженные файлы\n"
        "/stats — статистика хранилища\n"
        "/cancel — отмена текущего действия\n\n"
        "Пример: /search отчет\n"
        "Пример: /download 3\n"
        "Пример: /comment 3 финальная версия проекта"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    await update.message.reply_text(
        "Чтобы загрузить файл, просто отправьте мне документ или фото. "
        "После этого я попрошу выбрать категорию и написать комментарий."
    )


async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _log(update)
    message = update.message
    user = update.effective_user

    if message.document:
        attachment = message.document
        original_name = attachment.file_name or f"document_{attachment.file_unique_id}.bin"
        file_size = attachment.file_size or 0
        telegram_file_id = attachment.file_id
        file_type = "document"
    elif message.photo:
        attachment = message.photo[-1]
        original_name = f"photo_{attachment.file_unique_id}.jpg"
        file_size = attachment.file_size or 0
        telegram_file_id = attachment.file_id
        file_type = "photo"
    else:
        await message.reply_text("Пожалуйста, отправьте документ или фото.")
        return ConversationHandler.END

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size and file_size > max_bytes:
        await message.reply_text(
            f"Файл слишком большой. Максимальный размер: {MAX_FILE_SIZE_MB} МБ."
        )
        return ConversationHandler.END

    context.user_data["pending_file"] = {
        "user_id": user.id,
        "original_name": original_name,
        "file_size": file_size,
        "telegram_file_id": telegram_file_id,
        "file_type": file_type,
    }

    await message.reply_text(
        f"Файл получен: {original_name}\n"
        f"Размер: {human_size(file_size)}\n\n"
        "Выберите категорию:",
        reply_markup=categories_keyboard(),
    )
    return SELECT_CATEGORY


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _log(update)
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    category_key = data.replace("category:", "")

    if category_key not in CATEGORIES:
        await query.edit_message_text("Неизвестная категория. Попробуйте загрузить файл заново.")
        return ConversationHandler.END

    pending_file = context.user_data.get("pending_file")
    if not pending_file:
        await query.edit_message_text("Не найден файл для сохранения. Отправьте файл ещё раз.")
        return ConversationHandler.END

    pending_file["category_key"] = category_key
    context.user_data["pending_file"] = pending_file

    await query.edit_message_text(
    f"Категория выбрана: {CATEGORIES[category_key]}\n\n"
    "Теперь напишите, как назвать файл.\n\n"
    "Например:\n"
    "конспект_по_python\n\n"
    "Если хотите автоматическое название, напишите: -"
)
    return WAIT_CUSTOM_NAME

async def custom_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _log(update)

    pending_file = context.user_data.get("pending_file")
    if not pending_file:
        await update.message.reply_text("Не найден файл для сохранения. Отправьте файл ещё раз.")
        return ConversationHandler.END

    user_text = (update.message.text or "").strip()
    original_name = pending_file["original_name"]
    user_id = pending_file["user_id"]
    file_type = pending_file["file_type"]

    if user_text == "-":
        if file_type == "photo":
            prefix = "photo"
            extension = ".jpg"
        else:
            prefix = "document"
            extension = Path(original_name).suffix or ".bin"

        number = db.get_next_auto_number(user_id, prefix)
        custom_name = f"{prefix}_{number}{extension}"
    else:
        custom_name = make_custom_filename(user_text, original_name)

    pending_file["custom_name"] = custom_name
    context.user_data["pending_file"] = pending_file

    await update.message.reply_text(
        f"Название файла: {custom_name}\n\n"
        "Теперь отправьте комментарий к файлу.\n"
        "Если комментарий не нужен, напишите: -"
    )

    return WAIT_COMMENT


async def save_file_with_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _log(update)
    pending_file = context.user_data.get("pending_file")
    if not pending_file:
        await update.message.reply_text("Не найден файл для сохранения. Отправьте файл ещё раз.")
        return ConversationHandler.END

    comment = (update.message.text or "").strip()
    if comment == "-":
        comment = ""

    user_id = pending_file["user_id"]
    original_name = pending_file.get("custom_name") or pending_file["original_name"]
    category_key = pending_file["category_key"]
    version = db.get_next_version(user_id, original_name)
    stored_name, storage_path = build_storage_path(category_key, original_name, version)

    try:
        telegram_file = await context.bot.get_file(pending_file["telegram_file_id"])
        await telegram_file.download_to_drive(custom_path=storage_path)

        file_id = db.add_file(
            user_id=user_id,
            original_name=original_name,
            stored_name=stored_name,
            category_key=category_key,
            version=version,
            comment=comment,
            file_path=storage_path,
            file_size=pending_file["file_size"],
            telegram_file_id=pending_file["telegram_file_id"],
        )
    except Exception as exc:
        logger.exception("Ошибка при сохранении файла")
        await update.message.reply_text(f"Ошибка при сохранении файла: {exc}")
        return ConversationHandler.END
    finally:
        context.user_data.pop("pending_file", None)

    await update.message.reply_text(
        "Файл успешно сохранён.\n\n"
        f"ID файла: {file_id}\n"
        f"Название: {original_name}\n"
        f"Категория: {CATEGORIES[category_key]}\n"
        f"Версия: {version}\n"
        f"Комментарий: {comment or 'без комментария'}\n\n"
        f"Скачать файл можно командой: /download {file_id}"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _log(update)
    context.user_data.pop("pending_file", None)
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END


async def files_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    rows = db.list_files(update.effective_user.id, limit=30)
    text = "Ваши файлы:\n\n" + format_files_list(rows)
    if rows:
        text += "\n\nДля скачивания используйте: /download ID"
    await update.message.reply_text(text)


async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    stats = db.get_category_stats(update.effective_user.id)
    stats_by_key = {row["category_key"]: row for row in stats}

    lines = ["Категории:"]
    for key, title in CATEGORIES.items():
        row = stats_by_key.get(key)
        count = row["count_files"] if row else 0
        size = human_size(row["total_size"]) if row else "0 Б"
        lines.append(f"• {title}: {count} файл(ов), {size}")

    await update.message.reply_text("\n".join(lines))


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    if not context.args:
        await update.message.reply_text("Напишите запрос после команды. Пример: /search отчет")
        return

    query = " ".join(context.args)
    rows = db.search_files(update.effective_user.id, query)
    text = f"Результаты поиска по запросу '{query}':\n\n" + format_files_list(rows)
    await update.message.reply_text(text)


async def versions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    if not context.args:
        await update.message.reply_text(
            "Укажите название файла или ID. Пример: /versions project.docx или /versions 3"
        )
        return

    arg = " ".join(context.args).strip()
    user_id = update.effective_user.id

    if arg.isdigit():
        row = db.get_file_by_id(user_id, int(arg))
        if not row:
            await update.message.reply_text("Файл с таким ID не найден.")
            return
        original_name = row["original_name"]
    else:
        original_name = arg

    rows = db.get_versions_by_name(user_id, original_name)
    if not rows:
        await update.message.reply_text("Версии не найдены.")
        return

    lines = [f"История версий файла: {original_name}\n"]
    for row in rows:
        comment = f" — {row['comment']}" if row["comment"] else ""
        lines.append(
            f"ID {row['id']}: версия {row['version']} | "
            f"{row['category_title']} | {row['uploaded_at']}{comment}"
        )
    await update.message.reply_text("\n".join(lines))


async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Укажите ID файла. Пример: /download 3")
        return

    file_id = int(context.args[0])
    row = db.get_file_by_id(update.effective_user.id, file_id)
    if not row:
        await update.message.reply_text("Файл с таким ID не найден.")
        return

    file_path = Path(row["file_path"])
    try:
        if file_path.exists():
            await update.message.reply_document(
                document=file_path,
                filename=row["original_name"],
                caption=f"{row['original_name']} | версия {row['version']}",
            )
        else:
            await update.message.reply_document(
                document=row["telegram_file_id"],
                filename=row["original_name"],
                caption=f"{row['original_name']} | версия {row['version']}",
            )
    except Exception as exc:
        logger.exception("Ошибка при скачивании файла")
        await update.message.reply_text(f"Не удалось отправить файл: {exc}")


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Укажите ID файла. Пример: /delete 3")
        return

    file_id = int(context.args[0])
    row = db.delete_file_record(update.effective_user.id, file_id)
    if not row:
        await update.message.reply_text("Файл с таким ID не найден.")
        return

    file_path = Path(row["file_path"])
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            logger.warning("Не удалось удалить файл с диска: %s", file_path)

    await update.message.reply_text(
        f"Файл удалён из базы и хранилища:\n{row['original_name']} | версия {row['version']}"
    )


async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    if len(context.args) < 2 or not context.args[0].isdigit():
        await update.message.reply_text(
            "Используйте формат: /comment ID новый комментарий\n"
            "Пример: /comment 3 финальная версия проекта"
        )
        return

    file_id = int(context.args[0])
    new_comment = " ".join(context.args[1:]).strip()
    ok = db.update_comment(update.effective_user.id, file_id, new_comment)
    if not ok:
        await update.message.reply_text("Файл с таким ID не найден.")
        return

    await update.message.reply_text("Комментарий обновлён.")


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Укажите ID файла. Пример: /info 3")
        return

    row = db.get_file_by_id(update.effective_user.id, int(context.args[0]))
    if not row:
        await update.message.reply_text("Файл с таким ID не найден.")
        return

    await update.message.reply_text(format_file_row(row))


async def last_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    rows = db.latest_files(update.effective_user.id, limit=5)
    text = "Последние загруженные файлы:\n\n" + format_files_list(rows)
    await update.message.reply_text(text)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    user_id = update.effective_user.id
    total = db.get_total_stats(user_id)
    categories = db.get_category_stats(user_id)

    lines = [
        "Статистика хранилища:",
        f"Всего файлов: {total['total_files']}",
        f"Уникальных названий: {total['unique_names']}",
        f"Общий размер: {human_size(total['total_size'])}",
        "",
        "По категориям:",
    ]
    if categories:
        for row in categories:
            lines.append(
                f"• {row['category_title']}: {row['count_files']} файл(ов), "
                f"{human_size(row['total_size'])}"
            )
    else:
        lines.append("Пока нет файлов.")

    await update.message.reply_text("\n".join(lines))


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    text = (update.message.text or "").strip().lower()

    if text in {"❓ помощь", "помощь", "help", "команды"}:
        await help_command(update, context)

    elif text in {"📁 файлы", "файлы", "список файлов"}:
        await files_command(update, context)

    elif text in {"🗂 категории", "категории"}:
        await categories_command(update, context)

    elif text in {"📊 статистика", "статистика"}:
        await stats_command(update, context)

    elif text in {"🕘 последние", "последние"}:
        await last_command(update, context)

    elif text in {"📤 загрузить файл", "загрузить", "загрузка"}:
        await upload_command(update, context)

    else:
        await update.message.reply_text(
            "Я не понимаю эту команду. Используйте /help или кнопки меню.",
            reply_markup=main_menu_keyboard()
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _log(update)
    await update.message.reply_text(
        "Неизвестная команда. Используйте /help, чтобы посмотреть список доступных команд."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка при обработке обновления: %s", context.error)
