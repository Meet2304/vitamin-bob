# Contract 0.2: decisions for Meet

Implementation stays within Stuart. No contract version was changed.

1. The brief's “anything sent by SMS is encrypted” conflicts with ordinary readable clinic SMS commands and clinician alerts. Stuart encrypts Central data and ACKs; `/v1/sms` currently transports Bob's supplied text unchanged. Meet must resolve the intended scope before patient-bearing SMS is used.
2. When Bob is down at `missed_call`, Stuart durably stores a pending decision and does not call without `callback:true`. After the initial request and three retries, an operator can recover with `POST /operator/retry-pending`. Propose a specified recovery/outbox policy and an event-delivery failure indication for the dashboard.
3. Exactly-once Central storage is implemented by authenticated frames, repeated delivery and persistent record-ID deduplication. Eventual delivery requires a working transport and receiver. After five transmission attempts the record is failed; this is visible and needs operator retry rather than a false guarantee.
4. ADB telephony state does not reliably distinguish dialing from remote answer on every OEM. The adapter cannot promise accurate `no_answer` versus remote hangup yet; a phone capability test or companion dialer will determine it.
5. In fake-Bob tests, a synthetic test WAV is intentionally retained so Stuart's recording can be inspected. Real Bob must delete recordings after processing as specified.
6. Bob dependency found in the supplied ZIP: fixture h08 extracts “two and a half weeks” as 7 days with the keyword baseline, reducing HIGH to MEDIUM. Duration evidence/clarification, Gujarati prompts, actual appointments, clinic location/status freshness and reliable alert acknowledgements are needed in Bob. Stuart does not edit Bob's source or medical protocol.
7. Action representation uses `type: play|keypad|listen|hangup`, plus the fields in section 7.3. Please ensure Bob uses this discriminator. Status output remains the section 7.5 shape; additional transport diagnostics and cost are separate endpoints.
8. Kevin's line and Clinic A's clinician phone are the same device. A clinician dashboard acknowledgement is the honest demo path unless a separate alert destination is supplied.
