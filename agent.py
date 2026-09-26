# -*- coding: utf-8 -*-
import os, json, datetime, requests, time, io, glob, base64, uuid, urllib3, re
from PIL import Image, ImageEnhance
urllib3.disable_warnings()

GROQ_KEY = os.environ.get("GROQ_KEY", "").strip()
GROQ_KEY2 = os.environ.get("GROQ_KEY2", "").strip()
OR_KEY = os.environ.get("OPENROUTER_KEY", "").strip()
OR_KEY2 = os.environ.get("OPENROUTER_KEY2", "").strip()
CEREBRAS_KEY = os.environ.get("CEREBRAS_KEY", "").strip()
MISTRAL_KEY = os.environ.get("MISTRAL_KEY", "").strip()
OPENAI_KEY = os.environ.get("OPENAI_KEY", "").strip()
GIGACHAT_CLIENT_ID = os.environ.get("GIGACHAT_CLIENT_ID1", "").strip()
GIGACHAT_CLIENT_SECRET = os.environ.get("GIGACHAT_CLIENT_SECRET1", "").strip()
TG_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MAX_TOKEN = os.environ.get("MAX_BOT_TOKEN", "").strip()
MAX_CHAT = os.environ.get("MAX_CHAT_ID", "").strip()

MAX_APIS = ["https://platform-api.max.ru", "https://platform-api2.max.ru", "https://botapi.max.ru"]
POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
TAGS = "#ПавелГнесюк #книги #авторскийблог #писатель"
RU = "\n\nВАЖНО: Пиши ТОЛЬКО на русском языке."

GROQ_MODELS = ["meta-llama/llama-4-scout-17b-16e-instruct",
               "meta-llama/llama-4-maverick-17b-128e-instruct",
               "openai/gpt-oss-120b",
               "llama-3.1-8b-instant"]

HEAD_STYLES = [
    "острый вопрос к читателю",
    "интрига: намёк на тайну, без раскрытия",
    "парадокс или неожиданное утверждение",
    "цитата героя + продолжение-интрига",
    "предупреждение об опасности",
    "шокирующий факт или число из мира книги",
    "вызов читателю на «ты»",
]

LABEL_RE = re.compile(
    r'^(заголовок[-\s]?тизер|заголовок|тизер|статья|анонс|ти?тр|caption|title|headline)\s*[:\-–]?\s*',
    re.I
)

def head_style(day, shift=0):
    return HEAD_STYLES[(day + shift) % len(HEAD_STYLES)]

def log(msg):
    print(msg, flush=True)

log("Версия ️ pavel-gnesyuk-dzen v45 (OpenAI 1024x1024 low + лица; pollinations — силуэты; «Книгу можно купить на ЛитРес»; запрет дублирования заголовка в теле статьи)")

# ============================================================
# ИИ-ТЕКСТ
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
        log(f"️ GigaChat OAuth: статус {r.status_code}")
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
            json={"model": "GigaChat:latest", "temperature": 0.9, "max_tokens": 4000,
                  "messages": [{"role": "user", "content": prompt + RU}]},
            timeout=120, verify=False)
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
        log(f"   ️ pollinations-text: {str(e)[:80]}")
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
        log("️ cerebras: CEREBRAS_KEY не передан в env!")
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
        for mt in (4000, 2000, 1000):
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
        f"Расширь следующий текст до {target}-{target+500} символов, сохранив стиль, структуру, "
        f"заголовок и смысл. Добавь абзацы: детали сюжета, атмосферу, интригу, вопросы к читателю. "
        f"Не добавляй хэштеги и символы ** и #.\n\nТЕКСТ:\n{txt}")
    if ext and len(ext) >= target:
        log(f"✅ Расширено: {len(ext)} симв.")
        return ext
    log("⚠️ Расширение не удалось — оставляю как есть")
    return txt

def clean_txt(t):
    return t.replace("**", "").replace("##", "").replace("#", "").strip()

