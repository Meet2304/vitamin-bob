import type { ReactNode } from "react";
import { Screen } from "./Phone";
import { rise } from "./rise";
import { Sprite } from "./Sprite";

export function Src({ children, d = 9 }: { children: ReactNode; d?: number }) {
  return (
    <p
      className="rise mt-[clamp(10px,3svh,32px)] max-w-[900px] font-mono text-[11px] leading-relaxed opacity-70 md:text-[12px]"
      style={rise(d)}
    >
      Source: {children}
    </p>
  );
}

export function Kicker({ children, d = 0, className = "" }: { children: ReactNode; d?: number; className?: string }) {
  return (
    <div
      className={`rise drop-2 mb-[clamp(12px,2.4svh,24px)] flex items-center gap-4 font-mono text-sm font-medium ${className}`}
      style={rise(d)}
    >
      {children}
    </div>
  );
}

export const Chip = ({ children }: { children: ReactNode }) => (
  <span className="bg-accent px-2 py-1 text-lcd">{children}</span>
);

/* 1 · Care is out of reach, for billions */
export function OutOfReach() {
  return (
    <Screen id="problem" title="THE PROBLEM" signal={2} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <Kicker>
          <Chip>THE PROBLEM</Chip>
          <span>Care is out of reach</span>
        </Kicker>
        <h2 className="rise t-h2 max-w-[1000px]" style={rise(1)}>
          Primary care is still <span className="text-accent">out of reach</span> for billions of people.
        </h2>
        <div className="mt-[clamp(16px,4svh,48px)] flex flex-wrap items-end gap-x-10 gap-y-3">
          <div
            className="rise text-[clamp(88px,min(17vw,22svh),220px)] leading-none font-bold tracking-tighter"
            style={rise(2)}
          >
            4.6B
          </div>
          <p className="rise t-lead max-w-[460px] pb-[1.2em]" style={rise(3)}>
            That is how many people around the world still cannot get the essential health care they need.
          </p>
        </div>
        <Src d={4}>WHO &amp; World Bank, UHC Global Monitoring Report 2025.</Src>
      </div>
    </Screen>
  );
}

/* 2 · The journey to care, and why the clinician hears the story last */
const JOURNEY: { title: string; body: string; art: ReactNode }[] = [
  {
    title: "Feels sick",
    body: "They are not sure how serious it is, and there is no one nearby to ask.",
    art: <Sprite role="patient" mood="worried" px={4} />,
  },
  {
    title: "Travels and waits",
    body: "They travel far, then wait in one line where urgent cases wait with everyone else.",
    art: (
      <div className="flex items-end gap-1">
        <Sprite role="patient" mood="calm" px={3} blink={false} />
        <Sprite role="child" mood="worried" px={3} blink={false} />
        <Sprite role="patient" mood="worried" px={4} />
      </div>
    ),
  },
  {
    title: "Explains again",
    body: "They tell the whole story from the start, often from memory.",
    art: (
      <div className="flex items-start gap-2">
        <Sprite role="patient" mood="calm" px={4} />
        <span className="px-box mt-1 bg-lcd px-1.5 font-mono text-[13px] font-bold">…?</span>
      </div>
    ),
  },
  {
    title: "Clinician decides",
    body: "The clinician hears it all for the first time, with little time to decide.",
    art: <Sprite role="clinician" mood="worried" px={4} />,
  },
];

export function Journey() {
  return (
    <Screen id="journey" title="THE PROBLEM" signal={2} data={false}>
      <div className="journey mx-auto w-full max-w-[1280px]">
        <Kicker>
          <Chip>JOURNEY</Chip>
          <span>From sick to seen</span>
        </Kicker>
        <h2 className="rise t-h2 max-w-[1000px]" style={rise(1)}>
          Patients arrive <span className="text-accent">before their story does.</span>
        </h2>

        <ol className="relative mt-[clamp(20px,5svh,56px)] grid grid-cols-2 gap-6 lg:grid-cols-4">
          {JOURNEY.map((j, i) => (
            <li key={j.title} data-step={i} className="rise group flex flex-col" style={rise(i + 2)}>
              <div className="drop-1 flex h-[clamp(52px,10svh,96px)] items-end">
                <div className="art-fit">{j.art}</div>
              </div>
              <div className="drop-1-tight mt-[clamp(14px,3svh,32px)] flex items-center gap-3">
                <span className="bg-px px-2 py-0.5 font-mono text-sm font-semibold text-lcd group-hover:bg-accent">
                  {i + 1}
                </span>
                <h3 className="t-h3">{j.title}</h3>
              </div>
              <p className="t-body drop-4 mt-2 max-w-[300px]">{j.body}</p>
            </li>
          ))}
        </ol>
        {/* the road: the walker steps along to whichever step you point at */}
        <div
          className="rise relative mt-[clamp(14px,3svh,28px)] hidden h-10 border-b-4 border-dotted border-px lg:block"
          style={rise(6)}
          aria-hidden
        >
          <span className="walker absolute bottom-0">
            <Sprite role="patient" mood="worried" px={2} blink={false} />
          </span>
        </div>
      </div>
    </Screen>
  );
}

/* The turn: an inverted screen. Listen. Guide. Connect. */
const PILLARS: { word: string; role: "patient" | "bob" | "clinician"; body: string }[] = [
  {
    word: "Listen.",
    role: "patient",
    body: "Bob calls back for free and listens in Hindi or Gujarati, on any phone.",
  },
  {
    word: "Guide.",
    role: "bob",
    body: "Bob asks only what is missing, then tells the patient what to do next.",
  },
  {
    word: "Connect.",
    role: "clinician",
    body: "The clinic receives a short summary before the patient arrives.",
  },
];

export function Turn() {
  return (
    <Screen id="turn" title="WHAT IF" signal={4} data={false} dark>
      <div className="mx-auto w-full max-w-[1280px]">
        <h2 className="rise t-display max-w-[1000px]" style={rise(0)}>
          What if care began <span className="text-accent-hi">with a phone call?</span>
        </h2>
        <p className="rise t-lead mt-[clamp(12px,2.6svh,28px)] max-w-[680px] drop-3" style={rise(1)}>
          No app, no smartphone and no internet. Just a call in your own language, answered by a small AI.
        </p>
        <ol className="mt-[clamp(20px,5svh,56px)] grid grid-cols-1 gap-[clamp(10px,2svh,24px)] md:grid-cols-3">
          {PILLARS.map((p, i) => (
            <li
              key={p.word}
              className="rise flex flex-col border-l-4 border-lcd py-1 pl-4 md:border-4 md:p-[clamp(12px,2.4svh,24px)]"
              style={rise(i + 2)}
            >
              <div className="hidden h-[84px] items-start justify-between md:flex">
                <span className="font-mono text-sm font-semibold text-accent-hi">0{i + 1}</span>
                <Sprite role={p.role} mood="happy" px={3} inverse />
              </div>
              <div className="t-h3 text-accent-hi md:mt-3 md:text-[clamp(30px,min(5vw,6.4svh),66px)]">{p.word}</div>
              <p className="t-body mt-2">{p.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </Screen>
  );
}
