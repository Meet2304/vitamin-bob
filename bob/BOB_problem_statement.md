# Problem statement 2 of 2: Bob (conversation, understanding, routing and decisions)

**For: the Claude Code agent, working on branch `bob`, only inside `bob/`.**
The other half of the system, Stuart, is being built at the same time by a Codex agent on branch `stuart`. Read the whole document, especially sections 5–7, before writing code.

## 1. The project in one paragraph

**Vitamin Bob** lets a patient with any phone, even a basic feature phone, reach primary care without paying anything and without internet. The patient gives a **missed call** (free, because the call never connects) to the district number. The district machine calls them back (the health system pays; receiving a call is free for the patient in India), offers a language menu, lets them describe their problem in their own words, asks a few yes/no follow-up questions on the keypad, classifies the case by urgency, and routes them to the **nearest clinic that is actually open**. The result is a booked appointment, an instruction to go to a clinic now, or an instruction to call 108 (India's ambulance line). Clinicians are alerted to every urgent or uncertain case. Clinics report their status to the district machine by SMS or a free missed call, and the district machine forwards compact case records to a central source of truth over SMS, so the system keeps working with no internet anywhere.

This is an entry for the **World Bank × Hack-Nation "Small AI for Development" hackathon (health track)**, and separately for a Gemma 4 hackathon. **Submission deadline: 8:00am ET, Sunday 4 October 2026.** The submission needs a working demo and a 2–5 minute video.

## 2. Names used everywhere

| Name | What it is |
|---|---|
| **Vitamin Bob** | The whole system |
| **Kevin** | A district hub machine. One Kevin serves **many clinics**. In the demo: Meet's laptop. Both modules run on Kevin. |
| **Stuart** | The telephony and messaging module: phone lines, missed calls, the callback queue, audio on calls, SMS in and out, and the SMS data link to Central. **Built by the Codex agent.** |
| **Bob** | The brain module: conversation, language, understanding (Gemma 4), urgency, clinic routing and failover, appointments, alerts, what gets synced, and the dashboard. **Built by the Claude Code agent.** |
| **Kevin's line** | The phone whose SIM receives missed calls and SMS and places callbacks. In the demo it is **Meet's Android phone**, connected to the laptop by USB, which is **also Clinic A's clinician phone**. |
| **Central** | The higher source of truth above all Kevins (in reality a state-level system). In the demo, a small receiver that decodes the records Kevin sends. |
| **Meet** | The human designing the system, owner of the repo, the only person who changes the contract, and the one who merges. |

## 3. The live demo we are building towards

Devices:
- **Laptop = Kevin, running Windows.** Runs Stuart and Bob, the local model, and the dashboard. No internet during the demo. Everything on Kevin must run on Windows.
- **Meet's Android phone = Kevin's line and Clinic A's clinician phone.** Connected to the laptop by USB. It is the only device that must be Android.
- **The patient's phone = any phone.** In the demo, a friend's iPhone or a temporary Android. **Everything on the patient side must be OS-agnostic**: no app, nothing installed; the patient only places a call, answers a call, presses keys and speaks. iPhone users must open the in-call keypad, so the keypad prompts should say so in plain words.
- **Other clinics** (Clinic B, C) exist as data on Kevin. Their status changes come from SMS, a missed call, or a dashboard toggle.

The demo, end to end:
1. The patient gives a missed call to Kevin's line. It appears on the dashboard within seconds.
2. Stuart queues it and calls the patient back.
3. A bilingual language menu (**Hindi or Gujarati**); the patient presses a key.
4. In that language: who is sick (keypad), then "describe the problem" (spoken, up to about 25 seconds).
5. Bob understands the description with an on-device Gemma 4 model and asks only the follow-up yes/no questions it still needs (keypad: 1 yes, 2 no, 3 don't know).
6. Bob classifies the case (EMERGENCY / HIGH / UNCERTAIN / MEDIUM / LOW), picks the nearest open clinic with capacity, tells the patient the outcome, and hangs up.
7. The dashboard shows the call timeline, transcript, what was understood and why, the tier, and either an appointment in that clinic's queue or an urgent alert a clinician must acknowledge.
8. **Failover:** Clinic A is marked closed (by an SMS command, or a dashboard toggle standing in for one). The next patient is routed to Clinic B, and the dashboard says why.
9. **Sync:** the case record is packed into an SMS-sized payload and sent towards Central; Central's view shows it arriving.

## 4. Non-negotiable constraints

- **The patient never pays.** Missed call in, callback out. The patient never has to send an SMS. Everything that costs money (callbacks, alert SMS, sync SMS) is paid by the health system, and the design keeps those costs small and visible.
- **Offline.** No internet at runtime on any device. Cloud services may be used **before** the demo to prepare assets (for example generating prompt audio), never during operation.
- **Works on a device the user already has:** any phone that can make and receive calls.
- **Small models** that fit on a laptop or could be side-loaded over a weak connection.
- **Two languages: Hindi and Gujarati.** Adding a third must be data and audio files, not code.
- **No diagnosis, no medical advice.** Bob routes; it does not diagnose. Everything Bob *says* to a patient is a fixed, pre-recorded prompt. The model listens and fills a form; it never generates speech.
- **Human in the loop.** A person makes the final call on anything urgent or uncertain. "Not sure → ask a person" beats guessing. This is a pass/fail criterion in judging.
- **Privacy.** Raw patient data stays on Kevin. Phone numbers are masked on screen and never sent to Central in the clear. Recordings are deleted once processed. Anything sent by SMS is encrypted.

## 5. Priorities, because the time is short

Build in this order. A lower priority never delays a higher one.

| Priority | Scope |
|---|---|
| **P0** | The full call flow in both languages, from missed call to tier, outcome prompt and dashboard, on the simulator line and then the real phone |
| **P1** | Many clinics per Kevin: clinic status (SMS commands, free missed-call check-ins, dashboard), routing to the nearest open clinic, failover, and alert escalation |
| **P2** | The SMS data link to Central: compact encrypted records, acknowledgements and retries, and a Central receiver showing what arrived |
| **Design only** | Looking up a patient's history from another district (section 7 of Bob's brief describes the intended approach); no code tonight |

## 6. How the two of you work in parallel

- The repo has one `main` branch. Meet commits this brief, the other brief, and nothing else to `main` before you start.
- **Codex works on branch `stuart` in its own worktree; Claude Code works on branch `bob` in its own worktree.** Each pushes only its own branch. Meet merges both into `main`.
- **Directory ownership is strict, so the merge has no conflicts:**
  - Codex may create and change files **only inside `stuart/`**.
  - Claude Code may create and change files **only inside `bob/`**.
  - **Neither agent edits anything at the repo root or in the other's directory**, including the root README, root `.gitignore`, or any shared config. Put your own `.gitignore`, dependency file and README inside your directory.
  - Runtime data lives in `data/` at the repo root and is never committed (Meet adds it to the root `.gitignore`). Both modules may read and write there only as described in the contract.
- **You cannot talk to each other.** Everything you may assume about the other module is in the contract below. If you need the contract to change, **do not change it yourself**: write the proposal in `stuart/CONTRACT_NOTES.md` or `bob/CONTRACT_NOTES.md` and keep working against the current version. Meet will decide and tell both of you.
- **Build a mock of the other module first**, so you can finish and test your side alone. Integration happens only after merge.
- Technical choices inside your module are **yours and may change**. The suggestions in your brief are the current direction, not a specification. Record any significant change in your module README so Meet and the other agent's next session can see it.
## 7. The contract between Stuart and Bob (version 0.2)

This section is **word-for-word identical in both briefs**. Only Meet changes it.

### 7.1 Transport and basics

- Both modules run on Kevin as separate processes and talk over **HTTP + JSON on localhost**.
  - Bob listens on `http://127.0.0.1:8100` (env `VB_BOB_URL`).
  - Stuart listens on `http://127.0.0.1:8200` (env `VB_STUART_URL`).
- Every request carries the header `X-VB-Contract: 0.2`.
- Both expose `GET /v1/health` → `{"ok": true, "module": "bob" | "stuart"}`.
- IDs are strings and globally unique (UUID or ULID). Timestamps are ISO 8601 with timezone. Phone numbers are E.164 (`+14125550123`).
- Shared data directory: env `VB_DATA_DIR`, default `<repo root>/data`.
  - `data/recordings/` is written by Stuart (what the patient said).
  - `data/prompts/` is written by Bob (what Bob says). Stuart only reads it.
- **Audio format for every file in both directions: WAV, 16 kHz, mono, 16-bit PCM.** Paths in messages are absolute.

### 7.2 Events: Stuart → Bob

Stuart sends every event as `POST {VB_BOB_URL}/v1/events`. Every event has `event_id`, `type`, and `at`. **Bob must treat a repeated `event_id` as a duplicate and return the same response.** Stuart retries a failed POST up to 3 times with the same `event_id`.

| `type` | Extra fields | When | Bob's response |
|---|---|---|---|
| `missed_call` | `missed_call_id`, `phone`, `line_id` | A missed (or auto-rejected) call is detected | `{"ack": true, "callback": true \| false}`. **Stuart only queues a callback when `callback` is true.** Bob says false for, e.g., a registered clinician checking in. |
| `call_started` | `call_id`, `missed_call_id`, `phone`, `line_id` | A callback has been placed. **Stuart cannot reliably tell whether the patient has picked up yet, so Bob's first prompt must survive being partly missed** (for example, a menu that repeats until a key is pressed). | An **action list** (7.3) |
| `action_result` | `call_id`, `action_id`, `status`, plus `digits` / `recording_path` / `duration_ms` when relevant | The last action of a list has finished | The next **action list** |
| `call_ended` | `call_id`, `reason`: `completed` \| `caller_hung_up` \| `no_answer` \| `failed` | The call is over, for any reason | `{"ack": true}` |
| `callback_failed` | `missed_call_id`, `phone`, `attempts` | Stuart gave up calling a patient back | `{"ack": true}` |
| `sms_received` | `message_id`, `phone`, `line_id`, `text` | An SMS arrived on any of Kevin's lines | `{"ack": true}` |
| `sms_status` | `message_id`, `status`: `sent` \| `delivered` \| `failed` | An SMS Bob asked for changed state | `{"ack": true}` |
| `sync_status` | `record_id`, `status`: `queued` \| `sent` \| `acked` \| `failed` | A sync record changed state | `{"ack": true}` |

`action_result.status` is one of: `ok`, `timeout` (no input before the timeout), `no_input`, `caller_hung_up`, `error`.

### 7.3 Call actions: Bob → Stuart (in the response to a call event)

An action list is `{"actions": [ ... ]}`. **Rule: zero or more `play` actions, followed by exactly one of `keypad`, `listen`, or `hangup`.** Stuart runs them in order and then sends **one** `action_result` for the final action. (A `hangup` gets no `action_result`; Stuart sends `call_ended` instead.)

| Action | Fields | Stuart's job |
|---|---|---|
| `play` | `action_id`, `audio_path` | Play the WAV into the call |
| `keypad` | `action_id`, `max_digits`, `timeout_ms`, `terminator` (`"#"` or `null`) | Collect keypad presses; return them in `digits` |
| `listen` | `action_id`, `max_ms` (≤ 25000), `end_silence_ms` | Record the caller until silence or the limit; save to `data/recordings/`; return `recording_path` and `duration_ms` |
| `hangup` | `action_id` | End the call |

Timing:
- **Bob should answer each event within 2 seconds**, except straight after a `listen`, when understanding the recording may take **up to 20 seconds**.
- While waiting for any action list, **Stuart plays a neutral hold tone** into the call after 1.5 seconds. Stuart owns this tone.
- If Bob has not answered in 30 seconds, or is unreachable, Stuart plays `data/prompts/system/fallback.wav` (Bob provides it: a bilingual "please hold; a clinician will call you back"), hangs up, and sends `call_ended` with `reason: failed`. Bob treats any call that ends without a classification as **UNCERTAIN** and raises a clinician alert.

### 7.4 Messaging: Bob → Stuart

**Send an SMS:** `POST {VB_STUART_URL}/v1/sms` with `{"message_id", "to", "text", "priority": "urgent" | "normal" | "bulk"}` → `{"queued": true}`. Idempotent by `message_id`.
- Bob uses it for clinician alerts, clinic confirmations and replies to clinic commands. **Bob never sends an SMS that the patient must reply to.**
- Stuart sends **urgent before normal before bulk**, sends bulk only when a line is idle, handles splitting into segments, and enforces a configurable per-line daily cap (default 100) to keep costs bounded. If the cap blocks a message, Stuart reports `sms_status: failed`.

**Sync records to Central:** `POST {VB_STUART_URL}/v1/sync` with `{"records": [{"record_id", "kind", "payload"}]}` → `{"queued": true}`. Idempotent by `record_id`.
- `kind` is a short string chosen by Bob (e.g. `triage`, `clinic_status`, `daily_summary`). `payload` is a JSON object of **at most 200 bytes when serialised compactly**; Bob keeps field names short and never includes raw phone numbers, names or free text.
- **Stuart owns the SMS data link:** packing records into SMS-sized frames, compression, encryption with a pre-shared key, sequence numbers, acknowledgements from Central, retransmission, and sending at `bulk` priority. Bob only says *what* to sync; Stuart guarantees it arrives exactly once.
- Stuart reports progress with `sync_status` events.

### 7.5 Status: Bob reads from Stuart

`GET {VB_STUART_URL}/v1/status` returns what the dashboard needs:

```json
{
  "lines": [{"line_id": "...", "label": "Kevin line 1", "msisdn": "+1412...", "state": "idle | ringing | in_call | offline"}],
  "queue": [{"missed_call_id": "...", "phone": "+91...", "received_at": "...", "status": "queued | calling | done | failed", "attempts": 0}],
  "active_calls": [{"call_id": "...", "phone": "...", "line_id": "...", "started_at": "...", "current_action": "play | keypad | listen | waiting_for_bob"}],
  "sms": {"sent_today": 0, "segments_today": 0, "failed_today": 0, "queued": {"urgent": 0, "normal": 0, "bulk": 0}},
  "sync": {"queued": 0, "sent": 0, "acked": 0, "failed": 0}
}
```

Bob may poll this about once a second. Masking phone numbers on screen is Bob's job.

### 7.6 Ownership boundaries

| Concern | Stuart | Bob |
|---|---|---|
| Phones, SIMs, ADB, audio devices | Owns | Never touches |
| Missed-call detection, callback queue, retries, line pool | Owns (callback only if Bob says `callback: true`) | Decides who gets a callback |
| Hold tone | Owns | — |
| Recordings | Writes them | Reads them, then **deletes** them once processed |
| Prompts, languages, wording, menus | Never decides | Owns; files in `data/prompts/` |
| Health logic, tiers, clinics, routing, appointments, alerts, patients | Never knows | Owns |
| SMS content and meaning (including clinic commands) | Never interprets | Owns |
| SMS transport, priority, caps, segments | Owns | Asks via `/v1/sms` |
| What to sync to Central | — | Owns |
| How sync reaches Central (framing, encryption, acks, retries) and the Central receiver | Owns | Asks via `/v1/sync` |
| Dashboard | Provides `/v1/status` | Owns and serves it |
| Database | `stuart.db` only | `bob.db` only. **No module reads the other's database.** |

### 7.7 What each side's mock must do

- **Codex builds a fake Bob** that answers events with a scripted action list (play a test WAV, ask for one key, listen once, hang up), says `callback: true` to every missed call, sends a test SMS and a few test sync records, and validates every request against this contract.
- **Claude Code builds a fake Stuart** that drives Bob through scripted calls (sending events, using pre-recorded WAVs as "the patient", typing digits), injects `sms_received` clinic commands, accepts `/v1/sms` and `/v1/sync` calls, serves a fake `/v1/status`, and validates everything Bob sends against this contract.
- After merge, Meet will first run **real Stuart against real Bob on Stuart's simulator line** (laptop mic, speaker and keyboard instead of a phone), then on the real phone.

## 8. Your vision: Bob

Bob is the part of Vitamin Bob that a frightened parent actually talks to. In their own language it asks who is sick, listens to how they describe the problem, asks only the few questions that matter, and tells them clearly what to do next: call 108 now, go to a named clinic now, or come at a booked time. For the district, Bob turns a crowded, unrecorded stream of complaints into prioritised queues across many clinics, routes around clinics that are closed or full, and sends a compact record of every case upward so the health system can see what is happening.

Bob must be **safe before it is clever**:
- The tier comes from transparent rules, not from a model's opinion.
- The model only fills a fixed form, and every answer it gives must be backed by words the patient actually said; otherwise it is "unknown".
- The description may **raise** urgency but never silently lower it: a "no" on an emergency sign is always confirmed on the keypad.
- Anything that could hide an urgent case becomes UNCERTAIN and goes to a human.
- An urgent alert that no clinician acknowledges is escalated, never silently dropped.

Bob must also **scale**: languages, clinics, districts and protocol versions are data, so adding Marathi, a new clinic or a second district means adding rows and audio files, not code.

## 9. What you are expected to deliver

By the end, the `bob/` directory contains a service that, running on Kevin:

**P0: the call**
1. **Implements the contract** (section 7): accepts events, returns valid action lists, handles duplicates, decides `callback: true/false` for each missed call, and treats any call that ends without a classification as UNCERTAIN with an alert.
2. **Runs the call conversation:** bilingual language menu, **Hindi or Gujarati** (repeats until a key is pressed; a known caller may skip it) → who is sick (keypad) → describe the problem (`listen`, about 25 seconds) → understanding → only the follow-up questions still needed (keypad: 1 yes, 2 no, 3 don't know) → outcome prompt → hangup. Keypad prompts must work for any phone; say "press 1" plainly and remind smartphone users to open the keypad.
3. **Understands the description on-device** with **Gemma 4** (E2B or E4B), producing the fixed symptom form with schema-locked output, plus the transcript.
4. **Classifies with deterministic rules** into EMERGENCY / HIGH / UNCERTAIN / MEDIUM / LOW, with human-readable reasons.
5. **Acts on the tier:** EMERGENCY → "call 108 now" plus an alert; HIGH and UNCERTAIN → "go to [clinic] now" plus an alert; MEDIUM → same- or next-day appointment; LOW → next available slot. Urgent cases go to the top of the clinic's queue.
6. **Serves the dashboard** (a local web page, e.g. `http://127.0.0.1:8100/dashboard`): the missed-call and callback queue (from Stuart's `/v1/status`), live calls, each call's timeline and transcript, what was understood and from where (description or keypad), the tier and its reasons, each clinic's status and appointment queue ordered by priority, and urgent alerts that a clinician must **acknowledge**. Phone numbers masked.
7. **Evaluation** per language: missed urgent cases (target 0), emergencies sent to a clinic instead of 108, tier accuracy, **Uncertain rate (the metric to drive down)**, keypad questions per call, and model misreads.

**P1: many clinics and failover**
8. **Clinic registry** with location, hours, capacity, clinician phone numbers and a status: `open`, `closed`, `full`, or `unknown` (no recent confirmation).
9. **Clinic status from three free or cheap inputs:**
   - **SMS commands** from a registered clinician number, parsed from `sms_received` (for example `OPEN`, `CLOSED`, `FULL`, `BACK 14:00`, in Latin letters so any phone can type them), each confirmed with a short reply SMS.
   - **A free missed call** from a registered clinician number counts as "on duty now" (reply `callback: false`).
   - **A dashboard toggle**, for the demo and for district staff.
10. **Routing with failover:** each village has a precomputed list of clinics ordered by travel time. Bob picks the first that is open, has capacity and has a recent confirmation; then the next; if none qualifies within reach, HIGH cases are sent to the district hospital and EMERGENCY always to 108. The outcome prompt names the clinic, and the dashboard explains why the first choice was skipped.
11. **Alert delivery and escalation:** urgent alerts appear on the dashboard and go to the chosen clinic's clinician by SMS (`urgent` priority). If not acknowledged within a set time, Bob escalates to the next clinic or the district contact. Acknowledgement can come from the dashboard or an `ACK <code>` SMS.

**P2: sync to Central**
12. **Decides what to sync and sends it via `/v1/sync`:** a compact record per triage (hub, date, clinic, tier, symptom and red-flag codes, durations, protocol and model version, and a privacy-preserving patient key, never the raw phone number), clinic status changes, and a daily summary. Track acknowledgements from `sync_status` and show sync state on the dashboard.
13. **Shows cost:** SMS sent, segments and estimated rupees per case, from Stuart's `/v1/status`.

**Always**
14. **A fake Stuart** (section 7.7).
15. **A `bob/README.md`** covering setup, model download and runtime, how to run Bob, the fake Stuart and the evaluation, how to add a language and a clinic, data sources and what the data does not cover, the guardrails, and the design for cross-district patient history (section 10).

**Done means:** the fake Stuart can run full scripted calls in Hindi and Gujarati, using recorded WAVs as the patient, through to a tier, a clinic choice, an appointment or alert, and a correct dashboard; a `CLOSED` SMS from a registered clinician reroutes the next patient to the next clinic; and triage records go out through `/v1/sync` with their status tracked. Every message Bob sends is valid under the contract, and the evaluation numbers are printed.

## 10. Suggested process (current direction; change it if reality disagrees)

These are starting points from research done with Meet, not decisions. Note any significant change in your README.

**Start from the existing core.** Meet has `vitamin-bob.zip` from an earlier session. Move it into `bob/` and adapt it rather than rewriting it. It contains:
- `protocol.py`: symptoms (fever, cough, diarrhoea), red flags, tiers, Hindi question and outcome text. Drafted from WHO IMCI danger signs; not yet clinician-reviewed.
- `rules.py`: the deterministic tiering and the "unknown → UNCERTAIN" logic.
- `extract.py`: an LLM extractor with the evidence guard, and a keyword baseline for comparison.
- `session.py`: a call state machine with the raise-only rule, built for a text command line; it needs to become an event/action machine for the contract.
- `eval/`: 38 synthetic Hindi vignettes (8 deliberately hard) and the evaluation harness.

**Phase 0: contract and fake Stuart (first ~30 minutes)**
- The event endpoint, action-list builder and contract validator, driven by the fake Stuart with text standing in for audio.

**Phase 1: conversation and data (by ~1:30am)**
- Turn `session.py` into the event-driven conversation, including menu repeats, "please answer with 1, 2 or 3" re-asks, and the patient hanging up mid-call.
- Create `bob.db` with clinics, translations and the rest (shape below), seeded with three demo clinics.
- Gujarati: translate the questions and outcomes and write Gujarati vignettes. Meet will arrange for a Gujarati speaker to check them.
- Generate the prompt WAVs for both languages. Meet has **Sarvam** and **ElevenLabs** credits for generating them *before* the demo; they must be files on disk at runtime. Case codes can be read digit by digit from pre-recorded digit clips; clinic names and times can be pre-recorded fragments.

**Phase 2: on-device understanding (by ~3:00am)**
- **Gemma 4 E2B/E4B accepts audio directly** (clips up to 30 seconds). Suggested two passes with the same model: (1) transcribe the recording, (2) fill the form from the transcript, with output constrained to the JSON schema. Keep the evidence guard: quotes must appear in the transcript.
- Runtime: **Kevin runs Windows**, so use llama.cpp (documented to support Gemma 4 audio). MLX is Apple-only, and Ollama audio support was not confirmed. 8-bit quantisation is recommended for audio. **Verify on Meet's laptop before building on it**, including whether it has a usable GPU.
- Keep a fallback: a separate speech-to-text model (for example Whisper) feeding the same text extractor, in case Gemma's Hindi or Gujarati transcription is weak.
- Expect callers to mix Hindi or Gujarati with English.

**Phase 3: clinics, failover, dashboard (by ~4:30am)**
- Clinic status inputs, routing, alerts and escalation; the dashboard as one local page refreshed by polling.

**Phase 4: sync and evaluation (until feature freeze)**
- Records to `/v1/sync`; per-language evaluation; an audio evaluation set if time allows (vignettes turned into speech with Sarvam or ElevenLabs, downsampled to 8 kHz to mimic a phone line, clearly labelled synthetic).

**Suggested `bob.db` shape (yours to change):**
`hubs`, `languages` (code, name, enabled), `villages` (hub_id, name, location), `clinics` (hub_id, name, location, hours, capacity_per_day, status, status_source, status_at), `clinic_routes` (village_id, clinic_id, rank, travel_minutes), `clinicians` (clinic_id, name, phone, on_duty_at), `patients` (hub_id, patient_key, preferred_lang, village_id, last_clinic_id), `protocols` (version, approved_by, approved_at), `questions` (protocol_id, key, tier, applies_to), `translations` (key, lang, text, audio_path), `sessions` (call_id, patient_id, lang), `turns` (session_id, seq, kind, key, digits, transcript, at), `triages` (session_id, protocol_id, model_version, tier, reasons, unknowns, routed_clinic_id, skipped_clinics), `answers` (triage_id, item_key, value, source: description | keypad, evidence), `appointments` (triage_id, clinic_id, slot_start, priority, status), `alerts` (triage_id, clinic_id, created_at, sent_message_id, acked_by, acked_at, escalated_to), `sync_outbox` (record_id, kind, payload, status, acked_at). Principles: `hub_id` on rows and globally unique IDs so many Kevins can sync upward without collisions; language, clinics and protocol as data; every triage records the protocol and model version that produced it.

**Cross-district patient history: design only, no code tonight.** Describe this in your README:
- **The goal:** a patient who falls ill away from home still has their history.
- **The approach:** Central holds compact case records keyed by a privacy-preserving patient key. A Kevin in another district can request a short history summary by SMS, through Stuart's data link; Central replies with a few frames. That costs only a few SMS per lookup, takes minutes rather than seconds, and should enrich the clinician's view **after** the call rather than delay triage.
- **The hard parts to name honestly:**
  - **Identity.** Phone numbers change and households share phones. India's ABHA health ID (Ayushman Bharat Digital Mission) is the right long-term key, and a 14-digit ABHA number can be entered on a keypad.
  - **Key strength.** A hashed phone number is weak, since there are few possible numbers.
  - **Consent.** India's data protection law and ABDM's consent model govern sharing records across regions.
  - **Integration.** In reality Central should be the state health information system, not something we build.

## 11. What Stuart will provide to you, and what Stuart expects from you

**You can rely on Stuart to:**
- Send every event in section 7.2, in order, with unique `event_id`s, retrying with the same ID on failure.
- Queue a callback only when you reply `callback: true`.
- Execute your action lists exactly and send one `action_result` per list (none after `hangup`; `call_ended` instead).
- Play a hold tone while you think, so a 20-second pause after `listen` is acceptable.
- Save recordings as WAV, 16 kHz mono 16-bit, under `data/recordings/`, and send absolute paths.
- Forward every incoming SMS, send your SMS in priority order within daily caps, and report their status.
- Deliver your sync records to Central exactly once, encrypted, and report `sync_status`.
- Serve `/v1/status` with lines, the callback queue, active calls, SMS counts and sync counts.
- Provide a simulator line (laptop speaker, microphone and keyboard, plus fake missed calls and SMS) so the whole system can be tested without a phone.

**Stuart relies on you to:**
- Return **valid** action lists only: zero or more `play`, then exactly one `keypad`, `listen` or `hangup`.
- Make your first prompt tolerate being partly missed.
- Provide every audio file you reference, plus `data/prompts/system/fallback.wav`, in the agreed format.
- Answer within 2 seconds, or 20 seconds after a `listen`.
- Delete recordings after processing.
- Keep sync payloads at or under 200 bytes of compact JSON, with no raw phone numbers, names or free text.
- Never touch phones, SIMs, SMS transport or Stuart's database.

## 12. Things Meet still decides

- E2B versus E4B, after a quick test on his laptop.
- The three demo clinics, villages, travel times, hours and capacities (use sensible placeholders until told).
- The exact SMS command words for clinicians.
- Any contract change you propose in `bob/CONTRACT_NOTES.md`.

## 13. Timeline (Eastern Time, Sunday 4 October)

| Time | Milestone |
|---|---|
| ~12:15am | Start: contract, fake Stuart, move the existing core into `bob/` |
| ~1:30am | Text-only conversation passes the fake-Stuart test; `bob.db` in place; prompt WAVs in both languages (P0) |
| ~3:00am | Gemma 4 understanding working on audio, or the fallback path in use (P0) |
| ~3:30am | Push branch `bob`; Meet merges and integrates with Stuart |
| ~3:30–4:30am | Clinics, failover, alerts, dashboard (P1) |
| ~4:30–5:30am | Sync records, evaluation numbers (P2) |
| ~5:30am | Feature freeze; demo rehearsal and recording |
| 8:00am | Submission deadline |
