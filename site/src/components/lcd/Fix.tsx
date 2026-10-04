import type { ReactNode } from "react";
import { Screen } from "./Phone";
import { Kicker, Src } from "./Problem";
import { Sprite } from "./Sprite";

/** A little handset UI: a header strip, a body, optional soft keys. */
function Handset({ head, right, children, keys }: { head: string; right?: string; children: ReactNode; keys?: [string, string] }) {
  return (
    <div className="px-box w-full max-w-[420px] bg-lcd">
      <div className="flex items-center justify-between bg-px px-4 py-2 font-mono text-[13px] font-medium text-lcd">
        <span>{head}</span>
        <span>{right}</span>
      </div>
      <div className="px-5 py-5">{children}</div>
      {keys && (
        <div className="grid grid-cols-2 border-t-4 border-px font-mono text-[13px] font-medium">
          <span className="border-r-4 border-px py-2 text-center">{keys[0]}</span>
          <span className="bg-px py-2 text-center text-lcd">{keys[1]}</span>
        </div>
      )}
    </div>
  );
}

function Step({
  id,
  n,
  title,
  children,
  proof,
  screen,
  source,
  clock,
}: {
  id?: string;
  n: number;
  title: string;
  children: ReactNode;
  proof: string[];
  screen: ReactNode;
  source?: string;
  clock?: string;
}) {
  return (
    <Screen id={id ?? `fix-${n}`} title="THE FIX" signal={4} data={false} clock={clock}>
      <div className="mx-auto grid w-full max-w-[1280px] items-center gap-12 md:grid-cols-[1.1fr_1fr]">
        <div>
          <Kicker n={n} total={8}>How Bob helps</Kicker>
          <h2 className="text-[36px] leading-[1.05] font-bold tracking-tight md:text-[56px]">{title}</h2>
          <div className="mt-5 max-w-[580px] text-xl leading-snug md:text-2xl">{children}</div>
          <ul className="mt-6 flex flex-col gap-2 font-mono text-[14px]">
            {proof.map((p) => (
              <li key={p} className="flex gap-3">
                <span aria-hidden>▸</span>
                {p}
              </li>
            ))}
          </ul>
          {source && <Src>{source}</Src>}
        </div>
        <div className="flex justify-center">{screen}</div>
      </div>
    </Screen>
  );
}

function Tick({ on, label, quote }: { on: boolean | null; label: string; quote?: string }) {
  return (
    <div className="flex items-center gap-3 border-b-2 border-dotted border-px-2 py-2 last:border-0">
      <span className={`flex h-6 w-6 items-center justify-center border-2 border-px font-mono text-[13px] ${on ? "bg-px text-lcd" : ""}`}>
        {on ? "✓" : on === null ? "?" : ""}
      </span>
      <span className="flex-1 text-lg">{label}</span>
      {quote && <span className="bg-lcd-2 px-1.5 text-lg">“{quote}”</span>}
    </div>
  );
}

