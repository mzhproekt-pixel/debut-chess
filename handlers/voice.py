import asyncio
import os
from aiogram import Router, F
from aiogram.types import Message
from aiogram import Bot
from services import claude
from services.stt import transcribe
from services.tts import text_to_speech

router = Router()


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot):
    thinking = await message.answer("Слушаю...")
    try:
        file = await bot.get_file(message.voice.file_id)
        ogg_path = f"/tmp/{message.voice.file_id}.ogg"
        await bot.download_file(file.file_path, ogg_path)

        await thinking.edit_text("Понял, думаю...")
        text = await transcribe(ogg_path)
        os.remove(ogg_path)

        reply = await asyncio.get_event_loop().run_in_executor(
            None, claude.chat, message.from_user.id, text
        )

        voice_path = await asyncio.get_event_loop().run_in_executor(
            None, text_to_speech, reply
        )

        await thinking.delete()
        await message.answer(f"_{text}_\n\n{reply}", parse_mode="Markdown")
        await message.answer_voice(voice=open(voice_path, "rb"))
        os.remove(voice_path)

    except Exception as e:
        await thinking.edit_text(f"Ошибка обработки голоса: {e}")
