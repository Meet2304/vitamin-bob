"use client";

import { useEffect, useState } from "react";
import { Screen } from "./Phone";

/**
 * The real thing: Bob's live call view (/dashboard/live), embedded from the same local Bob server.
 * On the presenter's laptop the site is served by Bob, so the embed works. On a public copy
 * (Vercel or any static host) there is no Bob: we say so instead of showing an empty frame.
 */
type Where = "checking" | "local" | "public";

function useBob(): Where {
  const [where, setWhere] = useState<Where>("checking");
  useEffect(() => {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 2500);
    fetch("/api/state", { cache: "no-store", signal: ctl.signal })
      .then((r) => setWhere(r.ok && (r.headers.get("content-type") ?? "").includes("json") ? "local" : "public"))
      .catch(() => setWhere("public"))
      .finally(() => clearTimeout(timer));
    return () => ctl.abort();
  }, []);
  return where;
}

const STAGES = ["Missed call received", "Queued for callback", "Bob rings back", "In conversation", "Result recorded"];

export function Live() {
  const where = useBob();
  return (
    <Screen id="live" title="LIVE CALL" signal={4} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h2 className="text-[40px] leading-[1.05] font-bold tracking-tight md:text-[60px]">Watch a real call.</h2>
            <p className="mt-4 max-w-[680px] text-xl leading-snug md:text-2xl">
              Give a missed call to the district line and follow it: received, called back, connected, in
              conversation, and the record Bob keeps at the end. Everything runs on one laptop.
            </p>
          </div>
          {where === "local" && (
            <div className="flex flex-wrap gap-3 font-mono text-[13px] font-medium">
              <a href="/dashboard/live" className="px-box px-4 py-2 hover:bg-px hover:text-lcd">Full screen</a>
              <a href="/dashboard/details" className="px-box px-4 py-2 hover:bg-px hover:text-lcd">Operations dashboard</a>
            </div>
          )}
        </div>

        {where === "local" ? (
          <div className="px-box mt-8 overflow-hidden bg-lcd">
            <div className="flex items-center justify-between bg-px px-4 py-2 font-mono text-[13px] font-medium text-lcd">
              <span>LIVE · /dashboard/live</span>
              <span>local Bob server</span>
            </div>
            <iframe title="Vitamin Bob live call" src="/dashboard/live" className="block h-[72vh] w-full border-0 bg-white" />
          </div>
        ) : (
          <div className="px-box mt-8 grid gap-8 p-6 md:grid-cols-[1fr_1.1fr]">
            <div>
              <div className="font-mono text-[13px] font-medium">
                {where === "checking" ? "LOOKING FOR THE LOCAL BOB SERVER…" : "THE LIVE CALL RUNS ON THE PRESENTER’S LAPTOP"}
              </div>
              <p className="mt-3 text-xl leading-snug">
                The phone line, Gemma and every patient’s data stay on one laptop at the district hub, with no
                internet. This public copy of the site cannot reach it, by design. Run it yourself to watch calls
                live, or see the demo video.
              </p>
              <a href="#try" className="mt-5 inline-block bg-px px-5 py-3 font-mono text-[13px] text-lcd">How to run it →</a>
            </div>
            <ol className="flex flex-col gap-2">
              {STAGES.map((s, i) => (
                <li key={s} className="flex items-center gap-3 border-b-2 border-dotted border-px-2 py-2 last:border-0">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center bg-px font-mono text-[13px] text-lcd">{i + 1}</span>
                  <span className="text-lg">{s}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </Screen>
  );
}
