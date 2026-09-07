# -*- coding: utf-8 -*-
import os, json, datetime, requests, time, glob, urllib3
from email.utils import formatdate, parsedate_to_datetime
urllib3.disable_warnings()

GROQ_KEY = os.environ.get("GROQ_KEY", "").strip()
OR_KEY   = os.environ.get("OPENROUTER_KEY", "").strip()
GROQ_KEY_T = os.environ.get("GROQ_KEY_TEASER", "").strip() or GROQ_KEY
OR_KEY_T   = os.environ.get("OPENROUTER_KEY_TEASER", "").strip() or OR_KEY

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TG_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "").strip()
MAX_TOKEN = os.environ.get("MAX_TOKEN", "").strip()
MAX_CHAT_ID = os.environ.get("MAX_CHAT_ID", "").strip()

POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
PAGES_BASE = "https://pavrus-ai.github.io/pavel-gnesyuk-dzen"
MAX_HOSTS = ["https://botapi.max.ru", "https://platform-api2.max.ru"]
TAGS = "#ПавелГнесюк #книги #авторскийблог #писатель"
RU = "\n\nВАЖНО: Пиши ТОЛЬКО на русском языке."
MIN_DZEN_ITEMS = 10
REPORT = []
MAX_HEADERS = {}

def log(msg):
    print(msg, flush=True); REPORT.append(msg)

log("Версия ℹ️ pavel-gnesyuk-dzen v24 (RSS под требования Дзена: content:encoded, ЧПУ, без капса и внешних ссылок, авто-добор до 10)")

def _extract(r):
    try: return r["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError): return None

def ai_groq(prompt, model, key, suffix=RU):
    if not key: return None
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "temperature": 0.8,
                  "messages": [{"role": "user", "content": prompt + suffix}]}, timeout=45).json()
        if "error" in r: return None
        return _extract(r)
    except Exception:
        return None

def ai_openrouter(prompt, model, key, suffix=RU):
    if not key: return None
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "HTTP-Referer": "https://github.com"},
            json={"model": model, "temperature": 0.8,
                  "messages": [{"role": "user", "content": prompt + suffix}]}, timeout=45).json()
        if "error" in r: return None
        return _extract(r)
    except Exception:
        return None

def ai_text(prompt, minlen=600):
    models = [
        ("groq", "llama-3.3-70b-versatile", GROQ_KEY_T),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free", OR_KEY_T),
        ("openrouter", "google/gemma-3-27b-it:free", OR_KEY_T),
        ("openrouter", "deepseek/deepseek-chat-v3-0324:free", OR_KEY_T),
        ("openrouter", "auto", OR_KEY_T)
    ]
    for provider, model, key in models:
        if not key: continue
        try:
            res = ai_groq(prompt, model, key) if provider == "groq" else ai_openrouter(prompt, model, key)
            if res and len(res) > minlen:
                log(f"✅ Успех: {provider} ({model}), {len(res)} симв.")
                return res
        except Exception:
            pass
    return None

def ai_scene(prompt):
    models = [
        ("groq", "llama-3.3-70b-versatile", GROQ_KEY_T),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free", OR_KEY_T),
        ("openrouter", "google/gemma-3-27b-it:free", OR_KEY_T),
        ("openrouter", "deepseek/deepseek-chat-v3-0324:free", OR_KEY_T),
        ("openrouter", "auto", OR_KEY_T)
    ]
    for provider, model, key in models:
        if not key: continue
        try:
            res = ai_groq(prompt, model, key, suffix="") if provider == "groq" else ai_openrouter(prompt, model, key, suffix="")
            if res and len(res) > 15:
                return res.split("\n")[0].strip().strip('"')[:300]
        except Exception:
            pass
    return None

def clean_txt(t):
    return t.replace("**", "").replace("##", "").strip()

