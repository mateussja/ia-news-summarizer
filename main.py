import os
import re
import time
import feedparser
import requests
from google import genai

# Configurações
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

client = genai.Client(api_key=GEMINI_KEY)

# Fallback de modelos: tenta do mais novo para o mais compatível
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-latest",
]

OFFICIAL_FEEDS = [
    'https://openai.com/news/rss.xml',
    'https://deepmind.google/blog/rss.xml',
    'https://blogs.microsoft.com/ai/feed/',
    'https://blogs.nvidia.com/blog/category/deep-learning/feed/'
]

NEWS_FEEDS = [
    'https://techcrunch.com/category/artificial-intelligence/feed/',
    'https://the-decoder.com/feed/',
    'https://venturebeat.com/category/ai/feed/',
    'https://www.zdnet.com/topic/artificial-intelligence/rss.xml',
    'https://feeds.feedburner.com/AIWeekly',
    'https://machinelearningmastery.com/feed/',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; AINewsBot/1.0)'
}


def fetch_feed(url, source_label, max_entries=5):
    """Busca feed com requests primeiro para evitar erros de encoding do feedparser."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        if not feed.entries:
            print(f"[WARN] Feed sem entries: {url}")
            return []
        articles = []
        for entry in feed.entries[:max_entries]:
            articles.append({
                'title':  entry.get('title', 'No title').strip(),
                'link':   entry.get('link', '').strip(),
                'source': source_label
            })
        return articles
    except Exception as e:
        print(f"[WARN] Feed ignorado ({url}): {e}")
        return []


def collect_all_feeds():
    articles = []
    for url in OFFICIAL_FEEDS:
        articles += fetch_feed(url, 'OFFICIAL')
    for url in NEWS_FEEDS:
        articles += fetch_feed(url, 'NEWS')
    return articles


def call_gemini(prompt):
    """Tenta cada modelo em ordem até um funcionar."""
    for model in MODELS:
        for attempt in range(3):
            try:
                print(f"[INFO] Tentando modelo: {model} (tentativa {attempt + 1})")
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                print(f"[OK] Modelo {model} respondeu.")
                return response.text
            except Exception as e:
                err = str(e)
                if "429" in err and attempt < 2:
                    wait = 60 * (attempt + 1)
                    print(f"[WARN] Rate limit, aguardando {wait}s...")
                    time.sleep(wait)
                elif "404" in err or "not found" in err.lower() or "not available" in err.lower():
                    print(f"[WARN] Modelo {model} indisponível, tentando próximo...")
                    break  # tenta próximo modelo
                else:
                    print(f"[ERROR] {model} falhou: {e}")
                    break
    return None


def filter_and_summarize(all_articles):
    articles_text = "\n".join([
        f"- Title: {a['title']} | Source: {a['source']} | Link: {a['link']}"
        for a in all_articles
    ])

    prompt = f"""
You are an expert AI news editor. Below is a list of latest AI news from official blogs and news sites.

TASK:
1. Remove duplicate stories (keep only the most relevant one).
2. RULE FOR OFFICIAL BLOGS: Only include an official announcement (from OpenAI, Meta, Google, etc.) IF there is also a news article from a tech site discussing it. If it's a standalone minor official update, ignore it.
3. Pick the top 5-7 most important unique stories.
4. For each selected story, write a concise summary in ENGLISH (max 2 sentences).
5. Format the output EXACTLY like this (no extra blank lines inside a block):
TITLE: [News Title]
SUMMARY: [English Summary]
LINK: [URL]
---

ARTICLES:
{articles_text}
"""
    return call_gemini(prompt)


def parse_blocks(result):
    news_items = []
    for block in result.split("---"):
        block = block.strip()
        if not block:
            continue
        title_m   = re.search(r'TITLE:\s*(.+)',          block, re.IGNORECASE)
        summary_m = re.search(r'SUMMARY:\s*(.+)',        block, re.IGNORECASE)
        link_m    = re.search(r'LINK:\s*(https?://\S+)', block, re.IGNORECASE)
        if title_m and summary_m and link_m:
            news_items.append((
                title_m.group(1).strip(),
                summary_m.group(1).strip(),
                link_m.group(1).strip()
            ))
        else:
            print(f"[WARN] Bloco ignorado (campos faltando):\n{block[:200]}")
    return news_items


def send_to_discord(news_items):
    if not news_items:
        print("[WARN] Nenhuma noticia para enviar.")
        return

    header = "🤖 **INTELLIGENCE REPORT: SELECTED AI NEWS**\n\n"
    formatted = [
        f"🚀 **{title}**\n{summary}\n🔗 <{link}>"
        for title, summary, link in news_items
    ]

    chunks, current = [], header
    for item in formatted:
        candidate = current + item + "\n\n"
        if len(candidate) > 1990:
            chunks.append(current.rstrip())
            current = item + "\n\n"
        else:
            current = candidate
    if current.strip():
        chunks.append(current.rstrip())

    for i, chunk in enumerate(chunks, 1):
        resp = requests.post(DISCORD_WEBHOOK, json={"content": chunk})
        if resp.status_code not in (200, 204):
            print(f"[ERROR] Chunk {i}: HTTP {resp.status_code} — {resp.text}")
        else:
            print(f"[OK] Chunk {i}/{len(chunks)} enviado ao Discord.")


def run():
    all_articles = collect_all_feeds()
    print(f"[INFO] Total de artigos coletados: {len(all_articles)}")

    if not all_articles:
        print("[ERROR] Nenhum artigo coletado. Abortando.")
        return

    result = filter_and_summarize(all_articles)
    if not result:
        print("[ERROR] Gemini nao retornou resultado.")
        return

    news_items = parse_blocks(result)
    print(f"[INFO] Noticias parseadas: {len(news_items)}")

    send_to_discord(news_items)


if __name__ == "__main__":
    run()
