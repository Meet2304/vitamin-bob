# Bob: the brain of Vitamin Bob

A patient with any phone gives a free missed call. Stuart (the telephony module) calls back. **Bob**
runs the conversation in Hindi or Gujarati and understands the spoken description **on-device with
Gemma 4**. It asks only the keypad questions it still needs, sets an urgency tier with
**transparent rules**, and routes to the **nearest clinic that is actually open**. The outcome is call
108, go to a named clinic now, or come at a booked time. Clinicians get an alert for every urgent or
uncertain case. A compact record goes to Central over SMS. No internet is needed at runtime.

Built for the World Bank × Hack-Nation *Small AI for Development* hackathon (health track).

## Quick start (Windows, offline at runtime)

```powershell
cd bob
uv venv --python 3.13 .venv; uv pip install --python .venv\Scripts\python.exe -r requirements.txt
# one-time, needs internet: prompt audio (Sarvam key in bob\.env) and the model files
.venv\Scripts\python tools\gen_prompts.py
#   llama.cpp b11382 win-cuda-13.4 + ggml-org/gemma-4-E2B-it-GGUF (Q8_0 + mmproj BF16), see "Model" below

tools\start_model.cmd                          # 1. Gemma 4 E2B on http://127.0.0.1:8300
.venv\Scripts\python -m vitamin_bob.server     # 2. Bob on http://127.0.0.1:8100, dashboard at /dashboard
.venv\Scripts\python -m fake_stuart run        # 3a. scripted calls through Bob (no phone needed), or
                                               # 3b. real Stuart (stuart/) on :8200
.venv\Scripts\python eval\run_eval.py --mode all   # evaluation per language, shown on the dashboard
```