def trim_text(t, limit):
    if len(t) <= limit: return t
    c = t[:limit]
    i = max(c.rfind("."), c.rfind("!"), c.rfind("?"), c.rfind("\n"))
    return (c[:i+1] if i > limit//2 else c).rstrip()

# ============================================================
# САНИТАЙЗЕРЫ ПОД ТРЕБОВАНИЯ ДЗЕНА
# ============================================================

def fix_title(t):
    """КАПС-заголовок -> обычное предложение (Дзен не любит капс)."""
    t = t.strip()
    if not t.isupper():
        return t
    out, done = [], False
    for ch in t:
        if not done and ch.isalpha():
            out.append(ch.upper()); done = True
        else:
            out.append(ch.lower())
    return "".join(out)

def strip_promo(text):
    """Убирает из тела статьи ссылки на ЛитРес и хэштеги (внешняя реклама в контенте)."""
    parts = text.replace("<br><br>", "\n\n").split("\n\n")
    keep = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if "litres.ru" in p or "литрес" in p.lower():
            continue
        if p.startswith("#") and " " not in p.strip("#"):
            continue
        if p.count("#") >= 2 and p.replace("#", "").replace(" ", "") .isalnum() and len(p) < 120 and p.startswith("#"):
            continue
        keep.append(p)
    return keep

def to_content_html(text, img_url):
    """Полный текст статьи в разрешённом Дзеном HTML: figure + p."""
    paras = strip_promo(text)
    if not paras:
        paras = [text[:500]]
    body = ""
    if img_url:
        body += f'<figure><img src="{img_url}"></figure>\n'
    for p in paras:
        p = p.replace("**", "").replace("##", "")
        body += f"<p>{p}</p>\n"
    return body

def to_plain(text, limit=250):
    txt = " ".join(strip_promo(text))
    txt = txt.replace("**", "").replace("##", "")
    return txt[:limit].rstrip() + ("…" if len(txt) > limit else "")

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ============================================================
# САМОДИАГНОСТИКА МЕССЕНДЖЕРОВ
# ============================================================

def tg_check():
    if not TG_TOKEN or not TG_CHANNEL:
        log("⚠️ DIAG: TELEGRAM_TOKEN или TELEGRAM_CHANNEL не заданы в env воркфлоу!")
        return False
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=30).json()
        if not r.get("ok"):
            log(f"⚠️ DIAG: TG токен недействителен: {str(r)[:150]}")
            return False
        log(f"✅ DIAG: TG токен рабочий, бот @{r['result'].get('username')}")
    except Exception as e:
        log(f"⚠️ DIAG: TG getMe ошибка сети: {e}")
        return False
    if not (TG_CHANNEL.startswith("@") or TG_CHANNEL.startswith("-100")):
        log(f"⚠️ DIAG: TELEGRAM_CHANNEL='{TG_CHANNEL}' похож на ошибку: нужно '@имя' или '-100…'")
    return True

def max_check():
    global MAX_HEADERS
    if not MAX_TOKEN:
        log("⚠️ DIAG: MAX_TOKEN не задан в env воркфлоу!")
        return False
    for style in ("plain", "bearer"):
        headers = {"Authorization": MAX_TOKEN} if style == "plain" else {"Authorization": f"Bearer {MAX_TOKEN}"}
        for host in MAX_HOSTS:
            try:
                r = requests.get(host + "/me", headers=headers, timeout=30, verify=False)
                j = r.json()
                if r.status_code == 200 and not j.get("code"):
                    MAX_HEADERS = headers
                    log(f"✅ DIAG: MAX токен рабочий (auth={style}, host={host})")
                    return True
            except Exception:
                continue
    log("⚠️ DIAG: MAX /me не ответил ни с обычным токеном, ни с Bearer — проверьте MAX_TOKEN")
    return False

# ============================================================
# ТЕКСТЫ
# ============================================================

