# -*- coding: utf-8 -*-
import os, json, datetime, requests, time, hashlib, smtplib
from xml.etree.ElementTree import Element, SubElement, tostring, parse
from xml.dom import minidom
from email.mime.text import MIMEText

# --- Настройки окружения ---
GROQ_KEY = os.environ.get("GROQ_KEY", "").strip()
GROQ_KEY2 = os.environ.get("GROQ_KEY2", "").strip()
OR_KEY = os.environ.get("OPENROUTER_KEY", "").strip()
OR_KEY2 = os.environ.get("OPENROUTER_KEY2", "").strip()

SITE_URL = "https://pavrus-ai.github.io/pavel-gnesyuk-dzen"
POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
MAX_RSS_ITEMS = 15

# Настройки SMTP (Яндекс)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.yandex.ru").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
ERROR_EMAIL_TO = os.environ.get("ERROR_EMAIL_TO", "").strip()

def log(msg): 
    print(msg, flush=True)

log("Версия ℹ️ dzen-agent v5 (модели из agent.py + Яндекс SMTP + KEY2)")

# --- Уведомления на почту ---
def send_email(subject, body):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, ERROR_EMAIL_TO]):
        log("⚠️ Настройки SMTP не заданы — пропускаем отправку письма")
        return
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = ERROR_EMAIL_TO
        
        # Для Яндекса используем порт 587 и starttls()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        log(f"✅ Письмо отправлено на {ERROR_EMAIL_TO}")
    except Exception as e:
        log(f"⚠️ Ошибка отправки письма: {e}")

