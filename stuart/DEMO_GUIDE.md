# Integrated Vitamin Bob demonstration

Combines merged `main` at `58d2341` (Claude's Bob PR) with Stuart. Open **http://127.0.0.1:8200/demo**. Bob's full dashboard is at **http://127.0.0.1:8100/dashboard**.

## Start and stop

From this repository's `stuart/` directory in PowerShell:

```powershell
.\Start-IntegratedDemo.ps1
.\Stop-IntegratedDemo.ps1
```

The launcher starts local Gemma, Bob, and Stuart, waits for the model, and reports the demo URL. It refuses occupied ports. Stop shuts down both HTTP services and the model it started. History survives a restart. It does not install a Windows service.

The existing Python environment in `stuart/.venv` satisfies Bob's dependencies too. On a new machine, create that environment and install `stuart/requirements.txt`. Supply assets with `-AssetsDir`, `-LlamaExe`, and `-ModelsDir`; defaults use this laptop's existing Bob data, llama.cpp, and Gemma directories. AssetsDir must contain `prompts/` and `eval_audio/` with the ten original team recordings. No downloads or TTS generation happen at startup.

Private profiles, copied assets, databases, recordings, logs, and tokens live under ignored `stuart/runtime/`. The original Bob worktree and database are untouched. The demo seeds from the merged dummy district, not a private clinician seed.

## Five-minute presentation

1. Open the demo page. The top status should show Gemma + Bob + Stuart, local.
2. Select **Hindi · fever for two days**. Preview its audio if useful, then click **Start conversation**. Watch the description, follow-up questions, MEDIUM tier, and appointment below.
3. Click **Gujarati emergency**. The original Gujarati WAV passes through Gemma; scripted keypad replies answer the remaining questions. Watch the EMERGENCY outcome and clinician alert. Acknowledge the alert on Bob's dashboard.
4. Set Clinic A to **closed** on Bob's dashboard. Select **Hindi · persistent cough** and start it. The HIGH case should route to Clinic B, with the reason for skipping Clinic A shown. Reopen Clinic A afterward.
5. Show SMS delivery and Central acknowledgements. Stuart uses its actual durable queues, encrypted frames, authenticated ACKs, and Central database. SMS delivery is simulated locally; records do not travel over the cellular network in this mode.

Calls take roughly 20–45 seconds with accelerated prompt playback. Audio preview plays the original patient recording; recorded mode does not play every Bob prompt aloud. Bob's dashboard shows each prompt's text. Expected tiers in the selector are team reference labels, never supplied to Gemma or used to override the outcome.

## Design and compatibility

| Component | Decision and reason |
|---|---|
| Bob | Reuse Claude's merged conversation, clinic routing, rules, and dashboard. Stuart does not duplicate clinical decisions. |
| Contract | Keep contract 0.2 and localhost HTTP: Bob 8100, Stuart 8200. Each module owns its database and exchanges events/actions. |
| Gemma | Reuse installed E2B Q8_0 and audio projector on llama.cpp 8300. It processes the WAV, then fills Bob's fixed form. No reference transcript sidecar is supplied. |
| Recorded patient | Adapt Stuart's line interface. Keypad replies follow the vignette's reference facts; Bob makes all conversation decisions. This gives a repeatable presentation without Phone Link routing interruptions. |
| Persistence | Preserve SQLite queues and receipts. A two-line Bob fix prevents a fast delivered/acked receipt being overwritten by the enqueue response. |
| Lifecycle | One attended launcher owns the two HTTP servers and model process. Existing Stuart supervision/backup tools remain available for standalone deployment. |
| Central | Exercise actual encryption, framing, and storage over local loopback. Over-air delivery still needs a separate receiver phone. |

## Live S24 mode

Stop recorded mode first, then:

```powershell
.\Start-IntegratedDemo.ps1 -Mode phone
# when finished:
.\Stop-IntegratedDemo.ps1 -Mode phone
```

The first launch derives the allowed test peer from private `kevin.json`, uses a separate dataset, and enables actual callbacks for that peer. Keep USB connected, Bluetooth paired, Phone Link open, and SMSGate's Local server running. From the approved second phone, call the S24 and hang up. Answer the callback and choose **Transfer to PC**. Use 1 for Hindi or 2 for Gujarati, then follow Bob's prompts.

This wires the previously verified phone transport to real Bob/Gemma. A full physical call through this new integrated mode has **not** been performed, following the request to stop phone probes. Outbound SMS starts disabled; alerts remain in Bob's outbox and can be acknowledged on the dashboard. Plain incoming SMS remains unverified because earlier messages arrived as MMS.

## Integration result, 2026-10-04

| Recording | Actual tier | Gemma understanding time | Routing |
|---|---|---|---|
| Hindi_1 | MEDIUM | 10.2 s | Clinic A |
| Gujarati_5 | EMERGENCY | 7.2 s | Emergency outcome plus Clinic A alert |
| Hindi_3, Clinic A closed | HIGH | 9.7 s | Clinic B |

All calls completed; two simulated SMS were delivered, nine Central records acknowledged, and two clinician alerts acknowledged through Bob's API. Evidence: `runtime/integrated-reports/85149e27-1df0-4908-9e62-3c52a59aeac4.json`. This validates integration and these scenarios, not clinical validity or population accuracy.

A full stop/start preserved all three calls and both delivery receipts; reopening Clinic A added the tenth acknowledged record. Stuart's 65 automated tests and Bob's core checks, including the receipt-race regression, pass. Browser verification confirmed the embedded dashboard displays live outcomes and retained history. One observed extraction error labelled blood in sputum as blood in stool in Hindi_3; its HIGH tier still matched the reference due to the long cough. Matching tiers do not establish that every extracted symptom is correct.

To repeat the integration check against an idle recorded demo:

```powershell
.\.venv\Scripts\python.exe tools/check_integrated_demo.py
```

It refuses phone mode, uses real Gemma without transcript sidecars, retains history, and saves a report under `runtime/integrated-reports/`.
