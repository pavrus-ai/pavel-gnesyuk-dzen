# -*- coding: utf-8 -*-
import os, json, datetime, requests, time
from email.utils import formatdate

GROQ_KEY = os.environ.get("GROQ_KEY", "")
OR_KEY   = os.environ.get("OPENROUTER_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
MAX_TOKEN = os.environ.get("MAX_TOKEN", "")
MAX_CHAT_ID = os.environ.get("MAX_CHAT_ID", "")

POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
PAGES_BASE = "https://pavrus-ai.github.io/pavel-gnesyuk-dzen"
MAX_API = "https://botapi.max.ru"
TAGS = "#ПавелГнесюк #книги #авторскийблог #писатель"
REPORT = []

def log(msg):
    print(msg, flush=True); REPORT.append(msg)

log("Версия ℹ️ pavel-gnesyuk-dzen v12 (новая картинка каждый запуск + без дублей RSS)")

def _extract(r):
    try: return r["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError): return None

def ai_groq(prompt, model):
    if not GROQ_KEY: return None
    full_prompt = f"{prompt}\n\nВАЖНО: Пиши ТОЛЬКО на русском языке."
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            json={"model": model, "temperature": 0.8,
                  "messages": [{"role": "user", "content": full_prompt}]}, timeout=90).json()
        if "error" in r: return None
        return _extract(r)
    except Exception:
        return None

def ai_openrouter(prompt, model):
    if not OR_KEY: return None
    full_prompt = f"{prompt}\n\nВАЖНО: Пиши ТОЛЬКО на русском языке."
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "https://github.com"},
            json={"model": model, "temperature": 0.8,
                  "messages": [{"role": "user", "content": full_prompt}]}, timeout=90).json()
        if "error" in r: return None
        return _extract(r)
    except Exception:
        return None

def ai_text(prompt, minlen=600):
    models = [
        ("groq", "llama-3.3-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter", "google/gemma-3-27b-it:free"),
        ("openrouter", "deepseek/deepseek-chat-v3-0324:free"),
        ("openrouter", "auto")
    ]
    for provider, model in models:
        try:
            res = ai_groq(prompt, model) if provider == "groq" else ai_openrouter(prompt, model)
            if res and len(res) > minlen:
                log(f"✅ Успех: {provider} ({model}), {len(res)} симв.")
                return res
        except Exception:
            pass
    return None

def clean_txt(t):
    return t.replace("**","").replace("##","").strip()

