from duckduckgo_search import DDGS
from config import MAX_SEARCH_RESULTS


def web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_SEARCH_RESULTS))
        if not results:
            return "Ничего не найдено."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r['title']}**\n{r['body']}\nИсточник: {r['href']}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Ошибка поиска: {e}"