def build_long_article(book, mode, day):
    t, a, u, s = book["title"], book["about"], book["url"], book["series"]
    base = (f"Напиши развёрнутую статью для Дзена о романе Павла Гнесюка «{t}» (серия «{s}»). "
            f"Текст ПОЛНОСТЬЮ уникальный, живой, как литературный блог. "
            f"Требования: 1. ТОЛЬКО русский язык. 2. Длина СТРОГО 2500-4000 символов. "
            f"3. Первая строка — заголовок ОБЫЧНЫМИ буквами (только первое слово с заглавной), без ** и ##, БЕЗ капса. "
            f"4. Не пиши «как я писал книгу» — пиши как литературный обозреватель. "
            f"5. Никаких внешних ссылок в тексте. ")
    if mode == "quote" and book.get("fragments"):
        fr = book["fragments"][day % len(book["fragments"])]
        prompt = (base + f"Тип: РАЗБОР ЦИТАТЫ. Цитата: «{fr}» — раскрой смысл, атмосферу, связь с сюжетом ({a}). 4-6 абзацев.")
        theme = f"dramatic symbolic scene with ancient flame and golden light: {fr[:60]}"
    elif mode == "hero":
        prompt = (base + f"Тип: ГЕРОИ. Характеры, мотивы, внутренний конфликт героев. Сюжет: {a}. 4-6 абзацев.")
        theme = f"ancient sword and dark cloak on sunlit stone altar, {a[:60]}"
    elif mode == "plot":
        prompt = (base + f"Тип: СЮЖЕТ. Завязка и развитие интриги БЕЗ спойлеров концовки. Сюжет: {a}. 4-6 абзацев.")
        theme = f"sunlit mountain path leading to shining ancient fortress, {a[:60]}"
    elif mode == "world":
        prompt = (base + f"Тип: МИР КНИГИ. Вселенная, атмосфера, правила мира серии «{s}». Сюжет: {a}. 4-6 абзацев.")
        theme = f"epic fantasy landscape with golden sky and ancient ruins, {a[:60]}"
    else:
        prompt = (base + f"Тип: ИНТРИГА. Тайны, вопросы, повороты (без спойлеров), сильный призыв в конце. Сюжет: {a}. 4-6 абзацев.")
        theme = f"warm candlelit desk with old map and shining artifacts, {a[:60]}"
    txt = ai_text(prompt, minlen=1500)
    if not txt:
        log("⚠️ ИИ недоступны. Стандартная длинная статья.")
        txt = (f"Роман «{t}»: история, которая затягивает\n\n{a}\n\n"
               f"Роман «{t}» из серии «{s}» — захватывающее путешествие, полное тайн и неожиданных поворотов. "
               f"Герои, которым сопереживаешь, мир, в который веришь, и интрига, которая не отпускает до последней страницы. "
               f"Каждая глава добавляет новые вопросы, а ответы оказываются совсем не такими, как ждёшь.")
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

def build_scene(teaser_text):
    prompt = (f"По этому тексту придумай ОДНУ динамичную сцену для иллюстрации. "
              f"Верни ТОЛЬКО одно предложение на АНГЛИЙСКОМ (15-25 слов): кто и что делает в кадре, "
              f"где происходит, атмосфера и свет. Люди — в действии, в полный рост, НЕ портрет. "
              f"Сцена должна быть СВЕТЛОЙ и КРАСОЧНОЙ: дневной или тёплый золотой свет, яркие цвета, "
              f"никакого тёмного мрачного фэнтези. "
              f"Текст: {teaser_text[:900]}")
    scene = ai_scene(prompt)
    if scene:
        log(f"🎨 Сцена для картинки: {scene[:120]}")
    return scene

# ============================================================
# ПУБЛИКАЦИЯ: TELEGRAM / MAX
# ============================================================

def tg_post_channel(img_bytes, caption):
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
        data={"chat_id": TG_CHANNEL, "caption": caption},
        files={"photo": ("cover.jpg", img_bytes, "image/jpeg")}, timeout=120).json()
    if not r.get("ok"):
        log(f"⚠️ TG sendPhoto ошибка: {str(r)[:200]}")
        return
    log("✅ Тизер опубликован в Telegram-канал")

def max_api(path, payload=None, params=None):
    errs = []
    for host in MAX_HOSTS:
        try:
            if payload is not None:
                r = requests.post(host + path, headers=MAX_HEADERS, params=params, json=payload, timeout=30, verify=False)
            else:
                r = requests.get(host + path, headers=MAX_HEADERS, params=params, timeout=30, verify=False)
            j = r.json()
            if j.get("code") == "too.many.requests":
                log("⏳ MAX: лимит запросов, жду 4 сек...")
                time.sleep(4)
                continue
            if r.status_code == 200:
                return j
            errs.append(f"{host}:{r.status_code}:{str(j)[:60]}")
        except Exception as e:
            errs.append(f"{host}:{str(e)[:60]}")
    log(f"⚠️ MAX {path}: {' | '.join(errs)}")
    return None

