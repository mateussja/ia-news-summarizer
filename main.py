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
MODEL = "gemini-2.0-flash"

OFFICIAL_FEEDS = [
    'https://openai.com/news/rss.xml',
    'https://deepmind.google/blog/rss.xml',
    'https://www.anthropic.com/news/rss.xml',
    'https://ai.meta.com/blog/rss/',
    'https://blogs.microsoft.com/ai/feed/',
    'https://blogs.nvidia.com/blog/category/deep-learning/feed/'
]

NEWS_FEEDS = [
    'https://techcrunch.com/category/artificial-intelligence/feed/',
    'https://the-decoder.com/feed/',
    'https://www.technologyreview.com/topic/artificial-intelligence/rss/',
    'https://www.theverge.com/ai-artificial-intelligence/rss/index.xml',
    'https://venturebeat.com/category/ai/feed/',
    'https://www.wired.com/category/science/ai/feed/',
    'https://www.zdnet.com/topic/artificial-intelligence/rss.xml'
]


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

    # Retry com backoff para lidar com rate limits transientes (429)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt
            )
            return response.text if response.text else None
        except Exception as e:
            err = str(e)
            if "429" in err and attempt < 2:
                wait = 60 * (attempt + 1)
                print(f"[WARN] Rate limit hit, aguardando {wait}s (tentativa {attempt + 1}/3)...")
                time.sleep(wait)
            else:
                print(f"[ERROR] Gemini falhou: {e}")
                return None

    return None


def parse_blocks(result):
    news_items = []
    blocks = result.split("---")

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        title_match   = re.search(r'TITLE:\s*(.+)', block, re.IGNORECASE)
        summary_match = re.search(r'SUMMARY:\s*(.+)', block, re.IGNORECASE)
        link_match    = re.search(r'LINK:\s*(https?://\S+)', block, re.IGNORECASE)

        if title_match and summary_match and link_match:
            news_items.append((
                title_match.group(1).strip(),
                summary_match.group(1).strip(),
                link_match.group(1).strip()
            ))
        else:
            print(f"[WARN] Bloco ignorado (campos faltando):\n{block[:200]}")

    return news_items


def send_to_discord(webhook_url, news_items):
    if not news_items:
        print("[WARN] Nenhuma noticia para enviar.")
        return

    header = "🤖 **INTELLIGENCE REPORT: SELECTED AI NEWS**\n\n"
    formatted = [
        f"🚀 **{title}**\n{summary}\n🔗 <{link}>"
        for title, summary, link in news_items
    ]

    chunks = []
    current = header
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
        resp = requests.post(webhook_url, json={"content": chunk})
        if resp.status_code not in (200, 204):
            print(f"[ERROR] Falha ao enviar chunk {i}: HTTP {resp.status_code} — {resp.text}")
        else:
            print(f"[OK] Chunk {i}/{len(chunks)} enviado.")


def collect_feeds(feed_urls, source_label, max_per_feed=5):
    articles = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            # bozo indica XML malformado, mas feedparser ainda parseia o que consegue
            # só ignora se não trouxe nenhuma entry
            if not feed.entries:
                raise ValueError(f"Nenhuma entry retornada (bozo={feed.bozo})")
            for entry in feed.entries[:max_per_feed]:
                articles.append({
                    'title': entry.get('title', 'No title'),
                    'link':  entry.get('link', ''),
                    'source': source_label
                })
        except Exception as e:
            print(f"[WARN] Feed ignorado ({url}): {e}")
    return articles


def run():
    all_articles = []
    all_articles += collect_feeds(OFFICIAL_FEEDS, 'OFFICIAL')
    all_articles += collect_feeds(NEWS_FEEDS, 'NEWS')

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

    send_to_discord(DISCORD_WEBHOOK, news_items)


if __name__ == "__main__":
    run()
