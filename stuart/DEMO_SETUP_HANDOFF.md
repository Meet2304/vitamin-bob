# Phone-role setup screen: implementation handoff

This is a specification for the dashboard branch, not an implemented settings API. The current working demo retains manual Phone Link **Transfer to PC**. Read `WEBSITE_INTEGRATION.md` and `DEMO_GUIDE.md` first.

## 1. Screen and roles

Add **Demo setup** beside **Live demo**, with three cards in order:

| Role | Fields | Purpose |
|---|---|---|
| Kevin | Receiving phone number | The connected S24 receives missed calls, places callbacks and sends SMS. The laptop runs Bob, Stuart and Gemma. |
| Patient | Demonstration caller number | Places the missed call, answers the callback and receives the proposed patient summary. |
| Clinician | Name, phone number, existing clinic selection | Receives clinician summaries and alerts for the selected clinic. |

Load numbers from the private active configuration; never put real numbers in source, seed defaults or public HTML. The current local profile has Kevin and patient configured, but no real clinician. Show **Configured**, **Not configured**, **Changes awaiting restart**, and separate delivery-verification status. Configured does not mean tested.

Explain that changing Kevin's displayed number does not change the connected phone's SIM or provision a telephone line. Keep the verified USB, Bluetooth, PC audio and manual transfer setup unchanged.

## 2. Validation

- Normalize formatted input into E.164 on the server. Offer an explicit country selector; do not silently assume India.
- Require distinct Kevin, patient and clinician numbers. Reject patient numbers registered as a clinician or district contact: Bob treats those missed calls as check-ins, not patient callbacks.
- Require a valid existing clinic when adding a clinician. Allow an unconfigured clinician while clearly disabling clinician SMS readiness.
- Validate the entire proposed configuration before saving. Reject stale revisions from another tab.

## 3. Backend mapping

Relevant files: `stuart/stuart/runtime.py`, `stuart/stuart/integrated.py`, `stuart/stuart/service.py`, `bob/vitamin_bob/db.py`, and `bob/vitamin_bob/server.py`.

- Kevin's number maps to the active profile's `line_phone`.
- Patient and clinician must be included in Stuart's `allowed_phones`. Preserve separately configured peers such as a Central receiver; remove superseded demo-role entries only when no other role needs them.
- Register the clinician in Bob's database against the selected clinic. An allowlist entry alone is insufficient.
- Resolve the profile selected by the running launcher. Editing `kevin.json` does not change an already-created `demo-phone.json`.
- Do not reset/reseed the database or rewrite historical calls when changing recipients. Preserve stable clinician identities where appropriate and update registrations idempotently.
- Keep real numbers, pending settings and credentials in ignored local runtime storage. Never return SMSGate credentials or operator tokens to the browser.

## 4. Save and apply safely

The current process loads these settings at startup. Implement **Save changes -> Restart required** first; do not claim live application.

Save a validated private pending configuration with a revision. Display applied and pending settings separately. Apply the revision at startup before callback and SMS workers begin. Use recoverable application steps across the profile and Bob database; only mark the revision applied when both agree. If interrupted or inconsistent, keep workers disabled and expose a repairable error. Do not rely on a filesystem write and a SQLite transaction being one atomic operation.

Never interrupt an active call to apply settings. Saving does not send messages or place calls. Show the existing stop/start commands until an owned, idle-only restart mechanism is implemented:

```powershell
.\Stop-IntegratedDemo.ps1 -Mode phone
.\Start-IntegratedDemo.ps1 -Mode phone
```

Fetch the applied revision after restart before displaying success.

## 5. Proposed settings API

These routes must be implemented; they are not present in the current build:

- `GET /api/demo/settings`: applied/pending role settings, revision and feature availability.
- `PUT /api/demo/settings`: validate and save the pending revision.
- Optional separate test-SMS operation for an explicitly selected configured recipient; never trigger it on save.

Use a fixed validated schema, not arbitrary paths, environment variables or shell commands. Keep configuration writes and full phone numbers in the local operator interface. A public website feed must not expose these endpoints. Preserve the existing local-origin restrictions and add suitable operator authorization for sensitive setup actions; a custom request header alone is not authentication.

## 6. SMS summaries

Show outgoing SMS enablement, patient completion summary, clinician consultation summary and urgent-alert options. Distinguish implemented features from planned ones:

- Outgoing SMS is currently disabled in the phone profile.
- Bob already queues clinician alerts for HIGH, EMERGENCY and UNCERTAIN cases.
- Patient completion SMS and all-consultation clinician summaries require implementation.
- Browser/app push notifications do not exist. Label this feature **SMS summaries**.

Generate concise summaries from Bob's finalized result: case code, outcome and next step. Avoid unnecessary transcript disclosure. Preserve urgent-alert behavior and avoid duplicate routine/urgent summaries to the same recipient. Persist an idempotency identity tied to the finalized case, recipient and notification purpose so repeated completion events do not enqueue duplicates. Reuse durable Bob -> Stuart -> SMSGate delivery rather than sending directly from the UI.

Selecting Clinic A does not subscribe that clinician to Clinic B's cases. Explain this in the screen. If one demo clinician represents multiple clinics, make that explicit and deduplicate notifications. Flag clinics without configured real recipients; do not send to dummy seed numbers.

## 7. Backlog and delivery status

The existing demo has a pending test alert. Before enabling SMS, review/hold pending messages in both Bob's outbox and Stuart's queue. Never automatically release stale messages or rewrite their recipients to a newly configured clinician. Retain audit history and require an explicit disposition of old queued work.

Display **queued**, **accepted by SMSGate**, **sent**, **delivered**, or **failed** from actual transport evidence. Acceptance is not delivery. Correct any UI text claiming an alert was sent when it was only queued.

Incoming SMS acknowledgement remains unverified on this setup. Keep dashboard acknowledgement as the demonstrated fallback until a real inbound SMS test succeeds.

## 8. Acceptance checks

1. Settings survive restart, and the screen reports the applied revision accurately.
2. Invalid numbers, role conflicts, invalid clinics and stale writes are rejected without partial changes.
3. Updating recipients preserves call history. An interrupted apply does not start workers with inconsistent settings.
4. Patient missed calls trigger callbacks and actual live progress; clinician missed calls take the check-in path.
5. Saved settings alone trigger no calls or SMS. Old queued messages remain held until explicitly handled.
6. A completed consultation queues the intended summaries once, including under event retries. Urgent cases do not generate duplicate routine summaries.
7. Actual receipt is verified on the patient and clinician phones. SMS errors are visible and delivery is not inferred from enqueue success.
8. The public website exposes neither private setup settings nor SMS controls.

Keep setup separate from the five-stage call story: missed call, queue, callback, conversation, result. Integration into a public website also requires the secured backend connection described in `WEBSITE_INTEGRATION.md`; localhost does not refer to the presenter's laptop for remote visitors.
