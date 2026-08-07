import { chromium } from "@playwright/test";

/* 80-second scripted demo capture.
 * Every number that appears on screen is produced live by the running app.
 * Timing budget is enforced by `beat()` so the cut lands at 1:20 without
 * needing an edit pass. */

const OUT = "/private/tmp/claude-501/-Users-lakshgoyal-idk/d9c42c58-c045-460a-a825-fa41db36034c/scratchpad/video";
const QUERY = "asymmetric parietal hypometabolism on FDG-PET with progressive apraxia";
const t0 = Date.now();
const at = () => ((Date.now() - t0) / 1000).toFixed(1);
const marks = [];

function beat(label) {
  marks.push(`${at().padStart(5)}s  ${label}`);
  console.log(`${at().padStart(5)}s  ${label}`);
}

// Deterministic starting state: clear the demo profile, set a specialty, and
// warm it with two real queries so §04 has genuine history to show. Doing this
// in-script (not by hand beforehand) means the recording is reproducible.
const API = "http://localhost:8000";
await fetch(`${API}/memory/forget`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ user_id: "demo-user" }),
});
await fetch(`${API}/memory/specialty`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ user_id: "demo-user", specialty: "Nuclear medicine" }),
});
for (const q of [
  "scalp angiosarcoma FDG-PET case report",
  "progressive supranuclear palsy midbrain hypometabolism",
]) {
  await fetch(`${API}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: q,
      session_id: "demo-warm",
      user_id: "demo-user",
      personalize: true,
    }),
  });
}

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
  deviceScaleFactor: 1,
});
const page = await ctx.newPage();

const wait = (ms) => page.waitForTimeout(ms);

async function smoothTo(selectorOrY) {
  if (typeof selectorOrY === "number") {
    await page.evaluate((y) => window.scrollTo({ top: y, behavior: "smooth" }), selectorOrY);
  } else {
    await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }, selectorOrY);
  }
}

async function runQuery(policyLabel) {
  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  if (policyLabel) {
    await page.getByRole("radio", { name: policyLabel, exact: true }).click();
  }
  await page.getByPlaceholder(/asymmetric parietal/i).fill(QUERY);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page
    .getByRole("heading", { name: /Every sentence carries the paper/i })
    .waitFor({ state: "visible", timeout: 90000 });
}

// ── 0:00 ─ Hero. The thesis. ────────────────────────────────────────────
beat("hero");
await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
await wait(5200);

// ── 0:05 ─ The corpus: rare conditions first. ───────────────────────────
beat("corpus / rarity ladder");
await smoothTo("#query");
await wait(1200);
await page.evaluate(() => window.scrollBy({ top: 900, behavior: "smooth" }));
await wait(4200);

// ── 0:11 ─ Ask the question. ────────────────────────────────────────────
beat("compose query");
await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
await smoothTo("#query");
await wait(900);
await page.getByPlaceholder(/asymmetric parietal/i).click();
await page.getByPlaceholder(/asymmetric parietal/i).type(QUERY, { delay: 38 });
await wait(1400);

// ── 0:19 ─ Tight: today's system. ───────────────────────────────────────
beat("run TIGHT");
await page.getByRole("radio", { name: "Tight", exact: true }).click();
await wait(900);
await page.getByRole("button", { name: "Search", exact: true }).click();
await page
  .getByRole("heading", { name: /Every sentence carries the paper/i })
  .waitFor({ state: "visible", timeout: 90000 });
await wait(1500);

beat("TIGHT panel");
await smoothTo('[data-testid="policy-panel"]');
await wait(9500);

// ── 0:33 ─ Generous: same budget, three times the papers. ───────────────
beat("run GENEROUS");
await runQuery("Generous");
await wait(1200);
beat("GENEROUS panel");
await smoothTo('[data-testid="policy-panel"]');
await wait(13500);

// ── 0:49 ─ The papers it actually found. ────────────────────────────────
beat("papers tab");
await page.getByRole("tab", { name: "Papers", exact: true }).click();
await smoothTo('[role="tabpanel"]');
await wait(2000);
await page.evaluate(() => window.scrollBy({ top: 420, behavior: "smooth" }));
await wait(5500);

// ── 0:57 ─ What it cost, per pipeline step. ─────────────────────────────
beat("cost tab");
await page.getByRole("tab", { name: "This answer's cost", exact: true }).click();
await wait(600);
// Centre the per-call-site bars. Deliberately does NOT scroll up into the
// stat row: on the fake profile FakeLLM returns a canned summary with no
// citations, so "Claims traced 0 / 0" sits there and says nothing true about
// the product. That tile is real once Snowflake credentials are in place.
await page.evaluate(() => {
  const el = [...document.querySelectorAll("*")].find((e) =>
    /^relevance_check$/.test((e.textContent || "").trim()),
  );
  if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
});
await wait(7000);

// ── 1:05 ─ Memory. ──────────────────────────────────────────────────────
beat("memory panel");
await page.evaluate(() => {
  const h = [...document.querySelectorAll("h2")].find((e) =>
    /What it remembers/i.test(e.textContent || ""),
  );
  if (h) h.scrollIntoView({ behavior: "smooth", block: "start" });
});
await wait(4500);
await page.evaluate(() => window.scrollBy({ top: 520, behavior: "smooth" }));
await wait(7000);

// ── 1:17 ─ Close on the hero. ───────────────────────────────────────────
beat("close");
await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
await wait(3200);

beat("END");
await ctx.close();
await browser.close();

console.log("\n--- beat sheet ---\n" + marks.join("\n"));
