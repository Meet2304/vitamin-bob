# Bob integration evidence and handoff

**Update, 2026-10-04:** merged `origin/main` at `58d2341` into the Stuart integration branch. The outbox fix below is now applied to that integrated checkout, with regression coverage. Real Gemma WAV scenarios, Clinic A failover, SMS receipts, and Central ACKs passed together. See [DEMO_GUIDE.md](DEMO_GUIDE.md). The older candidate-only evidence below is retained as history; the separate Bob worktree remains unchanged.

The smoke check runs current Bob and Stuart over localhost HTTP, with fresh shared data, dummy seed phones, scripted calls, keyword understanding, simulated SMS and encrypted loopback Central transport. It never enables Android or sends real SMS. Bob's source and existing database are inputs, not modified by this check.

```powershell
& .\.venv\Scripts\python.exe tools/check_bob_contract.py --bob-root '<absolute bob module path>' --prompt-root '<absolute existing data/prompts path>'
```

Default ports are 18101 and 18201. The script rejects occupied ports, copies prompt audio to an isolated ignored runtime directory, starts both services, executes synthetic Hindi/Gujarati conversations, submits a registered dummy clinician's `CLOSED` SMS, verifies delivery and ACK statuses through the APIs, writes a report and stops both services. It validates every copied WAV against the contract (121 clips on this laptop). It does not evaluate Gemma or clinical accuracy.

## Discovered status race

Current Bob completed both conversations and Stuart delivered three simulated SMS and acknowledged four Central records. The stricter check failed because Bob's flush code could overwrite a received `acked` status with `queued` after its enqueue HTTP request returned. Queuing a batch gives the first records enough time to finish while later records are still being admitted.

The prepared two-line patch applies the enqueue result only when the record is still `pending`. A later status from Stuart survives. It covers SMS and sync. The actual Bob worktree remains unchanged; the patch was tested in an isolated source copy.

Candidate evidence: `runtime/bob-contract-check/63027435-f0ac-4cd9-b5f2-6487bbc41334/result.json`.

- Hindi and Gujarati conversations completed with UNCERTAIN outcomes (the synthetic descriptions supplied no usable symptoms).
- Three simulated SMS delivered, including the clinician command reply.
- The registered clinician command closed Clinic A.
- Four Central records committed and all four remained `acked` in Bob.
- No transport errors or unacknowledged Stuart events remained.

## Applying at Bob's integration step

Review `tools/Bob-Outbox-Status-Fix.patch` with Bob's source owner, then apply it from the repository root containing `bob/`:

```powershell
git apply --check --ignore-space-change '<absolute path to stuart/tools/Bob-Outbox-Status-Fix.patch>'
git apply --ignore-space-change '<absolute path to stuart/tools/Bob-Outbox-Status-Fix.patch>'
```

The check command passed against the current Bob worktree; `--ignore-space-change` handles its Windows line endings. Repeat the smoke check against the actual Bob module after applying. Existing Bob tests should also run on its branch. Physical Hindi/Gujarati audio, Gemma latency on call recordings, real clinician SMS and over-air encrypted Central sync are later checks.
