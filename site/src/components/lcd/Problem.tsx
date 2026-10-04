import type { ReactNode } from "react";
import { Screen } from "./Phone";
import { Sprite } from "./Sprite";

export function Src({ children }: { children: ReactNode }) {
  return <p className="mt-8 max-w-[900px] font-mono text-[12px] leading-relaxed opacity-70">Source: {children}</p>;
}

export function Kicker({ n, total, children }: { n: number; total: number; children: ReactNode }) {
  return (
    <div className="mb-6 flex items-center gap-4 font-mono text-sm font-medium">
      <span className="bg-px px-2 py-1 text-lcd">
        {n}/{total}
      </span>
      <span>{children}</span>
    </div>
  );
}

/* 1 · Clinicians are a scarce resource */
export function Scarcity() {
  const have = 37; // 36.7, one segment each
  const need = 45; // 44.5
  return (
    <Screen id="problem" title="THE PROBLEM" signal={2} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <Kicker n={1} total={3}>Clinicians are scarce</Kicker>
        <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
          <div className="text-[120px] leading-none font-bold tracking-tighter md:text-[220px]">36.7</div>
          <div className="max-w-[440px] pb-6 text-2xl leading-snug">
            health workers for every 10,000 people in India, below the <b>44.5</b> WHO uses as a minimum.
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-[6px]" aria-label="36.7 of the 44.5 needed">
          {Array.from({ length: need }).map((_, i) => (
            <span key={i} className={`h-9 w-[18px] ${i < have ? "bg-px" : "flicker border-2 border-dashed border-px"}`} />
          ))}
        </div>

        <div className="mt-12 grid items-center gap-8 md:grid-cols-[auto_1fr]">
          <div className="flex items-end gap-6">
            <div className="flex flex-col items-center gap-2">
              <Sprite role="clinician" mood="worried" px={8} />
              <span className="font-mono text-[12px] font-medium">1 health worker</span>
            </div>
            <div className="grid grid-cols-12 gap-1" aria-label="many patients">
              {Array.from({ length: 60 }).map((_, i) => (
                <Sprite key={i} role={i % 9 === 4 ? "child" : "patient"} px={2} blink={false} />
              ))}
            </div>
          </div>
          <p className="max-w-[420px] text-2xl leading-snug">
            That is one health worker for about <b>270 people</b>. Their time is the scarcest thing in the clinic, and
            today it goes to whoever arrives first.
          </p>
        </div>
        <Src>WHO Global Health Observatory, India 2024 (doctors, nurses and midwives); WHO SDG threshold 44.5 (2016). 270 = 10,000 ÷ 36.7.</Src>
      </div>
    </Screen>
  );
}

/* 2 · One queue for everyone */
export function Queue() {
  return (
    <Screen id="queue" title="THE PROBLEM" signal={2} data={false} clock="16:00">
      <div className="mx-auto w-full max-w-[1280px]">
        <Kicker n={2} total={3}>One line for everyone</Kicker>
        <h2 className="max-w-[900px] text-[40px] leading-[1.05] font-bold tracking-tight md:text-[60px]">
          The urgent wait with the routine.
        </h2>
        <p className="mt-5 max-w-[640px] text-2xl leading-snug">
          Without a way to sort people before they travel, the clinic sees whoever came first. Somewhere in the line,
          a child has had a fit. Nobody at the door knows.
        </p>
        <div className="mt-12 flex items-end gap-3 overflow-hidden border-b-4 border-px pb-3">
          <div className="mr-3 flex flex-col items-center gap-1">
            <span className="font-mono text-[11px] font-medium">DOOR</span>
            <span className="h-28 w-3 bg-px" />
          </div>
          {Array.from({ length: 14 }).map((_, i) =>
            i === 8 ? (
              <div key={i} className="flex flex-col items-center gap-1">
                <span className="bg-px px-1.5 font-mono text-[11px] font-medium text-lcd">URGENT</span>
                <Sprite role="child" mood="worried" px={5} inverse />
              </div>
            ) : (
              <Sprite key={i} role="patient" mood={i % 3 === 0 ? "worried" : "calm"} px={5} blink={i % 4 === 0} />
            ),
          )}
        </div>
        <div className="mt-4 flex flex-wrap gap-x-10 gap-y-2 font-mono text-sm">
          <span>09:00 the line forms</span>
          <span>12:30 still waiting</span>
          <span className="bg-px px-1.5 text-lcd">16:00 the child is seen</span>
        </div>
        <Src>Illustrative. First-come queues, long travel and little time per case are described in the World Bank brief, Annex A (2026).</Src>
      </div>
    </Screen>
  );
}

/* 3 · Paperwork eats the scarce time */
export function Paperwork() {
  return (
    <Screen id="paperwork" title="THE PROBLEM" signal={2} data={false}>
      <div className="mx-auto grid w-full max-w-[1280px] items-center gap-12 md:grid-cols-2">
        <div>
          <Kicker n={3} total={3}>And half the visit is paperwork</Kicker>
          <div className="text-[96px] leading-none font-bold tracking-tighter md:text-[150px]">26–53%</div>
          <p className="mt-4 max-w-[520px] text-2xl leading-snug">
            of every consultation goes to writing in registers. A clinic can keep up to <b>48</b> of them, and the
            same details are written again and again.
          </p>
          <div className="mt-8 max-w-[520px]">
            <div className="mb-2 font-mono text-[12px] font-medium">ONE CONSULTATION</div>
            <div className="flex h-10 border-4 border-px">
              <div className="flex w-[55%] items-center bg-px px-3 font-mono text-[12px] text-lcd">patient</div>
              <div className="dith-50 flex flex-1 items-center justify-end px-3 font-mono text-[12px]">
                <span className="bg-lcd px-1">writing</span>
              </div>
            </div>
          </div>
          <Src>Siyam et al. (2021), BMC Health Services Research 21(Suppl 1):691, five countries.</Src>
        </div>
        <div className="flex items-end justify-center gap-6">
          <Sprite role="clinician" mood="worried" px={8} />
          <div className="flex flex-col-reverse gap-1" aria-label="A stack of 48 registers">
            {Array.from({ length: 16 }).map((_, i) => (
              <div key={i} className="flex gap-1">
                {[0, 1, 2].map((j) => (
                  <span key={j} className={`h-4 w-14 border-2 border-px ${(i + j) % 3 === 0 ? "bg-px" : (i + j) % 3 === 1 ? "dith-50" : ""}`} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Screen>
  );
}

/* The turn: an inverted screen */
export function Turn() {
  return (
    <Screen id="turn" title="WHAT IF" signal={4} data={false} className="bg-px text-lcd">
      <div className="mx-auto grid w-full max-w-[1280px] items-center gap-12 md:grid-cols-[1.4fr_1fr]">
        <div>
          <h2 className="text-[44px] leading-[1.02] font-bold tracking-tight md:text-[76px]">
            What if the clinic’s front desk lived inside a missed call?
          </h2>
          <p className="mt-6 max-w-[620px] text-2xl leading-snug">
            Not an app. Not a smartphone. The call anyone can already make, answered by a small AI that listens, sorts
            and routes, so the scarce clinician’s time goes to the people who need it most.
          </p>
        </div>
        <div className="flex items-end justify-center gap-6">
          <Sprite role="patient" mood="worried" px={6} inverse />
          <Sprite role="bob" mood="happy" px={10} inverse label="Bob" />
          <Sprite role="clinician" mood="happy" px={7} inverse />
        </div>
      </div>
    </Screen>
  );
}
