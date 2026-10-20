"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

/**
 * The phone's chrome. Every screen declares how the phone should look while it is on display:
 *   <Screen id="…" title="…" signal={0-4} data={false}>
 * and the status bar follows the story (the signal drops on the problem screens). A screen can also pin the
 * clock with `clock="16:00"`; none does now, so it always shows the real time.
 *
 * A screen is one viewport tall, with its content centred below the status bar. A `tall`
 * screen (the fix) lays out its own pinned panel and scroll steps instead.
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
  tall = false,
  dark = false,
}: {
  id: string;
  title: string;
  signal?: number;
  data?: boolean;
  clock?: string;
  children: ReactNode;
  className?: string;
  tall?: boolean;
  /** A dark screen: a turn in the story. The glass dims as it arrives, like a backlight fading (globals.css). */
  dark?: boolean;
}) {
  return (
    <section
      id={id}
      data-screen=""
      data-title={title}
      data-signal={signal}
      data-data={data ? "1" : "0"}
      data-clock={clock ?? ""}
      data-tone={dark ? "dark" : undefined}
      className={
        tall
          ? `relative ${className}`
          : `screen relative flex min-h-[100svh] flex-col justify-center px-6 pt-[68px] pb-6 md:px-12 ${dark ? "isolate text-lcd" : ""} ${className}`
      }
    >
      {dark && <div className="dark-veil" aria-hidden />}
      {children}
    </section>
  );
}

/**
 * The screen on display is the one covering the middle of the viewport, checked on every scroll frame. It is
 * marked `data-active` so its pieces move in (globals.css, `.rise`), and the status bar follows it. Measuring
 * directly, rather than waiting for intersection reports, means no screen is ever skipped: a report could go
 * missing when leaving the tall, pinned fix, which left the next screen blank.
 */
function useStatus(initial: Status): Status {
  const [s, setS] = useState<Status>(initial);
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      const mid = innerHeight / 2;
      const els = Array.from(document.querySelectorAll<HTMLElement>("[data-screen]"));
      const hit = els.find((el) => {
        const r = el.getBoundingClientRect();
        return r.top <= mid && r.bottom > mid;
      });
      if (!hit || hit.hasAttribute("data-active")) return;
      els.forEach((el) => el.toggleAttribute("data-active", el === hit));
      const d = hit.dataset;
      setS({
        title: d.title ?? "",
        signal: Number(d.signal ?? 4),
        data: d.data === "1",
        clock: d.clock || undefined,
      });
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(raf);
      removeEventListener("scroll", schedule);
      removeEventListener("resize", schedule);
    };
  }, []);
  return s;
}

/**
 * Moving between screens. Stops are the snap points: each screen's top, each step of the fix, a few stops inside
 * anything taller than the viewport, and the end of the page (the footer).
 */
function stops() {
  const vh = innerHeight;
  const max = document.documentElement.scrollHeight - vh;
  const out = new Set<number>();
  for (const el of document.querySelectorAll<HTMLElement>(".screen, .snap-step")) {
    const top = el.getBoundingClientRect().top + scrollY;
    const h = el.offsetHeight;
    out.add(Math.round(top));
    for (let y = top + vh * 0.85; y < top + h - vh; y += vh * 0.85) out.add(Math.round(y));
    if (h > vh) out.add(Math.round(top + h - vh));
  }
  out.add(max); // the very end: the footer
  // a footer taller than the screen (the smallest phones) also stops at its top, so none of it is skipped
  const foot = document.querySelector<HTMLElement>(".site-footer");
  if (foot && foot.offsetHeight > vh) out.add(Math.round(foot.getBoundingClientRect().top + scrollY));
  return [...out].map((y) => Math.min(Math.max(y, 0), max)).sort((a, b) => a - b);
}

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const easeOut = (t: number) => 1 - (1 - t) ** 3;
let frame = 0;
let target: number | null = null; // where the current glide is heading, while one is running

/**
 * Glide to a scroll position on one eased curve. Asked again mid-glide (fast scrolling), it sets off for the new
 * stop from wherever it is, easing out only, so it carries on without a stall. Snapping is paused while gliding,
 * or the browser would pull each frame back to the nearest snap point.
 */
