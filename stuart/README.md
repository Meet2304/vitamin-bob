# Stuart: Kevin's switchboard and SMS courier

**Integrated demo:** [Start here](DEMO_GUIDE.md). `Start-IntegratedDemo.ps1` runs merged Bob, local Gemma, and real Stuart at http://127.0.0.1:8200/demo, with recorded Hindi/Gujarati scenarios and a live-phone mode.

Contract 0.2. Windows service for local call actions, callback queues, SMS and encrypted Central sync. No health logic or patient wording belongs here. All source and tooling are under `stuart/`, on branch `stuart` in a separate worktree.

## Current evidence

Latest verification: 65 automated tests passed. A real missed call triggered an Android callback and answer detection. A later callback, transferred to the PC by the operator, carried spoken instructions, decoded `12` with `#`, recorded 3.4 seconds of speech and hung up cleanly. Evidence: ignored `runtime/hardware-callback-result.json`. The simulator previously completed eight calls, one outbound SMS and three acknowledged Central records. Actual Bob/Stuart HTTP integration completed synthetic Hindi and Gujarati conversations, but exposed a Bob outbox status race. With the prepared fix in an isolated Bob copy, three simulated SMS were delivered and four encrypted Central records remained acknowledged in Bob. One approved nonclinical SMS reached the second phone exactly once. SMSGate reports Delivered; Stuart recovered that status by polling after the success webhook was missed. Evidence: ignored runtime/hardware-sms-result.json. A further callback passed with the S24 Wi-Fi and mobile data both off: keypad 12#, 2.8 seconds of speech, and clean hangup. Inbound SMS and Gemma processing over a real phone call remain unverified.

- Scripted missed-call → Bob callback decision → play → keypad → record → hangup works against fake Bob.
- Callback queue, duplicate-number merging, event IDs and HTTP acknowledgements persist in SQLite.
- Multiple simulated lines execute through the same action executor.
- SMS ordering, encoding-aware segment caps and status events are tested on simulated transport.
- Encrypted SMS-sized frames, authenticated ACKs, fragment restart recovery and one Central record per ID are tested under drop, duplicate and tamper faults.
- ADB is authorized on the S24 Plus (SM-S926B, Android 16). Call-log detection, answer state and operator-transferred callback audio passed. Direct Bluetooth playback failed. The verified route uses VB-CABLE transmit and native WASAPI Realtek loopback receive. Selecting “Transfer to PC” remains a human step. See `PHONE_AUDIO_SETUP.md`.
- Fake Bob uses tones, not bilingual clinical prompts. Hindi/Gujarati content and the real routing dashboard are Bob's responsibility.

## Managed Windows runtime

See `OPERATIONS.md` for validated profiles, DPAPI-protected credentials, start/stop/status commands, crash supervision, USB/webhook repair, readiness diagnostics, and SQLite backup/restore. `POC_EVIDENCE.md` separates observed hardware results from simulated checks. The prepared `runtime/profiles/kevin.json` targets Bob on port 8100 and keeps real calls/outbound SMS disabled until an attended demo is configured.

## Quick demo (no phone required)

In PowerShell, from this directory:

```powershell
python -m venv --system-site-packages .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\Start-Demo.ps1
```

Open `http://127.0.0.1:18200`. Three scripted lines are the default. Trigger multiple distinct synthetic callers to see the queue drain. Phones are masked in the console. The underlying contract APIs include the unmasked number for Bob's local processing.

```powershell
& .\.venv\Scripts\python.exe -m stuart trigger --phone +919000000001 --line sim-1
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18100/mock/messages
```

The second command requests one simulated SMS and three sync records. Central records appear in the console and at `/central/records`. Fake Bob's raw transport events are available at `http://127.0.0.1:18100/mock/events`. The mock retains recordings for inspection under `runtime/demo-data/recordings/`; they are synthetic and not clinical samples.

Stop the hidden demo processes with `.\Stop-Demo.ps1`. Restart in interactive mode with `.\Start-Demo.ps1 -Interactive`: prompts play on laptop speakers, keypad input comes from the console, and speech is recorded from the laptop microphone. Confirm Windows microphone permissions first. Stop before changing modes or ports.

The venv uses existing system packages on this laptop to avoid duplicating audio/scientific libraries. A clean installation can omit `--system-site-packages` and install the same requirements. All operation after installation is local; there are no runtime CDN, font or cloud-model calls.

## Real Bob integration

Do not start fake Bob on port 8100 if real Bob already uses it. In a separate PowerShell window:

```powershell
$env:VB_BOB_URL = 'http://127.0.0.1:8100'
$env:VB_DATA_DIR = '<absolute shared data path agreed with Bob>'
$env:VB_SIM_MODE = 'interactive'
$env:VB_SIM_LINES = '1'
& .\.venv\Scripts\python.exe -m stuart serve
```

Stuart listens on `127.0.0.1:8200`. Bob and Stuart must use the same `VB_DATA_DIR`. Bob writes all prompt WAVs, including `prompts/system/fallback.wav`. Paths must be absolute, beneath the prompts root, and WAV 16 kHz, mono, PCM16. Stuart writes recordings under `recordings/`; real Bob deletes them after processing. Meet must ignore the root `data/` directory in the final repository; Stuart does not edit the root `.gitignore`.

