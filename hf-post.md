<!--
DRAFT, not posted. Suggested Discussion title:
HER Hack-Astron # 7 — PlainLetter: offline plain-language help for medical bills, insurance denials and benefits letters (Health + Accessibility)

Before posting: drag the screenshots from build/screenshots/ into the editor where the
[screenshot: ...] markers are (HF uploads them and inserts the image links), and fill in
the repository link. Then reply to https://github.com/XHToken/Spark-X2.6/issues/16 with the Discussion link.
-->

## Project name and track
Project name: **PlainLetter**
Track: **Health and well-being** + **Accessibility**

## Who this helps and what problem it solves
Target users: people who get official letters they can't easily read or act on: older adults, people with limited literacy or limited English, people with cognitive or visual disabilities, patients and caregivers under stress, and the community health workers, benefits navigators and librarians who help them.

Concrete scenario and problem: a hospital bill threatens collections in 120 days but buries a financial-assistance option in the fine print; an insurance denial gives 180 days to appeal and a 14-day window for a peer-to-peer review; a food-benefits notice says benefits stop "without further notice" if a form and a phone interview are missed. These letters read at a college level (our three samples score Flesch-Kincaid grade 12.0–12.8), and they are full of private health and money details that people shouldn't have to paste into a cloud chatbot.

Expected public benefit: fewer missed deadlines, appeals and assistance programs; people know who to call and what to say. Because the model runs locally, it can be used on a library or clinic computer, or on a personal laptop, with no account, no internet and no data leaving the machine.

## How Spark-X2.6-4B is used
Model source and revision: `SparkLLM/Spark-X2.6-4B` via Ollama (BF16, Ollama digest `44ca4d700630e9a402cb439007132da135b2ca5329985b7f8944d04b7d59f43a`); upstream Hugging Face `XHToken/Spark-X2.6-4B` at revision `66e3ae7bee54e0a523d692cb8ef841f35409807b`.

The model's role in the application: Spark-X2.6-4B does all of the language work, in two calls per letter:
1. **Explain**: reads the letter and fills a JSON schema (Ollama structured output): letter type, sender, key amount, plain-language summary, actions (most urgent first), deadlines each with an exact quote from the letter, contacts, rights/help mentioned, questions to ask, and a short reply/appeal draft (optionally tailored with a "your situation" note). Works in English, Spanish or Simplified Chinese.
2. **Simplify**: rewrites only the summary for a 6th-grade reader (≤12 words per sentence, numbers kept exactly).

Deterministic Python checks then ground the answer against the letter, shown as ✓/⚠ badges: deadline quotes must appear word-for-word, phone digits must appear in the letter, every explicit date is found by regex and unused ones are listed, "within N days of this notice" rules are converted to calendar dates from the letter's own date (but not rules counted from some other date), past dates are flagged, and Flesch-Kincaid grade is measured. If the simplify step introduces a number that is not in the letter, the first draft is kept.

Other models, tools, or services used, if any: no other model and no cloud service. Ollama (runtime), Python standard library, optional Tesseract for offline photo-to-text, browser speech synthesis for "Read aloud".

## Demo (required: video OR illustrated walkthrough)
Video link / embedded screenshots: illustrated walkthrough below; every result shown is real Spark-X2.6-4B output from the run, and the JSON each screenshot's run returned is saved next to it.

1. **Start screen.** Paste a letter (or read a photo), add an optional note, pick a language. The banner confirms the model is local: `SparkLLM/Spark-X2.6-4B · 4.1B · BF16`.
[screenshot: 01-start.png]

2. **Running locally.** The letter is processed on the laptop; the timer shows elapsed seconds (about 3–4 minutes on an M1 with BF16).
[screenshot: 02-letter-pasted-running.png]

3. **Hospital bill → plain language.** Summary at about grade 5 (the letter is grade 12), what to do, deadlines with quotes from the letter, one number to call, and a reply asking about a payment plan and financial assistance.
[screenshot: 03-hospital-results.png]

4. **Insurance denial → deadlines** (run with the note "My back pain is getting worse and I want to appeal."). "Within 180 calendar days" becomes about March 28, 2027; the 14-day peer-to-peer window becomes October 13, 2026 and is flagged *may have passed*. Each deadline shows its exact quote with a ✓ found-in-letter badge.
[screenshot: 04b-denial-deadlines-closeup.png]

5. **Food benefits renewal → who to call + reply.** Caseworker, fax and State Hearings Office numbers (all ✓ in letter), and a reply draft with [brackets] for what only the reader knows.
[screenshot: 05b-benefits-call-and-reply.png]

6. **Accessibility.** Phone-width layout, Bigger text, and the same benefits letter explained in Spanish, with Spanish headings (Read aloud and Print buttons at the top).
[screenshot: 06-mobile-spanish-bigtext.png] [screenshot: 06b-mobile-spanish-deadlines.png] [screenshot: 06c-mobile-spanish-reply.png]

Example input (synthetic, excerpt of sample 02):
> NOTICE OF ADVERSE BENEFIT DETERMINATION … the clinical criteria in Northstar Medical Policy MP-RAD-014 … were not met … Your appeal must be received within 180 calendar days from the date of this notice … Your provider may also request a peer-to-peer discussion with our medical director by calling (555) 010-7790 within 14 calendar days of this notice.

Application workflow and actual output (Spark-X2.6-4B, sample 02, after the simplify step):
> - Northstar Health Plan denied your MRI of the lumbar spine without contrast.
> - You can still get the service.
> - But the plan will not cover the cost without an approved authorization.
> - You must submit your standard appeal within 180 calendar days.
> - Or request an expedited appeal if your condition is urgent.
>
> **Deadline:** within 180 calendar days from the date of this notice → about **March 28, 2027** (computed by PlainLetter from the letter date) — “Your appeal must be received within 180 calendar days from the date of this notice.” ✓ found in letter

