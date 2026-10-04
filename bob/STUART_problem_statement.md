# Problem statement 1 of 2: Stuart (telephony, messaging and the data link)

**For: the Codex agent, working on branch `stuart`, only inside `stuart/`.**
The other half of the system, Bob, is being built at the same time by a Claude Code agent on branch `bob`. Read the whole document, especially sections 5–7, before writing code.

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

## 8. Your vision: Stuart

Stuart is the part of Vitamin Bob that turns ordinary phone lines into a free, reliable doorway to care, and a cheap data link that works where there is no internet. It notices every missed call, never loses one, calls each patient back in a sensible order, carries Bob's voice into the call and the patient's voice and keypad presses out of it, and moves text and data by SMS at the lowest possible cost. Stuart knows nothing about health. It is a dependable switchboard and courier that would work for any other service.

It must be honest about the real world: phones ring out, patients hang up, lines go busy, cables come loose, SMS get delayed or lost. Stuart handles each case predictably and reports it to Bob.

It must scale on paper even though the demo has one line: a pool of lines (more SIMs, more phones, later a GSM modem bank) behind one interface, so a district could add capacity without changing Bob.

## 9. What you are expected to deliver

By the end, the `stuart/` directory contains a service that, running on Kevin:

**P0: calls**
1. **Detects missed calls** on Kevin's line (Meet's Android phone over USB) within a few seconds, including the caller's number. It should reject or end the incoming call so it never connects, which keeps it free for the caller. Each one is stored and sent to Bob as `missed_call`; a callback is queued only if Bob replies `callback: true`.
2. **Manages the callback queue:** first come, first served; the same number within about 10 minutes merges into one entry; a busy line waits; no answer is retried a limited number of times with a gap, then reported as `callback_failed`.
3. **Places the callback** and sends `call_started`. The patient's phone may be **any phone and any OS**; never assume anything about it beyond voice and keypad tones.
4. **Executes Bob's action lists** exactly as the contract says: plays WAVs into the call, collects keypad digits, records the caller until silence, hangs up, plays the hold tone while waiting for Bob, and falls back safely if Bob is slow or down.
5. **Reports call endings** accurately, including the patient hanging up mid-call.
6. **Serves `GET /v1/status`** for Bob's dashboard.
7. **Provides a simulator line**: the same line interface using the laptop's speaker, microphone and keyboard instead of a phone, plus a way to trigger a fake missed call and inject a fake incoming SMS. This is the demo's safety net. Stuart should also be able to run **several simulated lines at once** (scripted patients, no audio devices needed) so the dashboard can show the callback queue draining in parallel: the scaling story without extra hardware.

**P1: SMS**
8. **Receives SMS** on Kevin's line and forwards each one to Bob as `sms_received`.
9. **Sends SMS** for Bob via `POST /v1/sms` with priorities, segment counting, per-line daily caps, and `sms_status` events.

**P2: the SMS data link to Central**
10. **Implements `POST /v1/sync`:** packs records into SMS-sized frames (compact binary or text encoding, compression, a pre-shared-key encryption and an integrity check), numbers them, sends them at bulk priority, and retransmits until Central acknowledges, reporting `sync_status`.
11. **Builds a Central receiver** in `stuart/central/`: decodes frames, verifies and decrypts them, de-duplicates, stores records in `central.db`, sends acknowledgements, and shows a minimal page of what has arrived from which Kevin. In the demo it may run on the same laptop with a **loopback transport** (frames passed locally instead of over the air), clearly labelled as such. If time allows, a real over-the-air path is a bonus; Meet's Android phone has a second SIM slot that could act as Central's number.
12. **Reports cost:** SMS and segments per day, and the estimated rupee cost at a configurable price per segment, so the dashboard can show "cost per case".

**Always**
13. **A fake Bob** (section 7.7) and tests showing Stuart honours the contract.
14. **A `stuart/README.md`** with phone setup (USB debugging and so on), how to run Stuart, the simulator, the fake Bob and the Central receiver, environment variables, the sync frame format, and known limitations.

**Done means:** with the fake Bob, Meet can give a missed call from a patient phone (iPhone or Android), watch it appear in `/v1/status`, get called back, hear the scripted WAV, press a key, say something, and find the keypad digits and a playable recording in the right places, with every event having reached the fake Bob in order. The same works on the simulator line with no phone attached. For P1, an SMS sent to Kevin's line reaches the fake Bob, and an SMS requested by the fake Bob arrives on a real phone. For P2, test records from the fake Bob show up exactly once in the Central receiver, even when frames are dropped or duplicated in a test.

## 10. Suggested process (current direction; change it if reality disagrees)

These are starting points from research done with Meet, not decisions. If something doesn't work, try the next option and note it in your README.

**Phase 0: contract and mocks (first ~30 minutes)**
- The event sender, action executor and SMS and sync endpoints against the contract, with the fake Bob and a fake line, before touching any phone.

**Phase 1: the simulator line (by ~1:30am)**
- One `Line` interface (place call, end call, play audio, read keypad digits, record until silence, report call state, send SMS, receive SMS), with a simulator implementation first.

**Phase 2: the real phone (aim for ~3:00am)**
- **Control the phone over ADB (USB).** Likely approaches, to verify on the actual phone:
  - Missed calls: poll the call log (`adb shell content query --uri content://call_log/calls ...`, missed and rejected types), or watch the call state and end a ringing call with a key event so it never connects.
  - Placing a call: `adb shell am start -a android.intent.action.CALL -d tel:<number>`. The phone may ask which SIM to use; set a default calling SIM.
  - Hanging up: the end-call key event.
  - Incoming SMS: poll `content://sms/inbox`. Sending SMS from the shell is unreliable across Android versions; an SMS gateway app with a local REST API (for example "SMS Gateway for Android", whose local webhooks can reach the laptop through `adb reverse` over USB with no internet) or Termux:API are the likely options.
  - Knowing whether the patient has answered is unreliable on Android. The contract makes Bob repeat its first prompt until a key is pressed. If you find a dependable answer signal (for example from `dumpsys telecom`), use it, but don't depend on it.