def trim_text(t, limit):
    if len(t) <= limit: return t
    c = t[:limit]
    i = max(c.rfind("."), c.rfind("!"), c.rfind("?"), c.rfind("\n"))
    return (c[:i+1] if i > limit//2 else c).rstrip()

def build_long_article(book, mode, day):
    t, a, u, s = book["title"], book["about"], book["url"], book["series"]
    base = (f"Напиши развёрнутую статью для Дзена о романе Павла Гнесюка «{t}» (серия «{s}»). "
            f"Текст ПОЛНОСТЬЮ уникальный, живой, как литературный блог. "
            f"Требования: 1. ТОЛЬКО русский язык. 2. Длина СТРОГО 2500-4000 символов. "
            f"3. Первая строка — заголовок ЗАГЛАВНЫМИ буквами, без ** и ##. "
            f"4. Не пиши «как я писал книгу» — пиши как литературный обозреватель. "
            f"5. В конце обязательно: «Читайте роман «{t}» на ЛитРес: {u}». ")
    if mode == "quote" and book.get("fragments"):
        fr = book["fragments"][day % len(book["fragments"])]
        prompt = (base + f"Тип: РАЗБОР ЦИТАТЫ. Цитата: «{fr}» — раскрой смысл, атмосферу, связь с сюжетом ({a}). 4-6 абзацев.")
        theme = f"dramatic scene from novel: {fr[:80]}"
    elif mode == "hero":
        prompt = (base + f"Тип: ГЕРОИ. Характеры, мотивы, внутренний конфликт героев. Сюжет: {a}. 4-6 абзацев.")
        theme = f"portrait of the novel protagonist, {a[:80]}"
    elif mode == "plot":
        prompt = (base + f"Тип: СЮЖЕТ. Завязка и развитие интриги БЕЗ спойлеров концовки. Сюжет: {a}. 4-6 абзацев.")
        theme = f"adventure plot scene, {a[:80]}"
    elif mode == "world":
        prompt = (base + f"Тип: МИР КНИГИ. Вселенная, атмосфера, правила мира серии «{s}». Сюжет: {a}. 4-6 абзацев.")
        theme = f"fantasy world landscape of the novel series, {a[:80]}"
    else:
        prompt = (base + f"Тип: ИНТРИГА. Тайны, вопросы, повороты (без спойлеров), сильный призыв в конце. Сюжет: {a}. 4-6 абзацев.")
        theme = f"mysterious intrigue scene with hidden clues, {a[:80]}"
    txt = ai_text(prompt, minlen=1500)
    if not txt:
        log("⚠️ ИИ недоступны. Стандартная длинная статья.")
        txt = (f"РОМАН «{t.upper()}»: ИСТОРИЯ, КОТОРАЯ ЗАТЯГИВАЕТ\n\n{a}\n\n"
               f"Роман «{t}» из серии «{s}» — захватывающее путешествие, полное тайн и неожиданных поворотов. "
               f"Герои, которым сопереживаешь, мир, в который веришь, и интрига, которая не отпускает до последней страницы. "
               f"Каждая глава добавляет новые вопросы, а ответы оказываются совсем не такими, как ждёшь.\n\n"
               f"Читайте роман «{t}» на ЛитРес: {u}")
    return clean_txt(txt) + f"\n\n{TAGS}", theme

def build_teaser(book, long_title):
    t, a, s = book["title"], book["about"], book["series"]
    prompt = (f"Напиши тизер для поста о романе Павла Гнесюка «{t}» (серия «{s}»). "
              f"Сюжет: {a}. Требования: 1. ТОЛЬКО русский язык. 2. Первая строка — заголовок ЗАГЛАВНЫМИ, "
              f"без ** и ##, и он ОБЯЗАН отличаться от этого заголовка: «{long_title}». "
              f"3. Текст 800-1000 символов, интригующий, как анонс. 4. Закончи вопросом или крючком.")
    txt = ai_text(prompt, minlen=300)
    if not txt:
        log("⚠️ Тизер не создан — беру начало статьи.")
        return None
    return clean_txt(txt)

def esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def tg_post_channel(img_bytes, caption):
    if not TG_TOKEN or not TG_CHANNEL:
        log("⚠️ Нет TELEGRAM_TOKEN/TELEGRAM_CHANNEL — пропуск Telegram")
        return
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                      data={"chat_id": TG_CHANNEL, "caption": caption},
                      files={"photo": ("cover.jpg", img_bytes, "image/jpeg")}, timeout=120).json()
    if not r.get("ok"):
        log(f"⚠️ TG sendPhoto: {str(r)[:100]}")
        return
    log("✅ Тизер опубликован в Telegram-канал")

def max_api(path, payload=None):
    """Пробует все способы авторизации MAX"""
    variants = [
        {"Authorization": f"Bearer {MAX_TOKEN}"},
        {"Authorization": MAX_TOKEN},
        {},
    ]
    for i, headers in enumerate(variants):
        try:
            if payload is not None:
                r = requests.post(f"{MAX_API}{path}", headers=headers, json=payload, timeout=30)
            else:
                r = requests.get(f"{MAX_API}{path}", headers=headers, timeout=30)
            j = r.json()
            if r.status_code == 200 and j.get("code") != "verify.token":
                log(f"✅ MAX: авторизация вариант {i+1} работает")
                return j
        except Exception:
            pass
    try:
        if payload is not None:
            r = requests.post(f"{MAX_API}{path}?token={MAX_TOKEN}", json=payload, timeout=30)
        else:
            r = requests.get(f"{MAX_API}{path}?token={MAX_TOKEN}", timeout=30)
        j = r.json()
        if j.get("code") != "verify.token":
            log("✅ MAX: авторизация через ?token= работает")
            return j
        log(f"⚠️ MAX: токен отклонён всеми способами: {str(j)[:150]}")
    except Exception as e:
        log(f"⚠️ MAX: {e}")
    return None

