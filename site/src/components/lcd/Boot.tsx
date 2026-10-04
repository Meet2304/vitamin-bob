import { IvrMenu, Screen } from "./Phone";
import { Sprite } from "./Sprite";

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
          <div className="ring px-box w-full max-w-[380px] bg-lcd">
            <div className="flex items-center justify-between bg-px px-4 py-2 font-mono text-[13px] font-medium text-lcd">
              <span>1 MISSED CALL</span>
              <span>02:14</span>
            </div>
            <div className="flex flex-col items-center gap-5 px-6 py-8">
              <Sprite role="bob" mood="happy" px={11} label="Bob, the character, as pixels on a phone screen" />
              <div className="text-center">
                <div className="text-xl font-semibold">Calling you back</div>
                <div className="font-mono text-lg">+91 ••••••0021<span className="cursor">█</span></div>
              </div>
            </div>
            <div className="grid grid-cols-2 border-t-4 border-px font-mono text-[13px] font-medium">
              <span className="border-r-4 border-px py-2.5 text-center">IGNORE</span>
              <span className="bg-px py-2.5 text-center text-lcd">ANSWER</span>
            </div>
          </div>
        </div>
      </div>
    </Screen>
  );
}