def fix_headline(txt):
    lines = [l for l in txt.split("\n") if l.strip() not in ("*", "-", "_", "**", "***")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines:
        first = lines[0].strip()
        m = LABEL_RE.match(first)
        if m:
            rest = first[m.end():].strip()
            label = first[:m.end()].strip()
            if rest:
                lines[0] = rest
                log(f"🩹 fix_headline: срезана метка «{label}» → заголовок: {rest[:80]}")
            else:
                lines.pop(0)
                while lines and not lines[0].strip():
                    lines.pop(0)
                if lines:
                    log(f" fix_headline: метка «{label}» удалена, заголовком стала строка: {lines[0].strip()[:80]}")
    return "\n".join(lines).strip()

def trim_text(t, limit):
    if len(t) <= limit: return t
    c = t[:limit]
    i = max(c.rfind("."), c.rfind("!"), c.rfind("?"), c.rfind("\n"))
    return (c[:i+1] if i > limit//2 else c).rstrip()

# ============================================================
# ТЕКСТЫ: статья (Дзен) + тизер (TG/MAX) + сцена
# ============================================================

NO_LABEL = ("Первая строка — САМ текст заголовка (живая фраза), БЕЗ слов «Заголовок», "
            "«Тизер», «Статья», «Анонс», «ТИТР», «Caption» и БЕЗ двоеточия после служебных слов; "
            "не начинай строку со слов-меток. ")

def build_article(book, day):
    t, a, s = book["title"], book["about"], book["series"]
    style = head_style(day, 1)
    prompt = (f"Напиши статью для Дзена о романе Павла Гнесюка «{t}» (серия «{s}»). "
              f"Сюжет: {a}. Требования: 1. ТОЛЬКО русский язык. "
              f"2. {NO_LABEL}"
              f"Заголовок до 110 символов, приём: {style}; привязан к конкретике книги, "
              f"НЕ повторяет название «{t}»; стиль образца: «\"{t}\" — когда история оживает». "
              f"3. Объём СТРОГО 1500-2000 символов, 4-6 абзацев: завязка, герои, конфликт, "
              f"атмосфера, 1-2 интригующих вопроса, без пересказа финала. "
              f"4. Живой литературный язык, без капса и кликбейта-мусора. "
              f"5. ПЕРВАЯ СТРОКА ТЕКСТА НЕ ДОЛЖНА ПОВТОРЯТЬ ЗАГОЛОВОК — начинай сразу с сюжета, "
              f"атмосферы или вопроса, а не с пересказа заголовка. "
              f"6. Последняя строка — «Книгу можно купить на ЛитРес» + ссылка.")
    txt = ai_text(prompt, minlen=1000, rescue_min=600)
    if not txt:
        log("⚠️ Статья не создана — стандартный текст.")
        txt = f"РОМАН «{t.upper()}»: ИСТОРИЯ, КОТОРАЯ ЗАТЯГИВАЕТ\n\n{a}"
    txt = extend_text(txt, 1500)
    return fix_headline(clean_txt(txt))

def build_teaser(book, day):
    t, a, s = book["title"], book["about"], book["series"]
    style = head_style(day)
    prompt = (f"Напиши короткий тизер-анонс романа Павла Гнесюка «{t}» (серия «{s}»). "
              f"Сюжет: {a}. Требования: 1. ТОЛЬКО русский язык. "
              f"2. {NO_LABEL}"
              f"Заголовок-крючок до 90 символов, приём сегодня: {style}; привязан к конкретике книги; "
              f"НЕ повторяет название «{t}». "
              f"3. Текст 500-900 символов, 3-4 абзаца, интригующий, живой. "
              f"4. Закончи вопросом-крючком.")
    txt = ai_text(prompt, minlen=300, rescue_min=200)
    if not txt:
        log("⚠️ Тизер не создан — стандартный текст.")
        txt = f"РОМАН «{t.upper()}»: ИСТОРИЯ, КОТОРАЯ ЗАТЯГИВАЕТ\n\n{a}"
    return fix_headline(clean_txt(txt))

def build_scene(post):
    """v45: сцена может включать героя с эмоцией/лицом (OpenAI); pollinations уйдёт в силуэт."""
    prompt = (f"Из текста ниже выбери ОДНУ самую интригующую сцену и опиши её в 1-2 предложениях: "
              f"драматичный момент с героем (допустимы эмоция, пол-оборота, лицо) ИЛИ загадочный "
              f"предмет/место, ощущение опасности или тайны. Без толп людей.\n\n"
              f"ТЕКСТ: {post[:1500]}")
    return ai_text(prompt, minlen=30, rescue_min=30)

# ============================================================
# КАРТИНКИ v45: OpenAI 1024x1024 low + лица; pollinations — силуэты
# ============================================================

def image_stats(img_bytes):
    try:
        im = Image.open(io.BytesIO(img_bytes))
        im.verify()
        im = Image.open(io.BytesIO(img_bytes)).convert("L")
        im.thumbnail((64, 64))
        px = list(im.tobytes())
        avg = sum(px) / len(px)
        bright_ratio = sum(1 for p in px if p > 160) / len(px)
        return True, avg, bright_ratio
    except Exception:
        return False, 0.0, 0.0

def image_ok(img_bytes):
    ok, avg, br = image_stats(img_bytes)
    if not ok:
        return False
    good = avg >= 65 or br >= 0.10
    log(f"🔆 Яркость: средняя {avg:.0f}, ярких пикселей {br:.0%} "
        f"(пропуск: средняя≥65 ИЛИ акцент≥10%) → {'ПРОПУСК' if good else 'ОТБРАКОВКА'}")
    return good

def brighten(img_bytes, target=80):
    ok, avg, br = image_stats(img_bytes)
    if not ok or avg >= target:
        return img_bytes
    factor = min(2.2, target / max(avg, 1))
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        im = ImageEnhance.Brightness(im).enhance(factor)
        im = ImageEnhance.Contrast(im).enhance(1.05)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        log(f"🌤 Авто-осветление: коэффициент {factor:.2f} (было средняя {avg:.0f})")
        return buf.getvalue()
    except Exception as e:
        log(f"⚠️ brighten: {e}")
        return img_bytes

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
    try:
        r = requests.post("https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
            json={"model": "gpt-image-1", "prompt": prompt, "n": 1,
                  "size": "1024x1024", "quality": "low"},
            timeout=180).json()
        if "error" not in r:
            b64 = (r.get("data") or [{}])[0].get("b64_json")
            if b64:
                data = base64.b64decode(b64)
                log(f"✅ OpenAI gpt-image-1 (1024x1024 low, $0.011): картинка {len(data)} байт (без водяного знака)")
                return data
        else:
            log(f"⚠️ OpenAI gpt-image-1: {str(r['error'])[:120]}")
    except Exception as e:
        log(f"⚠️ OpenAI gpt-image-1 ошибка: {e}")
    return None

def pollinations_image(scene, seed):
    url = (POLLINATIONS_API + requests.utils.quote(scene) +
           f"?nologo=true&seed={seed}&model=flux&width=1024&height=576")
    try:
        r = requests.get(url, timeout=240)
        r.raise_for_status()
        return r.content
    except Exception as e:
        log(f"⚠️ Ошибка скачивания картинки (seed={seed}): {e}")
        return None

def download_image(scene_text, seed):
    """v45: OpenAI — люди и лица разрешены; pollinations — только силуэты со спины."""
    clean_img = "".join(c for c in scene_text if c.isalnum() or c.isspace() or c in ".,-")[:220].strip()
    base = ("Eye-catching cinematic book-promo artwork, BRIGHT and LUMINOUS: golden-hour sunlight or "
            "glowing practical light filling the whole scene, vivid saturated colors, high contrast "
            "accents, one striking focal point, strong sense of danger and mystery, sharp focus, "
            "composition draws the eye to the center. Scene: " + clean_img + ". ")
    p_openai = base + ("People and FACES allowed: expressive half-turns and close-ups welcome, "
                       "anatomically perfect faces, coherent eyes and hands, natural skin texture, "
                       "cinematic portrait lighting. No text, no logos, no watermark")
    p_poll = base + ("People ONLY as distant silhouettes seen from behind, no faces, no close-ups. "
                     "No text, no logos, no watermark")
    g = openai_image(p_openai)
    if g:
        g = brighten(g)
        if image_ok(g):
            return g
        log("️ OpenAI картинка не прошла фильтр даже после осветления — пробую дальше")
    g = pollinations_image(p_poll, seed)
    if g:
        ok, avg, br = image_stats(g)
        if not ok:
            log(f"️ Pollinations вернул не картинку (seed={seed})")
            return None
        g = brighten(g)
        if image_ok(g):
            log(f"✅ Картинка-замануха: {len(g)} байт (seed={seed})")
            return strip_watermark(g)
        log(f"⚠️ Картинка не прошла фильтр даже после осветления (seed={seed})")
    return None

def convert_to_jpeg(img_bytes):
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        im.thumbnail((1024, 1024))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85, optimize=True)
        data = buf.getvalue()
        log(f"🖼 Финал: {im.size[0]}x{im.size[1]}, {len(data)} байт")
        return data
    except Exception:
        return img_bytes

# ============================================================
# TELEGRAM
# ============================================================

def tg_send_photo(img_bytes, caption):
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
            log(f"✅ TG: тизер с картинкой отправлен в {TG_CHAT}")
            return True
        log(f"⚠️ TG: {str(r)[:200]}")
    except Exception as e:
        log(f"⚠️ TG ошибка: {e}")
    return False

def tg_send_article(text):
    if not TG_BOT or not TG_CHAT:
        log("ℹ️ TG не задан — статья пропущена (Дзен не получит)")
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage",
            data={"chat_id": TG_CHAT, "text": text[:4096]}, timeout=60).json()
        if r.get("ok"):
            log(f"✅ TG: статья ({len(text)} симв.) ТЕКСТОМ → {TG_CHAT} → Дзен заберёт через zen_sync_bot")
            return True
        log(f"⚠️ TG статья: {str(r)[:200]}")
    except Exception as e:
        log(f"⚠️ TG статья ошибка: {e}")
    return False

