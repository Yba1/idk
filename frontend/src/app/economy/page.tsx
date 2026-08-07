import Link from "next/link";
import { EconomyDashboard } from "@/components/economy/economy-dashboard";

export default function EconomyPage() {
  return (
    <main className="relative z-10 mx-auto w-full max-w-6xl flex-1 px-6 py-12 md:px-12">
      <Link href="/" className="font-body text-sm text-mist underline hover:text-ink">← Back to search</Link>
      <div className="mb-10 mt-8">
        <p className="eyebrow">Snowflake showcase</p>
        <h1 className="mt-3 font-display text-4xl text-ink md:text-6xl">Token economy</h1>
        <p className="mt-4 max-w-2xl font-body text-paper">Every model call is measured, priced, and attributed to the pipeline step that caused it.</p>
      </div>
      <EconomyDashboard />
    </main>
  );
}
