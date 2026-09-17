# -*- coding: utf-8 -*-
import os, json, datetime, requests, time, io, glob, base64, uuid, urllib3
import html as htmllib
from PIL import Image
urllib3.disable_warnings()

GROQ_KEY = os.environ.get("GROQ_KEY", "").strip()
GROQ_KEY2 = os.environ.get("GROQ_KEY2", "").strip()
OR_KEY = os.environ.get("OPENROUTER_KEY", "").strip()
OR_KEY2 = os.environ.get("OPENROUTER_KEY2", "").strip()
CEREBRAS_KEY = os.environ.get("CEREBRAS_KEY", "").strip()
MISTRAL_KEY = os.environ.get("MISTRAL_KEY", "").strip()
OPENAI_KEY = os.environ.get("OPENAI_KEY", "").strip()
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()
GIGACHAT_CLIENT_ID = os.environ.get("GIGACHAT_CLIENT_ID1", "").strip()
GIGACHAT_CLIENT_SECRET = os.environ.get("GIGACHAT_CLIENT_SECRET1", "").strip()
TG_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MAX_TOKEN = os.environ.get("MAX_BOT_TOKEN", "").strip()
MAX_CHAT = os.environ.get("MAX_CHAT_ID", "").strip()

GH_PAGES = os.environ.get("GH_PAGES", "https://pavrus-ai.github.io/pavel-gnesyuk-dzen").rstrip("/")
POSTS_FILE = "posts.json"
RSS_FILE = "rss.xml"
RSS_TITLE = "Павел Гнесюк — романы и истории"
POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
TAGS = "#ПавелГнесюк #книги #авторскийблог #писатель"
RU = "\n\nВАЖНО: Пиши ТОЛЬКО на русском языке."
MIN_BRIGHTNESS = 70

GROQ_MODELS = ["meta-llama/llama-4-scout-17b-16e-instruct",
               "meta-llama/llama-4-maverick-17b-128e-instruct",
               "openai/gpt-oss-120b",
               "llama-3.1-8b-instant"]

# v28: 7 приёмов заголовка — ротация по дням, заголовки всегда разные
HEAD_STYLES = [
    "острый вопрос к читателю",
    "интрига: намёк на тайну, без раскрытия",
    "парадокс или неожиданное утверждение",
    "цитата героя + продолжение-интрига",
    "предупреждение об опасности",
    "шокирующий факт или число из мира книги",
    "вызов читателю на «ты»",
]

def head_style(day, shift=0):
    return HEAD_STYLES[(day + shift) % len(HEAD_STYLES)]

def log(msg):
    print(msg, flush=True)

log("Версия ℹ️ pavel-gnesyuk-dzen v28 (разные заголовки-крючки: 7 приёмов по дням; текст 800-1100; картинка-замануха 16:9; MAX с диагностикой; RSS для Дзена)")

# ============================================================
# ИИ-ТЕКСТ: ступени с диагностикой
# ============================================================

def _extract(r):
    try: return r["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError): return None

def _err_snippet(r):
    e = r.get("error") or {}
    code = e.get("code") or e.get("type") or "?"
    msg = str(e.get("message") or e)
    return f"{code}: {msg[:100]}"

_GIGACHAT_TOKEN = None
_GIGACHAT_TOKEN_EXPIRY = 0

def get_gigachat_token():
    global _GIGACHAT_TOKEN, _GIGACHAT_TOKEN_EXPIRY
    if not GIGACHAT_CLIENT_ID or not GIGACHAT_CLIENT_SECRET:
        return None
    if _GIGACHAT_TOKEN and time.time() < _GIGACHAT_TOKEN_EXPIRY:
        return _GIGACHAT_TOKEN
    try:
        credentials = base64.b64encode(f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}".encode()).decode()
        r = requests.post("https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={"Authorization": f"Basic {credentials}",
                     "RqUID": str(uuid.uuid4()),
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"scope": "GIGACHAT_API_PERS"},
            timeout=30, verify=False)
        log(f"ℹ️ GigaChat OAuth: статус {r.status_code}")
        if r.status_code != 200:
            log(f"⚠️ GigaChat OAuth тело: {r.text[:300]}")
            return None
        j = r.json()
        if "access_token" in j:
            _GIGACHAT_TOKEN = j["access_token"]
            _GIGACHAT_TOKEN_EXPIRY = time.time() + 1700
            log("✅ GigaChat: токен получен (действует 30 мин)")
            return _GIGACHAT_TOKEN
    except Exception as e:
        log(f"⚠️ GigaChat auth error: {e}")
    return None