# ============================================================
# MAX: chat_id в params URL, 3 домена
# ============================================================

def _max_headers():
    return ({"Authorization": f"Bearer {MAX_TOKEN}"}, {"Authorization": MAX_TOKEN})

def _max_call(method, params=None, payload=None):
    for base in MAX_APIS:
        for hdr in _max_headers():
            try:
                r = requests.post(f"{base}/{method}", headers=hdr, params=params,
                                  json=payload, timeout=60, verify=False)
                try:
                    j = r.json()
                except Exception:
                    continue
                if isinstance(j, dict) and j.get("code") == "verify.token":
                    continue
                log(f"ℹ️ MAX {method} → {base}")
                return j
            except Exception:
                continue
    return None

def _max_get(method, params=None):
    for base in MAX_APIS:
        for hdr in _max_headers():
            try:
                r = requests.get(f"{base}/{method}", headers=hdr, params=params,
                                 timeout=30, verify=False)
                try:
                    j = r.json()
                except Exception:
                    continue
                if isinstance(j, dict) and j.get("code") == "verify.token":
                    continue
                return j
            except Exception:
                continue
    return None

def max_collect_ids():
    ids = []
    user_ids = []
    u = _max_get("updates")
    if isinstance(u, dict):
        ups = u.get("updates") or []
        log(f"ℹ️ MAX /updates: событий = {len(ups)}")
        for up in ups:
            t = up.get("update_type") or ""
            if t in ("bot_added", "bot_started", "chat_added", "bot_added_to_chat"):
                chat = up.get("chat") or ((up.get("message") or {}).get("recipient")) or {}
                cid = chat.get("chat_id") or chat.get("id") or up.get("chat_id")
                if cid and cid not in ids:
                    ids.insert(0, cid)
                    log(f"ℹ️ MAX: ID из события подписки {t}: {cid}")
            rec = ((up.get("message") or {}).get("recipient")) or {}
            cid = rec.get("chat_id")
            if cid and cid not in ids:
                ids.append(cid)
            cid2 = up.get("chat_id")
            if cid2 and cid2 not in ids:
                ids.append(cid2)
                log(f"ℹ️ MAX: ID из события {t} (верхний уровень): {cid2}")
            uid = up.get("user_id") or ((up.get("message") or {}).get("user_id"))
            if uid and uid not in user_ids:
                user_ids.append(uid)
        if ups and not ids:
            log(f"ℹ️ MAX первое событие (диагностика): {str(ups[0])[:300]}")
    return ids, user_ids

