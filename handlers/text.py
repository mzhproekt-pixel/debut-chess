import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from services import claude
from services.tts import text_to_speech
from database import db
import os

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Джарвис онлайн. Чем могу помочь?\n\n"
        "Команды:\n"
        "/clear — очистить историю\n"
        "/memory — показать что я о тебе знаю\n"
        "/voice — переключить голосовые ответы"
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message):
    db.clear_history(message.from_user.id)
    await message.answer("История очищена.")


@router.message(Command("memory"))
async def cmd_memory(message: Message):
    memories = db.get_memories(message.from_user.id)
    if not memories:
        await message.answer("Я ничего о тебе не знаю пока.")
        return
    lines = [f"**{k}**: {v}" for k, v in memories.items()]
    await message.answer("Что я знаю о тебе:\n\n" + "\n".join(lines))


@router.message(F.text)
async def handle_text(message: Message):
    thinking = await message.answer("...")
    try:
        reply = await asyncio.get_event_loop().run_in_executor(
            None, claude.chat, message.from_user.id, message.text
        )
        await thinking.delete()
        await message.answer(reply, parse_mode="Markdown")
    except Exception as e:
        await thinking.edit_text(f"Ошибка: {e}")