def ai_gigachat(prompt):
    token = get_gigachat_token()
    if not token:
        return None
    try:
        r = requests.post("https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"model": "GigaChat:latest", "temperature": 0.9, "max_tokens": 2000,
                  "messages": [{"role": "user", "content": prompt + RU}]},
            timeout=90, verify=False)
        if r.status_code != 200:
            log(f"⚠️ GigaChat chat: статус {r.status_code}: {r.text[:200]}")
            return None
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log(f"⚠️ GigaChat error: {e}")
        return None

def ai_cerebras(prompt):
    if not CEREBRAS_KEY: return None
    try:
        r = requests.post("https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {CEREBRAS_KEY}"},
            json={"model": "llama-3.3-70b", "temperature": 0.8,
                  "messages": [{"role": "user", "content": prompt + RU}]}, timeout=60).json()
        if "error" in r:
            log(f"   ⚠️ cerebras: {_err_snippet(r)}")
            return None
        return _extract(r)
    except Exception as e:
        log(f"   ⚠️ cerebras: сеть/ошибка {str(e)[:80]}")
        return None

def ai_mistral(prompt):
    if not MISTRAL_KEY: return None
    try:
        r = requests.post("https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_KEY}"},
            json={"model": "mistral-small-latest", "temperature": 0.8,
                  "messages": [{"role": "user", "content": prompt + RU}]}, timeout=60).json()
        if "error" in r:
            log(f"   ⚠️ mistral: {_err_snippet(r)}")
            return None
        return _extract(r)
    except Exception as e:
        log(f"   ⚠️ mistral: сеть/ошибка {str(e)[:80]}")
        return None

def ai_groq(prompt, key, model):
    if not key: return None
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "temperature": 0.8,
                  "messages": [{"role": "user", "content": prompt + RU}]}, timeout=60).json()
        if "error" in r:
            log(f"   ⚠️ groq {model}: {_err_snippet(r)}")
            return None
        return _extract(r)
    except Exception as e:
        log(f"   ⚠️ groq {model}: сеть/ошибка {str(e)[:80]}")
        return None

def ai_openrouter_auto(prompt, key, max_tokens):
    if not key: return None
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "HTTP-Referer": "https://github.com"},
            json={"model": "auto", "temperature": 0.8, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt + RU}]}, timeout=60).json()
        if "error" in r:
            log(f"   ⚠️ openrouter auto (max={max_tokens}): {_err_snippet(r)}")
            return None
        return _extract(r)
    except Exception as e:
        log(f"   ⚠️ openrouter auto: сеть/ошибка {str(e)[:80]}")
        return None

def ai_pollinations_text(prompt):
    try:
        r = requests.post("https://text.pollinations.ai/openai",
            json={"model": "openai", "temperature": 0.8,
                  "messages": [{"role": "user", "content": prompt + RU}]}, timeout=90).json()
        res = _extract(r)
        if res:
            return res
    except Exception as e:
        log(f"   ⚠️ pollinations-text: {str(e)[:80]}")
    return None

def ai_text(prompt, minlen=600, rescue_min=300):
    best_res = ""

    def take(res, label):
        nonlocal best_res
        if not res:
            return None
        if len(res) >= minlen:
            log(f"✅ Успех: {label}, {len(res)} симв.")
            return res
        log(f"   ⚠️ {label}: текст короче нужного ({len(res)}/{minlen}) — запомнен кандидатом")
        if len(res) > len(best_res):
            best_res = res
        return None

    if not GIGACHAT_CLIENT_ID:
        log("⚠️ gigachat: GIGACHAT_CLIENT_ID1 не передан в env!")
    else:
        log("🔄 Попытка: gigachat (GigaChat:latest)...")
        r = take(ai_gigachat(prompt), "gigachat")
        if r: return r
    if not CEREBRAS_KEY:
        log("⚠️ cerebras: CEREBRAS_KEY не передан в env!")
    else:
        log("🔄 Попытка: cerebras (llama-3.3-70b)...")
        r = take(ai_cerebras(prompt), "cerebras")
        if r: return r
    if not MISTRAL_KEY:
        log("⚠️ mistral: MISTRAL_KEY не передан в env!")
    else:
        log("🔄 Попытка: mistral (mistral-small)...")
        r = take(ai_mistral(prompt), "mistral")
        if r: return r
    for i, key in enumerate((GROQ_KEY, GROQ_KEY2)):
        if not key: continue
        for model in GROQ_MODELS:
            log(f"🔄 Попытка: groq ({model}, ключ {i+1})...")
            r = take(ai_groq(prompt, key, model), f"groq ({model}, ключ {i+1})")
            if r: return r
    for i, key in enumerate((OR_KEY, OR_KEY2)):
        if not key: continue
        for mt in (1000, 512):
            log(f"🔄 Попытка: openrouter auto (max_tokens={mt}, ключ {i+1})...")
            r = take(ai_openrouter_auto(prompt, key, mt), f"openrouter auto (max={mt}, ключ {i+1})")
            if r: return r
    log("🔄 Попытка: pollinations-text (без ключа)...")
    r = take(ai_pollinations_text(prompt), "pollinations-text")
    if r: return r

    if best_res and len(best_res) >= rescue_min:
        log(f"ℹ️ Никто не дал {minlen} симв. — беру лучший кандидат ({len(best_res)} симв.)")
        return best_res
    return None

