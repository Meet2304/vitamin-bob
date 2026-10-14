"use client";

import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { Screen } from "./Phone";
import { Sprite } from "./Sprite";

/**
 * How Bob helps, as one story on one screen. A diagram stays pinned while four short chapters scroll past,
 * and each chapter moves the diagram on: Kevin's missed call, the call back in Hindi, the keypad answers,
 * and the decision (clinic alerted, or an appointment booked). Same cast as the pitch deck's slides.
 *
 * Scroll states (the chapter text that crosses a line ~62% down the viewport sets the state):
 *   0 missed call, free line found   1 call back in Hindi   2 Kevin explains, keypad answers
 *   3 emergency: clinic alerted      4 not urgent: appointment booked   5 summary
 */
type State = 0 | 1 | 2 | 3 | 4 | 5;

const CAPTIONS: Record<State, string> = {
  0: "Kevin rings once and hangs up. The computer finds a free line.",
  1: "Bob calls Kevin back, in Hindi.",
  2: "Kevin says what’s wrong. Bob asks only what’s missing.",
  3: "Emergency? The nearest clinic is alerted at once.",
  4: "Not urgent? An appointment is booked instead.",
  5: "Free for patients. In their language. No internet.",
};

const chapterOf = (s: State) => Math.min(s, 3) + 1;

/* ---------- the diagram ---------- */

const MONO = { fontFamily: "var(--font-mono)" };
const DISPLAY = { fontFamily: "var(--font-display)" };

/** Toggle a piece of the diagram: `on` fades or pops it in through the CSS in globals.css. */
const on = (cond: boolean) => (cond ? " on" : "");

function LineNode({ y, picked }: { y: number; picked: boolean }) {
  return (
    <g className={`dg-node${on(picked)}`} transform={`translate(226 ${y - 12})`}>
      <rect x={0} y={0} width={24} height={24} className="dg-node-box" />
      {/* a pixel handset */}
      <g className="dg-node-ink">
        <rect x={5} y={5} width={5} height={4} />
        <rect x={6} y={9} width={3} height={5} />
        <rect x={8} y={14} width={5} height={3} />
        <rect x={13} y={15} width={5} height={4} />
      </g>
      <g className={`dg-pop${on(picked)}`}>
        <rect x={16} y={-8} width={14} height={14} fill="var(--color-px)" />
        <g fill="var(--color-lcd)">
          <rect x={19} y={-1} width={2} height={2} />
          <rect x={21} y={1} width={2} height={2} />
          <rect x={23} y={-1} width={2} height={2} />
          <rect x={25} y={-3} width={2} height={2} />
        </g>
      </g>
    </g>
  );
}

function Outcome({
  x,
  icon,
  label,
  status,
  active,
  kind,
  alarm,
}: {
  x: number;
  icon: ReactNode;
  label: string;
  status: string;
  active: boolean;
  kind: "urgent" | "booked";
  alarm: boolean;
}) {
  return (
    <g className={`dg-outcome dg-${kind}${on(active)}`} transform={`translate(${x} 300)`}>
      <rect x={2} y={2} width={168} height={76} className="dg-outcome-box" />
      <g transform="translate(14 16)" className="dg-outcome-ink">
        {icon}
      </g>
      <text x={48} y={36} className="dg-outcome-ink" style={MONO} fontSize={16} fontWeight={600}>
        {label}
      </text>
      <text x={48} y={58} className={`dg-outcome-ink dg-fade${on(active)}`} style={MONO} fontSize={12.5}>
        {status}
      </text>
      {kind === "urgent" && (
        <g transform="translate(156 -10)">
          <g className={`dg-pop${on(active)}`}>
            <rect width={22} height={22} fill="var(--color-px)" stroke="var(--color-lcd)" strokeWidth={2} />
            <g fill="var(--color-lcd)" className={alarm ? "dg-blink" : ""}>
              <rect x={9} y={4} width={4} height={2} />
              <rect x={7} y={6} width={8} height={8} />
              <rect x={5} y={14} width={12} height={2} />
              <rect x={10} y={17} width={2} height={2} />
            </g>
          </g>
        </g>
      )}
    </g>
  );
}

