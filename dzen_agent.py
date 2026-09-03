# -*- coding: utf-8 -*-
import os, json, datetime, requests, time, hashlib
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

GROQ_KEY = os.environ.get("GROQ_KEY", "")
OR_KEY   = os.environ.get("OPENROUTER_KEY", "")
SITE_URL = "https://pavrus-ai.github.io/pavel-gnesyuk-dzen"
POLLINATIONS_API = "https://image.pollinations.ai/prompt/"

def log(msg): print(msg, flush=True)
log("Версия ℹ️ dzen-agent v1 (полноценные статьи 3000+ символов)")

def ai_call(prompt, minlen=2500):
    """Генерация длинной статьи для Дзена"""
    attempts = []
    if GROQ_KEY:
        attempts.append(("https://api.groq.com/openai/v1/chat/completions",
                         {"Authorization": f"Bearer {GROQ_KEY}"}, "llama-3.3-70b-versatile"))
    if OR_KEY:
        attempts.append(("https://openrouter.ai/api/v1/chat/completions",
                         {"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "https://github.com"}, 
                         "meta-llama/llama-3.3-70b-instruct:free"))
    
    for url, headers, model in attempts:
        try:
            r = requests.post(url, headers=headers,
                json={"model": model, "temperature": 0.7,
                      "messages": [{"role": "user", "content": prompt}]}, timeout=120).json()
            res = r["choices"][0]["message"]["content"].strip()
            if res and len(res) > minlen:
                log(f"✅ Успех: {model}, {len(res)} симв.")
                return res
        except Exception as e:
            log(f"⚠️ Ошибка {model}: {e}")
    return None

def generate_dzen_article(book):
    """Создание полноценной статьи для Дзена (3000-5000 символов)"""
    title = book["title"]
    series = book["series"]
    about = book["about"]
    fragments = book.get("fragments", [])
    
    # Выбираем случайную цитату
    quote = fragments[0] if fragments else ""
    
    prompt = f"""Напиши полноценную литературную статью для платформы Дзен о романе Павла Гнесюка "{title}" (серия "{series}").

ТРЕБОВАНИЯ:
1. Объём: 3500-5000 символов
2. Структура:
   - Цепляющий заголовок (без кликбейта)
   - Введение (2-3 абзаца): почему эта книга важна, что делает её уникальной
   - Основная часть (5-7 абзацев): 
     * Глубокий анализ сюжета и персонажей
     * Исторические или культурные параллели
     * Что делает эту книгу особенной в жанре
   - Заключение (2-3 абзаца): кому подойдёт книга, какие вопросы поднимает
3. Стиль: живой, увлекательный, но без пафоса
4. Обязательно включи цитату из книги: "{quote[:200]}"
5. Используй информацию о сюжете: {about[:800]}

ВАЖНО: Пиши ТОЛЬКО на русском языке. Статья должна быть уникальной, аналитической, глубокой."""

    article = ai_call(prompt, minlen=3000)
    if not article:
        log("⚠️ Не удалось сгенерировать статью")
        return None
    
    # Извлекаем заголовок (первая строка)
    lines = article.split('\n')
    headline = lines[0].strip().upper() if lines else title.upper()
    
    # Основной текст (без заголовка)
    content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else article
    
    return {
        "title": headline,
        "content": content,
        "full_text": article
    }

def generate_image(article_text, book):
    """Генерация яркой картинки для статьи"""
    scene_prompt = f"Photorealistic cinematic scene from Russian thriller novel: {book['about'][:300]}, bright vivid colors, dramatic daylight composition, people in action seen from behind, sharp focus, high resolution, no text"
    
    seed = int(time.time()) % 1000000
    url = (POLLINATIONS_API + requests.utils.quote(scene_prompt) + 
           f"?nologo=true&seed={seed}&model=flux&width=1280&height=720")
    
    try:
        r = requests.get(url, timeout=240)
        r.raise_for_status()
        return r.content
    except Exception as e:
        log(f"⚠️ Ошибка генерации картинки: {e}")
        return None

def save_article_html(article, book, day):
    """Сохранение статьи как HTML-файл"""
    slug = hashlib.md5(f"{book['title']}-{day}".encode()).hexdigest()[:12]
    filename = f"a/dzen_{slug}.html"
    
    # Создаём папку a/ если нет
    os.makedirs("a", exist_ok=True)
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article['title']}</title>
    <meta name="description" content="{article['content'][:200]}">
    <meta property="og:title" content="{article['title']}">
    <meta property="og:description" content="{article['content'][:200]}">
    <meta property="og:image" content="{SITE_URL}/img/dzen_{slug}.jpg">
    <meta property="og:type" content="article">
