"use client";

import { useEffect, useState } from "react";
import {
  forgetMemory,
  getMemoryProfile,
  setMemorySpecialty,
  type MemoryProfile,
} from "@/lib/api";

export function ProfilePanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [profile, setProfile] = useState<MemoryProfile | null>(null);
  const [specialty, setSpecialty] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let active = true;
    getMemoryProfile()
      .then((nextProfile) => {
        if (!active) return;
        setProfile(nextProfile);
        setSpecialty(nextProfile.specialty ?? "");
        setStatus("ready");
      })
      .catch(() => active && setStatus("error"));
    return () => {
      active = false;
    };
  }, [refreshKey]);

  async function saveSpecialty(event: React.FormEvent) {
    event.preventDefault();
    await setMemorySpecialty(specialty.trim());
    setProfile(await getMemoryProfile());
  }

  async function resetProfile() {
    if (!window.confirm("Forget this demo profile and start cold?")) return;
    await forgetMemory();
    const nextProfile = await getMemoryProfile();
    setProfile(nextProfile);
    setSpecialty(nextProfile.specialty ?? "");
  }

  return (
    <aside className="glass-panel h-fit p-5 lg:sticky lg:top-6">
      <details open>
        <summary className="cursor-pointer font-body font-semibold text-ink">EverMind profile</summary>
        {status === "loading" && <p className="mt-4 font-body text-sm text-mist">Loading memory…</p>}
        {status === "error" && <p className="mt-4 font-body text-sm text-accent-pink">Memory is unavailable.</p>}
        {profile && status === "ready" && (
          <div className="mt-5 grid gap-5">
            <form onSubmit={saveSpecialty} className="grid gap-2">
              <label htmlFor="memory-specialty" className="eyebrow">Specialty</label>
              <div className="flex gap-2">
                <input
                  id="memory-specialty"
                  value={specialty}
                  onChange={(event) => setSpecialty(event.target.value)}
                  placeholder="e.g. nuclear medicine"
                  className="min-w-0 flex-1 rounded-xl border border-line bg-void-2 px-3 py-2 font-body text-sm text-ink outline-none focus:border-line-bright"
                />
                <button className="rounded-xl border border-line-bright px-3 font-body text-sm text-paper hover:text-ink">
                  Save
                </button>
              </div>
            </form>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-void-2/50 p-3">
                <p className="font-data text-xl text-ink">{profile.query_count}</p>
                <p className="font-body text-xs text-mist">Queries</p>
              </div>
              <div className="rounded-xl bg-void-2/50 p-3">
                <p className="font-data text-xl text-ink">{profile.seen_pmid_count}</p>
                <p className="font-body text-xs text-mist">Papers seen</p>
              </div>
            </div>

            <div>
              <p className="eyebrow mb-2">Conditions explored</p>
              <div className="flex flex-wrap gap-2">
                {profile.conditions_explored.length ? profile.conditions_explored.map((condition) => (
                  <span key={condition} className="rounded-full bg-accent-purple/10 px-3 py-1 font-body text-xs text-paper">
                    {condition}
                  </span>
                )) : <span className="font-body text-sm text-mist">None yet</span>}
              </div>
            </div>

            <div>
              <p className="eyebrow mb-2">Distilled context</p>
              <blockquote className="border-l-2 border-rare pl-4 font-body text-sm italic leading-relaxed text-paper">
                {profile.distilled_context || "No context distilled yet. Run a few personalized queries."}
              </blockquote>
            </div>

            <button
              type="button"
              onClick={resetProfile}
              className="justify-self-start font-body text-xs text-mist underline hover:text-accent-pink"
            >
              Forget profile
            </button>
          </div>
        )}
      </details>
    </aside>
  );
}