export function Fix() {
  return (
    <>
      <Step
        id="fix"
        n={1}
        title="She rings once and hangs up. It costs her nothing."
        proof={["Works on any phone: no app, no data plan", "The district pays for the callback"]}
        screen={
          <Handset head="1 MISSED CALL" right="02:14" keys={["", "₹0"]}>
            <div className="flex items-center gap-5">
              <span className="ring">
                <Sprite role="patient" mood="worried" px={6} />
              </span>
              <div className="text-xl leading-snug">
                Call ended before it connected.
                <div className="mt-2 font-mono text-[14px]">callback queued at the district hub</div>
              </div>
            </div>
          </Handset>
        }
      >
        A missed call never connects, so the caller pays nothing. A laptop at the district hub sees it within
        seconds and queues a callback.
      </Step>

      <Step
        n={2}
        title="Bob calls back, in her language."
        proof={["Hindi or Gujarati; another language is data and audio files, not code", "Every sentence is a fixed recording: the AI never speaks"]}
        screen={
          <Handset head="BOB CALLING" right="00:04">
            <div className="flex items-center gap-5">
              <Sprite role="bob" mood="happy" px={6} />
              <div className="flex flex-1 flex-col gap-2 text-lg">
                <div className="border-2 border-px px-3 py-1.5">हिंदी के लिए 1 दबाएँ</div>
                <div className="bg-px px-3 py-1.5 text-lcd">ગુજરાતી માટે 2 દબાવો ✓</div>
                <div className="font-mono text-[12px]">repeats until a key is pressed</div>
              </div>
            </div>
          </Handset>
        }
      >
        The menu repeats until she presses a key, because nobody can be sure exactly when she picked up. Smartphone
        users are reminded to open the keypad.
      </Step>

      <Step
        n={3}
        title="She describes the problem once, in her own words."
        proof={["Gemma 4 runs on the district laptop: no internet", "A 25-second clip is understood in under 20 seconds"]}
        source="Measured on the demo laptop (RTX 3050 Ti, 4 GB). Gemma 4 E2B, 8-bit, via llama.cpp."
        screen={
          <Handset head="LISTENING" right="00:21">
            <div className="text-xl leading-snug">“મારી દીકરીને ખૂબ તાવ આવે છે અને હમણાં જ ખેંચ આવી છે.”</div>
            <div className="mt-4 flex h-12 items-end gap-1" aria-hidden>
              {Array.from({ length: 28 }).map((_, i) => (
                <span key={i} className="eq w-2 bg-px" style={{ height: `${20 + ((i * 37) % 80)}%`, animationDelay: `${(i % 7) * 0.12}s` }} />
              ))}
            </div>
            <div className="mt-3 font-mono text-[12px]">Gemma 4 · on this laptop · offline</div>
          </Handset>
        }
      >
        Up to 25 seconds of speech. A small model on one laptop turns it into text, then into a fixed form of
        symptoms and danger signs.
      </Step>

      <Step
        n={4}
        title="Every answer must be backed by her words."
        proof={["No quote, no answer: it is asked on the keypad instead", "What she already said is not asked again"]}
        screen={
          <Handset head="WHAT BOB UNDERSTOOD" right="case 1203">
            <Tick on label="Fever" quote="ખૂબ તાવ" />
            <Tick on label="Fits" quote="ખેંચ આવી" />
            <Tick on={null} label="Cough · not said, ask" />
            <Tick on={null} label="Drowsy · not said, ask" />
            <div className="mt-3 font-mono text-[12px]">press 1 yes · 2 no · 3 don’t know</div>
          </Handset>
        }
      >
        The model only fills the form. If it cannot point to the words she used, the answer stays unknown, and Bob
        asks a simple yes-or-no question on the keypad.
      </Step>

      <Step
        n={5}
        title="Written rules decide. Not sure? Ask a person."
        proof={["Five levels of urgency, each with its reasons", "Anything that could hide an emergency goes to a clinician"]}
        screen={
          <Handset head="DECISION" right="rules v0.3">
            {[
              ["EMERGENCY", "call 108 now", true],
              ["HIGH", "go to a clinic now", false],
              ["UNCERTAIN", "a clinician decides", false],
              ["MEDIUM", "booked today or tomorrow", false],
              ["LOW", "next free slot", false],
            ].map(([t, d, on]) => (
              <div key={t as string} className={`flex items-center justify-between px-3 py-2 ${on ? "bg-px text-lcd" : "border-b-2 border-dotted border-px-2"}`}>
                <span className="font-mono text-[14px] font-medium">{t}</span>
                <span className="text-lg">{d}</span>
              </div>
            ))}
            <div className="mt-3 font-mono text-[12px]">because: fits or convulsions</div>
          </Handset>
        }
      >
        The level comes from transparent rules drafted from WHO danger signs, never from the model’s opinion. When
        an answer is missing, the case becomes UNCERTAIN and a clinician decides.
      </Step>

      <Step
        n={6}
        title="The nearest clinic that is actually open."
        proof={["Clinics report OPEN, CLOSED or FULL by SMS or a free missed call", "Emergencies always go to 108"]}
        screen={
          <Handset head="ROUTING" right="village: Rampur">
            {[
              ["Rampur PHC", "10 min", "closed by SMS", false],
              ["Devgaon PHC", "25 min", "open · sent here", true],
              ["Lakhpur CHC", "40 min", "open", false],
            ].map(([c, m, s, on]) => (
              <div key={c as string} className={`flex items-center gap-3 px-3 py-2.5 ${on ? "bg-px text-lcd" : "border-b-2 border-dotted border-px-2"}`}>
                <span className="flex-1 text-lg">{c}</span>
                <span className="font-mono text-[12px]">{m}</span>
                <span className={`font-mono text-[12px] ${s === "closed by SMS" ? "line-through" : ""}`}>{s}</span>
              </div>
            ))}
            <div className="mt-3 font-mono text-[12px]">Rampur skipped: closed at 02:16</div>
          </Handset>
        }
      >
        Each village has its clinics in order of travel time. Bob picks the first that is open and has room, and
        tells her which one, by name.
      </Step>

      <Step
        n={7}
        title="Urgent cases land on a clinician’s phone."
        proof={["One reply acknowledges it", "No answer in 3 minutes: it moves to the next clinic, then the district"]}
        screen={
          <Handset head="NEW SMS" right="02:15" keys={["LATER", "REPLY"]}>
            <div className="flex items-start gap-4">
              <Sprite role="clinician" mood="calm" px={5} />
              <div className="font-mono text-[14px] leading-relaxed">
                VB 1203 EMERGENCY · Child under 5 · Fever · Fits · Call +91 ••••0022 · Reply ACK 1203
                <div className="mt-3 inline-block bg-px px-2 py-0.5 text-lcd">ACK 1203 ✓</div>
              </div>
            </div>
          </Handset>
        }
      >
        The routed clinic’s clinician gets what was heard and a number to call back, so they can prepare before the
        patient arrives. Unanswered alerts never disappear.
      </Step>

      <Step
        n={8}
        title="The record writes itself."
        proof={["Every case: urgency, reasons, rules and model version", "Sent to the state over SMS, 200 bytes, no names or numbers"]}
        screen={
          <Handset head="RECORD 1203" right="→ CENTRAL">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-lg">
              <span>urgency</span><b>EMERGENCY</b>
              <span>patient</span><b>child under 5</b>
              <span>heard</span><b>fever, fits</b>
              <span>sent to</span><b>108 + clinic alert</b>
            </div>
            <div className="mt-4 border-2 border-dashed border-px p-2 font-mono text-[11px] leading-relaxed break-all">
              {'{"h":"HUB-D1","r":"E","a":"c","s":"F1","f":"CV","q":0,"l":"gu","o":"108","pk":"5bwd3d4tnail6"}'}
            </div>
            <div className="mt-2 font-mono text-[12px]">delivered ✓ · acknowledged by Central</div>
          </Handset>
        }
      >
        The paperwork is done before she arrives: a complete record at the district, and a privacy-safe summary for
        the state, sent by SMS so it works with no internet anywhere.
      </Step>
    </>
  );
}

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
        <h2 className="text-[40px] leading-[1.05] font-bold tracking-tight md:text-[60px]">Does it work? We measured it.</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
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
        <Src>Bob’s own evaluation: 54 synthetic cases written by the team and 10 recordings of team members’ voices; not real patients. Labels not yet reviewed by a clinician.</Src>
      </div>
    </Screen>
  );
}

