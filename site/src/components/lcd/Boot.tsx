"use client";

import { useEffect, useState } from "react";
import { Screen, useKeypadNav } from "./Phone";
import { rise } from "./rise";
import { Sprite } from "./Sprite";
import { Recognition, WinnerSeal } from "./Wins";

/** Pixels of a ")" arc: part of a circle of radius r centred left of the grid, like a ringing signal. */
function arc(r: number, cy: number): [number, number][] {
  const span = Math.round(r * 0.7);
  const out: [number, number][] = [];
  for (let dy = -span; dy <= span; dy++)
    out.push([Math.round(Math.sqrt(r * r - dy * dy)) - Math.round(r * 0.7), cy + dy]);
  return out;
}

/** Three arcs that light up one after another while the phone rings, on the same 8px grid as Bob. */
export function RingWaves({ flip = false }: { flip?: boolean }) {
  return (
    <svg
      viewBox="0 3 9 15"
      width={9 * 8}
      height={15 * 8}
      shapeRendering="crispEdges"
      aria-hidden
      className={flip ? "-scale-x-100" : ""}
    >
      {[3, 6, 9].map((r, i) => (
        <g key={r} fill="var(--color-px)" className="wave" style={{ animationDelay: `${i * 0.25}s` }}>
          {arc(r, 10).map(([x, y]) => (
            <rect key={`${x},${y}`} x={x + i * 2} y={y} width={1} height={1} />
          ))}
        </g>
      ))}
    </svg>
  );
}

/**
 * The opening screen is one call. The phone rings; ANSWER (or any of the three words) plays it:
 *   listen   Bob hears what's wrong, in Hindi
 *   guide    Bob asks only what's missing and gives a next step
 *   connect  the clinic has the story before the patient arrives
 * Answering plays the three in turn; choosing a word holds the phone on it.
 */
type Stage = "ring" | "missed" | "listen" | "guide" | "connect";
const VERBS = [
  { id: "listen", word: "Listen." },
  { id: "guide", word: "Guide." },
  { id: "connect", word: "Connect." },
] as const;
const STEP_MS = 3400;