export function glideTo(top: number, slow = false) {
  const root = document.documentElement;
  const from = scrollY;
  const dist = top - from;
  const moving = target !== null;
  cancelAnimationFrame(frame);
  if (Math.abs(dist) < 2) {
    target = null;
    return;
  }
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    root.style.scrollSnapType = "none";
    scrollTo({ top, behavior: "instant" });
    requestAnimationFrame(() => (root.style.scrollSnapType = ""));
    return;
  }
  const dur = moving
    ? Math.min(700, 380 + Math.abs(dist) * 0.05)
    : slow
      ? 1250
      : Math.min(1000, 520 + Math.abs(dist) * 0.06);
  const ease = moving ? easeOut : easeInOut;
  const start = performance.now();
  target = top;
  root.style.scrollSnapType = "none";
  root.style.scrollBehavior = "auto";
  const tick = (now: number) => {
    const t = Math.min(1, (now - start) / dur);
    scrollTo(0, from + dist * ease(t));
    if (t < 1) frame = requestAnimationFrame(tick);
    else {
      target = null;
      root.style.scrollSnapType = "";
      root.style.scrollBehavior = "";
    }
  };
  frame = requestAnimationFrame(tick);
}

/** Glide one stop down (1) or up (-1): from where a running glide is heading, or else from where the page is. */
function step(dir: 1 | -1) {
  const y = target ?? scrollY;
  const all = stops();
  const to = dir > 0 ? all.find((s) => s > y + 4) : [...all].reverse().find((s) => s < y - 4);
  if (to === undefined) return;
  // crossing into or out of a dark screen takes its time: the story is turning
  const dark = Array.from(document.querySelectorAll<HTMLElement>('[data-tone="dark"]')).some((el) => {
    const top = el.getBoundingClientRect().top + scrollY;
    return Math.abs(top - to) < 4 || Math.abs(top - y) < 4;
  });
  glideTo(to, dark);
}

/**
 * Wheel and keys move a screen at a time, and fast input goes further, faster.
 *   A mouse wheel ticks in even steps: every tick moves one more stop, even mid-glide, so spinning the wheel
 *   runs straight through the six steps of the fix rather than getting stuck in them.
 *   A trackpad swipe moves one stop. Its momentum is swallowed, but a fresh swipe during it (the deltas
 *   jump up again instead of fading) counts as a new one.
 * Touch keeps the browser's own snapping.
 */
function useScreenSteps() {
  useEffect(() => {
    let acc = 0;
    let last = 0; // time of the previous wheel event
    let lastAbs = 0; // its size
    let moved = false; // this swipe has already moved a stop
    let lastStep = 0;
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey || Math.abs(e.deltaY) < Math.abs(e.deltaX)) return;
      e.preventDefault();
      const now = performance.now();
      const dy = e.deltaMode === 1 ? e.deltaY * 32 : e.deltaMode === 2 ? e.deltaY * innerHeight : e.deltaY;
      const abs = Math.abs(dy);
      const quiet = now - last > 180;
      const tick = e.deltaMode !== 0 || (Number.isInteger(e.deltaY) && abs >= 50 && (quiet || abs === lastAbs));
      const freshSwipe = quiet || (abs > lastAbs * 1.6 && abs > 12);
      last = now;
      lastAbs = abs;
      if (tick) {
        if (now - lastStep < 70) return;
        lastStep = now;
        step(dy > 0 ? 1 : -1);
        return;
      }
      if (freshSwipe) {
        acc = 0;
        moved = false;
      }
      if (moved) return;
      acc += dy;
      if (Math.abs(acc) < 24) return;
      moved = true;
      step(acc > 0 ? 1 : -1);
    };
    const KEYS: Record<string, 1 | -1> = { ArrowDown: 1, PageDown: 1, " ": 1, ArrowUp: -1, PageUp: -1 };
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, button, a, [contenteditable]")) return;
      let dir = KEYS[e.key];
      if (!dir) return;
      if (e.key === " " && e.shiftKey) dir = -1;
      e.preventDefault();
      const now = performance.now();
      if (e.repeat && now - lastStep < 160) return;
      lastStep = now;
      step(dir);
    };
    addEventListener("wheel", onWheel, { passive: false });
    addEventListener("keydown", onKey);
    return () => {
      removeEventListener("wheel", onWheel);
      removeEventListener("keydown", onKey);
    };
  }, []);
}

/**
 * Every screen fits the viewport. After layout, a screen taller than the viewport tucks away its least important
 * pieces a tier at a time (`data-tight` 1–4; globals.css says what each tier hides or shrinks) until it fits.
 * Rerun on resize and once the fonts have loaded.
 */