/* Try it */
export function TryIt() {
  const steps = [
    ["Get the code and models", "git clone https://github.com/Meet2304/vitamin-bob\n# + llama.cpp and Gemma 4 E2B (see README)"],
    ["Start the model and Bob", "cd bob\ntools\\start_model.cmd\n.venv\\Scripts\\python -m vitamin_bob.server"],
    ["Watch calls, no phone needed", ".venv\\Scripts\\python -m fake_stuart run --pace 1.5\n# open http://127.0.0.1:8100/dashboard"],
  ];
  return (
    <Screen id="try" title="TRY IT" signal={4} data={false}>
      <div className="mx-auto w-full max-w-[1280px]">
        <h2 className="text-[40px] leading-[1.05] font-bold tracking-tight md:text-[60px]">Run it on one laptop.</h2>
        <p className="mt-4 max-w-[640px] text-2xl leading-snug">
          Everything runs offline on a Windows laptop. A built-in simulator plays the patients, so you can watch full
          calls in Hindi and Gujarati without a phone.
        </p>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
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
        <a href="https://github.com/Meet2304/vitamin-bob" className="mt-8 inline-block bg-px px-5 py-3 font-mono text-lcd hover:bg-px-2">
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
      <div className="mx-auto grid w-full max-w-[1280px] items-center gap-12 md:grid-cols-[1.3fr_1fr]">
        <div>
          <div className="font-mono text-lg">CALL ENDED · 03:12 · ₹0</div>
          <h2 className="mt-4 text-[40px] leading-[1.05] font-bold tracking-tight md:text-[64px]">
            Localizing AI means meeting people on the phone they have, in the language they think in, and knowing
            when to step aside.
          </h2>
          <p className="mt-6 max-w-[620px] text-xl leading-snug">
            A small model on one laptop is enough to listen and sort. The decisions that matter stay with people.
          </p>
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
