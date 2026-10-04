# Stuart proof-of-concept evidence

The automated suite passes 65 tests. Evidence is scoped to what was observed on this Windows laptop and S24 Plus. Test phone numbers, credentials, recordings, and detailed reports stay in ignored `runtime/`.

| Capability | Result | Evidence |
|---|---|---|
| Missed call detection, Bob decision, callback/answer/hangup | Passed on the S24 | Earlier bounded callback report and call log detection |
| Spoken prompt, keypad `12#`, and speech capture | Passed with operator Transfer to PC | `runtime/hardware-callback-result.json`; 3.4 s speech |
| Voice with phone Wi-Fi and mobile data off | Passed; laptop stayed online for the assistant | `runtime/hardware-offline-call-result.json`; both phone settings 0, decoded 12#, 2.8 s speech, completed hangup |
| Outbound SMS | Passed; recipient confirmed exactly one copy | `runtime/hardware-sms-result.json`; gateway Delivered, status recovered through the production poller |
| Incoming SMS | Pending hardware proof | Test messages arrived as MMS; SMS-only probe timed out. RECEIVE_SMS permission is granted. No SMS history was imported |
| Hindi/Gujarati Bob–Stuart action contract | Passed in isolated Bob candidate with the outbox fix | `BOB_INTEGRATION.md`; 121 valid WAVs, two scripted calls |
| Real call with Gemma understanding | Not yet tested | Bob/model integration remains separate from the transport audio test |
| Encrypted Central framing, ACK, deduplication, loss/tamper/restart recovery | Passed in automated/local transport checks | Automated suite and Bob integration candidate |
| Encrypted Central over a real SMS link | Not yet tested | Needs a separate Central receiver/phone |
| Windows managed startup and readiness | Passed with fake Bob and real SMSGate | `runtime/infrastructure-proof.json` |
| SMSGate readiness with phone internet off | Passed over USB | Both phone data settings 0; only expected internet checks failed; authenticated local APIs remained available |
| Completed work survives service crash | Passed | Supervisor restarted the killed simulator service; two completed calls, one SMS receipt, three Central ACKs retained; no replay |
| USB tunnel and webhook recovery | Passed against the S24 | Removed one owned reverse tunnel and one webhook; the bridge recreated both |
| Managed hardware shutdown | Passed | Four owned hooks removed; queues retained |
| Backup and restore | Passed in tests; live SQLite backup also created | Integrity checked, queue/key preserved, overwrite refused |

The runtime uses localhost HTTP and USB forwarding. SMSGate's “Require Internet connection” setting was initially on and has been turned off for local webhooks. The phone-offline voice check passed with both phone settings independently read as 0 before and after the call. The laptop stayed online for the assistant; a whole-laptop network-disconnection demonstration has not been performed.

Carrier-formatted numeric senders are normalized to the contract's E.164 format. Alphanumeric sender IDs are not accepted by contract 0.2. MMS is a different delivery path and is not presented as a successful offline SMS test. A genuine incoming SMS from a suitable sender is still required.

Hardware PoC profiles restrict traffic to the supplied test peer and start with calls and outgoing SMS disabled. The simulator is ready to demonstrate queueing, concurrent lines, durable receipts, and encrypted local Central delivery immediately. Enabling the live phone path remains an attended operation because Phone Link requires Transfer to PC.
