import re
from datetime import datetime
from pathlib import Path

from config import FILES_DIR


def safe_filename(filename: str) -> str:
    """Очищает имя файла, чтобы его безопасно сохранять на диск."""
    filename = filename.strip() or "file"
    filename = re.sub(r"[\\/:*?\"<>|]+", "_", filename)
    filename = re.sub(r"\s+", "_", filename)
    return filename[:120]


def human_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "0 Б"
    size = float(size_bytes)
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


def build_storage_path(category_key: str, original_name: str, version: int) -> tuple[str, Path]:
    """Создаёт имя файла для хранения и путь к нему."""
    clean_name = safe_filename(original_name)
    path_obj = Path(clean_name)
    stem = path_obj.stem or "file"
    suffix = path_obj.suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stored_name = f"{stem}_v{version}_{timestamp}{suffix}"
    folder = FILES_DIR / category_key
    folder.mkdir(parents=True, exist_ok=True)
    return stored_name, folder / stored_name


def format_file_row(row) -> str:
    comment = row["comment"] if row["comment"] else "без комментария"
    return (
        f"ID: {row['id']}\n"
        f"📄 {row['original_name']}\n"
        f"Версия: {row['version']}\n"
        f"Категория: {row['category_title']}\n"
        f"Размер: {human_size(row['file_size'])}\n"
        f"Комментарий: {comment}\n"
        f"Дата: {row['uploaded_at']}"
    )


def format_files_list(rows) -> str:
    if not rows:
        return "Файлы не найдены."
    parts = []
    for row in rows:
        comment = f" — {row['comment']}" if row["comment"] else ""
        parts.append(
            f"ID {row['id']}: {row['original_name']} | v{row['version']} | "
            f"{row['category_title']} | {human_size(row['file_size'])}{comment}"
        )
    return "\n".join(parts)

def make_custom_filename(user_filename: str, original_filename: str) -> str:
    """
    Создаёт безопасное пользовательское имя файла.
    Если пользователь не указал расширение, оно берётся из исходного файла.
    """
    clean_name = safe_filename(user_filename)

    original_suffix = Path(original_filename).suffix
    custom_suffix = Path(clean_name).suffix

    if not custom_suffix and original_suffix:
        clean_name += original_suffix

    return clean_name