def max_upload(img_bytes, chat_val):
    u = _max_call("uploads", params={"type": "image", "chat_id": chat_val})
    up_url = (u or {}).get("url") if isinstance(u, dict) else None
    if not up_url:
        log(f"️ MAX uploads: нет url: {str(u)[:150]}")
        return None
    try:
        ru = requests.post(up_url, files={"data": ("cover.jpg", img_bytes, "image/jpeg")},
                           timeout=120, verify=False)
        rj = {}
        try:
            rj = ru.json()
        except Exception:
            pass
        tok = None
        if isinstance(rj, dict):
            ph = rj.get("photos") or {}
            if isinstance(ph, dict):
                for v in ph.values():
                    if isinstance(v, dict) and v.get("token"):
                        tok = v["token"]
                        break
            tok = tok or rj.get("token") or rj.get("file")
        if tok:
            log("✅ MAX: фото загружено, токен вложения получен")
            return [{"type": "image", "payload": {"token": tok}}]
        log(f"⚠️ MAX upload: токен не найден в ответе: {str(rj)[:150]}")
    except Exception as e:
        log(f"⚠️ MAX upload: {str(e)[:100]}")
    return None

def max_post(img_bytes, text):
    if not MAX_TOKEN:
        log("ℹ️ MAX_BOT_TOKEN не задан — MAX пропущен")
        return False
    ids, user_ids = max_collect_ids()
    variants = list(ids)
    if MAX_CHAT:
        sec = int(MAX_CHAT) if MAX_CHAT.lstrip("-").isdigit() else MAX_CHAT
        if sec not in variants:
            variants.append(sec)
        if str(MAX_CHAT) not in variants:
            variants.append(str(MAX_CHAT))
    if not variants:
        log("⚠️ MAX: ни одного chat_id из событий и секрета")
        return False
    log(f"️ MAX: кандидаты chat_id: {variants}")
    att = max_upload(img_bytes, variants[0]) if img_bytes else None
    for chat_val in variants:
        payload = {"text": text[:4000]}
        if att:
            payload["attachments"] = att
        r = _max_call("messages", params={"chat_id": chat_val}, payload=payload)
        ok = isinstance(r, dict) and (r.get("success") is True or isinstance(r.get("message"), dict))
        if ok:
            m = r.get("message") or {}
            log(f"✅ MAX: пост отправлен (chat_id={chat_val}, id={m.get('id')})")
            return True
        log(f"️ MAX: chat_id={chat_val} → {str(r)[:150]}")
    if user_ids:
        uid = user_ids[0]
        log(f"🔬 MAX диагностика: тест в личку user_id={uid} (params URL)")
        r = _max_call("messages", params={"user_id": uid},
                      payload={"text": " Служебная проверка отправки бота (v45)"})
        ok = isinstance(r, dict) and (r.get("success") is True or isinstance(r.get("message"), dict))
        log(f"🔬 MAX личка: {'УСПЕХ — токен работает, дело в правах на канал' if ok else str(r)[:150]}")
    return False

