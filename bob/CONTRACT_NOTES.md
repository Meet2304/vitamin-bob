# Contract notes from Bob (contract 0.2)

Bob implements contract 0.2 as written. Below are the interpretations Bob made where the text left
room, and small proposals. **None of them requires Stuart to change anything for the demo.**

## Interpretations (Bob's behaviour today)

1. **`call_ended` with `no_answer` and no patient input does not raise an alert.** Stuart retries
   unanswered callbacks and sends `callback_failed` when it gives up; Bob raises one UNCERTAIN
   alert then, so one patient doesn't produce one alert per attempt. Every other call that ends
   without a classification (hang-up, `failed`, Bob gave up) becomes UNCERTAIN with an alert,
   and never lower than what was already known.
2. **`action_result` with `caller_hung_up`:** Bob replies with a single `hangup` and waits for
   `call_ended`.
3. **The beep before `listen` is a Bob prompt** (`data/prompts/system/beep.wav`, played as the last
   `play` before `listen`). Stuart doesn't need to add one.
4. **Missing or wrong `X-VB-Contract` header:** Bob logs a warning (shown on the dashboard) and still
   processes the event, so a header slip can't drop a patient's call.
5. **Recordings:** Bob deletes a recording after processing, but only if it's inside
   `data/recordings/`. It never deletes an arbitrary path it is given.
6. **Test hook, ignored in production:** the fake Stuart may write `<recording>.transcript.txt` next
   to a recording so Bob can be tested without the model. Bob reads it only if Gemma produced no
   transcript, and deletes it with the recording. Real Stuart never needs to write it.
7. **SMS priorities used by Bob:** `urgent` for clinician alerts and escalations, `normal` for replies
   to clinician commands and check-ins. Bob never sends `bulk` SMS itself (sync is Stuart's).

## Proposals (for Meet to decide; Bob works without them)

1. **Optional `answered_at` on `call_started` or a new `call_answered` event**, if Stuart ever finds a
   dependable pick-up signal. Bob would then skip menu repeats played before pick-up.
2. **Optional `segments` and `estimated_inr` per message in `sms_status`**, so the dashboard's cost per
   case can use Stuart's exact segment counts per case rather than daily totals.
