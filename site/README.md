# Vitamin Bob · story website

The whole site is a feature phone's screen: a pastel-green LCD, pixel sprites of one simple character, and a
voice-menu navigation ("press 1", "press 2"). The World Bank Group's purple, from the summit deck, is the accent:
key phrases, step numbers and lifted cards, never whole surfaces.

The story follows the summit deck: access to care begins before reaching the clinic. The hero is one call you
can answer (Listen. Guide. Connect.); then care out of reach (4.6 billion people), India's health workers, the
patient's journey, the turn, the fix (Kevin's call in six steps on one pinned screen), recognition
(the summit ignite talk and the two wins), the team, and the footer. `/team` is the phone's contacts.

Every section is one screen. Scrolling snaps a screen at a time (one wheel or trackpad gesture moves one screen;
see `useWheelSteps` in `Phone.tsx`), and each screen's pieces rise in as it arrives and leave as you move on
(`.rise` and `.sweep` in `globals.css`). Type sizes follow the screen's height as well as its width (`t-display`,
`t-h2`, `t-h3`, `t-lead`, `t-body`), so nothing is cut off below the status bar.

**Stack:** Next.js 16 (App Router, static export), React 19, Tailwind CSS 4. No server needed.

```bash
cd site
npm install
npm run dev          # http://localhost:3000
npm run build        # public copy in ./out, served at the domain root (Vercel, any static host)
npm run build:bob    # Bob's copy, served at /website; then: python ../bob/tools/import_website.py
```

Before pushing, run what CI runs (`.github/workflows/site-ci.yml`, on every PR that touches `site/`):

```bash
npm run format:check # Prettier (npm run format to fix)
npm run lint         # ESLint
npm run typecheck    # next typegen + tsc
npm run build        # and npm run build:bob
```

## Deploying to Vercel

- **Root Directory:** `site`
- Framework preset: Next.js (detected). Build command `npm run build`; no environment variables needed.
- Do **not** set `SITE_BASE_PATH` on Vercel: the public copy lives at the domain root.

The public copy is the story only. The phone line, Gemma, patient data and the setup and SMS controls never
leave the presenter's laptop, and none of them appear on the public site.

## On the presenter's laptop

Bob serves the `build:bob` copy at http://127.0.0.1:8100/website/ (and `/` redirects there). The live call
dashboard is at `/dashboard/live`; the site no longer embeds it.

## Where things are

| Path                             | What                                                                             |
| -------------------------------- | -------------------------------------------------------------------------------- |
| `src/components/lcd/Sprite.tsx`  | The character as LCD pixels: `bob`, `patient`, `child`, `clinician`              |
| `src/components/lcd/Phone.tsx`   | Screens, the status bar that follows the story, voice-menu navigation, scrolling |
| `src/components/lcd/Boot.tsx`    | Opening screen: a call you can answer, driven by Listen / Guide / Connect        |
| `src/components/lcd/Problem.tsx` | Care out of reach, India, the patient's journey, the turn                        |
| `src/components/lcd/Story.tsx`   | The fix: one pinned diagram, moved on through six steps as you scroll            |
| `src/components/lcd/Wins.tsx`    | Hero summit badge and recognition: the summit talk and the two wins              |
| `src/components/lcd/People.tsx`  | The team on the home page, with a link to `/team`                                |
| `src/components/lcd/Footer.tsx`  | The footer, on both pages                                                        |
| `src/components/lcd/rise.ts`     | Order of the pieces that move in on each screen                                  |
| `src/app/team/page.tsx`          | The team page: group call, then one speed-dial card per person                   |
| `src/components/team/`           | Team page components; names, roles, emails and links are in `members.ts`         |
| `public/images/team/`            | Colour portraits and their LCD-dithered versions                                 |
| `public/images/logos/`           | Gmail, LinkedIn and X logos (svglogos.dev); globe.svg for personal sites         |

## Facts on the page, and their sources

- 4.6 billion people lack access to essential health services (WHO & World Bank, UHC Global Monitoring Report
  2025, as cited in the summit deck)
- Summit: World Bank Group Global AI & Digital Summit, Seoul, 19–22 October 2026; session "Benefiting Billions:
  Scaling AI for Healthier Lives", 21 October, 10:30 (speaker invitation, 7 October 2026)
- 36.7 health workers per 10,000 in India (WHO GHO, 2024); WHO SDG threshold 44.5 (2016); 270 = 10,000 ÷ 36.7

## Partner logos

- `world-bank-group.png`: the World Bank Group logo from Wikimedia Commons (`File:World_Bank_Group_logo.svg`,
  public domain), rendered at 640px.
- `hack-nation.png`: Hack-Nation's own logo from hack-nation.ai (`/images/hack_nation_logo-tight.jpeg`), with the
  white background made transparent.
- `meetbhatt.png`: the app icon of meetbhatt.com.
