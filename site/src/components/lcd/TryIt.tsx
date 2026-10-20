"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type RefObject } from "react";
import { RingWaves } from "./Boot";
import { FlyArrow } from "./Links";
import { Screen } from "./Phone";
import { Chip, Kicker } from "./Problem";
import { rise } from "./rise";

/**
 * The way into the booth demo (/demo). A small feature phone plays the demo's call on a loop, in a different
 * language each time round, and the four steps beside it light up in step with it: ring once, Bob calls back,
 * press 1 or 2, get a next step. Pointing at the call to action makes the phone ring. The loop only runs while
 * this screen is on display, and holds still with reduced motion.
 *
 * The greetings, questions and currencies are the demo's own, so the preview never promises what it doesn't do.
 */
const LANGS = [
  { id: "hi", name: "हिन्दी", hello: "नमस्ते", q: "क्या आपको बुखार है?", yes: "हाँ", no: "नहीं", cur: "₹0" },
  { id: "ko", name: "한국어", hello: "안녕하세요", q: "열이 있으신가요?", yes: "예", no: "아니요", cur: "₩0" },
  { id: "es", name: "Español", hello: "¡Hola!", q: "¿Tienes fiebre?", yes: "Sí", no: "No", cur: "$0" },
  { id: "fr", name: "Français", hello: "Bonjour", q: "Avez-vous de la fièvre ?", yes: "Oui", no: "Non", cur: "0 FCFA" },
  { id: "zh", name: "中文", hello: "你好", q: "你发烧吗？", yes: "是", no: "否", cur: "0元" },
  { id: "en", name: "English", hello: "Hello", q: "Do you have a fever?", yes: "Yes", no: "No", cur: "$0" },
] as const;

const STEPS = [
  { n: 1, title: "Ring once", sub: "Kevin hangs up. Free." },
  { n: 2, title: "Bob calls back", sub: "In Kevin’s language." },
  { n: 3, title: "Press 1 or 2", sub: "Three quick questions." },
  { n: 4, title: "Get a next step", sub: "A booking or an alert." },
] as const;

// How long each step stays on the little phone, in ms.
const DWELL = [1900, 2300, 2500, 2600];
const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"];

function useLoop(ref: RefObject<HTMLElement | null>) {
  const [step, setStep] = useState(0);
  const [lang, setLang] = useState(0);
  const [running, setRunning] = useState(false);

  // Run only while the screen is on display (the status bar marks it `data-active`).
  useEffect(() => {
    const el = ref.current?.closest<HTMLElement>("[data-screen]");
    if (!el) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const check = () => setRunning(!reduced && el.hasAttribute("data-active"));
    check();
    const mo = new MutationObserver(check);
    mo.observe(el, { attributes: true, attributeFilter: ["data-active"] });
    return () => mo.disconnect();
  }, [ref]);

  useEffect(() => {
    if (!running) return;
    const id = setTimeout(() => {
      if (step === 3) setLang((l) => (l + 1) % LANGS.length);
      setStep((s) => (s + 1) % 4);
    }, DWELL[step]);
    return () => clearTimeout(id);
  }, [running, step]);

  return { step, lang, running, pick: setStep };
}