</head>
<body>
    <article>
        <h1>{article['title']}</h1>
        <div class="content">
            {article['content'].replace('\n', '<br>')}
        </div>
        <div class="book-info">
            <p><strong>Книга:</strong> {book['title']}</p>
            <p><strong>Серия:</strong> {book['series']}</p>
            <p><a href="{book['url']}">Читать на ЛитРес</a></p>
        </div>
    </article>
</body>
</html>"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    log(f"✅ Статья сохранена: {filename}")
    return f"{SITE_URL}/{filename}"

def generate_rss(articles_list):
    """Генерация RSS-ленты для Дзена"""
    os.makedirs("a", exist_ok=True)
    
    rss = Element('rss', version='2.0')
    rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    
    channel = SubElement(rss, 'channel')
    
    # Основная информация о ленте
    title = SubElement(channel, 'title')
    title.text = "Павел Гнесюк — Книги и истории"
    
    link = SubElement(channel, 'link')
    link.text = SITE_URL
    
    description = SubElement(channel, 'description')
    description.text = "Авторские триллеры и приключения: циклы «Хранители» и «Тарские легенды». Глубокие разборы книг, исторические параллели, анализ сюжетов."
    
    language = SubElement(channel, 'language')
    language.text = "ru-ru"
    
    # Добавляем статьи
    for item in articles_list:
        entry = SubElement(channel, 'item')
        
        # Заголовок
        item_title = SubElement(entry, 'title')
        item_title.text = item['title']
        
        # Ссылка на статью
        item_link = SubElement(entry, 'link')
        item_link.text = item['url']
        
        # GUID (уникальный идентификатор)
        guid = SubElement(entry, 'guid')
        guid.text = item['url']
        guid.set('isPermaLink', 'true')
        
        # Дата публикации
        pub_date = SubElement(entry, 'pubDate')
        pub_date.text = item['date'].strftime("%a, %d %b %Y %H:%M:%S +0300")
        
        # Краткое описание
        desc = SubElement(entry, 'description')
        desc.text = item['content'][:300]
        
        # Полный контент (ОБЯЗАТЕЛЬНО для Дзена!)
        content_encoded = SubElement(entry, 'content:encoded')
        content_encoded.text = f"<![CDATA[{item['content']}]]>"
        
        # Изображение (enclosure)
        if item.get('image'):
            enclosure = SubElement(entry, 'enclosure')
            enclosure.set('url', f"{SITE_URL}/img/{item['image']}")
            enclosure.set('type', 'image/jpeg')
            enclosure.set('length', '0')
    
    # Форматируем XML
    xml_str = minidom.parseString(tostring(rss, encoding='unicode')).toprettyxml(indent="  ")
    
    # Сохраняем
    with open('dzen-rss.xml', 'w', encoding='utf-8') as f:
        f.write(xml_str)
    
    log("✅ RSS-лента сохранена: dzen-rss.xml")

def main():
    # Загружаем книги
    try:
        books = json.load(open("books.json", encoding="utf-8"))["books"]
    except Exception as e:
        log(f"❌ Ошибка загрузки books.json: {e}")
        return
    
    day = datetime.date.today().toordinal()
    book = books[day % len(books)]
    
    log(f"📚 Книга дня: «{book['title']}» ({book['series']})")
    
    # Генерируем статью
    article = generate_dzen_article(book)
    if not article:
        log("❌ Не удалось создать статью")
        return
    
    log(f" Статья создана: {len(article['full_text'])} символов")
    
    # Сохраняем HTML
    url = save_article_html(article, book, day)
    
    # Генерируем и сохраняем картинку
    img_bytes = generate_image(article['full_text'], book)
    if img_bytes:
        os.makedirs("img", exist_ok=True)
        slug = hashlib.md5(f"{book['title']}-{day}".encode()).hexdigest()[:12]
        with open(f"img/dzen_{slug}.jpg", 'wb') as f:
            f.write(img_bytes)
        log(f"✅ Картинка сохранена: img/dzen_{slug}.jpg")
    
    # Загружаем предыдущие статьи для RSS
    articles_list = [{
        "title": article['title'],
        "content": article['content'],
        "url": url,
        "date": datetime.datetime.now(),
        "image": f"dzen_{slug}.jpg" if img_bytes else None
    }]
    
    # Добавляем последние 9 статей из существующих (если есть)
    # (в реальной версии нужно парсить существующие HTML-файлы)
    
    # Генерируем RSS
    generate_rss(articles_list)
    
    log("=" * 50)
    log("✅ FINISH: статья и RSS для Дзена готовы!")
    log(f"📄 RSS: {SITE_URL}/dzen-rss.xml")
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        raise