def extend_text(txt, target):
    if not txt or len(txt) >= target:
        return txt
    log(f"✂️ Текст короткий ({len(txt)} < {target}) — прошу GigaChat расширить")
    ext = ai_gigachat(
        f"Расширь следующий пост до {target}-{target+300} символов, сохранив стиль, структуру, "
        f"заголовок и смысл. Добавь 2-3 абзаца: детали сюжета, атмосферу, интригу, вопросы к читателю. "
        f"Не добавляй хэштеги и символы ** и #.\n\nТЕКСТ:\n{txt}")
    if ext and len(ext) >= target:
        log(f"✅ Расширено: {len(ext)} симв.")
        return ext
    log("⚠️ Расширение не удалось — оставляю как есть")
    return txt

def clean_txt(t):
    return t.replace("**", "").replace("##", "").replace("#", "").strip()

def trim_text(t, limit):
    if len(t) <= limit: return t
    c = t[:limit]
    i = max(c.rfind("."), c.rfind("!"), c.rfind("?"), c.rfind("\n"))
    return (c[:i+1] if i > limit//2 else c).rstrip()

# ============================================================
# ТЕКСТЫ ПОСТОВ (v28: заголовок-крючок, 800-1100 симв.)
# ============================================================

def build_post(book, day):
    t, a, s = book["title"], book["about"], book["series"]
    style = head_style(day)
    prompt = (f"Напиши пост-анонс о романе Павла Гнесюка «{t}» (серия «{s}»). "
              f"Сюжет: {a}. Требования: 1. ТОЛЬКО русский язык. "
              f"2. Первая строка — ОРИГИНАЛЬНЫЙ цепляющий заголовок-крючок (до 90 символов), "
              f"приём сегодня: {style}. Заголовок НЕ должен повторять название книги «{t}» "
              f"и не должен быть скучным; регистр любой — как сильнее цепляет. "
              f"3. Текст СТРОГО 800-1100 символов, 4-6 абзацев, интригующий, живой. "
              f"4. Раскрой завязку, добавь 2-3 вопроса-крючка и атмосферу. "
              f"5. Закончи сильной строкой-призывом читать дальше.")
    txt = ai_text(prompt, minlen=600, rescue_min=300)
    if not txt:
        log("⚠️ Пост не создан — стандартный текст.")
        txt = f"РОМАН «{t.upper()}»: ИСТОРИЯ, КОТОРАЯ ЗАТЯГИВАЕТ\n\n{a}"
    txt = extend_text(txt, 800)
    return clean_txt(txt)

def build_quote_post(book, day):
    fr = book["fragments"][day % len(book["fragments"])]
    style = head_style(day, 3)
    prompt = (f"Напиши пост: разбор цитаты из романа Павла Гнесюка «{book['title']}». "
              f"Цитата: «{fr}». Требования: 1. ТОЛЬКО русский язык. "
              f"2. Первая строка — ОРИГИНАЛЬНЫЙ цепляющий заголовок-крючок (до 90 символов), "
              f"приём сегодня: {style}; НЕ повторяй название книги. "
              f"3. 600-900 символов: раскрой смысл цитаты, атмосферу и интригу романа. "
              f"4. Сама цитата должна войти в текст поста.")
    txt = ai_text(prompt, minlen=500, rescue_min=300)
    if not txt:
        log("⚠️ Разбор цитаты не создан — стандартный пост.")
        return build_post(book, day)
    txt = extend_text(txt, 600)
    return clean_txt(txt)

def build_scene(post):
    prompt = (f"Из текста ниже выбери ОДНУ самую интригующую сцену и опиши её в 1-2 предложениях "
              f"для обложки-заманухи: драматичный момент, загадочный предмет или место, ощущение опасности или тайны. "
              f"Люди — только силуэтом со спины или издалека, без лиц.\n\n"
              f"ТЕКСТ: {post[:1500]}")
    return ai_text(prompt, minlen=30, rescue_min=30)

# ============================================================
# КАРТИНКИ v28: замануха 16:9 (gpt-image-1 → HF router → pollinations+обрезка)
# ============================================================

def image_stats(img_bytes):
    try:
        im = Image.open(io.BytesIO(img_bytes))
        im.verify()
        im = Image.open(io.BytesIO(img_bytes)).convert("L")
        im.thumbnail((64, 64))
        px = im.tobytes()
        return True, sum(px) / len(px)
    except Exception:
        return False, 0.0

def strip_watermark(img_bytes):
    try:
        im = Image.open(io.BytesIO(img_bytes))
        w, h = im.size
        cut = int(h * 0.09)
        im = im.crop((0, 0, w, h - cut))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=90)
        log(f"✂️ Водяной знак: срезана нижняя полоса {cut}px (было {w}x{h}, стало {im.size[0]}x{im.size[1]})")
        return buf.getvalue()
    except Exception as e:
        log(f"⚠️ strip_watermark: {e}")
        return img_bytes

