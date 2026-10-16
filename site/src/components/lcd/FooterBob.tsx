"use client";

import { useEffect, useRef, useState } from "react";
import { capsule, runsPath } from "./Sprite";

/**
 * Bob, peeking over the footer's divider. His eyes follow the pointer anywhere on the page. With a mouse, he pops
 * up when the cursor enters the footer, and pointing at a footer link makes him say what it is (`data-say` on the
 * link). On a touchscreen, he pops up when the footer scrolls into view. Tapping or clicking him makes him hop and
 * say the next of his lines. Same pixel grid as the sprites; drawn here because his eyes move.
 */
const W = 12;
const H = 22;
const PX = 4;
const HELLO = "Thanks for stopping by!";
const LINES = [
  "Hi! I'm Bob.",
  "I always call back. Free.",
  "Hindi? Gujarati? Both!",
  "Not sure? A person decides.",
  "No internet needed.",
  HELLO,
];

// body: Bob's capsule, lower half dithered (his second tone)
const BODY = runsPath(capsule(W, H).filter(([x, y]) => !(y >= 14 && (x + y) % 2 === 1)));
const SMILE: [number, number][] = [
  [4, 12],
  [5, 13],
  [6, 13],
  [7, 12],
];
const TALK: [number, number][] = [
  [5, 12],
  [6, 12],
  [5, 13],
  [6, 13],
];

const sign = (v: number, dead: number) => (Math.abs(v) < dead ? 0 : Math.sign(v));

export function FooterBob() {
  const ref = useRef<HTMLDivElement>(null);
  const [look, setLook] = useState<[number, number]>([0, 0]);
  const [say, setSay] = useState<string | null>(null);
  const [hop, setHop] = useState(0);
  const line = useRef(-1);

  useEffect(() => {
    const me = ref.current;
    const footer = me?.closest("footer");
    if (!me || !footer) return;
    let raf = 0;
    let px = 0;
    let py = 0;
    const aim = () => {
      raf = 0;
      const r = me.querySelector("svg")?.getBoundingClientRect();
      if (!r) return;
      // eyes sit about a third of the way down his head
      const dx = sign(px - (r.left + r.width / 2), 36);
      const dy = sign(py - (r.top + r.height * 0.32), 36);
      setLook((l) => (l[0] === dx && l[1] === dy ? l : [dx, dy]));
    };
    const move = (e: PointerEvent) => {
      px = e.clientX;
      py = e.clientY;
      if (!raf) raf = requestAnimationFrame(aim);
    };
    const over = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const link = (e.target as HTMLElement).closest<HTMLElement>("[data-say]");
      setSay(link?.dataset.say ?? HELLO);
    };
    const leave = (e: PointerEvent) => {
      if (e.pointerType === "mouse") setSay(null);
    };
    // touchscreens have no hover: Bob pops up while the footer is in view instead
    const touch = matchMedia("(hover: none)").matches;
    const io = new IntersectionObserver(([e]) => setSay(e.isIntersecting ? HELLO : null), { threshold: 0.5 });
    if (touch) io.observe(footer);
    addEventListener("pointermove", move, { passive: true });
    addEventListener("pointerdown", move, { passive: true });
    footer.addEventListener("pointerover", over);
    footer.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      removeEventListener("pointermove", move);
      removeEventListener("pointerdown", move);
      footer.removeEventListener("pointerover", over);
      footer.removeEventListener("pointerleave", leave);
    };
  }, []);

  const [dx, dy] = look;
  const talking = say !== null && say !== HELLO;
  const talk = () => {
    line.current = (line.current + 1) % LINES.length;
    setSay(LINES[line.current]);
    setHop((h) => h + 1);
  };
  const mouth = talking ? TALK : SMILE;

  return (
    <div ref={ref} className="relative">
      <div className={`footer-bubble ${say ? "on" : ""}`} aria-live="polite">
        <span key={say ?? ""} className="fade-in block">
          {say ?? HELLO}
        </span>
      </div>
      {/* the clip box ends at the divider: Bob is behind it, and rises out of it */}
      <button
        type="button"
        onClick={talk}
        aria-label="Talk to Bob"
        className="footer-bob-btn mr-2 ml-auto block h-[112px] w-[56px] cursor-pointer overflow-hidden"
      >
        <svg
          viewBox={`-1 -5 ${W + 2} ${H + 6}`}
          width={(W + 2) * PX}
          height={(H + 6) * PX}
          shapeRendering="crispEdges"
          className={`footer-bob ${say ? "up" : ""}`}
          aria-hidden
        >
          {/* a fresh key on each tap replays the hop */}
          <g key={hop} className={hop ? "footer-bob-hop" : ""}>
            <g fill="var(--color-lcd)">
              <rect x={5} y={-2} width={2} height={2} />
              <rect x={4} y={-4} width={4} height={2} />
              <path d={BODY} />
            </g>
            {/* eyes and mouth are the dark glass showing through; the eyes move with the pointer */}
            <g fill="var(--color-px)">
              <rect className="footer-bob-eye" x={3 + dx} y={6 + dy} width={2} height={3} />
              <rect className="footer-bob-eye" x={7 + dx} y={6 + dy} width={2} height={3} />
              {mouth.map(([x, y]) => (
                <rect key={`${x},${y}`} x={x} y={y} width={1} height={1} />
              ))}
            </g>
          </g>
        </svg>
      </button>
    </div>
  );
}
