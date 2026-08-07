"use client";

import { useEffect, useState } from "react";
import {
  askEconomics,
  getEconomicsSummary,
  type EconomicsAnswer,
  type EconomicsSummary,
} from "@/lib/api";

const EXAMPLES = [
  "which pipeline step is most expensive?",
  "what did the last 10 queries cost?",
  "how many calls degraded?",
];

function SpendChart({ data }: { data: EconomicsSummary["by_hour"] }) {
  if (!data.length) return <p className="font-body text-sm text-mist">No hourly spend in this window.</p>;
  const width = 600;
  const height = 180;
  const maxTokens = Math.max(...data.map((point) => point.tokens), 1);
  const maxCost = Math.max(...data.map((point) => point.cost_usd), 0.000001);
  const points = (field: "tokens" | "cost_usd", max: number) => data.map((point, index) => {
    const x = data.length === 1 ? width / 2 : (index / (data.length - 1)) * width;
    const y = height - (point[field] / max) * (height - 20) - 10;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Tokens and USD spend over time" className="h-52 w-full overflow-visible">
        <polyline fill="none" stroke="var(--accent-purple)" strokeWidth="4" points={points("tokens", maxTokens)} />
        <polyline fill="none" stroke="var(--accent-pink)" strokeWidth="4" points={points("cost_usd", maxCost)} />
      </svg>
      <div className="flex gap-5 font-body text-xs text-mist">
        <span className="flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-accent-purple" />Tokens</span>
        <span className="flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-accent-pink" />USD</span>
      </div>
    </div>
  );
}

export function EconomyDashboard() {
  const [window, setWindow] = useState("24h");
  const [summary, setSummary] = useState<EconomicsSummary | null>(null);
  const [summaryError, setSummaryError] = useState(false);
  const [question, setQuestion] = useState(EXAMPLES[0]);
  const [answer, setAnswer] = useState<EconomicsAnswer | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState(false);

  useEffect(() => {
    let active = true;
    getEconomicsSummary(window)
      .then((data) => active && setSummary(data))
      .catch(() => active && setSummaryError(true));
    return () => {
      active = false;
    };
  }, [window]);

  async function submitQuestion(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setAskError(false);
    try {
      setAnswer(await askEconomics(question.trim()));
    } catch {
      setAskError(true);
    } finally {
      setAsking(false);
    }
  }

  const callSites = [...(summary?.by_call_site ?? [])].sort((left, right) => right.cost_usd - left.cost_usd);
  const maxSpend = Math.max(...callSites.map((site) => site.cost_usd), 0);
  const ledgerEmpty = summary !== null
    && summary.total_requests === 0
    && callSites.every((site) => site.tokens === 0 && site.cost_usd === 0);
  const rowKeys = answer?.rows[0] ? Object.keys(answer.rows[0]) : [];

  return (
    <div className="grid gap-6">
      <section className="glass-panel p-6">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <p className="eyebrow">Headline</p>
            <h2 className="mt-2 font-display text-2xl text-ink">What this agent actually costs</h2>
          </div>
          <select value={window} onChange={(event) => {
            setSummary(null);
            setSummaryError(false);
            setWindow(event.target.value);
          }} className="rounded-xl border border-line bg-void-2 px-3 py-2 font-body text-sm text-ink">
            <option value="1h">1 hour</option>
            <option value="24h">24 hours</option>
            <option value="7d">7 days</option>
          </select>
        </div>
        {summaryError && <p className="font-body text-sm text-accent-pink">Ledger summary is unavailable.</p>}
        {!summary && !summaryError && <p className="font-body text-sm text-mist">Loading ledger…</p>}
        {summary && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Requests", summary.total_requests.toLocaleString()],
              ["Tokens", summary.total_tokens.toLocaleString()],
              ["Total spend", `$${summary.total_cost_usd.toFixed(4)}`],
              ["Median / query", "Unavailable"],
            ].map(([label, value], index) => (
              <div key={label} className={`rounded-2xl border p-4 ${index === 3 ? "border-rare/50 bg-rare/10" : "border-line bg-void-2/40"}`}>
                <p className="font-body text-xs text-mist">{label}</p>
                <p className={`${index === 3 ? "text-3xl" : "text-2xl"} mt-2 font-data text-ink`}>{value}</p>
                {index === 3 && <p className="mt-2 font-body text-[11px] text-mist">Pending backend contract field</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="glass-panel p-6">
        <p className="eyebrow">Cost by pipeline step</p>
        <h2 className="mb-6 mt-2 font-display text-2xl text-ink">Where the money goes</h2>
        {ledgerEmpty && <p className="font-body text-sm text-mist">Ledger not yet reporting.</p>}
        {!ledgerEmpty && callSites.length === 0 && <p className="font-body text-sm text-mist">No call-site data in this window.</p>}
        {!ledgerEmpty && (
          <div className="grid gap-4">
            {callSites.map((site) => (
              <div key={site.call_site}>
                <div className="mb-1 flex justify-between gap-3 font-body text-sm">
                  <span className="text-paper">{site.call_site.replaceAll("_", " ")}</span>
                  <span className="font-data text-mist">{site.tokens.toLocaleString()} · ${site.cost_usd.toFixed(5)}</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-void-2">
                  <div className="h-full rounded-full bg-[linear-gradient(90deg,var(--accent-purple),var(--accent-pink))]" style={{ width: `${maxSpend ? (site.cost_usd / maxSpend) * 100 : 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="glass-panel p-6">
        <p className="eyebrow">Spend over time</p>
        <h2 className="mb-6 mt-2 font-display text-2xl text-ink">Tokens and USD by hour</h2>
        <SpendChart data={summary?.by_hour ?? []} />
      </section>

      <section className="glass-panel p-6">
        <p className="eyebrow">Ask the data</p>
        <h2 className="mb-4 mt-2 font-display text-2xl text-ink">Cortex Analyst</h2>
        <div className="mb-4 flex flex-wrap gap-2">
          {EXAMPLES.map((example) => (
            <button key={example} type="button" onClick={() => setQuestion(example)} className="rounded-full border border-line px-3 py-2 font-body text-xs text-mist hover:border-line-bright hover:text-ink">
              {example}
            </button>
          ))}
        </div>
        <form onSubmit={submitQuestion} className="flex flex-col gap-3 sm:flex-row">
          <input value={question} onChange={(event) => setQuestion(event.target.value)} className="min-w-0 flex-1 rounded-xl border border-line bg-void-2 px-4 py-3 font-body text-ink outline-none focus:border-line-bright" />
          <button disabled={asking || !question.trim()} className="btn-gradient rounded-xl px-6 py-3 font-body font-semibold text-white disabled:opacity-40">
            {asking ? "Asking…" : "Ask"}
          </button>
        </form>
        {askError && <p className="mt-4 font-body text-sm text-accent-pink">Cortex Analyst is unavailable.</p>}
        {answer && (
          <div className="mt-6 grid gap-5">
            <p className="border-l-2 border-rare pl-4 font-display text-2xl text-ink">{answer.answer}</p>
            {rowKeys.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse font-body text-sm">
                  <thead><tr>{rowKeys.map((key) => <th key={key} className="border-b border-line p-3 text-left text-mist">{key}</th>)}</tr></thead>
                  <tbody>{answer.rows.map((row, index) => <tr key={index}>{rowKeys.map((key) => <td key={key} className="border-b border-line p-3 text-paper">{String(row[key] ?? "")}</td>)}</tr>)}</tbody>
                </table>
              </div>
            )}
            <details className="font-body text-sm text-mist"><summary className="cursor-pointer">Generated SQL</summary><pre className="mt-3 overflow-x-auto rounded-xl bg-void-2 p-4 font-mono text-xs text-paper">{answer.sql}</pre></details>
          </div>
        )}
      </section>
    </div>
  );
}