def max_post_channel(caption, img_url, poll_url):
    chat_id = None
    chats = max_api("/chats")
    if chats:
        for c in chats.get("chats", []):
            if c.get("type") == "channel":
                chat_id = c.get("chat_id")
                log(f"ℹ️ MAX: канал из списка: {chat_id} «{c.get('title')}»")
                break
    if chat_id is None and MAX_CHAT_ID:
        chat_id = int(MAX_CHAT_ID)
        log(f"ℹ️ MAX: канал из секрета MAX_CHAT_ID: {chat_id}")
    if chat_id is None:
        log("⚠️ MAX: не найден канал (бот не админ? задайте MAX_CHAT_ID)")
        return
    for i, u in enumerate([poll_url, img_url], 1):
        body = {"text": caption,
                "attachments": [{"type": "image", "payload": {"url": u}}],
                "disable_link_preview": True}
        res = max_api("/messages", payload=body, params={"chat_id": chat_id})
        if res and res.get("message"):
            log(f"✅ MAX: пост с картинкой отправлен (вариант {i})")
            return
        log(f"⚠️ MAX: вариант {i} не прошёл: {str(res)[:80]}")
        time.sleep(2)
    res = max_api("/messages", payload={"text": caption}, params={"chat_id": chat_id})
    log(f"✅ MAX: отправлен текст без картинки: {str(res)[:100]}")

# ============================================================
# СТРАНИЦЫ САЙТА
# ============================================================

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

def build_backfill_page(title, img_url, body_html):
    """Страница-дополнение для Дзена: БЕЗ внешних ссылок."""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
</head>
<body style="font-family:Georgia,serif;background:#141414;color:#eee;margin:0;padding:20px">
<article style="max-width:800px;margin:0 auto">
<h1>{title}</h1>
<img src="{img_url}" style="width:100%;border-radius:10px">
<div>{body_html}</div>
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

# ============================================================
# ПОДГОТОВКА ПОСТОВ ДЛЯ RSS (санитайз + авто-добор до 10)
# ============================================================

def sanitize_posts(posts):
    """Чинит старые записи: ссылки на свой сайт, уникальные guid, заголовки без капса."""
    seen, out = set(), []
    for it in posts:
        g = it.get("guid", "")
        if not g or g in seen:
            continue
        seen.add(g)
        it = dict(it)
        it["title"] = fix_title(it.get("title", ""))
        link = it.get("link", "")
        if not link.startswith(PAGES_BASE):
            if g.startswith("pavel-gnesyuk-") and g.rsplit("-", 1)[-1].isdigit():
                link = f"{PAGES_BASE}/a/{g.rsplit('-', 1)[-1]}.html"
            else:
                continue  # запись без своей страницы в RSS не попадёт
        it["link"] = link
        out.append(it)
    return out

def backfill_posts(posts, books):
    """Если материалов меньше 10 (требование Дзена) — добавляет страницы из аннотаций."""
    have_titles = {p["title"].lower() for p in posts}
    have_books = set()
    for p in posts:
        for b in books:
            if b["title"].lower() in p["title"].lower():
                have_books.add(b["title"])
    imgs = sorted(glob.glob("img/vk_*.jpg"))
    img_url = f"{PAGES_BASE}/{imgs[-1]}" if imgs else f"{PAGES_BASE}/img/cover.jpg"
    i = 0
    for b in books:
        if len(posts) >= MIN_DZEN_ITEMS:
            break
        if b["title"] in have_books or b["title"].lower() in have_titles:
            continue
        i += 1
        slug = f"backfill-{i}"
        page = f"a/{slug}.html"
        frags = b.get("fragments", [])
        body = "<p>" + b["about"] + "</p>"
        if frags:
            body += f"\n<blockquote>{frags[0]}</blockquote>"
            body += f"\n<p>{frags[1] if len(frags) > 1 else frags[0]}</p>"
        os.makedirs("a", exist_ok=True)
        with open(page, "w", encoding="utf-8") as f:
            f.write(build_backfill_page(f"{b['title']} — {b['series']}: о чём роман", img_url, body))
        posts.append({
            "guid": f"pavel-gnesyuk-{slug}",
            "title": f"{b['title']} — {b['series']}: о чём роман",
            "text_html": b["about"] + "<br><br>" + (frags[0] if frags else ""),
            "img": img_url,
            "size": 0,
            "link": f"{PAGES_BASE}/{page}",
            "pubdate": formatdate(time.time() - i * 86400, usegmt=True)
        })
        log(f"📚 Авто-добор для Дзена: {page}")
    return posts

