import { Boot } from "@/components/lcd/Boot";
import { Footer } from "@/components/lcd/Footer";
import { People } from "@/components/lcd/People";
import { StatusBar } from "@/components/lcd/Phone";
import { India, Journey, OutOfReach, Turn } from "@/components/lcd/Problem";
import { Story } from "@/components/lcd/Story";
import { Wins } from "@/components/lcd/Wins";

export default function Home() {
  return (
    <>
      <StatusBar />
      <main>
        <Boot />
        <OutOfReach />
        <India />
        <Journey />
        <Turn />
        <Story />
        <Wins />
        <People />
      </main>
      <Footer />
    </>
  );
}
