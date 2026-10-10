import { IvrMenu, Screen } from "./Phone";
import { Sprite } from "./Sprite";

/** Pixels of a ")" arc: part of a circle of radius r centred left of the grid, like a ringing signal. */
function arc(r: number, cy: number): [number, number][] {
  const span = Math.round(r * 0.7);
  const out: [number, number][] = [];
  for (let dy = -span; dy <= span; dy++) out.push([Math.round(Math.sqrt(r * r - dy * dy)) - Math.round(r * 0.7), cy + dy]);
  return out;
}

/** Three arcs that light up one after another while the phone rings, on the same 8px grid as Bob. */
function RingWaves({ flip = false }: { flip?: boolean }) {
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

export function Boot() {
  return (
    <Screen id="top" title="VITAMIN BOB">
      <div className="mx-auto grid w-full max-w-[1280px] items-center gap-14 md:grid-cols-[1.25fr_1fr]">
        <div className="flex flex-col gap-8">
          <h1 className="text-[44px] leading-[1.02] font-bold tracking-tight md:text-[76px]">
            Care that starts with a missed call<span className="cursor">_</span>
          </h1>
          <p className="max-w-[600px] text-xl leading-snug md:text-2xl">
            Any phone. No internet. Free for the patient. Bob calls back, listens in Hindi or Gujarati, and sends
            you to the clinic that is actually open. Not sure? A person decides.
          </p>
          <IvrMenu />
        </div>

        <div className="flex justify-center">
          <div
            className="px-box w-full max-w-[380px] bg-lcd"
            role="img"
            aria-label="A phone screen: incoming call from Vitamin Bob, calling you back for free"
          >
            <div className="flex items-center justify-between bg-px px-4 py-2 font-mono text-[13px] font-medium tracking-wider text-lcd">
              <span>INCOMING CALL</span>
              <span className="border border-lcd px-1.5">FREE</span>
            </div>

            <div className="flex flex-col items-center gap-6 bg-lcd-2/60 px-6 pt-9 pb-8">
              <div className="flex items-center gap-2">
                <RingWaves flip />
                <Sprite role="bob" mood="happy" px={8} />
                <RingWaves />
              </div>
              <div className="flex flex-col items-center gap-1.5 text-center">
                <div className="text-[34px] leading-none font-bold tracking-tight">Vitamin Bob</div>
                <div className="text-lg">Calling you back…</div>
              </div>
              <div className="flex gap-2 font-mono text-[12px] font-medium">
                <span className="border-2 border-px px-2 py-0.5">हिंदी</span>
                <span className="border-2 border-px px-2 py-0.5">ગુજરાતી</span>
                <span className="bg-px px-2 py-0.5 text-lcd">₹0 FOR YOU</span>
              </div>
            </div>

            <div className="grid grid-cols-2 border-t-4 border-px font-mono text-[13px] font-medium tracking-wider">
              <span className="border-r-4 border-px py-3 text-center">IGNORE</span>
              <span className="bg-px py-3 text-center text-lcd">ANSWER</span>
            </div>
          </div>
        </div>
      </div>
    </Screen>
  );
}
