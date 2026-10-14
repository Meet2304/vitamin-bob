import Link from "next/link";
import { Screen } from "./Phone";
import { Src } from "./Problem";
import { Sprite } from "./Sprite";

/* Proof */
export function Proof() {
  const rows = [
    ["Hindi, 43 cases", "14%", "7%"],
    ["Gujarati, 21 cases", "10%", "5%"],
    ["10 real voices", "–", "0%"],
  ];
  return (
    <Screen id="proof" title="THE PROOF" signal={4} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <h2 className="text-[40px] leading-[1.05] font-bold tracking-tight md:text-[60px]">
          Does it work? We measured it.
        </h2>
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
          {[
            ["0", "urgent cases missed, in every test set and both languages"],
            ["½", "the “not sure” rate when Gemma listens, compared with keyword matching"],
            ["₹0", "paid by the patient; about ₹0.30 per case for the district (estimate)"],
          ].map(([n, l]) => (
            <div key={l} className="px-box p-6">
              <div className="text-[96px] leading-none font-bold tracking-tighter">{n}</div>
              <p className="mt-3 text-xl leading-snug">{l}</p>
            </div>
          ))}
        </div>
        <div className="px-box mt-8 max-w-[760px] overflow-x-auto p-5">
          <table className="w-full min-w-[460px] text-left text-lg">
            <thead className="font-mono text-[12px]">
              <tr className="border-b-4 border-px">
                <th className="py-2 font-medium">CASES</th>
                <th className="py-2 font-medium">NOT SURE · KEYWORDS</th>
                <th className="py-2 font-medium">NOT SURE · GEMMA</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r[0]} className="border-b-2 border-dotted border-px-2 last:border-0">
                  <td className="py-2">{r[0]}</td>
                  <td className="py-2">{r[1]}</td>
                  <td className="py-2 font-bold">{r[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Src>
          Bob’s own evaluation: 54 synthetic cases written by the team and 10 recordings of team members’ voices; not
          real patients. Labels not yet reviewed by a clinician.
        </Src>
      </div>
    </Screen>
  );
}

/* Try it */
export function TryIt() {
  const steps = [
    [
      "Get the code and models",
      "git clone https://github.com/Meet2304/vitamin-bob\n# + llama.cpp and Gemma 4 E2B (see README)",
    ],
    ["Start the model and Bob", "cd bob\ntools\\start_model.cmd\n.venv\\Scripts\\python -m vitamin_bob.server"],
    [
      "Watch calls, no phone needed",
      ".venv\\Scripts\\python -m fake_stuart run --pace 1.5\n# open http://127.0.0.1:8100/dashboard",
    ],
  ];
  return (
    <Screen id="try" title="TRY IT" signal={4} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <h2 className="text-[40px] leading-[1.05] font-bold tracking-tight md:text-[60px]">Run it on one laptop.</h2>
        <p className="mt-4 max-w-[640px] text-2xl leading-snug">
          Everything runs offline on a Windows laptop. A built-in simulator plays the patients, so you can watch full
          calls in Hindi and Gujarati without a phone.
        </p>
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
          {steps.map(([t, c], i) => (
            <div key={t} className="px-box p-5">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center bg-px font-mono text-lcd">{i + 1}</span>
                <span className="text-xl font-bold">{t}</span>
              </div>
              <pre className="mt-4 overflow-x-auto border-2 border-dashed border-px p-3 font-mono text-[12px] leading-relaxed">
                <code>{c}</code>
              </pre>
            </div>
          ))}
        </div>
        <a
          href="https://github.com/Meet2304/vitamin-bob"
          className="mt-8 inline-block bg-px px-5 py-3 font-mono text-lcd hover:bg-px-2"
        >
          Open the repository →
        </a>
      </div>
    </Screen>
  );
}

/* The end of the call */
export function CallEnded() {
  return (
    <Screen id="end" title="CALL ENDED" signal={4} data={false} className="bg-px text-lcd">
      <div className="mx-auto grid grid-cols-1 w-full max-w-[1280px] items-center gap-12 md:grid-cols-[1.3fr_1fr]">
        <div>
          <div className="font-mono text-lg">CALL ENDED · 03:12 · ₹0</div>
          <h2 className="mt-4 text-[40px] leading-[1.05] font-bold tracking-tight md:text-[64px]">
            Localizing AI means meeting people on the phone they have, in the language they think in, and knowing when
            to step aside.
          </h2>
          <p className="mt-6 max-w-[620px] text-xl leading-snug">
            A small model on one laptop is enough to listen and sort. The decisions that matter stay with people.
          </p>
          <Link
            href="/team"
            className="mt-8 inline-block border-4 border-lcd px-5 py-3 font-mono text-[13px] font-medium hover:bg-lcd hover:text-px"
          >
            Meet the four of us who built it →
          </Link>
          <p className="mt-10 max-w-[760px] font-mono text-[12px] leading-relaxed opacity-80">
            Built for the World Bank × Hack-Nation Small AI for Development hackathon, health track, October 2026.
            Sources: World Bank concept note (2026), WHO Global Health Observatory, Siyam et al. (2021). Not a
            diagnostic tool; the protocol is drafted from WHO IMCI and not yet clinician-reviewed. Demo clinics and
            numbers are placeholders.
          </p>
        </div>
        <div className="flex items-end justify-center gap-5">
          <Sprite role="child" mood="happy" px={5} inverse />
          <Sprite role="patient" mood="happy" px={6} inverse />
          <Sprite role="bob" mood="happy" px={9} inverse />
          <Sprite role="clinician" mood="happy" px={6} inverse />
        </div>
      </div>
    </Screen>
  );
}