def max_post_channel(img_bytes, caption):
    """Публикация в канал мессенджера MAX"""
    if not MAX_TOKEN:
        log("⚠️ Нет MAX_TOKEN — пропуск MAX")
        return
    if not MAX_CHAT_ID:
        chats = max_api("/chats")
        log(f"ℹ️ MAX: список чатов (ищем chat_id канала): {str(chats)[:500]}")
        return
    att = None
    up = max_api("/uploads", {"type": "image"})
    if up:
        up_url = up.get("url") or up.get("uploadUrl")
        up_token = up.get("token") or up.get("photoId")
        if up_url and up_token:
            try:
                requests.post(up_url, files={"file": ("cover.jpg", img_bytes, "image/jpeg")}, timeout=120)
                att = [{"type": "image", "payload": {"token": up_token}}]
                log("✅ MAX: картинка загружена")
            except Exception as e:
                log(f"⚠️ MAX upload: {e}")
    body = {"chat_id": MAX_CHAT_ID, "text": caption}
    if att:
        body["attachments"] = att
    res = max_api("/messages", body)
    log(f"✅ MAX: ответ отправки: {str(res)[:150]}")

def build_article_page(title, img_url, body_html, litres_url):
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta property="og:image" content="{img_url}">
</head>
<body style="font-family:Georgia,serif;background:#141414;color:#eee;margin:0;padding:20px">
<article style="max-width:800px;margin:0 auto">
<h1>{title}</h1>
<img src="{img_url}" style="width:100%;border-radius:10px">
<div>{body_html}</div>
<p><a href="{litres_url}" style="color:#7ab8ff">📖 Читать роман на ЛитРес</a></p>
</article>
</body>
</html>"""

def build_index(posts, meta):
    cards = ""
    for it in posts[:30]:
        cards += f'<a class="card" href="{it["link"]}" target="_blank"><img src="{it["img"]}" alt=""><h3>{it["title"]}</h3></a>\n'
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Павел Гнесюк — литературный блог</title>
<meta name="description" content="Статьи о романах Павла Гнесюка: Хранители и Тарские легенды.">
{meta}
<style>
body{{font-family:Georgia,serif;background:#141414;color:#eee;margin:0}}
header{{padding:40px 20px;text-align:center;background:#1e1e1e}}
h1{{margin:0 0 8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:20px;padding:20px;max-width:1100px;margin:0 auto}}
.card{{background:#1e1e1e;border-radius:10px;overflow:hidden;text-decoration:none;color:#eee}}
.card img{{width:100%;height:150px;object-fit:cover}}
.card h3{{font-size:15px;padding:12px;margin:0}}
</style>
</head>
<body>
<header><h1>Павел Гнесюк — литературный блог</h1>
<p>Романы «Хранители» и «Тарские легенды»: статьи, разборы, цитаты</p></header>
<div class="grid">{cards}</div>
</body>
</html>"""

