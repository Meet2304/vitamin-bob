# Vitamin Bob · story website

The whole site is a feature phone's screen: a pastel-green LCD, pixel sprites of one simple character, and a
voice-menu navigation ("Press 1 for the problem"). It tells the problem (scarce clinicians, one queue for
everyone, paperwork), then the fix in eight phone screens, the proof, a live call, and how to try it.

**Stack:** Next.js 16 (App Router, static export), React 19, Tailwind CSS 4. No server needed.

```bash
cd site
npm install
npm run dev          # http://localhost:3000
npm run build        # public copy in ./out, served at the domain root (Vercel, any static host)
npm run build:bob    # Bob's copy, served at /website; then: python ../bob/tools/import_website.py
```

## Deploying to Vercel

- **Root Directory:** `site`
- Framework preset: Next.js (detected). Build command `npm run build`; no environment variables needed.
- Do **not** set `SITE_BASE_PATH` on Vercel: the public copy lives at the domain root.

The public copy is the story only. Its "Live call" screen checks for Bob's API; on Vercel there is none, so
it explains that the live call runs on the presenter's laptop. The phone line, Gemma, patient data and the
setup and SMS controls never leave the laptop, and none of them appear on the public site.

## On the presenter's laptop

Bob serves the `build:bob` copy at http://127.0.0.1:8100/website/ (and `/` redirects there). There the "Live
call" screen embeds `/dashboard/live` from the same origin.

## Where things are

| Path | What |
|---|---|
| `src/components/lcd/Sprite.tsx` | The character as LCD pixels: `bob`, `patient`, `child`, `clinician` |
| `src/components/lcd/Phone.tsx` | Screens, the status bar that follows the story, voice-menu navigation, soft keys |
| `src/components/lcd/Boot.tsx` | Opening screen |
| `src/components/lcd/Problem.tsx` | Scarcity, the queue, paperwork, the turn |
| `src/components/lcd/Fix.tsx` | Eight fix screens, proof, try it, call ended |
| `src/components/lcd/Live.tsx` | Live call: embed on Bob, explanation elsewhere |

## Facts on the page, and their sources

- 36.7 health workers per 10,000 in India (WHO GHO, 2024); WHO SDG threshold 44.5 (2016); 270 = 10,000 ÷ 36.7
- 26–53% of a consultation spent writing; up to 48 registers per clinic (Siyam et al., 2021)
- Evaluation numbers: Bob's own evaluation (`bob/eval`), 54 synthetic cases and 10 team recordings
