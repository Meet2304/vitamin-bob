"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * The phone's chrome. Every screen declares how the phone should look while it is on display:
 *   <Screen id="…" title="…" signal={0-4} data={false} clock="16:00">
 * and the status bar follows the story: signal drops, data goes away, the clock jumps ahead.
 */
type Status = { title: string; signal: number; data: boolean; clock?: string };

export function Screen({
  id,
  title,
  signal = 4,
  data = true,
  clock,
  children,
  className = "",
}: {
  id: string;
  title: string;
  signal?: number;
  data?: boolean;
  clock?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      data-screen=""
      data-title={title}
      data-signal={signal}
      data-data={data ? "1" : "0"}
      data-clock={clock ?? ""}
      className={`screen relative flex min-h-screen flex-col justify-center px-6 pt-20 pb-24 md:px-12 ${className}`}
    >
      {children}
    </section>
  );
}

function useStatus(): Status {
  const [s, setS] = useState<Status>({ title: "HOME", signal: 4, data: true });
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>("[data-screen]"));
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!hit) return;
        const d = (hit.target as HTMLElement).dataset;
        setS({ title: d.title ?? "", signal: Number(d.signal ?? 4), data: d.data === "1", clock: d.clock || undefined });
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: [0, 0.01] },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return s;
}

function useClock() {
  const [t, setT] = useState("");
  useEffect(() => {
    const tick = () => setT(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }));
    tick();
    const id = setInterval(tick, 15000);
    return () => clearInterval(id);
  }, []);
  return t;
}

function Bars({ n }: { n: number }) {
  return (
    <span className="flex items-end gap-[3px]" aria-label={`signal ${n} of 4`}>
      {[1, 2, 3, 4].map((i) => (
        <span key={i} className={i <= n ? "bg-px" : "bg-ghost"} style={{ width: 5, height: 4 + i * 4 }} />
      ))}
    </span>
  );
}

export function StatusBar() {
  const s = useStatus();
  const now = useClock();
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b-4 border-px bg-lcd/95 backdrop-blur-[2px]">
      <div className="mx-auto flex max-w-[1280px] items-center gap-5 px-6 py-3 font-mono text-[13px] font-medium md:px-12">
        <Bars n={s.signal} />
        <span className="hidden sm:inline">VOICE</span>
        <span className={s.data ? "" : "line-through opacity-50"}>DATA</span>
        <span className="mx-auto truncate font-bold tracking-wider">{s.title}</span>
        <span className={s.clock ? "bg-px px-1.5 text-lcd" : ""}>{s.clock ?? now}</span>
        <span className="flex items-center gap-0.5" aria-label="battery">
          <span className="flex h-4 w-8 gap-[2px] border-2 border-px p-[2px]">
            <span className="flex-1 bg-px" /><span className="flex-1 bg-px" /><span className="flex-1 bg-px" />
          </span>
          <span className="h-2 w-1 bg-px" />
        </span>
      </div>
    </header>
  );
}

const MENU = [
  { key: "1", id: "problem", label: "the problem" },
  { key: "2", id: "fix", label: "the fix" },
  { key: "3", id: "proof", label: "the proof" },
  { key: "4", id: "live", label: "a live call" },
  { key: "5", id: "try", label: "trying it yourself" },
  { key: "0", id: "top", label: "the start" },
];

/** The site's navigation is an IVR menu: press a number. Works with the keyboard too. */
export function useKeypadNav() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      const m = MENU.find((x) => x.key === e.key);
      if (m) document.getElementById(m.id)?.scrollIntoView({ behavior: "smooth" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

export function IvrMenu() {
  useKeypadNav();
  return (
    <nav aria-label="Chapters" className="flex flex-col gap-3">
      {MENU.slice(0, 5).map((m) => (
        <a key={m.key} href={`#${m.id}`} className="group flex items-center gap-4 text-xl md:text-2xl">
          <span className="px-box flex h-11 w-11 shrink-0 items-center justify-center font-mono text-lg font-semibold group-hover:bg-px group-hover:text-lcd">
            {m.key}
          </span>
          <span>
            Press {m.key} for <span className="font-semibold">{m.label}</span>
          </span>
        </a>
      ))}
    </nav>
  );
}

export function SoftKeys() {
  return (
    <footer className="fixed inset-x-0 bottom-0 z-50 border-t-4 border-px bg-lcd/95">
      <div className="mx-auto flex max-w-[1280px] items-center justify-between px-6 py-2.5 font-mono text-[13px] font-medium md:px-12">
        <a href="#top" className="hover:bg-px hover:text-lcd px-1">MENU</a>
        <span className="hidden text-[13px] sm:inline">press 0–5 or scroll ▼</span>
        <a href="#live" className="hover:bg-px hover:text-lcd px-1">LIVE CALL</a>
      </div>
    </footer>
  );
}
