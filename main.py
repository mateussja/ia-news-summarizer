import os
import feedparser
import requests
import google.generativeai as genai

# Configurações de API
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# LISTA AMPLIADA DE FONTES
RSS_FEEDS = [
    'https://techcrunch.com/category/artificial-intelligence/feed/',
    'https://the-decoder.com/feed/',
    'https://www.technologyreview.com/topic/artificial-intelligence/rss/',
    'https://www.theverge.com/ai-artificial-intelligence/rss/index.xml',
    'https://venturebeat.com/category/ai/feed/',
    'https://openai.com/news/rss.xml',
    'https://deepmind.google/blog/rss.xml',
    'https://www.zdnet.com/topic/artificial-intelligence/rss.xml',
    'https://mashable.com/category/artificial-intelligence/feed/',
    'https://www.wired.com/category/science/ai/feed/'
]

def summarize_article(title, link):
    # Prompt agora solicita explicitamente Inglês
    prompt = (
        f"You are an AI expert. Summarize the following news in English: {title}. "
        f"Context link: {link}. Focus on technical breakthroughs or market impact. "
        f"Be concise, maximum 3 sentences. Do not use bold inside the summary."
    )
    try:
        response = model.generate_content(prompt)
        if response.text:
            return response.text.strip()
        return "Summary generation failed (empty response)."
    except Exception as e:
        return f"Summary unavailable (Error: {str(e)[:50]}...)"

def run():
    all_news = []
    seen_links = set() # Evita duplicatas entre feeds
    
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        # Pegamos as 2 mais recentes de cada fonte para não exceder o limite do Discord
        for entry in feed.entries[:2]:
            if entry.link not in seen_links:
                summary = summarize_article(entry.title, entry.link)
                
                # FORMATO NO DISCORD:
                # Usamos < > ao redor do link para desativar a pré-visualização automática
                # que estava bagunçando o layout.
                news_item = f"🚀 **{entry.title}**\n{summary}\n🔗 <{entry.link}>"
                all_news.append(news_item)
                seen_links.add(entry.link)

    if all_news:
        header = "🤖 **DAILY AI INTELLIGENCE REPORT**\n\n"
        # O Discord tem um limite de 2000 caracteres. Vamos enviar em blocos se necessário.
        full_message = header + "\n\n---\n\n".join(all_news)
        
        if len(full_message) > 2000:
            # Se for muito grande, pegamos apenas as primeiras notícias
            full_message = full_message[:1990] + "\n..."

        payload = {"content": full_message}
        requests.post(DISCORD_WEBHOOK, json=payload)

if __name__ == "__main__":
    run()