function MiniPhone({ step, lang }: { step: number; lang: number }) {
  const L = LANGS[lang];
  const ringing = step === 0 || step === 1;
  // On the question, Kevin presses 2 ("no") a beat after it is asked.
  const pressed = step === 2 ? "2" : null;
  return (
    <div className={`try-phone relative w-[min(100%,290px)] border-4 border-px bg-lcd ${step === 1 ? "ring" : ""}`}>
      {/* earpiece */}
      <div className="flex justify-center pt-3 pb-2" aria-hidden>
        <span className="h-1.5 w-14 bg-px" />
      </div>

      {/* the screen */}
      <div className="mx-3 border-4 border-px bg-lcd-2/70">
        <div className="flex items-center justify-between bg-px px-2.5 py-1 font-mono text-[11px] font-medium tracking-wider text-lcd">
          <span>{["CALLING…", "INCOMING", "ON CALL", "BOOKED"][step]}</span>
          <span key={L.id} className="fade-in">
            {L.cur}
          </span>
        </div>
        <div className="flex h-[clamp(118px,19svh,168px)] flex-col items-center justify-center gap-1.5 px-3 text-center">
          {step === 0 && (
            <div key="s0" className="stage-in flex flex-col items-center gap-1">
              <div className="text-[22px] leading-tight font-bold">District Health</div>
              <div className="font-mono text-[11px]">1 ring, then hang up</div>
            </div>
          )}
          {step === 1 && (
            <div key="s1" className="stage-in flex flex-col items-center gap-1">
              <div className="font-mono text-[11px] tracking-wider">FREE CALL · {L.name}</div>
              <div className="text-[clamp(26px,4.4svh,36px)] leading-tight font-bold text-accent" lang={L.id}>
                {L.hello}
              </div>
              <div className="font-mono text-[11px]">Vitamin Bob is calling</div>
            </div>
          )}
          {step === 2 && (
            <div key="s2" className="stage-in flex flex-col items-center gap-1.5">
              <div className="font-mono text-[11px] tracking-wider">QUESTION 1 OF 3</div>
              <div className="text-[clamp(17px,2.6svh,21px)] leading-snug font-bold" lang={L.id}>
                {L.q}
              </div>
              <div className="font-mono text-[11px]" lang={L.id}>
                1 = {L.yes} · 2 = {L.no}
              </div>
            </div>
          )}
          {step === 3 && (
            <div key="s3" className="stage-in flex flex-col items-center gap-1">
              <div className="flex items-center gap-2 bg-accent px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wider text-lcd">
                ✓ NOT URGENT
              </div>
              <div className="text-[22px] leading-tight font-bold">Booked</div>
              <div className="font-mono text-[11px]">Tomorrow, 09:00 · nearest clinic</div>
            </div>
          )}
        </div>
      </div>

      {/* call and end keys */}
      <div className="mx-3 mt-3 grid grid-cols-2 gap-2" aria-hidden>
        <span
          className={`try-key flex h-7 items-center justify-center border-4 border-px font-mono text-[11px] font-semibold ${ringing ? "is-on" : ""}`}
        >
          CALL
        </span>
        <span className="flex h-7 items-center justify-center border-4 border-px font-mono text-[11px] font-semibold">
          END
        </span>
      </div>

      {/* keypad */}
      <div className="mx-3 mt-2 mb-3 grid grid-cols-3 gap-1.5" aria-hidden>
        {KEYS.map((k) => (
          <span
            key={k}
            className={`try-key flex h-[clamp(22px,3.4svh,30px)] items-center justify-center border-2 border-px font-mono text-[13px] font-semibold ${pressed === k ? "is-pressed" : ""} ${step === 2 && (k === "1" || k === "2") ? "is-hint" : ""}`}
          >
            {k}
          </span>
        ))}
      </div>

      {/* the sticker: it runs with no internet */}
      <span className="try-sticker absolute -top-5 -left-12 flex items-center gap-1.5 border-4 border-px bg-accent px-2 py-1 font-mono text-[11px] font-semibold tracking-wider text-lcd">
        <NoSignal /> RUNS OFFLINE
      </span>
    </div>
  );
}

/** Signal bars with a cross through them, on the same pixel grid as the status bar. */
function NoSignal() {
  return (
    <svg viewBox="0 0 9 7" width={18} height={14} shapeRendering="crispEdges" aria-hidden>
      <g fill="currentColor" opacity={0.45}>
        <rect x={0} y={5} width={1.5} height={2} />
        <rect x={2.5} y={3.5} width={1.5} height={3.5} />
        <rect x={5} y={2} width={1.5} height={5} />
      </g>
      <g fill="currentColor">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <rect key={i} x={2 + i} y={i} width={1} height={1} />
        ))}
      </g>
    </svg>
  );
}

