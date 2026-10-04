# Vitamin Bob

**Primary care triage over a free missed call, with a small AI model that runs on one laptop.**

A patient with any phone gives a missed call, which costs nothing. A district laptop calls back. It listens to the patient describe the problem in Hindi or Gujarati, using **Gemma 4 running locally**. It asks only the keypad questions it still needs. Then it tells the patient to call 108, go to the nearest open clinic now, or come at a booked time. There is no app to install, nothing for the patient to pay, and no internet needed while it runs.

Built by Egshiglen, Meet, Rizaldy and Yusril for the Hack-Nation × World Bank *Small AI for Development* hackathon (Health track), October 2026.

| | Link |
|---|---|
| **Website** | **https://vitamin-bob.vercel.app/** |
| Data story and country explorer | https://rzrizaldy.github.io/vitamin-bob/ |
| Code | https://github.com/rzrizaldy/vitamin-bob |

---

## How a call works

1. **Missed call.** The patient calls Bob's number and hangs up, so the call costs them nothing.
2. **Callback.** A regular Android phone with a SIM, connected to the laptop, calls the patient back.
3. **Bob listens.** The patient picks Hindi or Gujarati, then describes the problem for up to 25 seconds. **Gemma 4, running on the laptop**, turns the speech into text, then into a fixed form (fever yes/no, days, danger signs).
4. **Only what's missing.** Bob asks keypad questions only for the items the description didn't answer (1 yes, 2 no, 3 don't know).
5. **Rules decide, not the AI.** Fixed rules set the urgency: EMERGENCY (call 108), HIGH (go to the nearest open clinic now), MEDIUM or LOW (booked slot). Clinicians get an alert for every urgent or uncertain case.

The AI never speaks (every sentence is a pre-recorded clip) and never decides the urgency. If the model is slow, down or unsure, Bob asks more keypad questions instead of skipping a safety check.

---

## ⭐ Run the local model (Gemma 4 E2B)

**This is the core of Vitamin Bob.** All speech understanding happens on the laptop through [llama.cpp](https://github.com/ggml-org/llama.cpp). There are no cloud AI calls. You need internet once, to download about 6 GB. After that, everything runs offline.

### What you need

| | Minimum | What we tested on |
|---|---|---|
| Computer | Windows, macOS or Linux | Windows 11 laptop: Ryzen 7 6800H, 15 GB RAM |
| GPU | Optional (CPU works, slower; not measured) | NVIDIA RTX 3050 Ti, 4 GB |
| Disk | About 7 GB free | |
| Model | Gemma 4 **E2B**, Q8_0, plus its audio projector | |

### Step 1. Put the folders side by side

The start scripts look for `llama.cpp/` and `models/` **next to** this repository:

```
anywhere/
├── vitamin-bob/      ← this repository
├── llama.cpp/        ← llama-server goes here (Step 2)
└── models/           ← the two .gguf files go here (Step 3)
```

```bash
git clone https://github.com/rzrizaldy/vitamin-bob.git
mkdir llama.cpp models
```

### Step 2. Get llama.cpp (the model server)

We used release **b11382**. Any newer release should also work.

- **Windows:**
  1. Open the [b11382 release page](https://github.com/ggml-org/llama.cpp/releases/tag/b11382) and download the Windows x64 build:
     - **CUDA 13** for an NVIDIA GPU. Also download the matching `cudart` zip.
     - **CPU** if there is no NVIDIA GPU.
  2. Unzip everything into `llama.cpp\`, so `llama.cpp\llama-server.exe` exists.
- **macOS:** `brew install llama.cpp`, or download the macOS Apple Silicon build from the same page.
- **Linux:** download the Ubuntu build from the same page, or build from source.

### Step 3. Download Gemma 4 E2B (two files, about 6 GB)

From Hugging Face, [ggml-org/gemma-4-E2B-it-GGUF](https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF):

| File | Size | Job |
|---|---|---|
| `gemma-4-E2B-it-Q8_0.gguf` | 4.97 GB | The language model |
| `mmproj-gemma-4-E2B-it-BF16.gguf` | 0.99 GB | The audio encoder. **Without it, Gemma cannot hear.** |

```bash
pip install -U huggingface_hub
hf download ggml-org/gemma-4-E2B-it-GGUF gemma-4-E2B-it-Q8_0.gguf mmproj-gemma-4-E2B-it-BF16.gguf --local-dir models
```

You can also download both files in the browser from the "Files" tab of that page and save them into `models/`. Keep the file names exactly as they are.

### Step 4. Start the model

**Windows** (from the `vitamin-bob\bob` folder):

```powershell
tools\start_model.cmd
```

**macOS / Linux** (from the folder that holds `models/`):

```bash
llama-server -m models/gemma-4-E2B-it-Q8_0.gguf \
  --mmproj models/mmproj-gemma-4-E2B-it-BF16.gguf \
  --host 127.0.0.1 --port 8300 -c 8192 --jinja
```

Leave this window open. The model listens on **http://127.0.0.1:8300**, on this machine only.

The script's defaults can be changed with environment variables:
- `VB_LLAMA_DIR`: where `llama-server` lives.
- `VB_MODEL_DIR`: where the `.gguf` files live.
- `VB_MODEL_SIZE=E4B`: use the larger model. It is about 3 times slower on a 4 GB GPU (see the table below).

### Step 5. Check that it works

```bash
curl http://127.0.0.1:8300/health
```

You should get `{"status":"ok"}`. Bob's dashboard also shows the model's status once Bob is running (next section).

### How fast it is (measured on the demo laptop, 25-second clip)

| Model | Generation speed | Time to transcribe 25 s | Verdict |
|---|---|---|---|
| E4B Q8_0 | 5.9 tokens/s (partly on CPU) | 14–18 s | Too slow once the form step is added |
| **E2B Q8_0** | **13–15 tokens/s** | **5–7 s** | **Used.** Same word error as E4B on clean speech |

**What Bob sends the model:**
- **Two passes:** audio → transcript, then transcript → form.
- **Compact output:** the form pass is locked by a grammar to a few short lines, so it takes 2–5 s.
- **Thinking off:** Bob turns Gemma's "thinking" mode off (`enable_thinking: false`), because there's no time for it.
- **Time budget:** 17 s for both passes. If it runs over, Bob falls back to keyword matching and asks more keypad questions.

**Honest limit:** public benchmarks put Gemma's word error on phone speech at about 9% in Hindi but 27% in Gujarati. In Gujarati, expect more keypad questions. Safety doesn't drop.

---

## Run Bob (the brain) with the local model

With the model running from the previous section, open a second terminal in `vitamin-bob/bob`:

**Windows:**

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python -m vitamin_bob.server        # Bob on http://127.0.0.1:8100
```

**macOS / Linux:**

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m vitamin_bob.server            # Bob on http://127.0.0.1:8100
```

Open **http://127.0.0.1:8100/dashboard**. Then, in a third terminal (same folder), play the team's 17 scripted calls through Bob. No phone is needed:

```bash
.venv/bin/python -m fake_stuart run --pace 1.5     # Windows: .venv\Scripts\python -m fake_stuart run --pace 1.5
```

**Useful extras:**
- `python eval/run_eval.py --mode all` runs the evaluation: keyword baseline and Gemma, per language. Results appear on the dashboard.
- `python tools/try_questionnaire.py` plays a call through the laptop speakers, with the keyboard as the keypad.
- `python -m vitamin_bob.db --reset` resets the demo district.

**Which understanding Bob uses.** `VB_UNDERSTAND` controls this:
- `auto` (the default) uses Gemma whenever port 8300 answers, and the keyword baseline otherwise.
- `gemma` forces the model.
- `keyword` runs without any model.

**One-time setup: the voice prompts.** Every sentence Bob says is a pre-recorded clip, generated once with Sarvam text-to-speech:
1. Copy `bob/.env.example` to `bob/.env` and add a Sarvam API key.
2. Run `python tools/gen_prompts.py`. This is the only other step that needs internet.

More detail is in [`bob/README.md`](bob/README.md).

---

## Run the full phone demo (Windows + Android phone)

This is the live setup in our technical walkthrough video: a real missed call, a real callback, and Gemma on the laptop.

**You need:**
- A Windows laptop with the model files from the steps above.
- An Android phone with a SIM, connected over USB (ADB) and Bluetooth.
- Phone Link open.
- A second phone to act as the patient.

From `vitamin-bob/stuart` in PowerShell:

```powershell
.\Start-IntegratedDemo.ps1 -Mode phone     # starts local Gemma, Bob and Stuart together
.\Stop-IntegratedDemo.ps1 -Mode phone
```

The launcher starts the model itself (from `..\..\llama.cpp` and `..\..\models`, the same layout as Step 1) and prints:
- the dashboard: http://127.0.0.1:8100/dashboard
- the setup screen, for the phone numbers: http://127.0.0.1:8100/dashboard/setup
- the website served locally: http://127.0.0.1:8100/website/

The first start can take up to 3 minutes while Gemma loads.

To make the call, from the patient phone dial Bob's number, let it ring, and hang up. Answer the callback, then click **Transfer to PC** in Phone Link. That one step is still manual. Follow the spoken prompts.

Step by step, including audio routing: [`stuart/DEMO_GUIDE.md`](stuart/DEMO_GUIDE.md) and [`stuart/PHONE_AUDIO_SETUP.md`](stuart/PHONE_AUDIO_SETUP.md).

**Privacy:** real phone numbers live only in git-ignored local files (`stuart/runtime/profiles/`, `bob/seed/demo_district.local.json`). They are never committed. Numbers are masked on screen.

---

## What is verified, and what is not yet

**Verified:**
- A real missed call → callback → Gujarati conversation → EMERGENCY result ran end to end through Bob and Gemma on the laptop on 4 Oct 2026. Gemma processed the recording in about 8 seconds.
- In the evaluation (54 synthetic cases and 10 team recordings): **0 urgent cases missed** in either language. Gemma **halves the "uncertain" rate** against the keyword baseline (Hindi 14% → 7%, Gujarati 10% → 5%).

**Not yet:**
- The danger-sign protocol (`imci-draft-0.3`) has not been reviewed by a clinician.
- No real patients have used it. The test cases were written and voiced by the team.
- Outgoing SMS is turned off in the demo. Incoming SMS (clinic status, acknowledgements) is built but not yet verified on real phones.
- The phone's "Transfer to PC" audio step is manual.

---

## What is in this repository

| Folder | What |
|---|---|
| [`bob/`](bob/) | **The brain:** conversation, Gemma 4 understanding, fixed urgency rules, clinic routing and failover, alerts, dashboard, evaluation |
| [`stuart/`](stuart/) | **Telephony and messaging:** missed calls, callbacks, SMS, encrypted sync to Central, the integrated demo launcher |
| [`site/`](site/) | The public website at https://vitamin-bob.vercel.app/ (Next.js, deploys to Vercel) |
| repository root | The data story and country explorer at https://rzrizaldy.github.io/vitamin-bob/ |
| [`slides/`](slides/) | Data slides for the video (static HTML, imported into Canva) |

### Website (`site/`)

```bash
cd site
npm install
npm run dev        # http://localhost:3000
```

See [`site/README.md`](site/README.md) for the Vercel deployment settings.

### Data story (repository root)

```bash
python3 -m http.server 8000      # then open http://localhost:8000
```

It has four tabs:
- **The story:** seven numbers that lead to the problem statement, including why Indonesia is ready and a Pareto of why India and Indonesia are worth it.
- **The product:** how a call works.
- **Explore countries:** a world map on an Esri basemap.
- **Data & method:** sources, licenses and limits.

The page loads `world.json`, so open it through the server, not as a file.

| File | What |
|---|---|
| `index.html` | Page and styles |
| `app.js` | Story charts (Observable Plot), explorer (Leaflet + D3), tabs and presenter keys |
| `data.js` | Pre-computed data bundle built from the sources below |
| `world.json` | Natural Earth 110m country shapes with ISO3 codes |

## Data and licenses

| Source | Used for | License |
|---|---|---|
| WHO Global Health Observatory: HWF_0001, HWF_0006, UHC_INDEX_REPORTED | Workforce density, service coverage | WHO terms of use |
| World Bank WDI: SP.POP.TOTL, SP.RUR.TOTL, SP.RUR.TOTL.ZS, IT.NET.USER.ZS, IT.CEL.SETS.P2, EG.ELC.ACCS.ZS, SH.TBS.INCD | Rural share, internet, mobile, electricity, TB incidence | CC BY 4.0 |
| Permenkes 24/2022; Kemenkes SATUSEHAT and SITB; Sahabat-AI model card | Indonesia's digital-health rails | cited |
| healthsites.io / OpenStreetMap via HDX | Indonesia facility map, record completeness | ODbL |
| Chaudhury et al. (2004 draft; *J. Econ. Perspectives* 2006) | Provider absence | cited |
| Siyam et al. (2021), *BMC Health Serv Res* 21(Suppl 1):691 | Recording share of consultations | cited |
| Natural Earth via world-atlas; Esri Light Gray Canvas | Country shapes; basemap | public domain; Esri terms |
| Gemma 4 E2B GGUF (ggml-org on Hugging Face, from google/gemma-4-E2B-it) | On-device speech understanding | Apache 2.0 |

**Not shown by this data:**
- Sub-national gaps.
- Measured waiting times.
- Recent absence data.
- Causation.
- Clinic-level connectivity (feasibility uses national averages).
