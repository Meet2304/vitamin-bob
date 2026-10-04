# Website integration handoff

For the proposed phone-number setup screen and SMS-summary work, follow [DEMO_SETUP_HANDOFF.md](DEMO_SETUP_HANDOFF.md). That document specifies remaining implementation work; those settings APIs and patient summaries are not part of the current working demo.

The working demo is launched by `Start-IntegratedDemo.ps1 -Mode phone`. It serves Bob and the live call dashboard on **http://127.0.0.1:8100**, Stuart on **8200**, and local Gemma on **8300**. A real missed-call callback completed with manual Phone Link audio transfer on October 4, 2026.

## Put the live demo inside the website

Recommended for the attended laptop presentation: serve the website from the same Bob server, under a separate route such as `/website`, and add a **Live demo** page. Keep the existing API routes and dashboard files when merging.

The stable embedded route is `/dashboard/live`. `/dashboard` currently serves the same page; `/dashboard/details` preserves the older operations dashboard. A simple same-origin embed is:

```html
<iframe title="Vitamin Bob live call" src="/dashboard/live"
        style="width:100%;height:85vh;border:0"></iframe>
```

Or use `<a href="/dashboard/live">Open live demo</a>`. Avoid restrictive iframe sandbox flags that remove same-origin access: the dashboard polls its APIs and posts callback controls. This is an attended local demo, not a public multi-user deployment.

If the website is served separately on port 8000, a link to `http://127.0.0.1:8100/dashboard/live` is the simplest laptop presentation. Keep both local servers running. An iframe with that absolute URL may also work, but embedding a local HTTP service from a public HTTPS page is browser-dependent and is not the recommended presentation setup.

## If replacing the dashboard UI

Use these existing endpoints instead of inventing simulated call states:

| Endpoint | Purpose |
|---|---|
| `GET /api/state` | Bob sessions, conversation turns, triage, clinics, alerts, SMS/sync summaries, model health |
| `GET /api/live-call` | Actual missed call, queue, callback, audio transfer, conversation and final receipt timeline; paused state and receiving number |
| `POST /api/live-call/control` | `{ "paused": true }` or `false`; send JSON and `X-VB-Demo: 1` |
| `POST /api/alerts/{id}/ack` | Existing clinician acknowledgement action |
| `POST /api/clinics/{id}/status` | Existing clinic availability action |

The live-call endpoints are registered by the **integrated launcher**, not standalone Bob. Poll once per second without overlapping requests. Correlate the two responses using `call_id`; a queued missed call may not have a call ID yet. Use timeline timestamps as the source of truth. `data_received` means Bob acknowledged the completed call; audio connection alone does not mean the consultation finished. Handle failures, early hangups and loss of backend connection visibly.

The pause control accepts the local dashboard origin `http://127.0.0.1:8100`. A different web origin needs deliberate proxy/origin configuration. Do not enable wildcard cross-origin control access. The receiving number and clinical conversation data are local/private; keep runtime files out of source control.

## Public website boundary

Static hosting can publish the website or a clearly labelled recorded demonstration. It cannot run the Python servers, Windows Phone Link, USB connection or local Gemma. `127.0.0.1` refers to each visitor's computer, not the presenter's laptop.

For a remotely visible live demo, add an authenticated backend/reverse proxy or a scoped stream of redacted, read-only events from the laptop. Keep call controls private and protect clinical data. That deployment is separate work; this build does not expose the laptop to the internet. For the current presentation, run locally and share the screen.

## Merge notes for the website branch

- Preserve `dashboard.html` as the live call view and its `/dashboard/live` route, or rename the file and update both routes together. Use a separate template for a new website home page.
- Preserve `dashboard-details.html` and `/dashboard/details` if the technical view is desired.
- Combine additions in `bob/vitamin_bob/server.py`; do not replace the server wholesale. Website static assets and additional statistics can coexist with these routes.
- Keep the Stuart progress table, phase reporting, missed-call deduplication and integrated API routes from this build.
- Start with the integrated launcher after merging and verify the website, live timeline, pause/resume and results on the same backend.