function useCall() {
  const [stage, setStage] = useState<Stage>("ring");
  const [auto, setAuto] = useState(false);
  const [secs, setSecs] = useState(0);
  const live = stage === "listen" || stage === "guide" || stage === "connect";

  // Answering plays listen → guide → connect, then holds on connect.
  useEffect(() => {
    if (!auto || stage === "connect" || !live) return;
    const id = setTimeout(() => setStage(stage === "listen" ? "guide" : "connect"), STEP_MS);
    return () => clearTimeout(id);
  }, [auto, stage, live]);

  // Ignoring is fine: Bob rings again.
  useEffect(() => {
    if (stage !== "missed") return;
    const id = setTimeout(() => setStage("ring"), 2600);
    return () => clearTimeout(id);
  }, [stage]);

  // The call timer runs while the call is live.
  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => setSecs((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [live]);

  return {
    stage,
    secs,
    answer: () => {
      setSecs(0);
      setAuto(true);
      setStage("listen");
    },
    ignore: () => setStage("missed"),
    hangUp: () => {
      setAuto(false);
      setStage("ring");
    },
    choose: (s: Stage) => {
      if (!live) setSecs(0);
      setAuto(false);
      setStage(s);
    },
  };
}

const mmss = (n: number) => `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;

const CAPTION: Record<Stage, string> = {
  ring: "Vitamin Bob is calling back, free.",
  missed: "Missed. Bob will try again.",
  listen: "Listen: Bob hears what is wrong, in Hindi.",
  guide: "Guide: Bob asks only what is missing, then gives a clear next step.",
  connect: "Connect: the clinic has the patient's story before they arrive.",
};

function PhoneScreen({ stage, secs }: { stage: Stage; secs: number }) {
  if (stage === "ring" || stage === "missed")
    return (
      <div key={stage} className="stage-in flex flex-col items-center gap-6 px-6 pt-9 pb-8">
        <div className="flex items-center gap-2">
          {stage === "ring" && <RingWaves flip />}
          <Sprite role="bob" mood={stage === "ring" ? "happy" : "calm"} px={8} />
          {stage === "ring" && <RingWaves />}
        </div>
        <div className="flex flex-col items-center gap-1.5 text-center">
          <div className="text-[34px] leading-none font-bold tracking-tight">Vitamin Bob</div>
          <div className="text-lg">{stage === "ring" ? "Calling you back…" : "Missed call. Calling again soon."}</div>
        </div>
        <div className="flex gap-2 font-mono text-[12px] font-medium">
          <span className="border-2 border-px px-2 py-0.5">हिंदी</span>
          <span className="border-2 border-px px-2 py-0.5">ગુજરાતી</span>
        </div>
      </div>
    );

  if (stage === "listen")
    return (
      <div key={stage} className="stage-in flex flex-col items-center gap-5 px-6 pt-7 pb-6">
        <div className="flex items-end gap-4">
          <Sprite role="bob" mood="calm" px={6} />
          <div className="flex h-16 items-end gap-[5px]" aria-hidden>
            {[0.1, 0.35, 0.2, 0.5, 0.05, 0.3, 0.15].map((d, i) => (
              <span key={i} className="eq h-full w-[7px] bg-accent" style={{ animationDelay: `${d}s` }} />
            ))}
          </div>
        </div>
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="font-mono text-[12px] font-medium tracking-wider">LISTENING · हिंदी</div>
          <div className="text-[26px] leading-tight font-bold" lang="hi">
            “तीन दिन से बुखार है…”
          </div>
          <div className="font-mono text-[12px] opacity-80">“I’ve had a fever for three days…”</div>
        </div>
      </div>
    );

  if (stage === "guide")
    return (
      <div key={stage} className="stage-in flex flex-col gap-4 px-6 pt-7 pb-6">
        <div className="flex items-start gap-3">
          <Sprite role="bob" mood="happy" px={4} />
          <div className="px-box relative flex-1 bg-lcd px-3 py-2 text-lg leading-snug">
            <span className="typing">Any trouble breathing?</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 font-mono text-[13px] font-semibold">
          <span className="border-4 border-px py-2 text-center">1 · YES</span>
          <span className="press border-4 border-px py-2 text-center">2 · NO</span>
        </div>
        <div className="border-t-2 border-dotted border-px pt-3 font-mono text-[12px] leading-relaxed">
          <div className="font-semibold">NEXT STEP</div>
          <div>Not urgent. A clinic visit is booked for Thursday, 10:00.</div>
        </div>
      </div>
    );

  return (
    <div key={stage} className="stage-in flex flex-col gap-4 px-6 pt-7 pb-6">
      <div className="flex items-center gap-3">
        <Sprite role="clinician" mood="happy" px={4} />
        <div className="font-mono text-[12px] leading-snug font-medium">
          <div className="bg-accent px-1.5 text-lcd">✓ SENT TO THE CLINIC</div>
          <div className="mt-1">at {mmss(Math.max(secs, 1))}, before Kevin leaves home</div>
        </div>
      </div>
      <div className="border-4 border-px">
        <div className="bg-px px-3 py-1 font-mono text-[11px] font-medium tracking-wider text-lcd">
          PATIENT SUMMARY · KEVIN
        </div>
        <ul className="flex flex-col gap-1 px-3 py-2 font-mono text-[12px] leading-snug">
          <li>▸ Fever, 3 days</li>
          <li>▸ Cough · no trouble breathing</li>
          <li>▸ Not urgent · Thu 10:00</li>
        </ul>
      </div>
      <div className="text-center text-lg leading-snug font-semibold">His story arrives before he does.</div>
    </div>
  );
}

function HeroPhone({ call }: { call: ReturnType<typeof useCall> }) {
  const { stage, secs } = call;
  const ringing = stage === "ring" || stage === "missed";
  return (
    <div className="hero-phone relative w-full max-w-[380px] border-4 border-px bg-lcd">
      <WinnerSeal />
      <div className="flex items-center justify-between bg-px py-2 pr-4 pl-[84px] font-mono text-[13px] font-medium tracking-wider text-lcd">
        <span>{ringing ? "INCOMING CALL" : "VITAMIN BOB"}</span>
        <span className="border border-lcd px-1.5">{ringing ? "FREE" : mmss(secs)}</span>
      </div>

      <div className="flex min-h-[436px] flex-col justify-center bg-lcd-2/60">
        <PhoneScreen stage={stage} secs={secs} />
      </div>
      <p className="sr-only" aria-live="polite">
        {CAPTION[stage]}
      </p>

      {ringing ? (
        <div className="grid grid-cols-2 border-t-4 border-px font-mono text-[13px] font-medium tracking-wider">
          <button
            type="button"
            onClick={call.ignore}
            disabled={stage === "missed"}
            className="cursor-pointer border-r-4 border-px py-3 text-center hover:bg-px hover:text-lcd disabled:cursor-default disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-px"
          >
            IGNORE
          </button>
          <button
            type="button"
            onClick={call.answer}
            className={`cursor-pointer bg-accent py-3 text-center text-lcd hover:bg-px ${stage === "ring" ? "answer-btn" : ""}`}
          >
            ANSWER
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={call.hangUp}
          className="w-full cursor-pointer border-t-4 border-px py-3 text-center font-mono text-[13px] font-medium tracking-wider hover:bg-px hover:text-lcd"
        >
          END CALL
        </button>
      )}
    </div>
  );
}

/**
 * The opening screen, in three calm layers: the promise and one next step on the left, the call on the right,
 * and along the bottom, who stands behind it (the two wins and the summit talk).
 */
export function Boot() {
  const call = useCall();
  useKeypadNav();
  return (
    <Screen id="top" title="VITAMIN BOB">
      <div className="mx-auto flex w-full max-w-[1280px] flex-1 flex-col">
        <div className="grid flex-1 grid-cols-1 content-center items-center gap-[clamp(12px,3.5svh,40px)] md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:gap-14">
          <div className="flex min-w-0 flex-col gap-[clamp(10px,3svh,30px)]">
            <p className="rise hidden font-mono text-[13px] font-medium tracking-wider md:block" style={rise(0)}>
              SMALL AI FOR RURAL HEALTHCARE
            </p>
            <h1 className="rise t-display max-w-[13ch]" style={rise(1)}>
              <span className="text-accent">Access to care</span> begins before the clinic
              <span className="cursor">_</span>
            </h1>
            <p className="rise t-lead drop-3 max-w-[30ch]" style={rise(2)}>
              No app. No smartphone. Just a call in your own language.
            </p>

            <div className="rise flex flex-wrap items-center gap-x-5 gap-y-3" style={rise(3)}>
              <div role="group" aria-label="Listen, guide, connect: show each on the phone" className="verbs">
                {VERBS.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    aria-pressed={call.stage === v.id}
                    onClick={() => call.choose(v.id)}
                    onMouseEnter={() => call.choose(v.id)}
                    className="verb"
                  >
                    {v.word}
                  </button>
                ))}
              </div>
              <a href="#fix" className="hero-cta hidden md:inline-flex">
                How it works <span aria-hidden>↓</span>
              </a>
            </div>
          </div>

          <div className="rise flex justify-center" style={rise(2)}>
            <div className="hero-phone-fit w-full max-w-[380px]">
              <HeroPhone call={call} />
            </div>
          </div>
        </div>

        <div className="rise" style={rise(4)}>
          <Recognition />
        </div>
      </div>
    </Screen>
  );
}