function useFitScreens() {
  useEffect(() => {
    let raf = 0;
    const fit = () => {
      raf = 0;
      for (const el of document.querySelectorAll<HTMLElement>("section.screen")) {
        el.removeAttribute("data-tight");
        for (let level = 1; level <= 4 && el.offsetHeight > innerHeight + 1; level++)
          el.setAttribute("data-tight", String(level));
      }
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(fit);
    };
    fit();
    document.fonts?.ready.then(schedule);
    addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(raf);
      removeEventListener("resize", schedule);
    };
  }, []);
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

/**
 * A header link. On the home page, links to its own screens glide there instead of jumping; from another page
 * they are ordinary links.
 */
function NavLink({ href, current, children }: { href: string; current?: boolean; children: ReactNode }) {
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    const hash = href.startsWith("/#") ? href.slice(2) : null;
    const el = hash ? document.getElementById(hash) : null; // on this page: glide; on another: follow the link
    if (!el) return;
    e.preventDefault();
    glideTo(el.getBoundingClientRect().top + scrollY);
  };
  return (
    <Link
      href={href}
      onClick={onClick}
      aria-current={current ? "page" : undefined}
      className={`nav-link px-1.5 py-0.5 ${current ? "bg-px text-lcd" : ""}`}
    >
      {children}
    </Link>
  );
}

/**
 * The status bar is also the site's navigation. Left: the signal, and the way home (the brand on the home page,
 * "◀ HOME" anywhere else). Centre: the screen on display. Right: the overview (how it works), the booth demo, the
 * team, the clock.
 */
export function StatusBar({ page = "home" }: { page?: "home" | "team" | "demo" }) {
  // until a screen is under the middle of the viewport (arriving mid-scroll from another page)
  const s = useStatus(
    page === "demo" ? { title: "BOOTH DEMO", signal: 0, data: false } : { title: "HOME", signal: 4, data: true },
  );
  useScreenSteps();
  useFitScreens();
  const now = useClock();
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b-4 border-px bg-lcd/95 backdrop-blur-[2px]">
      <nav
        aria-label="Main"
        className="relative mx-auto flex max-w-[1280px] items-center gap-3 px-4 py-2.5 font-mono text-[12px] font-medium sm:gap-5 sm:px-6 sm:text-[13px] md:px-12"
      >
        <Bars n={s.signal} />
        {page === "home" ? <NavLink href="/#top">VITAMIN BOB</NavLink> : <NavLink href="/">◀ HOME</NavLink>}

        <span
          key={s.title}
          className="fade-in pointer-events-none absolute left-1/2 hidden -translate-x-1/2 truncate font-bold tracking-wider md:inline"
        >
          {s.title}
        </span>

        <span className="ml-auto flex items-center gap-1 sm:gap-3">
          <span className="hidden sm:inline">
            <NavLink href="/#fix">OVERVIEW</NavLink>
          </span>
          <NavLink href="/demo" current={page === "demo"}>
            <span className="inline-flex items-center gap-1.5">
              <span className="nav-lamp h-1.5 w-1.5 bg-accent" aria-hidden />
              DEMO
            </span>
          </NavLink>
          <NavLink href="/team" current={page === "team"}>
            TEAM
          </NavLink>
        </span>
        <span className={s.clock ? "bg-px px-1.5 text-lcd" : ""}>{s.clock ?? now}</span>
        <span className="hidden items-center gap-0.5 sm:flex" aria-label="battery">
          <span className="flex h-4 w-8 gap-[2px] border-2 border-px p-[2px]">
            <span className="flex-1 bg-px" />
            <span className="flex-1 bg-px" />
            <span className="flex-1 bg-px" />
          </span>
          <span className="h-2 w-1 bg-px" />
        </span>
      </nav>
    </header>
  );
}

// The keypad shortcuts: press a number. Entries with an href go to another page; the rest glide to a screen here.
const MENU: { key: string; id: string; label: string; href?: string }[] = [
  { key: "1", id: "problem", label: "Why it matters" },
  { key: "2", id: "fix", label: "How it works" },
  { key: "3", id: "team", label: "The team" },
  { key: "4", id: "demo", label: "Try the demo", href: "/demo" },
  { key: "0", id: "top", label: "The start" },
];

/** The site's navigation is an IVR menu: press a number. Works with the keyboard too. */
export function useKeypadNav() {
  const router = useRouter();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      const m = MENU.find((x) => x.key === e.key);
      if (m?.href) router.push(m.href);
      else if (m) {
        const el = document.getElementById(m.id);
        if (el) glideTo(el.getBoundingClientRect().top + scrollY);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);
}