export function TryIt() {
  const ref = useRef<HTMLDivElement>(null);
  const { step, lang, running, pick } = useLoop(ref);
  return (
    <Screen id="demo" title="TRY IT" signal={4} data={false}>
      <div
        ref={ref}
        className="try-it mx-auto grid w-full max-w-[1280px] grid-cols-1 items-center gap-[clamp(18px,4svh,48px)] lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:gap-16"
      >
        <div className="min-w-0">
          <Kicker>
            <Chip>TRY IT</Chip>
            <span>Offline demo · one minute</span>
          </Kicker>
          <h2 className="rise t-h2" style={rise(1)}>
            Be Kevin for <span className="text-accent">one minute.</span>
          </h2>
          <p className="rise t-lead mt-[clamp(10px,2svh,20px)] max-w-[600px] drop-2" style={rise(2)}>
            Ring Bob from a basic phone, answer his call in one of six languages, and see what happens next. The whole
            call plays out in your browser, the way Bob runs on one laptop.
          </p>

          <ol className="drop-1 mt-[clamp(14px,3svh,32px)] grid grid-cols-2 gap-[clamp(8px,1.2vw,14px)] sm:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.n} className="rise flex" style={rise(i + 3)}>
                <button
                  type="button"
                  onMouseEnter={() => pick(i)}
                  onFocus={() => pick(i)}
                  onClick={() => pick(i)}
                  aria-pressed={step === i}
                  className={`try-step flex w-full cursor-pointer flex-col items-start gap-1 border-4 border-px px-3 py-2.5 text-left ${step === i ? "is-on" : ""}`}
                >
                  <span className="try-step-n bg-px px-1.5 font-mono text-[11px] font-semibold text-lcd">
                    {String(s.n).padStart(2, "0")}
                  </span>
                  <span className="text-[clamp(14px,2svh,17px)] leading-tight font-bold">{s.title}</span>
                  <span className="hidden font-mono text-[11px] leading-snug md:block">{s.sub}</span>
                  <span className="mt-1 block h-1 w-full bg-ghost" aria-hidden>
                    {step === i && (
                      <span
                        key={`${step}-${lang}-${running}`}
                        className={`block h-full bg-accent ${running ? "try-fill" : ""}`}
                        style={{ animationDuration: `${DWELL[i]}ms` }}
                      />
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ol>

          <div
            className="rise mt-[clamp(16px,3.4svh,36px)] flex flex-wrap items-center gap-x-6 gap-y-3"
            style={rise(7)}
          >
            <Link
              href="/demo"
              className="try-cta cta inline-flex items-center gap-3 border-4 border-px bg-px px-5 py-3 font-mono text-[14px] font-medium text-lcd shadow-[4px_4px_0_0_var(--color-accent)]"
            >
              <span className="try-cta-dot h-2.5 w-2.5 bg-accent-hi" aria-hidden />
              Start the demo
              <FlyArrow />
            </Link>
            <span className="hidden items-center gap-2 font-mono text-[12px] md:flex">
              or press
              <kbd className="border-2 border-px px-1.5 py-0.5 font-semibold shadow-[2px_2px_0_0_var(--color-px)]">
                4
              </kbd>
            </span>
          </div>
        </div>

        <div className="rise flex items-center justify-center gap-2" style={rise(3)}>
          <span className={`hidden transition-opacity sm:block ${step <= 1 ? "opacity-100" : "opacity-0"}`}>
            <RingWaves flip />
          </span>
          <Link
            href="/demo"
            aria-label="Open the demo: be Kevin for one minute"
            className="try-phone-link try-phone-fit"
          >
            <MiniPhone step={step} lang={lang} />
          </Link>
          <span className={`hidden transition-opacity sm:block ${step <= 1 ? "opacity-100" : "opacity-0"}`}>
            <RingWaves />
          </span>
        </div>
      </div>
    </Screen>
  );
}
