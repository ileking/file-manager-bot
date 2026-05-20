from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from config import CATEGORIES


def categories_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, title in CATEGORIES.items():
        rows.append([InlineKeyboardButton(title, callback_data=f"category:{key}")])
    return InlineKeyboardMarkup(rows)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ["📤 Загрузить файл", "📁 Файлы"],
        ["🗂 Категории", "🕘 Последние"],
        ["📊 Статистика", "❓ Помощь"],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие"
    )