def openai_image(prompt):
    if not OPENAI_KEY:
        return None
    full = prompt + ", photorealistic, high resolution, no text, no logos, no watermark"
    try:
        r = requests.post("https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-image-1", "prompt": full, "n": 1, "size": "1536x1024"},
            timeout=180).json()
        if "error" not in r:
            b64 = (r.get("data") or [{}])[0].get("b64_json")
            if b64:
                data = base64.b64decode(b64)
                log(f"✅ OpenAI gpt-image-1: картинка {len(data)} байт (без водяного знака)")
                return data
        else:
            log(f"⚠️ OpenAI gpt-image-1: {str(r['error'])[:120]}")
    except Exception as e:
        log(f"⚠️ OpenAI gpt-image-1 ошибка: {e}")
    return None

def hf_image(prompt):
    if not HF_TOKEN:
        return None
    full = prompt + ", photorealistic, high resolution, no text, no logos, no watermark"
    for mdl in ("black-forest-labs/FLUX.1-schnell", "black-forest-labs/FLUX.1-dev"):
        try:
            r = requests.post("https://router.huggingface.co/hf-inference/models/" + mdl,
                headers={"Authorization": f"Bearer {HF_TOKEN}"},
                json={"inputs": full}, timeout=60)
            if r.status_code == 410:
                log(f"⚠️ HF {mdl}: 410 модель устарела — HF пропускаем")
                return None
            if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/"):
                log(f"✅ HF {mdl}: картинка {len(r.content)} байт (без водяного знака)")
                return r.content
            log(f"⚠️ HF {mdl}: ответ {r.status_code}: {r.text[:80]}")
        except Exception as e:
            log(f"⚠️ HF {mdl} ошибка: {str(e)[:80]}")
    return None

def pollinations_image(scene, seed):
    url = (POLLINATIONS_API + requests.utils.quote(scene) +
           f"?nologo=true&seed={seed}&model=flux&width=1280&height=720")
    try:
        r = requests.get(url, timeout=240)
        r.raise_for_status()
        return r.content
    except Exception as e:
        log(f"⚠️ Ошибка скачивания картинки (seed={seed}): {e}")
        return None

