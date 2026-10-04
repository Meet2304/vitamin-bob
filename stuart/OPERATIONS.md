# Running Stuart on Kevin

Stuart now has a managed Windows runtime in addition to the standalone simulator. Run it in the signed-in Windows session used by Phone Link so that the verified audio devices are available. It is a foreground-user process supervisor launched in a hidden window; it is not an installed Windows service or an automatic logon task.

## What the runtime owns

- A validated JSON profile selects simulator or Android transport, Bob's localhost URL, shared data path, audio endpoints, country code, limits, and approved test peers.
- An OS file lock permits one managed Stuart instance per data directory. A busy TCP port aborts startup without touching the existing listener.
- The supervisor restarts a crashed service up to three times with increasing delays. An authenticated graceful shutdown stops the supervisor too. Queues, event IDs, receipts, and sync sequences persist in SQLite.
- The Android bridge checks USB and SMSGate every ten seconds, restores missing ADB tunnels, and reconciles only its own webhook IDs. It configures the app's local webhooks to operate without internet. Shutdown removes its hooks and tunnels it created; unrelated hooks and pre-existing tunnels are preserved.
- SMS status polling recovers missed receipts without submitting the message again. Unknown send outcomes after a crash are retained for operator review.
- `/v1/health` retains contract 0.2. `/ready` separately checks Bob, USB, the managed gateway, and failed background workers. Its audio field reports the required operator transfer; a healthy USB connection does not prove call audio.
- Operator and webhook tokens, and the SMSGate password, are encrypted with Windows DPAPI under ignored `runtime/`. They are loaded into the child environment, not command-line arguments. The JSON profile and process manifest contain no credentials.

## Existing profiles on this laptop

All profiles are private, ignored files under `runtime/profiles/`.

| Profile | Purpose | Ports | Initial hardware controls |
|---|---|---|---|
| `kevin.json` | Real Bob integration; shared data points to Bob's current worktree `data/` | Bob 8100, Stuart 8200 | Calls and outbound SMS disabled; only the supplied test peer allowed |
| `poc-sim.json` | Tested lifecycle and recovery demonstration | Fake Bob 18110, Stuart 18210 | Simulated calls/SMS only |
| `poc-phone.json` | Tested real USB/SMSGate management | Fake Bob 18110, Stuart 18220 | Calls and outbound SMS disabled |

Run only one hardware profile against the S24 at a time. After merge, change `kevin.json`'s `data_dir` to the absolute shared data directory used by Bob. Bob must provide `prompts/system/fallback.wav` and its language clips there.

From `stuart/` in PowerShell:

```powershell
.\Get-StuartStatus.ps1                       # Dependency check, no calls or messages
.\Start-Stuart.ps1                           # Starts the kevin profile
.\Get-StuartStatus.ps1
.\Stop-Stuart.ps1                            # Graceful stop; durable queues retained
```

Use `-Config runtime/profiles/poc-sim.json` or another profile to select a different instance. The pre-existing `.\Start-Demo.ps1` / `.\Stop-Demo.ps1` pair still provides the self-contained three-line simulator on port 18200.

If Bob is down, Stuart can remain running but `/ready` returns HTTP 503. Incoming events and callback decisions are preserved; no callback proceeds without Bob's decision. The current `kevin` profile's startup dependency check finds USB and the fallback WAV, but Bob must be started separately on 8100.

## Creating a profile elsewhere

```powershell
.\Initialize-Stuart.ps1 -Name district-demo -Mode hardware `
  -DataDir 'D:\VitaminBob\data' -CountryCode '+91' `
  -AllowedPhone '+919000000001' `
  -GatewayCredential (Get-Credential -Message 'SMS Gate local credentials')
.\Start-Stuart.ps1 -Config runtime/profiles/district-demo.json
```

Install the pinned Python requirements and Android platform-tools before this step. The initializer refuses to replace an existing profile. Edit its JSON to change configuration; restart to apply it. `calls_enabled` enables phone polling/callbacks, and `sms_send_enabled` enables outgoing texts. Both default to false for a hardware profile. The allowlist applies to incoming test events, queued callbacks, and outgoing texts; changing it also constrains work retained from earlier runs. SMS caps count reserved segments, including uncertain sends.

For the current S24 audio route, set `calls_enabled: true` only for an attended call demo. Answer on the second phone, then select **Transfer to PC** in Phone Link. Stuart waits for stable Bluetooth routing before it starts prompts. Call audio uses CABLE Input for transmission and Realtek speaker loopback for reception. Unattended PC transfer is not implemented.

## Logs and recovery

Each profile's `runtime_dir` contains `process.json`, `service.log`, and supervisor logs. Service logging excludes HTTP access URLs, which can contain webhook tokens. Logs roll to `service.previous.log` at the next launch if larger than 2 MB. Live rotation and a long-term retention policy are not implemented.

Check `/ready` and `/diagnostics` after reconnecting the phone. The bridge repairs tunnels and hook registrations automatically. USB authorization prompts and starting SMSGate's Local server are human steps. Stuart never changes Android permissions during routine startup.

With phone Wi-Fi and mobile data off, SMSGate can return HTTP 500 from `/health` because its internet connection checks fail. Stuart accepts that specific result only when the failed checks are limited to internet status/transport and its authenticated local API remains reachable. A cellular health failure still prevents readiness. This behavior was checked against the S24 over USB with both data settings off.

After resolving a Bob outage, explicit operator recovery is available:

```powershell
$h = @{ 'X-VB-Contract' = '0.2' }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8200/operator/retry-events -Headers $h
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8200/operator/retry-pending -Headers $h
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8200/operator/retry-sync -Headers $h
```

These are manual recovery actions, not a routine startup sequence. Event replay preserves IDs and never re-executes old call actions. Review pending callbacks before retrying: an approved decision can place a call when phone calling is enabled. Do not requeue an uncertain SMS with a new ID until its original gateway status has been checked.

## Backup and restore

```powershell
.\Backup-Stuart.ps1
```

The SQLite backup API takes consistent copies of Stuart's databases while running, checks their integrity, and includes the local sync key if present. Bob's database and recordings are not copied. The result lives under the profile's ignored `runtime_dir/backups/`; it contains private transport data and the encryption key. Copy it to the intended protected backup location yourself. A key supplied externally through `VB_SYNC_KEY_HEX` must be retained separately.

Restore into a fresh recovery profile with the same `hub_id`, empty data/runtime directories, and a free port:

```powershell
.\.venv\Scripts\python.exe -m stuart restore `
  --config runtime/profiles/recovery.json `
  --backup '<absolute backup directory>'
```

Restore checks integrity and refuses to overwrite existing databases or keys. It does not start a service. Configure Bob's prompts and shared data path before starting the recovery profile. Recovering Central's receiver and Stuart's queue can repeat encrypted frames; committed record IDs remain deduplicated.

## Remaining integration work

See `POC_EVIDENCE.md` for passed checks and remaining hardware evidence. Bob's two-line outbox status fix is prepared in `tools/Bob-Outbox-Status-Fix.patch`; its owner/Meet must apply it at integration. No Bob source is changed by these runtime tools. Gemma and Bob startup remain Bob's responsibility. Resolve the plain clinic-SMS versus encrypted-SMS requirement before enabling patient-bearing alerts.