const Clinic = (
  <g fill="currentColor">
    <polygon points="12,0 24,11 0,11" />
    <rect x={3} y={11} width={18} height={13} />
    <rect x={10} y={13} width={4} height={9} className="dg-hole" />
    <rect x={7} y={16} width={10} height={3} className="dg-hole" />
  </g>
);

const Calendar = (
  <g fill="currentColor">
    <rect x={0} y={4} width={24} height={20} />
    <rect x={3} y={10} width={18} height={11} className="dg-hole" />
    <rect x={5} y={0} width={3} height={7} />
    <rect x={16} y={0} width={3} height={7} />
    <rect x={5} y={12} width={3} height={3} />
    <rect x={10} y={12} width={3} height={3} />
    <rect x={15} y={12} width={3} height={3} />
    <rect x={5} y={17} width={3} height={3} />
  </g>
);

function Diagram({ s }: { s: State }) {
  const calling = s === 1 || s === 2;
  const lineUp = s <= 2; // a free line is held for Kevin's call
  const gauge = s === 3 || s === 4;
  const needle = s === 3 ? 58 : s === 4 ? -58 : 0;
  const happy = s >= 4;

  return (
    <svg
      viewBox="0 0 592 396"
      className="block h-auto w-full"
      shapeRendering="crispEdges"
      role="img"
      aria-label={CAPTIONS[s]}
    >
      {/* ---- Kevin and his phone ---- */}
      <g transform="translate(20 118)">
        <Sprite role="patient" mood={happy ? "happy" : "worried"} px={3} />
      </g>
      <g className={s === 0 ? "ring" : ""}>
        <rect x={72} y={96} width={52} height={100} fill="var(--color-px)" />
        <rect x={80} y={104} width={36} height={24} className={`dg-screen${on(s <= 2)}`} />
        {Array.from({ length: 12 }).map((_, i) => (
          <rect
            key={i}
            x={80 + (i % 3) * 13}
            y={136 + Math.floor(i / 3) * 14}
            width={10}
            height={8}
            className={`dg-key${on(s === 2 && i === 1)}`}
          />
        ))}
      </g>
      {/* ringing */}
      <g className={`dg-fade${on(s === 0)}`} fill="var(--color-px)">
        {[0, 1, 2].map((i) => (
          <g key={i} className="wave" style={{ animationDelay: `${i * 0.25}s` }}>
            <rect x={133 + i * 6} y={100 - i * 4} width={3} height={14 + i * 8} />
          </g>
        ))}
      </g>
      <text x={72} y={226} textAnchor="middle" style={DISPLAY} fontSize={19} fontWeight={700} fill="var(--color-px)">
        Kevin
      </text>
      <text x={72} y={244} textAnchor="middle" style={MONO} fontSize={12} fill="var(--color-px)" className="dg-sub">
        speaks Hindi
      </text>

      {/* ---- the missed call travels to the district computer ---- */}
      <path
        d="M98 90 C 120 8, 318 0, 348 58"
        fill="none"
        stroke="var(--color-px)"
        strokeWidth={4}
        className={`dg-march dg-fade${on(s === 0)}`}
      />

      {/* ---- phone lines ---- */}
      <g fill="none" strokeWidth={3}>
        <path d="M250 114 L340 150" className="dg-wire" />
        <path d="M250 186 L340 150" className="dg-wire" />
        <path d="M250 150 L340 150" className={`dg-wire${lineUp ? " hot" : ""}`} />
      </g>
      <LineNode y={114} picked={false} />
      <LineNode y={150} picked={lineUp} />
      <LineNode y={186} picked={false} />
      <text x={238} y={226} textAnchor="middle" style={MONO} fontSize={13} fill="var(--color-px)">
        phone lines
      </text>

      {/* ---- the call back: a live line from the free phone line to Kevin ---- */}
      <path
        d="M226 150 H124"
        pathLength={100}
        fill="none"
        stroke="var(--color-px)"
        strokeWidth={6}
        className={`dg-draw${on(calling)}`}
      />
      {/* keypad answers travel down the line to the computer */}
      <g className={`dg-fade${on(s === 2)}`} fill="var(--color-px)">
        {[0, 1, 2].map((i) => (
          <rect
            key={i}
            x={128}
            y={142}
            width={8}
            height={8}
            className="dg-packet"
            style={{ animationDelay: `${i * 0.45}s` }}
          />
        ))}
      </g>

      {/* speech: Bob greets in Hindi, then Kevin answers */}
      <g className={`dg-pop${on(s === 1)}`}>
        <rect x={134} y={46} width={96} height={40} fill="var(--color-px)" />
        <polygon points="142,86 156,86 134,100" fill="var(--color-px)" />
        <text x={182} y={73} textAnchor="middle" fontSize={20} fontWeight={700} fill="var(--color-lcd)" style={DISPLAY}>
          नमस्ते!
        </text>
      </g>
      <g className={`dg-pop${on(s === 2)}`}>
        <rect x={134} y={46} width={100} height={40} fill="var(--color-lcd)" stroke="var(--color-px)" strokeWidth={3} />
        <polygon points="142,86 156,86 134,100" fill="var(--color-px)" />
        <text x={184} y={73} textAnchor="middle" fontSize={18} fontWeight={700} fill="var(--color-px)" style={DISPLAY}>
          बुखार है
        </text>
      </g>
      <g className={`dg-pop dg-late${on(s === 2)}`}>
        <rect x={130} y={104} width={28} height={28} fill="var(--color-lcd)" stroke="var(--color-px)" strokeWidth={3} />
        <text x={144} y={125} textAnchor="middle" style={MONO} fontSize={18} fontWeight={700} fill="var(--color-px)">
          2
        </text>
      </g>

      {/* ---- the district computer ---- */}
      <text x={440} y={30} textAnchor="middle" style={DISPLAY} fontSize={19} fontWeight={700} fill="var(--color-px)">
        District computer
      </text>
      <text x={440} y={48} textAnchor="middle" style={MONO} fontSize={12} fill="var(--color-px)" className="dg-sub">
        its own AI · no internet
      </text>
      <rect
        x={343}
        y={63}
        width={194}
        height={126}
        fill="var(--color-lcd-2)"
        stroke="var(--color-px)"
        strokeWidth={6}
      />
      <polygon points="326,192 554,192 542,206 338,206" fill="var(--color-px)" />

      {/* screen: Bob, or the urgency gauge */}
      <g className={`dg-fade${on(!gauge)}`}>
        <g transform="translate(366 82)">
          <Sprite role="bob" mood={s === 1 || s === 5 ? "happy" : "calm"} px={3} />
        </g>
        {(
          [
            ["MISSED CALL", "from Kevin"],
            ["CALLING", "Kevin…"],
            ["LISTENING", ""],
            ["", ""],
            ["", ""],
            ["READY", "next call…"],
          ] as const
        ).map(([a, b], i) => (
          <g key={i} className={`dg-fade${on(s === i)}`}>
            <text x={420} y={118} style={MONO} fontSize={14} fontWeight={600} fill="var(--color-px)">
              {a}
            </text>
            <text x={420} y={138} style={MONO} fontSize={13} fill="var(--color-px)">
              {b}
            </text>
          </g>
        ))}
        <g className={`dg-fade${on(s === 2)}`} fill="var(--color-px)">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <rect
              key={i}
              x={421 + i * 14}
              y={128}
              width={8}
              height={36}
              className="dg-eq"
              style={{ animationDelay: `${(i % 4) * 0.13}s` }}
            />
          ))}
        </g>
      </g>
      <g className={`dg-fade${on(gauge)}`}>
        <text
          x={440}
          y={100}
          textAnchor="middle"
          style={MONO}
          fontSize={17}
          fontWeight={700}
          fill="var(--color-px)"
          className={s === 3 ? "dg-blink" : ""}
        >
          {s === 4 ? "NOT URGENT" : "EMERGENCY"}
        </text>
        <path d="M396 170 A44 44 0 0 1 440 126" fill="none" stroke="var(--color-px-2)" strokeWidth={12} />
        <path d="M440 126 A44 44 0 0 1 484 170" fill="none" stroke="var(--color-px)" strokeWidth={12} />
        <g className="dg-needle" style={{ transform: `rotate(${needle}deg)` }}>
          <rect x={438} y={130} width={4} height={40} fill="var(--color-px)" />
        </g>
        <rect x={434} y={164} width={12} height={12} fill="var(--color-px)" />
      </g>

      {/* ---- where Kevin is sent ---- */}
      <path d="M440 206 V254 H315 V300" fill="none" strokeWidth={3} className="dg-wire" />
      <path d="M440 206 V254 H498 V300" fill="none" strokeWidth={3} className="dg-wire" />
      <path
        d="M440 206 V254 H315 V300"
        pathLength={100}
        fill="none"
        stroke="var(--color-px)"
        strokeWidth={6}
        className={`dg-draw${on(s === 3 || s === 5)}`}
      />
      <path
        d="M440 206 V254 H498 V300"
        pathLength={100}
        fill="none"
        stroke="var(--color-px)"
        strokeWidth={6}
        className={`dg-draw${on(s === 4 || s === 5)}`}
      />
      <Outcome
        x={228}
        kind="urgent"
        icon={Clinic}
        label="CLINIC"
        status="ALERTED NOW"
        active={s === 3 || s === 5}
        alarm={s === 3}
      />
      <Outcome
        x={414}
        kind="booked"
        icon={Calendar}
        label="APPOINTMENT"
        status="BOOKED TOMORROW"
        active={s === 4 || s === 5}
        alarm={false}
      />

      {/* ---- what it costs Kevin ---- */}
      <g transform="translate(20 300)">
        <rect x={2} y={2} width={176} height={76} fill="var(--color-lcd)" stroke="var(--color-px)" strokeWidth={4} />
        <text x={18} y={54} style={DISPLAY} fontSize={40} fontWeight={700} fill="var(--color-px)">
          ₹0
        </text>
        <text x={90} y={36} style={MONO} fontSize={12.5} fill="var(--color-px)">
          for Kevin,
        </text>
        <text x={90} y={54} style={MONO} fontSize={12.5} fontWeight={600} fill="var(--color-px)">
          every call
        </text>
      </g>
    </svg>
  );
}

