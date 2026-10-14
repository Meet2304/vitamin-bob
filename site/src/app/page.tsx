import { Boot } from "@/components/lcd/Boot";
import { CallEnded, Proof, TryIt } from "@/components/lcd/Fix";
import { Live } from "@/components/lcd/Live";
import { SoftKeys, StatusBar } from "@/components/lcd/Phone";
import { Story } from "@/components/lcd/Story";
import { Wins } from "@/components/lcd/Wins";
import { Paperwork, Queue, Scarcity, Turn } from "@/components/lcd/Problem";

export default function Home() {
  return (
    <>
      <StatusBar />
      <main>
        <Boot />
        <Scarcity />
        <Queue />
        <Paperwork />
        <Turn />
        <Story />
        <Proof />
        <Wins />
        <Live />
        <TryIt />
        <CallEnded />
      </main>
      <SoftKeys />
    </>
  );
}