# --- Генерация текста ИИ (модели точно как в agent.py) ---
def ai_groq(prompt, model, key):
    if not key: return None
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "temperature": 0.8, "messages": [{"role": "user", "content": prompt}]},
            timeout=60).json()
        if "error" in r: return None
        return r["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

def ai_openrouter(prompt, model, key):
    if not key: return None
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "HTTP-Referer": "https://github.com"},
            json={"model": model, "temperature": 0.8, "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]},
            timeout=60).json()
        if "error" in r: return None
        return r["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

def ai_call(prompt, minlen=2000):
    # Используем KEY2, если есть, иначе обычные ключи
    g_key = GROQ_KEY2 or GROQ_KEY
    o_key = OR_KEY2 or OR_KEY
    
    # Модели точно как в agent.py
    models = [
        ("groq", "llama-3.3-70b-versatile", g_key),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free", o_key),
        ("openrouter", "google/gemma-3-27b-it:free", o_key),
        ("openrouter", "deepseek/deepseek-chat-v3-0324:free", o_key),
        ("openrouter", "auto", o_key)
    ]
    
    for provider, model, key in models:
        if not key and provider != "groq": # auto может работать без ключа в некоторых случаях, но лучше с ним
            continue
        try:
            log(f"🔄 Попытка: {provider} ({model})...")
            res = ai_groq(prompt, model, key) if provider == "groq" else ai_openrouter(prompt, model, key)
            if res and len(res) >= minlen:
                log(f"✅ Успех: {provider} ({model}), {len(res)} симв.")
                return res
            elif res:
                log(f"⚠️ {provider}: текст короткий ({len(res)} симв., нужно {minlen})")
        except Exception as e:
            log(f"⚠️ {provider} ошибка: {e}")
    
    log("❌ Все попытки генерации ИИ не удались")
    return None

# --- Генерация статьи ---
def generate_dzen_article(book):
    title = book["title"]
    series = book["series"]
    about = book["about"]
    url = book["url"]
    fragments = book.get("fragments", [])
    quote = fragments[0] if fragments else ""

    prompt = (
        f"Напиши развёрнутую статью для Дзена о романе Павла Гнесюка «{title}» (серия «{series}»).\n\n"
        f"ТРЕБОВАНИЯ:\n"
        f"1. ТОЛЬКО русский язык.\n"
        f"2. Длина СТРОГО 2500-4000 символов.\n"
        f"3. Первая строка — заголовок ЗАГЛАВНЫМИ буквами, без ** и ##.\n"
        f"4. Пиши как литературный обозреватель: живо, уникально, без пафоса.\n"
        f"5. Структура: заголовок, введение (2-3 абзаца), основная часть (анализ сюжета/героев/мира, 4-6 абзацев), заключение.\n"
        f"6. В тексте обязательно используй цитату: «{quote[:200]}»\n"
        f"7. В конце обязательно добавь: «Читайте роман «{title}» на ЛитРес: {url}»\n\n"
        f"Сюжет книги: {about[:800]}"
    )

    article = ai_call(prompt, minlen=2000)
    if not article:
        log("⚠️ Не удалось сгенерировать статью")
        send_email(
            "🚨 Ошибка: ИИ не смог создать статью для Дзена",
            f"Книга: {title}\nДата: {datetime.datetime.now()}\nВсе модели вернули ошибку или слишком короткий текст."
        )
        return None

    lines = article.split('\n')
    headline = lines[0].strip().upper() if lines else title.upper()
    content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else article

    return {"title": headline, "content": content, "full_text": article}

# --- Генерация картинки ---
def generate_image(book):
    scene_prompt = (
        f"Photorealistic cinematic scene from Russian fantasy thriller novel: "
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

# --- Сохранение HTML ---
def save_article_html(article, book, day):
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
<body style="font-family:Georgia,serif;background:#141414;color:#eee;margin:0;padding:20px">
    <article style="max-width:800px;margin:0 auto">
        <h1>{article['title']}</h1>
        <img src="{SITE_URL}/{img_filename}" alt="{article['title']}" style="width:100%;border-radius:10px">
        <div style="line-height:1.6">{content_html}</div>
        <p style="margin-top:30px"><a href="{book['url']}" style="color:#7ab8ff">📖 Читать роман на ЛитРес</a></p>
    </article>
</body>
</html>"""

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)

    log(f"✅ Статья сохранена: {filename}")
    return {"url": f"{SITE_URL}/{filename}", "img_url": f"{SITE_URL}/{img_filename}", "slug": slug}

# --- Работа с RSS ---
def load_existing_rss():
    items = []
    if os.path.exists("dzen-rss.xml"):
        try:
            tree = parse("dzen-rss.xml")
            root = tree.getroot()
            channel = root.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    items.append({
                        "title": item.findtext("title", ""),
                        "link": item.findtext("link", ""),
                        "guid": item.findtext("guid", ""),
                        "pub_date": item.findtext("pubDate", ""),
                        "description": item.findtext("description", ""),
                        "content": item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", ""),
                        "img_url": item.find("enclosure").get("url", "") if item.find("enclosure") is not None else ""
                    })
        except Exception as e:
            log(f"⚠️ Ошибка чтения старого RSS: {e}")
    return items

def generate_rss(new_item, existing_items):
    rss = Element('rss', version='2.0')
    rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')

    channel = SubElement(rss, 'channel')
    SubElement(channel, 'title').text = "Павел Гнесюк — Книги и истории"
    SubElement(channel, 'link').text = SITE_URL
    SubElement(channel, 'description').text = "Авторские триллеры: «Хранители» и «Тарские легенды». Глубокие разборы книг."
    SubElement(channel, 'language').text = "ru-ru"

    all_items = ([new_item] + existing_items)[:MAX_RSS_ITEMS]

    for item in all_items:
        entry = SubElement(channel, 'item')
        SubElement(entry, 'title').text = item['title']
        SubElement(entry, 'link').text = item['link']
        g = SubElement(entry, 'guid')
        g.text = item['guid']
        g.set('isPermaLink', 'true')
        SubElement(entry, 'pubDate').text = item['pub_date']
        SubElement(entry, 'description').text = item['description']
        
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

# --- Главная функция ---
def main():
    try:
        books = json.load(open("books.json", encoding="utf-8"))["books"]
    except Exception as e:
        log(f"❌ Ошибка загрузки books.json: {e}")
        send_email("🚨 Критическая ошибка: books.json не найден", str(e))
        return

    day = datetime.date.today().toordinal()
    book = books[day % len(books)]
    log(f"📚 Книга дня: «{book['title']}» ({book['series']})")

    article = generate_dzen_article(book)
    if not article:
        return

    log(f"📝 Статья создана: {len(article['full_text'])} символов")

    try:
        paths = save_article_html(article, book, day)
    except Exception as e:
        log(f"❌ Ошибка сохранения HTML: {e}")
        send_email("🚨 Ошибка сохранения HTML-статьи", str(e))
        return

    img_bytes = generate_image(book)
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

    send_email(
        "✅ Dzen Agent: Статья успешно опубликована",
        f"Книга: {book['title']}\n"
        f"Символов: {len(article['full_text'])}\n"
        f"URL статьи: {paths['url']}\n"
        f"RSS: {SITE_URL}/dzen-rss.xml"
    )

    log("=" * 50)
    log("✅ FINISH: статья и RSS для Дзена готовы!")
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        send_email("🚨 Критический сбой агента Дзена", f"Исключение: {e}")
        raise