/* ---------- the chapters ---------- */

function Chapter({
  step,
  active,
  n,
  kicker,
  title,
  children,
  notes,
}: {
  step: State;
  active: boolean;
  n: number;
  kicker: string;
  title: string;
  children: ReactNode;
  notes?: string[];
}) {
  return (
    <div data-step={step} className={`story-chapter flex min-h-[64vh] flex-col justify-center py-10${on(active)}`}>
      <div className="mb-5 flex items-center gap-4 font-mono text-sm font-medium">
        <span className="bg-px px-2 py-1 text-lcd">{n}/4</span>
        <span>{kicker}</span>
      </div>
      <h3 className="text-[32px] leading-[1.05] font-bold tracking-tight md:text-[48px]">{title}</h3>
      <div className="mt-4 max-w-[560px] text-lg leading-snug md:text-2xl">{children}</div>
      {notes && (
        <ul className="mt-5 flex flex-col gap-2 font-mono text-[13px] md:text-[14px]">
          {notes.map((t) => (
            <li key={t} className="flex gap-3">
              <span aria-hidden>▸</span>
              {t}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** One beat of the last chapter: each moves the diagram on by one state. */
function Beat({ step, active, children }: { step: State; active: boolean; children: ReactNode }) {
  return (
    <div data-step={step} className={`story-chapter flex min-h-[44vh] flex-col justify-center py-6${on(active)}`}>
      {children}
    </div>
  );
}

function useStoryState(root: RefObject<HTMLElement | null>) {
  const [s, setS] = useState<State>(0);
  useEffect(() => {
    const els = Array.from(root.current?.querySelectorAll<HTMLElement>("[data-step]") ?? []);
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setS(Number((e.target as HTMLElement).dataset.step) as State);
      },
      // a thin line about 62% down the viewport: below the pinned diagram on phones, mid-text on desktop
      { rootMargin: "-62% 0px -37% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [root]);
  return s;
}

export function Story() {
  const root = useRef<HTMLDivElement>(null);
  const s = useStoryState(root);
  const chapter = chapterOf(s);

  return (
    <Screen id="fix" title="THE FIX" signal={4} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <div className="max-w-[820px]">
          <div className="mb-5 flex items-center gap-4 font-mono text-sm font-medium">
            <span className="bg-px px-2 py-1 text-lcd">THE FIX</span>
            <span>How Bob helps</span>
          </div>
          <h2 className="text-[40px] leading-[1.02] font-bold tracking-tight md:text-[68px]">
            One computer in every district.
          </h2>
          <p className="mt-4 max-w-[640px] text-xl leading-snug md:text-2xl">
            It calls patients back, free, in their own language, and sends them to the right care. Here is one call,
            from start to finish.
          </p>
        </div>

        <div ref={root} className="mt-8 grid grid-cols-1 gap-x-14 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          {/* the pinned diagram: on top on phones, on the right on desktop */}
          <div className="story-pin sticky top-[48px] z-10 -mx-6 self-start px-3 pt-3 pb-5 lg:top-24 lg:order-2 lg:mx-0 lg:px-0 lg:pt-0 lg:pb-0">
            <div className="px-box bg-lcd">
              <div className="flex items-center justify-between bg-px px-4 py-2 font-mono text-[12px] font-medium tracking-wider text-lcd md:text-[13px]">
                <span>DISTRICT LINE · LIVE</span>
                <span className="flex items-center gap-1.5" aria-label={`chapter ${chapter} of 4`}>
                  {[1, 2, 3, 4].map((i) => (
                    <span key={i} className={`h-2.5 w-2.5 ${i <= chapter ? "bg-lcd" : "border border-lcd"}`} />
                  ))}
                </span>
              </div>
              <div className="bg-lcd px-1 pt-2 md:px-4 md:pt-4">
                <Diagram s={s} />
              </div>
              <p
                className="min-h-[3.4em] border-t-4 border-px px-4 py-2.5 font-mono text-[13px] leading-snug font-medium md:text-[15px]"
                aria-live="polite"
              >
                <span className="mr-2 bg-px px-1.5 text-lcd">{chapter}/4</span>
                {CAPTIONS[s]}
              </p>
            </div>
          </div>

          <div className="lg:order-1">
            <Chapter
              step={0}
              active={s === 0}
              n={1}
              kicker="The missed call"
              title="Ring once. Hang up. It’s free."
              notes={["Works on any phone: no app, no data plan", "The district pays for the call back"]}
            >
              Kevin has a fever and a basic phone. He rings Bob’s number and hangs up before it connects, so it costs
              him nothing. A computer at the district office notices within seconds and picks a free phone line.
            </Chapter>

            <Chapter
              step={1}
              active={s === 1}
              n={2}
              kicker="The call back"
              title="Bob calls back, in Kevin’s language."
              notes={[
                "Hindi or Gujarati today; a new language is new recordings, not new code",
                "Every sentence is a recording made by a person",
              ]}
            >
              Kevin picks Hindi with one key. Everything Bob says was recorded by a real person, so it is always clear
              and always the same.
            </Chapter>

            <Chapter
              step={2}
              active={s === 2}
              n={3}
              kicker="The conversation"
              title="Kevin explains. Bob listens."
              notes={["Gemma 4 runs on the district computer, offline", "Only the missing questions are asked"]}
            >
              Kevin says what’s wrong in his own words. Bob’s own AI, running on that one computer with no internet,
              understands him. Then Bob asks only what it still needs to know: press 1 for yes, 2 for no.
            </Chapter>

            <div className={`story-chapter pt-10${on(s >= 3)}`}>
              <div className="mb-5 flex items-center gap-4 font-mono text-sm font-medium">
                <span className="bg-px px-2 py-1 text-lcd">4/4</span>
                <span>The decision</span>
              </div>
              <h3 className="text-[32px] leading-[1.05] font-bold tracking-tight md:text-[48px]">
                The right care, at the right time.
              </h3>
            </div>
            <Beat step={3} active={s === 3}>
              <p className="max-w-[560px] text-lg leading-snug md:text-2xl">
                <b>Emergency?</b> Bob tells Kevin where to go right now, and the nearest open clinic is alerted at once.
              </p>
            </Beat>
            <Beat step={4} active={s === 4}>
              <p className="max-w-[560px] text-lg leading-snug md:text-2xl">
                <b>Not urgent?</b> Bob books Kevin a time instead, so he doesn’t spend a day waiting in the queue.
              </p>
            </Beat>
            <Beat step={5} active={s === 5}>
              <p className="max-w-[560px] text-lg leading-snug md:text-2xl">
                Simple written rules decide how urgent it is, not the AI. If anything is unclear, a clinician makes the
                call.
              </p>
              <p className="mt-6 text-[28px] leading-tight font-bold tracking-tight md:text-[40px]">
                Free for patients. In their language. No internet.
              </p>
            </Beat>
          </div>
        </div>
      </div>
    </Screen>
  );
}
