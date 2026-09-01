# -*- coding: utf-8 -*-
import os, json, datetime, requests, time
from email.utils import formatdate

GROQ_KEY = os.environ.get("GROQ_KEY", "")
OR_KEY   = os.environ.get("OPENROUTER_KEY", "")
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")

POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
PAGES_BASE = "https://pavrus-ai.github.io/pavel-gnesyuk-dzen"
TAGS = "#ПавелГнесюк #книги #авторскийблог #писатель"
REPORT = []

def log(msg):
    print(msg, flush=True); REPORT.append(msg)

log("Версия ℹ️ pavel-gnesyuk-dzen v7 (длинные статьи в RSS + тизеры с другими заголовками в TG)")

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
    """ДЛИННАЯ статья 2500-4000 для Дзена/RSS со своим заголовком"""
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
    """ТИЗЕР 800-1000 для Telegram с ДРУГИМ заголовком"""
    t, a, s = book["title"], book["about"], book["series"]
    prompt = (f"Напиши тизер для Telegram-поста о романе Павла Гнесюка «{t}» (серия «{s}»). "
              f"Сюжет: {a}. Требования: 1. ТОЛЬКО русский язык. 2. Первая строка — заголовок ЗАГЛАВНЫМИ, "
              f"без ** и ##, и он ОБЯЗАН отличаться от этого заголовка: «{long_title}». "
              f"3. Текст 800-1000 символов, интригующий, как анонс. 4. Закончи вопросом или крючком, "
              f"чтобы читатель захотел открыть полную статью.")
    txt = ai_text(prompt, minlen=300)
    if not txt:
        log("⚠️ Тизер не создан — беру начало статьи.")
        return None
    return clean_txt(txt)

def esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def tg_post_channel(img_bytes, caption):
    if not TG_TOKEN or not TG_CHANNEL:
        log("⚠️ Нет TELEGRAM_TOKEN/TELEGRAM_CHANNEL — только RSS")
        return
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                      data={"chat_id": TG_CHANNEL, "caption": caption},
                      files={"photo": ("cover.jpg", img_bytes, "image/jpeg")}, timeout=120).json()
    if not r.get("ok"):
        log(f"⚠️ sendPhoto: {str(r)[:100]}")
        return
    log("✅ Тизер опубликован в Telegram-канал")

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
    teaser_title = teaser.split("\n")[0][:150]
    log(f"✂️ Заголовок тизера: {teaser_title}")

    # Тизер в Telegram: до 1024 с учётом ссылки
    link_part = f"\n\n📖 Читайте на ЛитРес: {book['url']}"
    teaser = trim_text(teaser, 1024 - len(link_part))
    caption = teaser + link_part

    # --- Картинка ---
    clean_theme = "".join(c for c in theme if c.isalnum() or c.isspace())[:120].strip()
    p = ("Editorial illustration for russian literary article, "
         + clean_theme + ", artistic dramatic style, cinematic light, no text")
    url = (POLLINATIONS_API + requests.utils.quote(p) + "?nologo=true&seed=" + str(day + 2000000))
    log("Скачивание картинки...")
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    img_bytes = r.content
    os.makedirs("img", exist_ok=True)
    with open(f"img/{day}.jpg", "wb") as f:
        f.write(img_bytes)
    img_url = f"{PAGES_BASE}/img/{day}.jpg"
    log(f"✅ Картинка: img/{day}.jpg ({len(img_bytes)} байт)")

    tg_post_channel(img_bytes, caption)

    # --- RSS: ДЛИННАЯ статья со своим заголовком ---
    body_html = esc(long_text).replace("\n", "<br><br>")
    try:
        posts = json.load(open("posts.json", encoding="utf-8"))
    except Exception:
        posts = []
    posts.insert(0, {
        "guid": f"pavel-gnesyuk-{day}",
        "title": long_title,
        "text_html": body_html,
        "img": img_url,
        "size": len(img_bytes),
        "link": book["url"],
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
  <link>https://dzen.ru/bookpg</link>
  <description>Статьи о романах Павла Гнесюка: сюжет, герои, цитаты, миры и интриги.</description>
  <language>ru</language>
{items}</channel>
</rss>
"""
    open("rss.xml", "w", encoding="utf-8").write(rss)
    log(f"✅ RSS обновлён: статей в ленте: {len(posts)}")
    log("=" * 50)
    log("✅ FINISH: длинная статья → RSS, тизер с другим заголовком → Telegram!")
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        raise