Every `/v1/*` request requires `X-VB-Contract: 0.2`. Run `GET /v1/health`, `GET /v1/status`, `POST /v1/sms` and `POST /v1/sync` as described in the brief. `/docs` has the local API explorer. `/diagnostics` shows pending decisions, undelivered events, transport errors and estimated SMS cost; it is deliberately separate from the dashboard status contract.

## Phone setup and the required human steps

1. Enable Developer options and USB debugging on the S24 Plus. Connect with a data-capable cable, unlock it, select File transfer and accept the debugging authorization. If Windows cannot identify the Android debugging interface, check the phone debugging setting. Samsung Auto Blocker can block USB commands; report a blocked setting before changing protection. Install the official Samsung Android USB driver if Windows reports a driver problem, then reconnect.
2. Pair Phone Link's Calls feature and verify a manual PC call. That route passed on this laptop; an Android-initiated call can still remain on the phone's earpiece.
3. Configure independent routes. `VB_AUDIO_OUTPUT=wasapi:CABLE Input (VB-Audio Virtual Cable)` sends prompts to Phone Link's CABLE Output microphone. `VB_AUDIO_INPUT=loopback:Speaker (Realtek(R) Audio)` captures its actual speaker output. Both passed on a manual PC call. Windows communications defaults alone did not prove routing: another display was the default while Phone Link still played on Realtek. Check the actual route on each callback.
4. List devices with `python -m stuart devices`, then set the verified indices/names. Test prompt playback, caller recording, keypad tones and hangup with a second phone. Repeat with internet and mobile data off while retaining cellular calls and Bluetooth.
5. Set the default calling SIM manually to avoid an unattended SIM picker. Disable voicemail/diversions for the demonstration if they would answer the incoming missed call. Check actual patient/carrier charges instead of treating “never pays” as universal.

