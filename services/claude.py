import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from services.search import web_search
from database import db

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

TOOLS = [
    {
        "name": "web_search",
        "description": "Поиск актуальной информации в интернете. Используй когда нужны свежие данные, новости, цены, погода и т.д.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_memory",
        "description": "Сохранить важную информацию о пользователе для будущих разговоров (имя, предпочтения, факты о нём).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Короткий ключ (например: 'имя', 'город', 'профессия')"},
                "value": {"type": "string", "description": "Значение для сохранения"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "get_memories",
        "description": "Получить всю сохранённую информацию о пользователе.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _build_system(user_id: int) -> str:
    memories = db.get_memories(user_id)
    mem_text = ""
    if memories:
        lines = [f"- {k}: {v}" for k, v in memories.items()]
        mem_text = "\nЧто ты знаешь о пользователе:\n" + "\n".join(lines)

    return (
        "Ты Джарвис — умный, лаконичный и слегка саркастичный AI-ассистент. "
        "Отвечаешь на русском языке. Помогаешь с любыми задачами: поиском информации, "
        "анализом файлов, советами. Когда нужна свежая информация — используй web_search. "
        "Запоминай важные факты о пользователе через save_memory."
        + mem_text
    )


def chat(user_id: int, user_message: str, file_content: str | None = None) -> str:
    if file_content:
        user_message = f"{user_message}\n\n[Файл]\n{file_content}"

    db.save_message(user_id, "user", user_message)
    history = db.get_history(user_id)

    messages = history

    while True:
        response = _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=_build_system(user_id),
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            assistant_content = response.content

            for block in response.content:
                if block.type == "tool_use":
                    result = _handle_tool(user_id, block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages = messages + [
                {"role": "assistant", "content": assistant_content},
                {"role": "user", "content": tool_results},
            ]
            continue

        reply = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        db.save_message(user_id, "assistant", reply)
        return reply


def _handle_tool(user_id: int, name: str, inputs: dict) -> str:
    if name == "web_search":
        return web_search(inputs["query"])
    elif name == "save_memory":
        db.save_memory(user_id, inputs["key"], inputs["value"])
        return f"Запомнено: {inputs['key']} = {inputs['value']}"
    elif name == "get_memories":
        memories = db.get_memories(user_id)
        if not memories:
            return "Нет сохранённых данных."
        return "\n".join(f"{k}: {v}" for k, v in memories.items())
    return "Неизвестный инструмент."
