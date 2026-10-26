"""PlainLetter core: turn a confusing official letter into plain language with a
local Spark-X2.6-4B model served by Ollama. Standard library only."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL
MODEL = os.environ.get("PLAINLETTER_MODEL", "SparkLLM/Spark-X2.6-4B")

# Inference settings. Low temperature because this is extraction, not creative
# writing; a fixed seed makes reruns comparable. Thinking is off by default for
# latency on laptops (the model supports none/low/high thinking levels).
OPTIONS = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 0,
    "seed": 7,
    "num_ctx": 8192,
    "num_predict": 2048,
}
THINK = os.environ.get("PLAINLETTER_THINK", "false").lower() in ("1", "true", "yes")

LANGUAGES = {"en": "English", "es": "Spanish", "zh": "Simplified Chinese"}

SYSTEM_PROMPT = """You are PlainLetter, a careful helper that explains official letters \
(medical bills, insurance notices, benefits notices, tax or government letters) to people \
who find them confusing. Many readers are stressed, have limited reading skills, or speak \
English as a second language.

Rules:
- Use only facts written in the letter. Never invent dates, amounts, phone numbers, names, or rights.
- Write for a 6th-grade reader: sentences of 12 words or fewer, everyday words, talk to the reader \
as "you". Say "the hospital", "your insurance", "the county" instead of long official names. \
If you must use a term from the letter (like "deductible" or "appeal"), explain it in a few words.
- Be brief. The summary is 3 to 5 short sentences about what matters, not a copy of the letter. \
Do not list every charge, address, or account number.
- Copy dates, money amounts, and phone numbers exactly as they appear.
- "actions": 2 to 5 steps, most urgent first. Do not number them.
- "deadlines": only dates or time limits by which the reader must do something, or after which \
something happens to them. The date the letter was sent is not a deadline. For each one, copy a \
short exact quote from the letter that proves it. If it is written as a rule (for example "within \
180 days of this notice"), put the rule in "rule" and leave "date" empty.
- "contacts": one entry per phone number. Combine the reasons.
- "questions_to_ask": 2 to 4 useful questions the letter does not answer.
- "reply_draft": under 120 words, for the reader to send. Polite, uses facts from the letter, \
[brackets] for things the reader must fill in. Do not promise payment or admit anything for the reader.
- "letter_type": a few plain words, like "Hospital bill" or "Insurance said no". \
"sender": short name only, no address. "money": the one main amount and what it is, like \
"$250.00 you may owe", or empty.

Style example. Letter text: "Failure to remit payment by the due date may result in referral to a \
collection agency." Plain version: "Pay by the due date. If you don't, they may send your bill to \
a debt collector."

- You are not a lawyer or doctor. Do not give legal or medical advice."""

USER_TEMPLATE = """Explain this letter for me. Write every field in {language}, \
but copy names, numbers, and quotes exactly as they appear in the letter.
{note_block}
<letter>
{letter}
</letter>"""

SCHEMA = {
    "type": "object",
    "properties": {
        "letter_type": {"type": "string", "description": "e.g. hospital bill, insurance denial, benefits renewal"},
        "sender": {"type": "string"},
        "summary": {
            "type": "array",
            "minItems": 2,
            "items": {"type": "string"},
            "description": "3 to 5 short, simple sentences: what this letter is and what it means for me",
        },
        "money": {"type": "string", "description": "amount I owe or could lose, or empty"},
        "actions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "step": {"type": "string"},
                    "how": {"type": "string"},
                    "urgent": {"type": "boolean"},
                },
                "required": ["step", "how", "urgent"],
            },
        },
        "deadlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "what": {"type": "string"},
                    "date": {"type": "string"},
                    "rule": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["what", "date", "rule", "quote"],
            },
        },
        "contacts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "who": {"type": "string"},
                    "phone": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["who", "phone", "why"],
            },
        },
        "rights": {"type": "array", "items": {"type": "string"}, "description": "help or rights the letter mentions"},
        "reply_subject": {"type": "string"},
        "reply_draft": {"type": "string"},
        "questions_to_ask": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "letter_type", "sender", "summary", "money", "actions", "deadlines",
        "contacts", "rights", "reply_subject", "reply_draft", "questions_to_ask",
    ],
}


SIMPLIFY_PROMPT = """Rewrite each sentence below so a 6th grader can read it. \
Rules: at most 12 words per sentence, everyday words, talk to the reader as "you". \
You may split one sentence into two. Keep every date, money amount, and phone number exactly. \
Do not add any new facts. Write in {language}.