- **Audio in and out of the call.** No Android app can access call audio, so the sound must leave the phone some other way. Meet does **not** want speakerphone coupling as the main path. Try in this order:
  1. **Bluetooth through Windows Phone Link.** Phone Link can place and receive the Android phone's calls on the PC over Bluetooth, so call audio flows through Windows' audio devices. Route it into Stuart with a virtual audio cable (for example VB-Audio Virtual Cable): set the virtual devices as Windows' default communication devices so Phone Link's call audio goes to Stuart's recorder and Stuart's prompts go into the call. Keep using ADB for call control if Phone Link can't be automated. **Unverified:** check that calls work with Wi-Fi off after the one-time setup, and that the audio routing behaves.
  2. **A wired audio patch**, if Meet has the cables: the phone's headset output into the laptop's audio input, and the laptop's output into the phone's headset microphone (with a USB sound card if the laptop has a single combined jack).
  3. **Speakerphone coupling** only as a last resort.
  - **Kevin runs Windows:** ADB comes from Android platform-tools; use an audio library that works on Windows (for example `sounddevice`).
  - In every case: work **half duplex** (don't record while playing), **detect keypad tones** (DTMF) in the received audio (for example with the Goertzel algorithm; test with an iPhone and an Android as the patient), and detect end of speech with a simple voice-activity detector.
- If the real phone is not working by about 3am, stop and make the simulator line flawless. Meet set this cut-off with the deadline in mind.

**Phase 3: SMS, sync and robustness (until handover)**
- SMS in and out, priorities and caps; then the sync link and Central receiver.
- Retries, timeouts, Bob unreachable, cable unplugged, patient hanging up mid-prompt.

**Suggested `stuart.db` shape (yours to change):**
`lines` (id, hub_id, msisdn, label, sim_slot, role, state, daily_sms_cap), `missed_calls` (id, hub_id, line_id, from_phone, received_at, status, attempts, next_attempt_at), `calls` (id, missed_call_id, line_id, to_phone, started_at, ended_at, end_reason), `call_actions` (call_id, action_id, type, started_at, finished_at, status), `sms_out` (message_id, to, priority, segments, status, sent_at), `sms_in` (message_id, line_id, from_phone, received_at), `sync_frames` (frame_id, seq, records, status, attempts, acked_at). Keep `hub_id` on rows so many Kevins never collide.

**Rough cost model to verify and report** (bulk transactional SMS in India is about ₹0.12–₹0.30 per segment before tax; a Unicode segment holds 70 characters versus 160 for plain text): if a triage record compresses to about 25–35 bytes, one 140-byte binary SMS or one 160-character text SMS carries 3–4 records. At 200 cases a day that is roughly 50–70 SMS, about ₹6–20 per day per Kevin. Many retail prepaid plans also include a daily SMS allowance, which can make the marginal cost zero at low volume (though commercial use of retail SIMs has regulatory limits in India). Measure your real record and frame sizes and put the true numbers in your README.

## 11. What Bob will provide to you, and what Bob expects from you

**You can rely on Bob to:**
- Reply to every `missed_call` with whether to call back.
- Answer `call_started` with a list that starts with prompts and ends with a keypad or listen action, repeating its first prompt until a key is pressed.
- Provide every prompt as a WAV (16 kHz mono 16-bit) under `data/prompts/`, including `data/prompts/system/fallback.wav`.
- Answer quickly, except after a `listen`, when it may take up to 20 seconds.
- Delete recordings after processing them.
- Send SMS requests with a priority and never ask a patient to reply by SMS.
- Send sync records as small JSON payloads (≤ 200 bytes) with no raw phone numbers, names or free text.
- Poll `/v1/status` roughly once a second.

**Bob relies on you to:**
- Send every event in section 7.2, in order, with unique `event_id`s and retries.
- Never decide what to say, which language to use, who is a clinician, or anything medical; never interpret SMS content.
- Execute action lists exactly, report exactly one `action_result` per list (except after `hangup`), and play the hold tone while Bob thinks.
- Save recordings in the agreed format and send absolute paths.
- Deliver SMS in priority order within caps, and deliver sync records to Central exactly once.
- Keep `/v1/status` truthful and fast.

## 12. Things Meet still decides

- Which phone settings are acceptable to change (default SIM, speakerphone, do-not-disturb), and which SMS app, if any, to install.
- Whether the demo shows sync over loopback or over the air using the second SIM.
- Any contract change you propose in `stuart/CONTRACT_NOTES.md`.

## 13. Timeline (Eastern Time, Sunday 4 October)

| Time | Milestone |
|---|---|
| ~12:15am | Start: contract, fake Bob, line interface |
| ~1:30am | Simulator line passes the fake-Bob call test end to end (P0) |
| ~3:00am | Real phone calls working, or decision to rely on the simulator; SMS in and out (P1) |
| ~3:30am | Push branch `stuart`; Meet merges and integrates with Bob |
| ~3:30–5:30am | Integration fixes, then the sync link and Central receiver (P2) |
| ~5:30am | Feature freeze; demo rehearsal and recording |
| 8:00am | Submission deadline |