def download_image(scene_text, seed):
    clean_img = "".join(c for c in scene_text if c.isalnum() or c.isspace() or c in ".,-")[:220].strip()
    p = ("Eye-catching dramatic thriller book-cover style artwork: "
         "one striking mysterious focal point (artifact, glowing object, door, silhouette of a person "
         "seen from behind in the distance), cinematic moody lighting with a single bright accent, "
         "ultra high contrast, rich saturated colors, strong sense of danger and mystery, "
         "sharp focus on the focal point, composition draws the eye to the center. "
         "Scene: " + clean_img + ". "
         "No faces close-up, no text, no watermark")
    g = openai_image(p)
    if g:
        ok, bright = image_stats(g)
        if ok and bright >= MIN_BRIGHTNESS:
            return g
        log(f"⚠️ OpenAI картинка слишком тёмная ({bright:.0f}) — пробую дальше")
    g = hf_image(p)
    if g:
        ok, bright = image_stats(g)
        if ok and bright >= MIN_BRIGHTNESS:
            return g
        log(f"⚠️ HF FLUX картинка слишком тёмная ({bright:.0f}) — пробую дальше")
    g = pollinations_image(p, seed)
    if g:
        ok, bright = image_stats(g)
        if not ok:
            log(f"⚠️ Pollinations вернул не картинку (seed={seed})")
            return None
        log(f"🔆 Яркость картинки: {bright:.0f} (порог {MIN_BRIGHTNESS})")
        if bright < MIN_BRIGHTNESS:
            log(f"⚠️ Слишком тёмная картинка (seed={seed}) — отбракована")
            return None
        log(f"✅ Картинка-замануха: {len(g)} байт (seed={seed})")
        return strip_watermark(g)
    return None

def convert_to_jpeg(img_bytes):
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=92)
        return buf.getvalue()
    except Exception:
        return img_bytes

# ============================================================
# TELEGRAM
# ============================================================

def tg_post(img_bytes, caption):
    if not TG_BOT or not TG_CHAT:
        log("ℹ️ TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID не заданы — TG пропущен")
        return False
    caption = caption[:1020].rstrip()
    try:
        if img_bytes:
            r = requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendPhoto",
                data={"chat_id": TG_CHAT, "caption": caption},
                files={"photo": ("cover.jpg", img_bytes, "image/jpeg")}, timeout=120).json()
        else:
            r = requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage",
                data={"chat_id": TG_CHAT, "text": caption}, timeout=60).json()
        if r.get("ok"):
            log(f"✅ TG: карточка отправлена в {TG_CHAT}")
            return True
        log(f"⚠️ TG: {str(r)[:200]}")
    except Exception as e:
        log(f"⚠️ TG ошибка: {e}")
    return False

# ============================================================
# MAX MESSENGER (диагностика chat_id в логе)
# ============================================================

def max_post(img_bytes, text):
    if not MAX_TOKEN or not MAX_CHAT:
        log("ℹ️ MAX_BOT_TOKEN/MAX_CHAT_ID не заданы — MAX пропущен")
        return False
    log(f"ℹ️ MAX: целевой chat_id из секрета = {MAX_CHAT}")
    att = None
    if img_bytes:
        try:
            u = requests.get("https://botapi.max.ru/uploads",
                params={"type": "photo", "access_token": MAX_TOKEN, "chat_id": MAX_CHAT},
                timeout=30).json()
            up_url = u.get("url")
            if up_url:
                r = requests.post(up_url,
                    files={"data": ("cover.jpg", img_bytes, "image/jpeg")}, timeout=120).json()
                fid = r.get("file") or r.get("file_id")
                if fid:
                    att = [{"type": "photo", "file_id": fid}]
                    log("✅ MAX: фото загружено на сервер")
                else:
                    log(f"⚠️ MAX upload: нет file_id в ответе: {str(r)[:120]}")
            else:
                log(f"⚠️ MAX uploads: нет url в ответе: {str(u)[:120]}")
        except Exception as e:
            log(f"⚠️ MAX upload: {str(e)[:100]}")
    else:
        log("ℹ️ MAX: картинки нет — шлю только текст")
    payload = {"chat_id": MAX_CHAT, "text": text[:4000]}
    if att:
        payload["attachments"] = att
    try:
        r = requests.post("https://botapi.max.ru/messages",
            params={"access_token": MAX_TOKEN}, json=payload, timeout=60).json()
        if r.get("success") or r.get("message"):
            m = r.get("message") or {}
            log(f"✅ MAX: сообщение принято (chat_id в ответе={m.get('chat_id')}, id={m.get('id')})")
            return True
        log(f"⚠️ MAX: {str(r)[:200]}")
    except Exception as e:
        log(f"⚠️ MAX ошибка: {e}")
    return False

# ============================================================
# ДЗЕН через RSS
# ============================================================

def text_to_html(post, img_url, link):
    parts = [f'<img src="{img_url}" width="100%"/>'] if img_url else []
    for i, line in enumerate(post.split("\n")):
        line = line.strip()
        if not line:
            continue
        if i == 0:
            parts.append(f"<h2>{htmllib.escape(line)}</h2>")
        else:
            parts.append(f"<p>{htmllib.escape(line)}</p>")
    parts.append(f'<p><a href="{link}">Читать книгу на ЛитРес</a></p>')
    return "".join(parts)

