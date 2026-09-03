# -*- coding: utf-8 -*-
import os, json, datetime, requests, time, hashlib
from xml.etree.ElementTree import Element, SubElement, tostring, parse
from xml.dom import minidom

GROQ_KEY = os.environ.get("GROQ_KEY", "")
OR_KEY   = os.environ.get("OPENROUTER_KEY", "")
SITE_URL = "https://pavrus-ai.github.io/pavel-gnesyuk-dzen"
POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
MAX_RSS_ITEMS = 10

def log(msg): print(msg, flush=True)
log("Версия ℹ️ dzen-agent v3 (полноценные статьи 3000+ символов, RSS с guid)")

def ai_call(prompt, minlen=2000):
    """Генерация длинной статьи для Дзена (используем GROQ_KEY2 и OPENROUTER_KEY2)"""
    attempts = []
    
    # Используем ВТОРЫЕ токены для Дзена
    GROQ_KEY2 = os.environ.get("GROQ_KEY2", "")
    OR_KEY2 = os.environ.get("OPENROUTER_KEY2", "")
    
    if GROQ_KEY2:
        attempts.append((
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {GROQ_KEY2}"},
            "llama-3.3-70b-versatile",
            "Groq (Key2)"
        ))
    
    if OR_KEY2:
        attempts.append((
            "https://openrouter.ai/api/v1/chat/completions",
            {"Authorization": f"Bearer {OR_KEY2}", "HTTP-Referer": "https://github.com"},
            "meta-llama/llama-3.3-70b-instruct:free",
            "OpenRouter (Llama 3.3 Key2)"
        ))
        attempts.append((
            "https://openrouter.ai/api/v1/chat/completions",
            {"Authorization": f"Bearer {OR_KEY2}", "HTTP-Referer": "https://github.com"},
            "google/gemma-3-27b-it:free",
            "OpenRouter (Gemma 3 Key2)"
        ))
        attempts.append((
            "https://openrouter.ai/api/v1/chat/completions",
            {"Authorization": f"Bearer {OR_KEY2}", "HTTP-Referer": "https://github.com"},
            "deepseek/deepseek-chat-v3-0324:free",
            "OpenRouter (DeepSeek Key2)"
        ))
    
    for url, headers, model, provider_name in attempts:
        try:
            log(f"🔄 Попытка через {provider_name} ({model})...")
            
            payload = {
                "model": model,
                "temperature": 0.8,
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if r.status_code != 200:
                log(f"⚠️ {provider_name} код {r.status_code}: {r.text[:200]}")
                continue
            
            data = r.json()
            
            if "choices" not in data or not data["choices"]:
                log(f"️ {provider_name}: нет choices")
                continue
            
            res = data["choices"][0]["message"]["content"].strip()
            
            if res and len(res) > minlen:
                log(f"✅ Успех: {provider_name}, {len(res)} симв.")
                return res
            else:
                log(f"⚠️ {provider_name}: короткий текст ({len(res)} симв.)")
                
        except Exception as e:
            log(f"⚠️ {provider_name}: {e}")
    
    log("❌ Все попытки генерации не удались")
    return None

def generate_dzen_article(book):
    """Создание полноценной статьи для Дзена (2000-4000 символов)"""
    title = book["title"]
    series = book["series"]
    about = book["about"]
    fragments = book.get("fragments", [])
    quote = fragments[0] if fragments else ""

    prompt = (
        f"Напиши полноценную литературную статью для платформы Дзен о романе Павла Гнесюка "
        f"«{title}» (серия «{series}»).\n\n"
        f"ТРЕБОВАНИЯ:\n"
        f"1. Объём: 2500-4000 символов\n"
        f"2. Структура:\n"
        f"   - Цепляющий заголовок (без кликбейта, 8-12 слов)\n"
        f"   - Введение (2-3 абзаца): почему эта книга важна, что делает её уникальной\n"
        f"   - Основная часть (5-7 абзацев): глубокий анализ сюжета и персонажей, "
        f"исторические или культурные параллели, что делает эту книгу особенной в жанре\n"
        f"   - Заключение (2-3 абзаца): кому подойдёт книга, какие вопросы поднимает\n"
        f"3. Стиль: живой, увлекательный, но без пафоса\n"
        f"4. Обязательно включи цитату из книги: «{quote[:200]}»\n"
        f"5. Используй информацию о сюжете: {about[:800]}\n\n"
        f"ВАЖНО: Пиши ТОЛЬКО на русском языке. Статья должна быть уникальной, аналитической, глубокой."
    )

    article = ai_call(prompt, minlen=2000)
    if not article:
        log("⚠️ Не удалось сгенерировать статью")
        return None

    lines = article.split('\n')
    headline = lines[0].strip().upper() if lines else title.upper()
    content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else article

    return {"title": headline, "content": content, "full_text": article}

def generate_image(article_text, book):
    """Генерация яркой картинки для статьи"""
    scene_prompt = (
        f"Photorealistic cinematic scene from Russian thriller novel: "
        f"{book['about'][:300]}, bright vivid colors, dramatic daylight composition, "
        f"people in action seen from behind, sharp focus, high resolution, no text"
    )
    seed = int(time.time()) % 1000000
    url = POLLINATIONS_API + requests.utils.quote(scene_prompt) + \
          f"?nologo=true&seed={seed}&model=flux&width=1280&height=720"
    try:
        r = requests.get(url, timeout=240)
        r.raise_for_status()
        return r.content
    except Exception as e:
        log(f"⚠️ Ошибка генерации картинки: {e}")
        return None

def save_article_html(article, book, day):
    """Сохранение статьи как HTML-файл с постоянным URL"""
    slug = hashlib.md5(f"{book['title']}-{day}".encode()).hexdigest()[:12]
    filename = f"a/dzen_{slug}.html"
    img_filename = f"img/dzen_{slug}.jpg"

    os.makedirs("a", exist_ok=True)
    os.makedirs("img", exist_ok=True)

    content_escaped = article['content'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    content_html = content_escaped.replace('\n', '<br>\n')

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{article['title']}</title>
    <meta name="description" content="{article['content'][:200]}">
    <meta property="og:title" content="{article['title']}">
    <meta property="og:description" content="{article['content'][:200]}">
    <meta property="og:image" content="{SITE_URL}/{img_filename}">
    <meta property="og:type" content="article">
</head>
<body>
    <article>
        <h1>{article['title']}</h1>
        <img src="{SITE_URL}/{img_filename}" alt="{article['title']}" style="max-width:100%;height:auto;">
        <div class="content">
            {content_html}
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
    return {
        "url": f"{SITE_URL}/{filename}",
        "img_url": f"{SITE_URL}/{img_filename}",
        "slug": slug
    }

def load_existing_rss():
    """Загружает существующие статьи из dzen-rss.xml"""
    items = []
    if os.path.exists("dzen-rss.xml"):
        try:
            tree = parse("dzen-rss.xml")
            root = tree.getroot()
            channel = root.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    guid = item.findtext("guid", "")
                    pub_date = item.findtext("pubDate", "")
                    desc = item.findtext("description", "")
                    content_enc = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", "")
                    enclosure = item.find("enclosure")
                    img_url = enclosure.get("url", "") if enclosure is not None else ""
                    items.append({
                        "title": title, "link": link, "guid": guid,
                        "pub_date": pub_date, "description": desc,
                        "content": content_enc, "img_url": img_url
                    })
        except Exception as e:
            log(f"️ Ошибка чтения старого RSS: {e}")
    return items

def generate_rss(new_item, existing_items):
    """Генерация RSS-ленты для Дзена с правильными тегами"""
    os.makedirs("a", exist_ok=True)

    rss = Element('rss', version='2.0')
    rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')

    channel = SubElement(rss, 'channel')

    title_el = SubElement(channel, 'title')
    title_el.text = "Павел Гнесюк — Книги и истории"

    link_el = SubElement(channel, 'link')
    link_el.text = SITE_URL

    desc_el = SubElement(channel, 'description')
    desc_el.text = "Авторские триллеры и приключения: циклы «Хранители» и «Тарские легенды». Глубокие разборы книг, исторические параллели, анализ сюжетов."

    lang_el = SubElement(channel, 'language')
    lang_el.text = "ru-ru"

    all_items = [new_item] + existing_items
    all_items = all_items[:MAX_RSS_ITEMS]

    for item in all_items:
        entry = SubElement(channel, 'item')

        t = SubElement(entry, 'title')
        t.text = item['title']

        l = SubElement(entry, 'link')
        l.text = item['link']

        g = SubElement(entry, 'guid')
        g.text = item['guid']
        g.set('isPermaLink', 'true')

        pd = SubElement(entry, 'pubDate')
        pd.text = item['pub_date']

        d = SubElement(entry, 'description')
        d.text = item['description']

        ce = SubElement(entry, '{http://purl.org/rss/1.0/modules/content/}encoded')
        ce.text = f"<![CDATA[{item['content']}]]>"

        if item.get('img_url'):
            enc = SubElement(entry, 'enclosure')
            enc.set('url', item['img_url'])
            enc.set('type', 'image/jpeg')
            enc.set('length', '0')

    xml_str = minidom.parseString(tostring(rss, encoding='unicode')).toprettyxml(indent="  ")
    with open('dzen-rss.xml', 'w', encoding='utf-8') as f:
        f.write(xml_str)

    log("✅ RSS-лента сохранена: dzen-rss.xml")

def main():
    try:
        books = json.load(open("books.json", encoding="utf-8"))["books"]
    except Exception as e:
        log(f"❌ Ошибка загрузки books.json: {e}")
        return

    day = datetime.date.today().toordinal()
    book = books[day % len(books)]
    log(f"📚 Книга дня: «{book['title']}» ({book['series']})")

    article = generate_dzen_article(book)
    if not article:
        log("❌ Не удалось создать статью")
        return

    log(f"📝 Статья создана: {len(article['full_text'])} символов")

    paths = save_article_html(article, book, day)

    img_bytes = generate_image(article['full_text'], book)
    if img_bytes:
        img_path = f"img/dzen_{paths['slug']}.jpg"
        with open(img_path, 'wb') as f:
            f.write(img_bytes)
        log(f"✅ Картинка сохранена: {img_path}")

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0300")

    new_item = {
        "title": article['title'],
        "link": paths['url'],
        "guid": paths['url'],
        "pub_date": pub_date,
        "description": article['content'][:300],
        "content": article['content'],
        "img_url": paths['img_url'] if img_bytes else ""
    }

    existing = load_existing_rss()
    generate_rss(new_item, existing)

    log("=" * 50)
    log("✅ FINISH: статья и RSS для Дзена готовы!")
    log(f" RSS: {SITE_URL}/dzen-rss.xml")
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        raise