def main():
    books = json.load(open("books.json", encoding="utf-8"))["books"]
    day = datetime.date.today().toordinal()
    book = books[day % len(books)]
    modes = ["plot", "hero", "quote", "world", "intrigue"]
    mode = modes[day % len(modes)]
    if mode == "quote" and not book.get("fragments"):
        mode = "plot"
    log(f"📚 Книга дня: «{book['title']}» ({book['series']}) | Тип: {mode}")

    long_text, theme = build_long_article(book, mode, day)
    long_title = long_text.split("\n")[0][:150]
    log(f"📰 Заголовок статьи: {long_title}")

    teaser = build_teaser(book, long_title)
    if teaser is None:
        teaser = trim_text(long_text, 950)
    log(f"✂️ Заголовок тизера: {teaser.split(chr(10))[0][:150]}")

    link_part = f"\n\n📖 Читайте на ЛитРес: {book['url']}"
    teaser = trim_text(teaser, 1024 - len(link_part))
    caption = teaser + link_part

    # --- Картинка (новая при каждом запуске) ---
    clean_theme = "".join(c for c in theme if c.isalnum() or c.isspace())[:120].strip()
    p = ("Editorial illustration for russian literary article, "
         + clean_theme + ", artistic dramatic style, cinematic light, no text")
    run_no = int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    seed = day + 2000000 + (run_no % 100)
    url = (POLLINATIONS_API + requests.utils.quote(p) + f"?nologo=true&seed={seed}")
    log("Скачивание картинки...")
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    img_bytes = r.content
    os.makedirs("img", exist_ok=True)
    with open(f"img/{day}.jpg", "wb") as f:
        f.write(img_bytes)
    img_url = f"{PAGES_BASE}/img/{day}.jpg"
    log(f"✅ Картинка: img/{day}.jpg ({len(img_bytes)} байт)")

    # --- Публикации в мессенджеры ---
    tg_post_channel(img_bytes, caption)
    max_post_channel(img_bytes, caption)

    # --- Страница статьи на своём сайте ---
    body_html = esc(long_text).replace("\n", "<br><br>")
    os.makedirs("a", exist_ok=True)
    page_path = f"a/{day}.html"
    open(page_path, "w", encoding="utf-8").write(build_article_page(long_title, img_url, body_html, book["url"]))
    page_url = f"{PAGES_BASE}/a/{day}.html"
    log(f"✅ Страница статьи: {page_path}")

    # --- RSS + index.html ---
    meta = ""
    if os.path.exists("dzen_meta.txt"):
        meta = open("dzen_meta.txt", encoding="utf-8").read().strip()
    try:
        posts = json.load(open("posts.json", encoding="utf-8"))
    except Exception:
        posts = []
    posts = [p for p in posts if p["guid"] != f"pavel-gnesyuk-{day}"]
    posts.insert(0, {
        "guid": f"pavel-gnesyuk-{day}",
        "title": long_title,
        "text_html": body_html,
        "img": img_url,
        "size": len(img_bytes),
        "link": page_url,
        "pubdate": formatdate(time.time(), usegmt=True)
    })
    posts = posts[:30]
    json.dump(posts, open("posts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    items = ""
    for it in posts:
        items += f"""  <item>
    <title>{esc(it['title'])}</title>
    <link>{it['link']}</link>
    <guid isPermaLink="false">{it['guid']}</guid>
    <pubDate>{it['pubdate']}</pubDate>
    <description><![CDATA[<img src="{it['img']}" width="1200"><br><br>{it['text_html']}]]></description>
    <media:content url="{it['img']}" type="image/jpeg" medium="image"/>
    <enclosure url="{it['img']}" type="image/jpeg" length="{it['size']}"/>
  </item>
"""
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>Павел Гнесюк — литературный блог</title>
  <link>https://pavrus-ai.github.io/pavel-gnesyuk-dzen/</link>
  <description>Статьи о романах Павла Гнесюка: сюжет, герои, цитаты, миры и интриги.</description>
  <language>ru</language>
{items}</channel>
</rss>
"""
    open("rss.xml", "w", encoding="utf-8").write(rss)
    open("index.html", "w", encoding="utf-8").write(build_index(posts, meta))
    log(f"✅ RSS обновлён: статей в ленте: {len(posts)}")
    log("✅ index.html обновлён (витрина статей)")
    log("=" * 50)
    log("✅ FINISH: статья → RSS+сайт, тизер → Telegram и MAX!")
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        raise
