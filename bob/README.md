# Vitamin Bob

Missed-call health routing for feature phones. A patient gives a free missed call; Bob calls
back, listens to the problem in Hindi, asks only the follow-up questions it still needs
(keypad: 1 = yes, 2 = no, 3 = don't know), and routes the case: call 108, go to the clinic now,
or a booked slot. A clinician is alerted for every urgent or uncertain case.

Built for the World Bank × Hack-Nation Small AI for Development Hackathon, health track.

## Run it

```bash
pip install -r requirements.txt
ollama pull gemma3:4b             # or llama3.2:3b; set VB_MODEL to switch

python -m vitamin_bob.cli                       # text call, LLM extractor
python -m vitamin_bob.cli --extractor keyword   # text call, keyword baseline
python eval/run_eval.py --extractor both        # LLM vs keyword on all vignettes
```

## How it is put together

| Module | Job | AI? |
|---|---|---|
| `protocol.py` | Symptoms, red flags, Hindi prompts, tiers. Fixed and reviewable. | No |
| `extract.py` | Hindi description → fixed form (yes / no / unknown). LLM or keyword baseline. | Yes |
| `rules.py` | Form → tier. Deterministic, explains itself. | No |
| `session.py` | One call as a state machine; shared by CLI, eval and demo. | No |
| `eval/` | 38 synthetic vignettes and the evaluation harness. | — |

Everything runs on one gateway machine with no internet. The patient needs only a phone that
can make a call.

## Prompt audio (what Bob says)

Everything Bob says is a fixed, pre-recorded clip; the model never generates speech. Clip text is
data in `prompts/<lang>.json` (Hindi and Gujarati), languages and the TTS voice are set in
`prompts/languages.json`, and a sentence is a list of clips (`vitamin_bob/prompts.py`), which maps
onto the contract's `play` actions. Clinic names, times and case-code digits are separate clips
placed at the end of a sentence, so a new language is only translated rows plus audio.

```bash
cp .env.example .env                       # add SARVAM_API_KEY (used only before the demo)
python tools/gen_prompts.py --dry-run      # what will be generated (~4,400 characters)
python tools/gen_prompts.py                # Sarvam bulbul:v3 -> data/prompts/<lang>/<key>.wav
python tools/gen_prompts.py --placeholder  # tones instead of speech, to test offline
python tools/try_questionnaire.py          # hear a call on the laptop; keyboard = keypad
```

Clips are regenerated only when their text or voice changes (`data/prompts/manifest.json`).
Output is WAV, 16 kHz, mono, 16-bit, checked after every run. The Gujarati text was written by
the team and **needs a native speaker's check** before the demo.

## Guardrails

- **No diagnosis, no advice.** Bob only routes. Questions, tiers and every sentence Bob says are fixed.
- **The model can stay silent, not invent.** Each yes/no it extracts must quote words that
  appear in the transcript; otherwise it is dropped to "unknown".
- **The description can raise urgency, never silently lower it.** A "no" on an emergency sign
  is always confirmed on the keypad.
- **Unknown means a human decides.** Any open question that could hide an urgent case gives
  UNCERTAIN, which alerts a clinician.
- **Shared-phone safe.** The patient SMS carries only clinic, time and case code.

## Evaluation

Metrics, in order: missed urgent cases (target 0), emergencies sent to clinic instead of 108,
tier accuracy, **Uncertain rate (the metric to drive down)**, keypad questions per call, and
extractor misreads.

## Data card

- **Vignettes:** 38, synthetic, written by the team, labelled with the expected tier. 8 are
  deliberately hard (negation traps, colloquial and misspelt Hindi, durations in weeks/months).
- **Not covered:** real patient speech, regional dialects and other languages, speech-recognition
  errors on real phone audio, multiple simultaneous complaints beyond fever/cough/diarrhoea.
- **Protocol:** drafted from WHO IMCI danger signs; not yet reviewed by a clinician.