# ============================================================
# ГЛАВНАЯ ЛОГИКА
# ============================================================

def main():
    books = json.load(open("books.json", encoding="utf-8"))["books"]
    day = datetime.date.today().toordinal()
    book = books[day % len(books)]
    log(f"📚 Книга дня: «{book['title']}» ({book['series']})")
    log(f"🎯 Приём заголовка сегодня: {head_style(day)}")

    article = build_article(book, day)
    log(f"📄 Статья: {len(article)} симв. Заголовок: {article.split(chr(10))[0][:120]}")
    teaser = build_teaser(book, day)
    log(f"️ Тизер: {len(teaser)} симв. Заголовок: {teaser.split(chr(10))[0][:120]}")

    link = book.get("url", "")
    link_part = f"\n\n Книгу можно купить на ЛитРес: {link}" if link else ""
    teaser_caption = trim_text(teaser, 1000 - len(link_part) - len(TAGS) - 2) + link_part + "\n\n" + TAGS
    article_full = article + link_part

    scene = build_scene(teaser)
    base_img = scene if scene else book.get("about", "")[:120]
    run_no = int(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    img_bytes = None
    for attempt in range(4):
        seed = day + 5000000 + (run_no % 100) + attempt * 7919
        img_bytes = download_image(base_img, seed)
        if img_bytes:
            break
        log(f" Попытка {attempt + 1} не удалась, пробуем снова...")

    if img_bytes:
        img_bytes = convert_to_jpeg(img_bytes)
        os.makedirs("img", exist_ok=True)
        path = f"img/dz_{day}.jpg"
        with open(path, "wb") as f:
            f.write(img_bytes)
        log(f"💾 Картинка сохранена: {path}")
    else:
        candidates = []
        for f in glob.glob("img/dz_*.jpg"):
            with open(f, "rb") as fh:
                ok, avg, br = image_stats(fh.read())
            if ok and (avg >= 65 or br >= 0.10):
                candidates.append((avg, f))
        if candidates:
            candidates.sort(reverse=True)
            pick = candidates[0][1]
            log(f"️ Генерация не удалась — беру самую светлую прежнюю картинку {pick}")
            with open(pick, "rb") as f:
                img_bytes = f.read()
        else:
            log("⚠️ Нет ни свежей, ни подходящей старой картинки")

    tg1 = tg_send_photo(img_bytes, teaser_caption)
    tg2 = tg_send_article(article_full)
    max_ok = max_post(img_bytes, teaser_caption)

    log("=" * 50)
    parts = []
    if tg1: parts.append("TG-тизер(с картинкой)")
    if tg2: parts.append("TG-статья→Дзен")
    if max_ok: parts.append("MAX")
    log(f"✅ FINISH: {' + '.join(parts) if parts else 'НИКУДА'}!" + ("" if img_bytes else " (без картинки)"))
    log("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f" КРИТИЧЕСКАЯ ОШИБКА: {e}")
        raise