Official downloads: [Android platform-tools](https://developer.android.com/tools/releases/platform-tools), [Samsung Windows USB driver](https://developer.samsung.com/android-usb-driver), [VB-Audio routing tools](https://vb-audio.com/Cable/).

Platform-tools have been downloaded into `runtime/tools/platform-tools/` on this laptop. Diagnostics:

```powershell
& .\.venv\Scripts\python.exe -m stuart check-phone
& .\.venv\Scripts\python.exe -m stuart devices
```

`check-phone` checks model/version and empty call-log/SMS queries without reading message bodies or placing calls. Some Android versions deny shell provider access. A companion app may then be necessary; the README does not promise that ADB bypasses Android permissions.

After the checks succeed, enable the real adapter explicitly:

```powershell
$env:VB_ANDROID_ENABLED = '1'
$env:VB_SIM_LINES = '0'
$env:VB_AUDIO_INPUT = '<verified receiver>'
$env:VB_AUDIO_OUTPUT = '<verified transmitter>'
& .\.venv\Scripts\python.exe -m stuart serve
```

While enabled, Stuart rejects ringing incoming calls and detects new missed/rejected call-log entries. It calls back only with Bob's approval. Before dialing it requires an empty live Telecom call list; it waits for `ACTIVE` before requesting Bob's prompts. `VB_ANDROID_ANSWER_TIMEOUT_SECONDS` defaults to 45. Historical call states are excluded. On this S24, also set `VB_ANDROID_REQUIRED_AUDIO_ROUTE=TYPE_BLUETOOTH_SCO`: prompts wait for five consecutive Bluetooth route observations, for up to `VB_ANDROID_AUDIO_ROUTE_TIMEOUT_SECONDS` (60 by default). The operator must select “Transfer to PC” after answer. This guard verifies a route; it does not perform the transfer. Stuart ends only calls it started. USB loss cannot guarantee physical hangup.

## SMSGate local mode

SMS Gateway for Android is installed on the S24. Use **Local Server** mode. In the installed version, the enabled Local server toggle and **STOP SERVICE** button show that its service is running; there is no Online/Offline button. Verify reachability with GET /health. SEND_SMS was still denied after the phone settings attempt; the user authorized an ADB grant for user 0, which succeeded. RECEIVE_SMS has since been granted with user authorization; the inbound hardware probe remains unverified because the second phone sent MMS. [Official permission troubleshooting](https://docs.sms-gate.app/faq/errors/).

```powershell
& .\runtime\tools\platform-tools\adb.exe forward tcp:8080 tcp:8080
& .\runtime\tools\platform-tools\adb.exe reverse tcp:8200 tcp:8200
$env:VB_SMS_GATE_USER = '<shown in app>'
$env:VB_SMS_GATE_PASSWORD = '<shown in app>'
$env:VB_SMS_WEBHOOK_TOKEN = '<random secret>'
$env:VB_SMS_LINE_ID = 'android-1'
```

Register the app's `sms:received`, `sms:sent`, `sms:delivered` and `sms:failed` webhooks at `http://127.0.0.1:8200/android/smsgate?token=<same-secret>`. The adapter accepts the documented `event` + `payload` shape. Credentials and token are env variables, never committed. Android permissions and webhook delivery must be tested on the actual phone. A POST accepted by the gateway is recorded as `accepted`; it becomes `sent` or `delivered` through a webhook or an authenticated status query for that known message ID. Stuart checks up to ten outstanding Android message receipts every ten seconds, rotating through them. A receipt lookup never resends a message, and a network error leaves its delivery outcome unresolved. Failed webhook reasons are retained locally, bounded to 1,024 characters; the Bob event shape stays at v0.2. [Official status tracking](https://docs.sms-gate.app/features/status-tracking/).

SMS contents are transported unchanged. The Central link is encrypted, but a supplied ordinary clinician SMS is not automatically encrypted: Meet must resolve the brief's encryption scope before using patient-bearing SMS. All callbacks and SMS are charged to the line owner. Caps use segments, not logical messages; cost is a configurable assumption, not a verified tariff.

## Central frame format

`VB1|<hub>|<seq>|<fragment-index>|<fragment-total>|<Base64 chunk>`

The encrypted envelope contains hub, sequence and records. Compact UTF-8 JSON is optionally zlib-compressed only if smaller. AES-256-GCM encrypts it with a fresh 12-byte nonce; a 16-byte tag authenticates it and the version/hub/sequence header. The ciphertext is Base64-encoded and split into 95-character chunks. Hub IDs are 1–16 safe ASCII characters. Fragment indices start at 1 and the maximum is 99. Frames remain within one GSM-7 SMS, including extension-character counting.

ACK: `VBA1|<hub>|<seq>|<Base64(nonce + authenticated encrypted ACK)>`.

Central stores partial fragments and committed records in SQLite. It checks/decrypts a complete envelope, validates record size, and commits records and batch identity before acknowledging. A repeated record ID with the same content stores once; different content is rejected. Repeated fragments of a committed batch produce an ACK again, so a lost ACK does not duplicate a record. This is one committed record over repeated delivery; it is not an unconditional network-delivery guarantee.

Default transport is explicitly labelled `loopback`, using the same codec and receiver on this machine. Set `VB_SYNC_DROP_FIRST=1` to drop the first frame once and demonstrate retry. A random demo key is stored in ignored `runtime/demo-sync.key`. For separate Central machines, configure the same 32-byte secret via `VB_SYNC_KEY_HEX`; never put it in SMS or a committed file. `python -m stuart central` serves the standalone receiver on port 8300 (`POST /frames`, `GET /records`, minimal page).

Set `VB_SYNC_TRANSPORT=sms` and `VB_CENTRAL_PHONE` for a proposed over-air path. It queues frames at bulk priority; return ACKs through the SMS receive webhook. This path is not yet validated on hardware. Five attempts are made with increasing delays before reporting failure. Operator recovery after a long outage and key rotation are future work. One record per encrypted envelope is the initial implementation; batching can improve cost after measurements. A 200-byte payload may require several segments after framing.

## Configuration and testing

See `.env.example` for all environment variables. Principal settings: `VB_BOB_URL`, `VB_DATA_DIR`, simulator mode/count/digits, Android enable flag and ADB path, input/output audio devices, daily segment cap, price per segment, callback retry gap/count, model-wait timeout, sync transport/key/hub, and SMSGate credentials/webhook token.

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Tests cover action validation, UTF-8 payload bounds, GSM/Unicode counting, DTMF signal/noise cases, encrypted-frame drop/duplicate/restart/tamper, an entire fake-Bob call, SMS and sync, Bob-down callback gating, priority/caps and HTTP contract/idempotency conflicts. They use synthetic cases and do not establish medical safety or handset compatibility.

## Known limitations and contract decisions

See `CONTRACT_NOTES.md`. Callback audio passes with operator transfer; unattended routing, inbound SMS and Gemma over the call path remain checks. Outbound SMS passed on the S24, including recovery of its Delivered status through the local gateway API. VAD uses a simple RMS threshold. Normal sounddevice devices require 16 kHz support; WASAPI shared-mode conversion is enabled. Native `wasapi:<speaker name>` transmit and `loopback:<speaker name>` receive use SoundCard with per-thread COM initialization. Receive captures stereo and downmixes to mono at 16 kHz. It includes all sound on that speaker; keep other app audio quiet. The hold tone is half duplex; barge-in during prompts is not captured. Caller keys must follow the entire prompt. A readiness beep followed by a two-second pause passed the physical keypad check. Fake Bob is a transport mock.

After event retry exhaustion, failures remain in the outbox for inspection. Pending missed-call decisions can be retried by `POST /operator/retry-pending` with the contract header. No phone callback is queued while its decision is unknown. Interrupted outgoing SMS are marked as an unknown failed outcome rather than automatically resent, to avoid charging for a duplicate send.

`POST /operator/retry-events` replays unacknowledged events in stored order without executing old call actions again. `POST /operator/retry-sync` requeues failed sync records. Both require the contract header. The demo launcher creates a private operator token for graceful shutdown; do not publish `runtime/demo-processes.json`. Cost diagnostics distinguish reserved segments from confirmed sent segments.