{sentences}"""

SIMPLIFY_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "array", "items": {"type": "string"}, "minItems": 2}},
    "required": ["summary"],
}


class ModelError(RuntimeError):
    pass


def _post(path: str, payload: dict, timeout: float = 600) -> dict:
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ModelError(f"Ollama error {e.code}: {e.read().decode(errors='replace')[:400]}") from e
    except urllib.error.URLError as e:
        raise ModelError(f"Cannot reach Ollama at {OLLAMA_URL}. Is `ollama serve` running? ({e.reason})") from e


def model_info() -> dict:
    """Runtime facts recorded with every output (reproducibility)."""
    info = {"model": MODEL, "ollama_url": OLLAMA_URL, "think": THINK, "options": OPTIONS}
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/version", timeout=5) as r:
            info["ollama_version"] = json.loads(r.read()).get("version")
        show = _post("/api/show", {"model": MODEL}, timeout=30)
        d = show.get("details", {})
        info.update({
            "family": d.get("family"),
            "parameter_size": d.get("parameter_size"),
            "quantization": d.get("quantization_level"),
            "format": d.get("format"),
        })
        tags = _post_get("/api/tags")
        for m in tags.get("models", []):
            if m.get("name", "").lower().startswith(MODEL.lower()):
                info["ollama_digest"] = m.get("digest")
                info["size_bytes"] = m.get("size")
        info["available"] = True
    except ModelError as e:
        info["available"] = False
        info["error"] = str(e)
    except Exception as e:  # noqa: BLE001
        info["available"] = False
        info["error"] = str(e)
    return info


def _post_get(path: str) -> dict:
    with urllib.request.urlopen(OLLAMA_URL + path, timeout=10) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------- checks ---
# Deterministic checks run on every model answer so the reader can see what is
# grounded in the letter and what is not. A 4B model can slip; these catch it.

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9$]+", " ", s.lower()).strip()


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_DATE_RE = re.compile(
    rf"\b(?:\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|(?:{_MONTHS})\.?\s+\d{{1,2}},?\s+\d{{4}})",
    re.I,
)


def _parse_date(s: str) -> dt.date | None:
    s = s.strip().replace(",", "")
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d %Y", "%b %d %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def find_dates(letter: str) -> list[dict]:
    """Every explicit calendar date in the letter, with a little context."""
    out = []
    for m in _DATE_RE.finditer(letter):
        start = max(0, m.start() - 60)
        line_start = letter.rfind("\n", 0, m.start()) + 1
        ctx = letter[max(start, line_start): m.end() + 40].split("\n")[0].strip()
        out.append({"text": m.group(0), "iso": (d.isoformat() if (d := _parse_date(m.group(0))) else None), "context": ctx})
    return out


_ISSUE_LABELS = [
    # explicit issue-date labels first, then a bare "Date:" header
    re.compile(r"^\s*(?:(?:notice|statement|letter|issue|mailing)\s+date|date\s+of\s+(?:this\s+)?(?:notice|letter|statement))\s*[:\-]", re.I),
    re.compile(r"^\s*date\s*[:\-]", re.I),
]


def letter_date(letter: str) -> dt.date | None:
    """The date the letter was issued, from an issue-date header line only."""
    lines = letter.splitlines()
    for label in _ISSUE_LABELS:
        for line in lines:
            if label.search(line) and (m := _DATE_RE.search(line)) and (d := _parse_date(m.group(0))):
                return d
    return None


_DAYS_RE = re.compile(r"(\d+)\s*(?:\(\d+\)\s*)?(calendar\s+|business\s+|working\s+)?days?\b", re.I)
# The time limit must be counted from this letter's own date...
_ANCHOR_RE = re.compile(
    r"\b(?:of|from|after)\s+(?:the\s+date\s+of\s+)?(?:this|the)\s+(?:notice|letter|statement)\b(?!\s+of\b)"
    r"|\b(?:of|from|after)\s+the\s+(?:notice|statement|letter)\s+date\b", re.I)
# ...and not from some other event whose date we don't know.
_OTHER_ANCHOR_RE = re.compile(
    r"\b(?:of|from|after)\s+(?:the\s+)?(?:date\s+of\s+)?(?:(?:your|our|its)\s+)?"
    r"(?:receipt|receiving|delivery|mailing|first|discharge|denial|decision|service)"
    r"|notice\s+of\s+action|\bafter\s+you\b|\bthe\s+day\s+you\b", re.I)


def computed_deadline(quote: str, rule: str, issued: dt.date | None) -> tuple[dt.date | None, str | None]:
    """Turn 'within N days of this notice' into a date, using only the verified quote.
    Returns (date, reason-not-computed)."""
    if not issued:
        return None, "no issue date found in the letter"
    m = _DAYS_RE.search(quote)
    if not m:
        return None, None
    if (m.group(2) or "").lower().startswith(("business", "working")):
        return None, "business days: count them yourself"
    if not _ANCHOR_RE.search(quote) or _OTHER_ANCHOR_RE.search(quote):
        return None, "counted from a date that is not in this letter"
    rule_days = {int(x.group(1)) for x in _DAYS_RE.finditer(rule)}
    if rule_days and int(m.group(1)) not in rule_days:
        return None, "the model's rule does not match the letter's wording"
    return issued + dt.timedelta(days=int(m.group(1))), None


def readability_grade(text: str) -> float | None:
    """Flesch-Kincaid grade level (heuristic syllable count)."""
    sentences = [s for s in re.split(r"[.!?]+\s", text) if s.strip()]
    words = re.findall(r"[A-Za-z']+", text)
    if not sentences or len(words) < 10:
        return None

    def syl(w: str) -> int:
        w = w.lower().strip("'")
        groups = re.findall(r"[aeiouy]+", w)
        n = len(groups)
        if w.endswith("e") and n > 1 and not w.endswith(("le", "ee")):
            n -= 1
        return max(1, n)

    syllables = sum(syl(w) for w in words)
    return round(0.39 * len(words) / len(sentences) + 11.8 * syllables / len(words) - 15.59, 1)


def tidy(result: dict) -> None:
    """Small fixes that do not change meaning: drop self-numbering, merge duplicate phones."""
    for a in result.get("actions", []):
        # only explicit list markers ("1. ", "2) ", "3 — ", "Step 4: "), never "30 days ..."
        a["step"] = re.sub(r"^\s*(?:step\s+\d+\s*[.):\-—]?|\d+\s*(?:[.):]|\s[-—]))\s+", "", a.get("step", ""), flags=re.I)
    merged: dict[str, dict] = {}
    for c in result.get("contacts", []):
        key = _digits(c.get("phone", "")) or c.get("who", "")
        if key in merged:
            if c.get("why") and c["why"] not in merged[key]["why"]:
                merged[key]["why"] += " " + c["why"]
        else:
            merged[key] = dict(c)
    result["contacts"] = list(merged.values())


def check(letter: str, result: dict, language: str = "en") -> dict:
    """Ground the model answer against the letter text."""
    nl = _norm(letter)
    letter_digits = _digits(letter)
    issued = letter_date(letter)

    for d in result.get("deadlines", []):
        quote = d.get("quote", "")
        q = _norm(quote)
        d["quote_found"] = bool(q) and q in nl
        date_txt = d.get("date", "").strip()
        if date_txt and not _DATE_RE.search(date_txt):
            # the model put a rule like "30 days" in the date field
            d["rule"] = d.get("rule") or date_txt
            d["date"] = date_txt = ""
        d["date_found"] = bool(date_txt) and (_norm(date_txt) in nl)
        # An explicit date counts only if the verified quote itself contains it.
        quote_dates = {_parse_date(x.group(0)) for x in _DATE_RE.finditer(quote)} if d["quote_found"] else set()
        parsed = _parse_date(m.group(0)) if date_txt and (m := _DATE_RE.search(date_txt)) else None
        d["date_supported"] = bool(parsed) and parsed in quote_dates
        d["computed_date"] = d["not_computed_reason"] = None
        due = parsed if d["date_supported"] else None
        if not date_txt and d["quote_found"]:
            due, d["not_computed_reason"] = computed_deadline(quote, d.get("rule", ""), issued)
            if due:
                d["computed_date"] = due.strftime("%B %-d, %Y")
        d["days_left"] = (due - dt.date.today()).days if due else None

    for c in result.get("contacts", []):
        p = _digits(c.get("phone", ""))
        c["phone_found"] = (not p) or (len(p) >= 3 and p in letter_digits)

    explicit = find_dates(letter)
    used = {_norm(d.get("date", "")) for d in result.get("deadlines", [])}
    used_quotes = " ".join(_norm(d.get("quote", "")) for d in result.get("deadlines", []))
    missed, seen = [], set()
    for x in explicit:
        key = _norm(x["text"])
        if key in used or key in used_quotes or key in seen or (issued and x["iso"] == issued.isoformat()):
            continue
        seen.add(key)
        missed.append(x)

    summary_text = " ".join(result.get("summary", []))
    first = result.get("summary_first_draft")
    flags = {
        "first_draft_grade": readability_grade(" ".join(first)) if first and language == "en" else None,
        "letter_date": issued.isoformat() if issued else None,
        "summary_grade": readability_grade(summary_text) if language == "en" else None,
        "letter_grade": readability_grade(letter),
        "dates_in_letter": explicit,
        "dates_not_in_deadlines": missed,
        "ungrounded_quotes": sum(1 for d in result.get("deadlines", []) if not d["quote_found"]),
        "unsupported_dates": sum(1 for d in result.get("deadlines", []) if d.get("date") and not d["date_supported"]),
        "ungrounded_phones": sum(1 for c in result.get("contacts", []) if not c["phone_found"]),
    }
    return flags


# ------------------------------------------------------------------ main ---

def simplify_summary(sentences: list[str], lang: str, letter: str) -> tuple[list[str], dict | None]:
    """Second, short model pass: rewrite only the summary in simpler words.
    Falls back to the first draft if the rewrite drops or invents a number."""
    resp = _post("/api/chat", {
        "model": MODEL,
        "messages": [{"role": "user", "content": SIMPLIFY_PROMPT.format(
            language=lang, sentences="\n".join(f"- {x}" for x in sentences))}],
        "format": SIMPLIFY_SCHEMA, "stream": False, "think": False, "options": OPTIONS, "keep_alive": "30m",
    })
    try:
        new = json.loads(resp["message"]["content"])["summary"]
    except (KeyError, json.JSONDecodeError):
        return sentences, resp
    nums = lambda t: set(re.findall(r"\$?\d[\d,./:]*\d|\d", t))  # noqa: E731
    before, after = nums(" ".join(sentences)), nums(" ".join(new))
    if not after <= nums(letter) | before:  # a number appeared that is not in the letter
        return sentences, resp
    if not before <= after:  # a date, amount or phone number was dropped
        return sentences, resp
    return new, resp


def explain(letter: str, language: str = "en", note: str = "", simplify: bool = True) -> dict:
    letter = letter.strip()
    if len(letter) < 40:
        raise ValueError("Please paste the full letter text (at least a few sentences).")
    if len(letter) > 20000:
        raise ValueError("This letter is very long. Paste one letter at a time (under 20,000 characters).")
    lang = LANGUAGES.get(language, "English")
    note_block = f"\nMy situation (use this for the reply draft): {note.strip()}\n" if note.strip() else ""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(language=lang, note_block=note_block, letter=letter)},
    ]
    t0 = time.time()
    resp = _post("/api/chat", {
        "model": MODEL,
        "messages": messages,
        "format": SCHEMA,
        "stream": False,
        "think": THINK,
        "options": OPTIONS,
        "keep_alive": "30m",
    })
    raw = resp.get("message", {}).get("content", "")
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ModelError(f"Model returned invalid JSON: {raw[:300]}") from e
    passes = [resp]
    if simplify and result.get("summary"):
        result["summary_first_draft"] = result["summary"]
        result["summary"], resp2 = simplify_summary(result["summary"], lang, letter)
        if resp2:
            passes.append(resp2)
    wall = time.time() - t0
    for key, default in (("summary", []), ("actions", []), ("deadlines", []), ("contacts", []),
                         ("rights", []), ("questions_to_ask", [])):
        result.setdefault(key, default)
    tidy(result)
    flags = check(letter, result, language)
    out_tok = sum(p.get("eval_count") or 0 for p in passes)
    eval_ns = sum(p.get("eval_duration") or 0 for p in passes)
    stats = {
        "wall_seconds": round(wall, 1),
        "model_calls": len(passes),
        "prompt_tokens": sum(p.get("prompt_eval_count") or 0 for p in passes),
        "output_tokens": out_tok,
        "tokens_per_second": round(out_tok / (eval_ns / 1e9), 1) if eval_ns else None,
        "load_seconds": round(sum(p.get("load_duration", 0) for p in passes) / 1e9, 1),
    }
    return {
        "result": result,
        "checks": flags,
        "stats": stats,
        "thinking": resp.get("message", {}).get("thinking"),
        "raw": raw,
        "language": language,
        "model": MODEL,
        "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def ocr_image(path: str) -> str:
    """Offline OCR for a photo of a letter, if Tesseract is installed."""
    exe = shutil.which("tesseract")
    if not exe:
        raise ModelError("Photo reading needs Tesseract (brew install tesseract). "
                         "Or copy the text from the photo with Live Text and paste it.")
    out = subprocess.run([exe, os.path.realpath(path), "-", "--psm", "4"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if out.returncode != 0:
        raise ModelError("Could not read text from the image: " + out.stderr[:200])
    return out.stdout.strip()


def to_markdown(data: dict) -> str:
    """Human-readable report (used by the CLI and saved sample outputs)."""
    r, c, s = data["result"], data["checks"], data["stats"]
    L = [f"# PlainLetter: {r.get('letter_type', 'Letter')}", ""]
    if r.get("sender"):
        L.append(f"**From:** {r['sender']}  ")
    if r.get("money"):
        L.append(f"**Money:** {r['money']}  ")
    L += ["", "## 1. What this letter means", ""]
    L += [f"- {x}" for x in r["summary"]]
    if c.get("summary_grade") is not None:
        L += ["", f"_Reading level of this summary: grade {c['summary_grade']} (first draft before the simplify pass: grade {c.get('first_draft_grade')}; letter itself: grade {c['letter_grade']}). Flesch-Kincaid, computed by PlainLetter._"]
    L += ["", "## 2. What you need to do", ""]
    for i, a in enumerate(r["actions"], 1):
        L.append(f"{i}. {'**[URGENT]** ' if a.get('urgent') else ''}{a['step']} — {a['how']}")
    L += ["", "## 3. Deadlines", ""]
    for d in r["deadlines"]:
        when = d.get("date") or (f"{d.get('rule')} → about **{d['computed_date']}** (computed by PlainLetter from the letter date; double-check)" if d.get("computed_date") else d.get("rule"))
        mark = "" if d.get("quote_found") else " ⚠️ quote not found word-for-word in letter"
        if d.get("date") and not d.get("date_supported"):
            mark += " ⚠️ this date is not in the quoted text, check the letter"
        if d.get("not_computed_reason"):
            mark += f" (date not counted: {d['not_computed_reason']})"
        if d.get("days_left") is not None and d["days_left"] < 0:
            mark += f" ⚠️ this date may already have passed (as of {data['created'][:10]})"
        L.append(f"- **{d['what']}**: {when}  \n  > \"{d.get('quote', '')}\"{mark}")
    if c.get("dates_not_in_deadlines"):
        L += ["", "_Other dates in the letter (check if any matter):_ " + "; ".join(f"{x['text']} ({x['context']})" for x in c["dates_not_in_deadlines"])]
    L += ["", "## 4. Who to call", ""]
    for x in r["contacts"]:
        mark = "" if x.get("phone_found") else " ⚠️ number not found in letter"
        L.append(f"- **{x['who']}** {x['phone']}{mark} — {x['why']}")
    if r.get("rights"):
        L += ["", "### Help and rights mentioned in the letter", ""] + [f"- {x}" for x in r["rights"]]
    if r.get("questions_to_ask"):
        L += ["", "### Questions you could ask", ""] + [f"- {x}" for x in r["questions_to_ask"]]
    L += ["", "## 5. Reply draft", "", f"**Subject:** {r.get('reply_subject', '')}", "", "```text", r.get("reply_draft", ""), "```", ""]
    L += ["---", f"_Generated locally by {data['model']} via Ollama in {s['wall_seconds']} s "
          f"({s['output_tokens']} output tokens, {s['tokens_per_second']} tok/s) on {data['created']}. "
          "Not legal, medical, or financial advice. Check every date and number against the original letter, "
          "and ask a professional or the agency before acting on real claims._", ""]
    return "\n".join(L)
