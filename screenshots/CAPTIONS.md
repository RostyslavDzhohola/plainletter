# PlainLetter: illustrated demo

All screenshots show the app running locally on an Apple M1 (16 GB) with `SparkLLM/Spark-X2.6-4B` (BF16) in Ollama 0.40.6. Every result is a live model run; the JSON the page received for each run is saved next to it (`NN-response.json`). Letters are synthetic. Captured with a headless browser on 2026-10-25.

| # | File | Caption |
|---|---|---|
| 1 | `01-start.png` | **Start screen.** Paste a letter or read a photo of one, add an optional note about your situation, and choose English, Spanish or Chinese. The green banner confirms the model runs on this computer (`SparkLLM/Spark-X2.6-4B · 4.1B · BF16`). |
| 2 | `02-letter-pasted-running.png` | **Running locally.** The synthetic hospital bill is pasted and Spark-X2.6-4B is reading it on the laptop. Nothing is uploaded. |
| 3 | `03-hospital-results.png` | **Hospital bill in plain words** (180 s). Summary at grade 4.8 (the letter: grade 12), the one urgent step, the deadlines with quotes found in the letter (including "30 days of the statement date", counted as about Nov 2, 2026), one number to call, and a reply asking about a payment plan and financial assistance. |
| 4 | `04-denial-deadlines.png`, `04b-denial-deadlines-closeup.png` | **Insurance denial: deadlines** (191 s; note: "My back pain is getting worse and I want to appeal."). "Within 180 calendar days" becomes about March 28, 2027; the 14-day peer-to-peer window becomes October 13, 2026 and is flagged **may have passed**. |
| 5 | `05-benefits-reply.png`, `05b-benefits-call-and-reply.png` | **Food benefits renewal: who to call and a reply** (247 s). Four dated deadlines with countdowns; the fair-hearing rule is *not* turned into a date because it counts from a different notice. Caseworker, fax and hearings numbers are all ✓ in the letter. Reply draft with [brackets]. |
| 6 | `06-mobile-spanish-bigtext.png`, `06b-mobile-spanish-deadlines.png`, `06c-mobile-spanish-reply.png` (`06-full.png` = whole page) | **Accessibility: phone, bigger text, Spanish** (268 s). The same benefits letter explained in Spanish with Spanish headings. Deadline quotes stay in English because they are copied word for word from the letter. |
