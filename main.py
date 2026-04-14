import os
import feedparser
import requests
import google.generativeai as genai

# Configurações de API via Variáveis de Ambiente (Segurança)
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

# Configurar Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

RSS_FEEDS = [
    'https://techcrunch.com/category/artificial-intelligence/feed/',
    'https://the-decoder.com/feed/',
    'https://www.technologyreview.com/topic/artificial-intelligence/rss/'
]

def summarize_article(title, link):
    prompt = f"Resuma de forma concisa e em português a seguinte notícia de IA: {title}. Link: {link}. Foque no impacto técnico ou de mercado. Máximo 3 frases."
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "Resumo indisponível no momento."

def run():
    all_news = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        # Pega as 3 mais recentes de cada feed para não estourar limites
        for entry in feed.entries[:3]:
            summary = summarize_article(entry.title, entry.link)
            news_item = f"🔹 **{entry.title}**\n{summary}\n🔗 [Leia mais]({entry.link})"
            all_news.append(news_item)

    if all_news:
        message = "🤖 **Relatório Diário de IA (Resumido por Gemini)**\n\n" + "\n\n".join(all_news)
        # Discord tem limite de 2000 caracteres, vamos garantir que não passe
        payload = {"content": message[:2000]}
        requests.post(DISCORD_WEBHOOK, json=payload)

if __name__ == "__main__":
    run()
