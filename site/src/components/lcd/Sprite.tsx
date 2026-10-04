/**
 * The character, as LCD pixels. Same capsule as before, drawn on a grid:
 *   bob       antenna, lower half dithered (his two tones)
 *   patient   solid
 *   child     smaller
 *   clinician solid with a cross cut out of the chest
 * Eyes are holes in the body (the glass shows through); they blink by being covered.
 */
export type SpriteRole = "bob" | "patient" | "child" | "clinician";
export type SpriteMood = "calm" | "happy" | "worried";

type Px = [number, number];

function capsule(w: number, h: number): Px[] {
  // Slightly squarer than a true semicircle, so the shoulders read as a body, not a bullet.
  const r = w / 2 - 1;
  const half = w / 2;
  const out: Px[] = [];
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const cx = x + 0.5;
      const cy = y + 0.5;
      const dy = cy < r ? r - cy : cy > h - r ? cy - (h - r) : 0;
      const dx = Math.max(0, Math.abs(cx - half) - (half - r));
      if (dx ** 2 + dy ** 2 <= r * r + 0.4) out.push([x, y]);
    }
  }
  return out;
}

/** Pixels as one path: each horizontal run of lit pixels becomes one rectangle segment. */
function runsPath(px: Px[]): string {
  const rows = new Map<number, number[]>();
  for (const [x, y] of px) rows.set(y, [...(rows.get(y) ?? []), x]);
  let d = "";
  for (const [y, xs] of rows) {
    xs.sort((p, q) => p - q);
    let start = xs[0];
    let prev = xs[0];
    for (let i = 1; i <= xs.length; i++) {
      if (i < xs.length && xs[i] === prev + 1) {
        prev = xs[i];
        continue;
      }
      d += `M${start} ${y}h${prev - start + 1}v1h${start - prev - 1}z`;
      if (i < xs.length) start = prev = xs[i];
    }
  }
  return d;
}

export function Sprite({
  role = "patient",
  mood = "calm",
  px = 6,
  blink = true,
  inverse = false,
  ghost = false,
  className = "",
  label,
}: {
  role?: SpriteRole;
  mood?: SpriteMood;
  /** Size of one pixel in CSS px. */
  px?: number;
  blink?: boolean;
  /** Light figure on dark (used to mark the urgent case). */
  inverse?: boolean;
  /** Drawn in "off" pixels: someone who is not there. */
  ghost?: boolean;
  className?: string;
  label?: string;
}) {
  const child = role === "child";
  const W = child ? 10 : 12;
  const H = child ? 16 : 22;
  const top = role === "bob" ? 4 : 0; // room for the antenna
  const ey = child ? 5 : 7; // eye row
  const eyes: Px[] = child
    ? [[2, ey], [2, ey + 1], [7, ey], [7, ey + 1]]
    : [[3, ey], [3, ey + 1], [3, ey + 2], [8, ey], [8, ey + 1], [8, ey + 2]];
  const my = child ? 9 : 12;
  const mouth: Px[] =
    mood === "happy"
      ? [[child ? 3 : 4, my], [child ? 4 : 5, my + 1], [child ? 5 : 6, my + 1], [child ? 6 : 7, my]]
      : mood === "worried"
        ? [[child ? 3 : 4, my + 1], [child ? 4 : 5, my], [child ? 5 : 6, my], [child ? 6 : 7, my + 1]]
        : [[child ? 4 : 5, my], [child ? 5 : 6, my]];
  const holes = new Set([...eyes, ...mouth].map(([x, y]) => `${x},${y}`));
  if (role === "clinician") {
    for (const [x, y] of [[8, 16], [7, 17], [8, 17], [9, 17], [8, 18]] as Px[]) holes.add(`${x},${y}`);
  }
  const body = capsule(W, H).filter(([x, y]) => {
    if (holes.has(`${x},${y}`)) return false;
    // Bob's lower half is a 50% dither: his second tone.
    if (role === "bob" && y >= 14 && (x + y) % 2 === 1) return false;
    return true;
  });
  const ink = ghost ? "var(--color-ghost)" : inverse ? "var(--color-lcd)" : "var(--color-px)";
  const glass = inverse ? "var(--color-px)" : "var(--color-lcd)";

  return (
    <svg
      viewBox={`-1 ${-top - 1} ${W + 2} ${H + top + 2}`}
      width={(W + 2) * px}
      height={(H + top + 2) * px}
      shapeRendering="crispEdges"
      className={className}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {inverse && <rect x={-1} y={-top - 1} width={W + 2} height={H + top + 2} fill={glass} />}
      {role === "bob" && (
        <g fill={ink}>
          <rect x={5} y={-2} width={2} height={2} />
          <rect x={4} y={-4} width={4} height={2} />
        </g>
      )}
      <path fill={ink} d={runsPath(body)} />
      {blink && <path fill={ink} className="blink-lids" d={runsPath(eyes)} />}
    </svg>
  );
}