Full outputs for all three letters (Markdown + JSON with raw model output, checks and timings) are in `outputs/` of the project.

## How to reproduce
Code repository or runnable example, if available: [ADD LINK — the project zip / repository]. Pure Python standard library, no `pip install` needed.

Setup and run instructions:
```bash
ollama pull SparkLLM/Spark-X2.6-4B     # Ollama v0.34.1+, ~8.2 GB BF16
cd plainletter
python3 -m plainletter info             # model, precision, digest
python3 -m plainletter serve            # http://127.0.0.1:8765
python3 -m plainletter samples/02-insurance-denial.txt      # CLI
python3 scripts/run_samples.py          # regenerate outputs/
```

Runtime and versions: Ollama 0.40.6, Python 3.11.1, macOS 27.0.1.

Hardware and precision/quantization: Apple M1, 16 GB unified memory; BF16 (no quantization), 4.1B parameters, context window set to 8,192 tokens. Observed 6.6–6.8 output tokens/s, 179–248 s per letter (two model calls, ~1,100–1,600 output tokens).

Key prompts and inference settings: `temperature 0.2`, `top_p 0.95`, `top_k 0`, `seed 7`, `num_ctx 8192`, `num_predict 2048`, `think: false`, `format: <JSON schema>`. The system prompt tells the model to use only facts in the letter, never invent dates/amounts/phones, write at about a 6th-grade level, copy numbers exactly, give an exact quote for each deadline, put relative deadlines in a `rule` field instead of guessing a date, and not give legal or medical advice; it includes one short plain-language style example. Full prompts, schema and settings are in `plainletter/core.py` and `outputs/run-metadata.json`.

## Results and limitations
Observed results and how they were evaluated: 3 synthetic letters (hospital bill, insurance prior-authorization denial, food-benefits recertification), one run each with the final prompt. Measured by PlainLetter's deterministic checks plus a line-by-line read of each output against its letter:
- Reading level of the summary: grade 4.8 / 6.5 / 4.2 (letters: 12.0 / 12.0 / 12.8). The simplify step brought them down from 7.4 / 11.7 / 9.9.
- Deadline quotes found word-for-word in the letter: 3/3, 2/2, 5/5. Phone numbers found in the letter: 1/1, 4/4, 3/3. No invented numbers.
- All explicit due dates were found; relative deadlines were converted correctly (Mar 28, 2027; Oct 13, 2026; Nov 2, 2026), and rules counted from dates not in the letter were correctly left as rules.
- Prompt iteration on the same letters: the first prompt produced long, grade 9–10 copies of the letter (1,689 tokens, 273 s for the bill); one intermediate run returned no actions for the bill, fixed with `minItems` in the schema.
- Re-running sample 02 through the CLI later with the same seed and settings gave a byte-identical model answer.
- An independent AI code review (OpenAI Codex) found 8 bugs in the first version of the checks/CLI/server (e.g. a computed deadline could follow the model's paraphrase instead of the letter's quote; "30 days of receipt" was counted from the letter date). All were fixed and the checks re-applied to the same saved model answers; no deadline in the samples changed.
This is a 3-letter demo, not a benchmark; it shows the workflow works, not its error rate on real letters.

Failure cases and current limitations:
- Wrong actor: in the denial, the model tells the member to request the peer-to-peer call; the letter says the *provider* may request it.
- Imprecise wording: "They did not have your required therapy … records" (the letter says only ~3 of 6 required weeks were documented); "If you miss the call, contact your worker before 11/18" (should be "if you can't make the call").
- The hospital bill lists only one action; "apply for financial assistance" and "ask for an itemized bill" appear only under rights.
- Spanish (1 run on the benefits letter): dates, numbers, 5/5 deadline quotes and 3/3 phones verified, but it contains a non-word ("reserguar" for *reprogramar*), mixes tú/usted, and has one ungrammatical sentence and a stray English word. Needs review by a Spanish speaker.
- With Spanish/Chinese output the headings are translated, but small badges ("found in letter", "URGENT") are still English; quotes stay in the letter's language on purpose.
- Reply drafts need editing (e.g., "Dear [Patient Name]").
- Some jargon survives ("first post-discharge billing statement").
- Slow on a 2020 M1 laptop: ~3–4 minutes per letter in BF16. Quantized builds not tested.
- Flesch-Kincaid is a heuristic and is not computed for Spanish/Chinese; Chinese output and real scanned letters were not evaluated.
- Application boundary: PlainLetter is a reading aid. It does not decide whether a bill is right, whether someone qualifies, or what to do medically or legally. The app says so on every screen and in every report, and tells people to confirm with the sender, a benefits counselor, patient advocate or legal aid before acting; for urgent health needs, use the plan's expedited line or a clinician, and emergency services in an emergency.

## Contributors and disclosure
Individual / team: individual — Ros Dzhohola.

Contributor profiles and respective contributions: Ros Dzhohola ([ADD HF / GitHub profile]): concept, direction and submission.

AI-assisted development disclosure: the code, synthetic sample letters and documentation were written by an AI coding agent (Claude by Anthropic, in Claude Code) working for Ros Dzhohola; the screenshots were captured by another AI agent (OpenAI Codex) driving a headless browser; a Codex agent also reviewed the code. No AI persona is presented as a human participant. All model outputs shown were generated by Spark-X2.6-4B running locally.

Data sources and authorization, if applicable: no real letters or personal data. The three sample letters are synthetic and written for this project (fictional names, account numbers and 555-01xx phone numbers). Dependencies: Spark-X2.6-4B (Apache-2.0), Ollama, Python standard library, optional Tesseract OCR (Apache-2.0). Project license: MIT.
