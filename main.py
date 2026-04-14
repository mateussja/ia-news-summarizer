import os
import feedparser
import requests
import google.generativeai as genai

# Configurações
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

genai.configure(api_key=GEMINI_KEY)
# Ajuste do nome do modelo para evitar o erro 404
model = genai.GenerativeModel('gemini-1.5-flash')

# LISTA EXPANDIDA (OFICIAIS + NOTÍCIAS)
# Fontes Oficiais
OFFICIAL_FEEDS = [
    'https://openai.com/news/rss.xml',
    'https://deepmind.google/blog/rss.xml',
    'https://www.anthropic.com/news/rss.xml',
    'https://ai.meta.com/blog/rss/',
    'https://blogs.microsoft.com/ai/feed/',
    'https://blogs.nvidia.com/blog/category/deep-learning/feed/'
]

# Fontes de Notícias
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
    # Criamos uma lista de texto com Título e Link para a IA analisar
    articles_text = "\n".join([f"- Title: {a['title']} | Source: {a['source']} | Link: {a['link']}" for a in all_articles])
    
    prompt = f"""
    You are an expert AI news editor. Below is a list of latest AI news from official blogs and news sites.
    
    TASK:
    1. Remove duplicate stories (keep only the most relevant one).
    2. RULE FOR OFFICIAL BLOGS: Only include an official announcement (from OpenAI, Meta, Google, etc.) IF there is also a news article from a tech site discussing it. If it's a standalone minor official update, ignore it.
    3. Pick the top 5-7 most important unique stories.
    4. For each selected story, write a concise summary in ENGLISH (max 2 sentences).
    5. Format the output exactly like this:
    TITLE: [News Title]
    SUMMARY: [English Summary]
    LINK: [URL]
    ---
    
    ARTICLES:
    {articles_text}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text if response.text else None
    except Exception as e:
        print(f"Error in Gemini Processing: {e}")
        return None

def run():
    all_articles = []
    
    # Coletar de fontes oficiais
    for url in OFFICIAL_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            all_articles.append({'title': entry.title, 'link': entry.link, 'source': 'OFFICIAL'})

    # Coletar de fontes de notícias
    for url in NEWS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            all_articles.append({'title': entry.title, 'link': entry.link, 'source': 'NEWS'})

    # Processamento Inteligente com Gemini
    result = filter_and_summarize(all_articles)
    
    if result:
        # Formatação para o Discord
        formatted_news = []
        # Quebrar o resultado da IA em blocos
        blocks = result.split("---")
        for block in blocks:
            if "TITLE:" in block:
                # Extrair campos com cuidado
                lines = block.strip().split("\n")
                title = lines[0].replace("TITLE:", "").strip()
                summary = lines[1].replace("SUMMARY:", "").strip()
                link = lines[2].replace("LINK:", "").strip()
                
                # Desativa pre-visualização com < >
                formatted_news.append(f"🚀 **{title}**\n{summary}\n🔗 <{link}>")

        if formatted_news:
            header = "🤖 **INTELLIGENCE REPORT: SELECTED AI NEWS**\n\n"
            final_message = header + "\n\n".join(formatted_news)
            
            # Envia em partes se exceder 2000 caracteres
            if len(final_message) > 2000:
                final_message = final_message[:1990] + "..."
                
            requests.post(DISCORD_WEBHOOK, json={"content": final_message})

if __name__ == "__main__":
    run()