Run these from the `bob\` folder with the virtualenv's Python (`.venv\Scripts\python`).
`python -m vitamin_bob.db --reset` recreates `data/bob.db` from `seed/demo_district.json`.
`python -m fake_stuart run --pace 1.5` slows the scripted calls so the dashboard can be watched live.
`python tools/try_questionnaire.py` plays a call through the laptop speakers, with the keyboard as the keypad.
`python tools/import_audio.py` converts recordings in `data/Patient/<lang>/` (m4a, mp3, ...) to test WAVs.

## What is where

| Path | Job | AI? |
|---|---|---|
| `vitamin_bob/server.py` | HTTP service: `/v1/events` (contract 0.2), dashboard API | No |
| `vitamin_bob/contract.py` | The contract as typed models; Bob and the fake Stuart both validate against it | No |
| `vitamin_bob/conversation.py` | The call as a state machine: one event in, one action list out, state in `bob.db` | No |
| `vitamin_bob/understand.py` | Gemma 4: audio → transcript → fixed form, evidence guard, fallbacks | **Yes** |
| `vitamin_bob/extract.py` | Evidence guard; keyword baseline and safety net (Hindi + Gujarati) | No |
| `vitamin_bob/protocol.py`, `rules.py` | Symptoms, red flags, deterministic tiers with reasons | No |
| `vitamin_bob/session.py` | Case state, which question to ask next, the raise-only guardrails | No |
| `vitamin_bob/clinics.py` | Clinic status, routing with failover, booking, queues | No |
| `vitamin_bob/alerts.py`, `sms_commands.py` | Urgent alerts, SMS acknowledgement, escalation; clinician SMS commands | No |
| `vitamin_bob/sync.py`, `stuart_client.py` | What goes to Central; durable outboxes to Stuart | No |
| `vitamin_bob/prompts.py`, `prompts/*.json` | Every sentence Bob says, as a list of pre-recorded clips | No |
| `vitamin_bob/dashboard.html` | One offline page polling `/api/state` every second | No |
| `fake_stuart/` | Drives Bob through 17 scripted calls and checks every message against the contract | No |
| `eval/` | 54 synthetic vignettes + 10 real recordings, per-language evaluation | — |

## The call

Language menu (Hindi 1, Gujarati 2). It repeats until a key is pressed, because Stuart can't tell
when the patient picks up; a known caller skips it. Then: who is sick (keypad) → "describe the
problem" (beep, up to 25 s) → Gemma understands → only the follow-up questions still needed (1 yes,
2 no, 3 don't know; days then #) → tier → route → outcome → hangup. Wrong keys and silence are
re-asked twice; after that the answer counts as "don't know", which keeps the case from looking
safer than it is. Prompts say "press 1" plainly and tell smartphone users to open the keypad.

| Tier | Patient hears | Also |
|---|---|---|
| EMERGENCY | Call 108 now (said twice) + case number | Alert to the nearest open clinic |
| HIGH / UNCERTAIN | Go now to *[clinic]*; the doctor will call you | Top of that clinic's queue + alert |
| MEDIUM | Booked at *[clinic]*, *today/tomorrow* at *hour* | Slot today or tomorrow |
| LOW | Booked at the next free slot | |

Every sentence is a list of fixed clips (`play` actions). The model never speaks. Clinic names, times
and case-code digits are separate clips placed at the end of a sentence, so word order never needs code.

## Guardrails (safe before clever)

- **The tier comes from rules, not the model.** `rules.py` is deterministic and explains every tier.
- **The model only fills a fixed form**, and every yes/no must quote words found in the transcript.
  A claim without evidence is dropped to "unknown" (shown on the dashboard as "dropped").
  **The bar is asymmetric:** a "yes" needs two words or a word naming the item; a "no", which could
  skip a red-flag question, must name the item *and* contain a negation. (Found in testing: on silent
  audio the model "transcribed" its own instruction and marked fever "no" by quoting one stray word.
  Bob now discards transcripts that echo the instruction, and a "no" like that no longer passes.)
- **The description may raise urgency, never silently lower it:**
  - a "no" on an emergency sign is always confirmed on the keypad;
  - **a duration heard in the description that is shorter than the HIGH threshold is confirmed on the keypad.**
    This is new; it fixed a missed urgent case where "17 days" was read as 7;
  - the keyword list may **add** findings the model missed (e.g. Gujarati "ખેંચ", fit), never remove them.
- **Unknown means a human decides.** Any open question that could hide an urgent case gives UNCERTAIN.
- **Any call that ends without a classification is UNCERTAIN** (never lower than what was known) with an alert.
- **An unacknowledged alert escalates:** the next open clinic on the patient's route, then the referral
  hospital, then the district contact, and it stays red on the dashboard until acknowledged.
- **If Bob ever produced an invalid action list**, the server replaces it with the bilingual fallback and a hangup.
- **Privacy:** raw data stays on Kevin; phone numbers are masked everywhere on screen (including inside
  SMS text); recordings are deleted once processed; sync records carry a keyed hash, never a number.

## Understanding on-device (Gemma 4)

Two passes with one local model through llama.cpp's `llama-server`:
1. **audio → transcript** (Gemma's audio encoder; thinking disabled);
2. **transcript → form**, locked by a grammar to at most 6 lines of `item|yes/no|days|evidence`,
   then the evidence guard and the raise-only keyword merge.

Pass 2 is exactly what the text evaluation measures. If the model is slow, down or wrong-shaped, Bob
falls back to the keyword matcher on whatever transcript it has: more keypad questions, never a
skipped safety check. The budget is 17 s of the contract's 20 s after `listen`.

**Model: Gemma 4 E2B, Q8_0, llama.cpp b11382 (CUDA 13.4), on the demo laptop** (Ryzen 7 6800H, 15 GB,
RTX 3050 Ti 4 GB). Measured on a 25 s clip:

| | Generation speed | Transcribe 25 s | Note |
|---|---|---|---|
| E4B Q8_0 | 5.9 tok/s (partly on CPU) | 14–18 s | too slow once the form is added |
| **E2B Q8_0** | **13–15 tok/s** | **5–7 s** | same word error as E4B on clean speech |

Gemma 4 "thinks" by default in llama-server, so Bob sends `enable_thinking: false`. Pass 2 went from
~14 s (pretty-printed JSON schema output) to 2–5 s with the compact grammar. Public phone-speech
benchmarks put Gemma E4B at about 9% word error in Hindi but 27% in Gujarati (Josh Talks "Voice of
India"); Whisper is no better in Gujarati. So expect more keypad questions in Gujarati, not less safety.

## Clinics and failover

`seed/demo_district.json` holds the hub, villages, clinics (hours, capacity), each village's clinics
ordered by travel time, clinicians' phones and the district contact. **All names and numbers are dummies.**
For real numbers (e.g. your own phone as the demo clinician), copy it to `seed/demo_district.local.json`,
edit that, and reset the database. Bob prefers the local file, and git ignores it, so personal numbers
never reach the public repository.

Status comes from three free or cheap inputs:
- **SMS commands** from a registered clinician number, in Latin letters so any phone can type them:
  `OPEN`, `CLOSED`, `FULL`, `BACK 14:00`, `ACK <code>`, `STATUS`. Each is confirmed with a short reply.
  One phone may serve several clinics (in the demo, one phone is every clinician): a plain command applies
  to its first clinic (Clinic A), and `CLOSED B` or `OPEN devgaon` names another. Numbers in the seed may
  be written with spaces or dashes; Bob compares them in E.164 form (`+15550100199`).
  Unregistered numbers are ignored with no reply, so strangers can't change routing or run up costs.
- **A free missed call** from a registered clinician means "on duty now" (`callback: false`).
- **A dashboard toggle.**

A status nobody confirmed in the last 12 h counts as `unknown`. Routing takes the first clinic on the
patient's village list that is open, recently confirmed, has capacity and is within 60 min; otherwise
the referral hospital. EMERGENCY is always 108. The dashboard shows why each earlier clinic was skipped.
Unknown callers use the hub's default village (a real deployment would map lines or ask on the keypad).

## Sync to Central

Bob decides **what** to sync; Stuart owns **how** (framing, encryption, acks, retries). Each payload is
compact JSON ≤ 200 bytes (worst case with every flag: under 200; optional fields are dropped first if ever needed), checked before queueing for size and phone-like digit runs.

| Kind | Fields |
|---|---|
| `triage` | `h` hub, `d` yymmdd, `tm` HHMM, `c` clinic, `r` tier E/H/U/M/L, `a` age i/c/a, `s` symptoms `"F3C?"`, `f` red flags `"CVFB"`, `u` unknowns, `q` keypad questions, `du` call seconds, `l` language, `o` 108/now/appt, `x` 1 if the call ended early, `pv` protocol, `mv` model, `pk` patient key |
| `clinic_status` | `h`, `c`, `st` o/c/f/u, `src` s(ms)/m(issed call)/d(ashboard), `d`, `tm` |
| `daily_summary` | `h`, `d`, `n` cases, `t` {E,H,U,M,L}, `ua` unacknowledged alerts, `q` avg questions |

The patient key is HMAC-SHA256(hub secret, phone), 64 bits in base32. A plain hash of a phone number is
weak (few possible numbers); a keyed one is only as strong as the secret, which stays on Kevin and Central.

## Evaluation

`python eval/run_eval.py --mode all`: the keyword baseline and Gemma on text for every vignette, and
Gemma on the real recordings through the full audio path. The simulated patient answers keypad
questions from ground truth. Results also appear on the dashboard.

| Set | Cases | Missed urgent | Emergency not to 108 | Tier accuracy | Uncertain rate | Keypad questions / call | Misreads | Understand time |
|---|---|---|---|---|---|---|---|---|
| keyword / hi / text | 43 | **0** | 0 | 93% | 14% | 6.65 | 6 | 0.0 s |
| keyword / gu / text | 21 | **0** | 0 | 95% | 10% | 5.71 | 2 | 0.0 s |
| gemma / hi / text | 43 | **0** | 0 | 93% | 7% | 5.6 | 8 | 5.8 s |
| gemma / gu / text | 21 | **0** | 0 | 95% | 5% | 4.67 | 2 | 4.8 s |
| audio / hi / real recordings | 5 | **0** | 0 | 100% | 0% | 5.8 | 2 | 8.4 s |
| audio / gu / real recordings | 5 | **0** | 0 | 100% | 0% | 6.0 | 1 | 7.4 s |

Run 2026-10-04 02:42 with Gemma 4 E2B Q8_0 on the demo laptop. What it shows:
- **No missed urgent case and no emergency sent to a clinic, in any set or language.**
- **Gemma halves the Uncertain rate** against the keyword baseline (Hindi 14% → 7%, Gujarati 10% → 5%) and
  saves about one keypad question per call. That's the work the model does, measured rather than asserted.
- **Gemma's misreads lean toward over-triage** (HIGH cases read as EMERGENCY), the safe direction.
  Its duration misreads ("17 days" heard as 2, "21 days" as 7, "10 times" taken as 10 days) were
  **caught by the duration guardrail**, so those cases still came out correctly.
- The keyword list added red flags Gemma missed (e.g. sunken eyes, unable to drink, blood in stool).
- The asymmetric evidence rule costs about one extra keypad question per call (correct "no"s with weak
  evidence are confirmed on the keypad); we accept that for never letting a fabricated "no" skip a red flag.

**What the data does not cover:** real patients; clinician-reviewed labels; regional dialects beyond the
team's voices; noisy phone lines (the recordings are phone-microphone audio, not a call path); conditions
outside fever, cough and diarrhoea (for example, blood in sputum is not in the protocol and was flagged
for clinician review). The vignettes and recordings were written and recorded by the team; reference
transcripts of the recordings were reconstructed by the team and should be checked.

## Adding a language, a clinic, a protocol version

- **Language** (e.g. Marathi): add an entry to `prompts/languages.json` (menu key, TTS voice), copy
  `prompts/hi.json` to `prompts/mr.json` and translate, run `tools/gen_prompts.py`. The generator refuses
  to run if any key is missing. For the keyword safety net, add words to `extract.KEYWORDS`.
- **Clinic:** add it to `seed/demo_district.json` (clinic, routes, clinicians), add `clinic_<id>` to every
  `prompts/<lang>.json`, regenerate prompts, and reset the database.
- **Protocol:** every triage stores `protocol_version` and `model_version`; bump `config.PROTOCOL_VERSION`.

## Data sources

- Danger signs and referral criteria: WHO IMCI (drafted by the team; **not yet clinician-reviewed**).
- Prompt audio: Sarvam Bulbul v3 (generated before the demo; files on disk at runtime).
- Model: Google Gemma 4 E2B/E4B instruct, GGUF builds by ggml-org; runtime llama.cpp.
- Gujarati text translated by the team; **needs a native speaker's check**.

## Cross-district patient history (design only, not built)

**Goal:** a patient who falls ill away from home still has their history at the clinic that sees them.

**Approach:** Central already receives compact triage records keyed by the patient key. A Kevin in
another district asks Central for a short summary by SMS through Stuart's data link (`kind:
"history_request"` with the patient key). Central replies with a few frames: the last 3–5 cases with
date, tier, red-flag codes and clinic. That costs a few SMS per lookup and takes minutes, not seconds,
so it **enriches the clinician's view after the call** and never delays triage. The tier is always
decided from the current call alone.

**The hard parts, honestly:**
- **Identity.** Phone numbers change and households share phones. India's ABHA health ID (Ayushman
  Bharat Digital Mission) is the right long-term key; its 14 digits can be typed on a keypad, at the cost
  of one more keypad step for patients who have one.
- **Key strength.** A hash of a phone number can be reversed by trying every number. A keyed hash
  needs the key shared across districts, so a leak of the key exposes every district.
  Pseudonymous IDs issued by Central, or ABHA, avoid this.
- **Consent.** India's Digital Personal Data Protection Act and ABDM's consent model govern sharing
  records across regions; a history lookup needs the patient's consent (for example, a keypad "press 1
  to let the clinic see your past visits"), and an audit trail.
- **Integration.** In reality Central should be the state health information system (an ABDM-registered
  HIE), not something we build; Bob's records are shaped so they could map onto it.

## Recorded changes from the brief

- **Model: E2B, not E4B**, after measuring both on the demo laptop (table above).
- **Pass 2 uses a compact grammar instead of a JSON schema**, for speed; it's just as strict.
- **New guardrails:** short durations from the description are confirmed on the keypad; evidence for a
  "no" must name the item and a negation; transcripts that echo the model's instruction are discarded.
- **Keyword list as a raise-only safety net** after Gemma, in Hindi and Gujarati.
- `callback_failed`, not each unanswered `call_ended`, raises the alert for unreachable patients
  (see `CONTRACT_NOTES.md`).
- **Languages live in `prompts/*.json`, clinics and routes in `seed/*.json`**, loaded into `bob.db`.
- **The Ollama dependency is replaced by llama.cpp's server**, which is Windows-native and supports Gemma 4 audio.