# ============================================================
# ГЛАВНАЯ ЛОГИКА
# ============================================================

def main():
    books = json.load(open("books.json", encoding="utf-8"))["books"]
    day = datetime.date.today().toordinal()
    book = books[day % len(books)]
    modes = ["plot", "hero", "quote", "world", "intrigue"]
    mode = modes[day % len(modes)]
    if mode == "quote" and not book.get("fragments"):
        mode = "plot"
    log(f"📚 Книга дня: «{book['title']}» ({book['series']}) | Тип: {mode}")

    tg_ok = tg_check()
    max_ok = max_check()

    long_text, theme = build_long_article(book, mode, day)
    long_title = fix_title(long_text.split("\n")[0][:150])
    log(f"📰 Заголовок статьи: {long_title}")

    teaser = build_teaser(book, long_title)
    if teaser is None:
        teaser = trim_text(long_text, 950)
    log(f"✂️ Заголовок тизера: {teaser.split(chr(10))[0][:150]}")

    link_part = f"\n\n📖 Читайте на ЛитРес: {book['url']}"
    teaser_trim = trim_text(teaser, 1024 - len(link_part))
    caption = teaser_trim + link_part

    scene = build_scene(teaser)
    base_img = scene if scene else theme
    clean_img = "".join(c for c in base_img if c.isalnum() or c.isspace() or c in ".,-")[:220].strip()
    p = ("Photorealistic cinematic movie still for russian fantasy novel article, "
         + clean_img + ", bright vivid colors, beautiful epic composition, warm golden daylight, "
         "highly detailed, sharp focus, crisp edges, high resolution, full-body figures in action, "
         "no close-up portraits, no text")
    run_no = int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    seed = day + 2000000 + (run_no % 100)
    fname = f"img/{day}_{run_no % 1000}.jpg"
    url = (POLLINATIONS_API + requests.utils.quote(p) +
           f"?nologo=true&seed={seed}&model=flux&width=1280&height=960")
    log("Скачивание картинки (flux, 1280x960)...")
    r = requests.get(url, timeout=240)
    r.raise_for_status()
    img_bytes = r.content
    os.makedirs("img", exist_ok=True)
    with open(fname, "wb") as f:
        f.write(img_bytes)
    img_url = f"{PAGES_BASE}/{fname}"
    log(f"✅ Картинка: {fname} ({len(img_bytes)} байт)")

    if tg_ok:
        tg_post_channel(img_bytes, caption)
    else:
        log("⚠️ Telegram пропущен (см. DIAG выше)")
    if max_ok:
        max_post_channel(caption, img_url, url)
    else:
        log("⚠️ MAX пропущен (см. DIAG выше)")

    body_html = esc(long_text).replace("\n", "<br><br>")
    os.makedirs("a", exist_ok=True)
    page_path = f"a/{day}.html"
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(build_article_page(long_title, img_url, body_html, book["url"]))
    page_url = f"{PAGES_BASE}/a/{day}.html"
    log(f"✅ Страница статьи: {page_path}")

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
    posts = sanitize_posts(posts)
    posts = backfill_posts(posts, books)
    posts = posts[:30]
    json.dump(posts, open("posts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    items = ""
    for it in posts:
        content_html = to_content_html(it.get("text_html", ""), it.get("img", ""))
        desc = to_plain(it.get("text_html", ""))
        size = it.get("size") or 0
        items += f"""  <item>
    <title>{esc(it['title'])}</title>
    <link>{it['link']}</link>
    <guid isPermaLink="false">{it['guid']}</guid>
    <pubDate>{it['pubdate']}</pubDate>
    <description>{esc(desc)}</description>
    <enclosure url="{it['img']}" type="image/jpeg" length="{size}"/>
    <content:encoded><![CDATA[{content_html}]]></content:encoded>
  </item>
"""
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>Павел Гнесюк — литературный блог</title>
<link>{PAGES_BASE}/</link>
<description>Статьи о романах Павла Гнесюка: сюжет, герои, цитаты, миры и интриги.</description>
<language>ru</language>
{items}</channel>
</rss>
"""
    with open("rss.xml", "w", encoding="utf-8") as f:
        f.write(rss)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(build_index(posts, meta))
    log(f"✅ RSS обновлён: материалов в ленте: {len(posts)} (минимум для Дзена: {MIN_DZEN_ITEMS})")
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