def dzen_update(day, title, post, img_url, link):
    try:
        posts = json.load(open(POSTS_FILE, encoding="utf-8"))
        if not isinstance(posts, list):
            posts = []
    except Exception:
        posts = []
    guid = f"gnesyuk-dzen-{day}"
    posts = [p for p in posts if p.get("guid") != guid]
    pub = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    posts.insert(0, {"guid": guid, "title": title, "pubdate": pub,
                     "img": img_url, "link": link,
                     "text_html": text_to_html(post, img_url, link)})
    posts = posts[:20]
    json.dump(posts, open(POSTS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    items = []
    for p in posts:
        items.append(
            "<item>"
            f"<title>{htmllib.escape(p['title'])}</title>"
            f"<link>{htmllib.escape(p['link'])}</link>"
            f"<guid isPermaLink=\"false\">{htmllib.escape(p['guid'])}</guid>"
            f"<pubDate>{p['pubdate']}</pubDate>"
            f"<content:encoded><![CDATA[{p['text_html']}]]></content:encoded>"
            "</item>")
    rss = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
           "<rss version=\"2.0\" xmlns:content=\"http://purl.org/rss/1.0/modules/content/\">\n"
           "<channel>"
           f"<title>{htmllib.escape(RSS_TITLE)}</title>"
           f"<link>{htmllib.escape(GH_PAGES)}</link>"
           "<description>Новые посты о романах Павла Гнесюка</description>"
           + "".join(items) +
           "</channel>\n</rss>\n")
    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(rss)
    log(f"✅ Дзен RSS: обновлён {RSS_FILE} ({len(posts)} записей, свежая: {guid})")

# ============================================================
# ГЛАВНАЯ ЛОГИКА
# ============================================================

def main():
    books = json.load(open("books.json", encoding="utf-8"))["books"]
    day = datetime.date.today().toordinal()
    book = books[day % len(books)]
    log(f"📚 Книга дня: «{book['title']}» ({book['series']})")
    log(f"🎯 Приём заголовка сегодня: {head_style(day)}")

    if day % 3 == 0 and book.get("fragments"):
        post = build_quote_post(book, day)
    else:
        post = build_post(book, day)
    log(f"✂️ Заголовок поста: {post.split(chr(10))[0][:150]}")
    log(f"📝 Длина поста: {len(post)} симв.")
    link = book.get("url", "")
    link_part = f"\n\n📖 Читайте на ЛитРес: {link}" if link else ""
    caption = trim_text(post, 1000 - len(link_part) - len(TAGS) - 2) + link_part + "\n\n" + TAGS

    scene = build_scene(post)
    base_img = scene if scene else book.get("about", "")[:120]
    run_no = int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    img_bytes = None
    for attempt in range(4):
        seed = day + 5000000 + (run_no % 100) + attempt * 7919
        img_bytes = download_image(base_img, seed)
        if img_bytes:
            break
        log(f"⏳ Попытка {attempt + 1} не удалась, пробуем снова...")

    img_url = ""
    if img_bytes:
        img_bytes = convert_to_jpeg(img_bytes)
        os.makedirs("img", exist_ok=True)
        path = f"img/dz_{day}.jpg"
        with open(path, "wb") as f:
            f.write(img_bytes)
        img_url = GH_PAGES + "/" + path
        log(f"💾 Картинка сохранена: {path} → {img_url}")
    else:
        candidates = []
        for f in glob.glob("img/dz_*.jpg"):
            with open(f, "rb") as fh:
                ok, bright = image_stats(fh.read())
            if ok and bright >= MIN_BRIGHTNESS:
                candidates.append((bright, f))
        if candidates:
            candidates.sort(reverse=True)
            pick = candidates[0][1]
            log(f"⚠️ Генерация не удалась — беру прежнюю картинку {pick}")
            with open(pick, "rb") as f:
                img_bytes = f.read()
            img_url = GH_PAGES + "/" + pick
        else:
            log("⚠️ Нет ни свежей, ни подходящей старой картинки")

    tg_post(img_bytes, caption)
    max_post(img_bytes, caption)
    dzen_update(day, post.split("\n")[0], post, img_url, link)

    log("=" * 50)
    log("✅ FINISH: книга → TG + MAX + Дзен(RSS)!")
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        raise
