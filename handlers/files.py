import asyncio
import os
from aiogram import Router, F
from aiogram.types import Message
from aiogram import Bot
from services import claude

router = Router()

SUPPORTED_EXTENSIONS = {".txt", ".py", ".js", ".ts", ".json", ".md", ".csv", ".html", ".css", ".yaml", ".yml"}
MAX_FILE_SIZE = 500_000  # 500KB


@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    doc = message.document
    _, ext = os.path.splitext(doc.file_name or "")

    if ext.lower() not in SUPPORTED_EXTENSIONS:
        await message.answer(f"Поддерживаются только текстовые файлы: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    if doc.file_size > MAX_FILE_SIZE:
        await message.answer("Файл слишком большой (макс. 500KB).")
        return

    thinking = await message.answer("Читаю файл...")
    try:
        file = await bot.get_file(doc.file_id)
        path = f"/tmp/{doc.file_id}{ext}"
        await bot.download_file(file.file_path, path)

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        os.remove(path)

        caption = message.caption or "Проанализируй этот файл."

        await thinking.edit_text("Анализирую...")
        reply = await asyncio.get_event_loop().run_in_executor(
            None, claude.chat, message.from_user.id, caption, content
        )
        await thinking.delete()
        await message.answer(reply, parse_mode="Markdown")

    except Exception as e:
        await thinking.edit_text(f"Ошибка обработки файла: {e}")
