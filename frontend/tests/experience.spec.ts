import { expect, test, type Page, type Route } from "@playwright/test";

const api = "http://localhost:8000";
const query = "asymmetric parietal hypometabolism on FDG-PET";

function queryResult({ applied = true, seenFiltered = 0 } = {}) {
  return {
    request_id: "req-demo",
    summary_markdown: "The finding is reported in a rare corticobasal presentation [1].",
    citations: [{ index: 1, pmid: "12345678", supported: true, note: null }],
    papers: [{
      paper: {
        pmid: "12345678",
        title: "Asymmetric metabolism in corticobasal syndrome",
        abstract: "A focused case report.",
        journal: "Neurology",
        year: 2025,
        condition: "Corticobasal syndrome",
        isRare: true,
        url: "https://pubmed.ncbi.nlm.nih.gov/12345678/",
      },
      score: 0.92,
      lexicalScore: 0.8,
      semanticScore: 0.9,
      rarityMultiplier: 1.3,
      memoryMultiplier: applied ? 1.1 : 1,
    }],
    trace: [{
      iteration: 1,
      retrieved_pmids: ["12345678"],
      relevant: true,
      confidence: 0.92,
      note: "Relevant imaging pattern",
      memory_applied: applied,
      seen_filtered: seenFiltered,
    }],
    region: null,
    memory: {
      applied,
      seen_filtered: seenFiltered,
      profile_used: applied,
      distilled_context: "Tracks asymmetric cortical metabolism.",
    },
    cost: {
      total_tokens: 840,
      cost_usd: 0.0012,
      by_call_site: { summary: { tokens: 840, cost_usd: 0.0012 } },
    },
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function submit(page: Page, text = query) {
  await page.getByPlaceholder(/asymmetric parietal/i).fill(text);
  await page.getByRole("button", { name: "Search", exact: true }).click();
}

test.describe.configure({ mode: "serial" });

test("fake backend query shows the loader, papers, and request cost", async ({ page }) => {
  await page.route(`${api}/query/stream`, async (route) => {
    if (route.request().method() === "POST") await new Promise((resolve) => setTimeout(resolve, 5200));
    await route.continue();
  });
  await page.goto("/");
  await submit(page);
  // Copy below tracks the trace-light redesign: the prose loader became the
  // terse stage rail in progress-timeline.tsx, and §03's heading changed.
  await expect(page.getByText("Expand", { exact: true })).toBeVisible();
  await expect(page.getByText("Retrieve", { exact: true })).toBeVisible();
  await expect(page.getByText("Check", { exact: true })).toBeVisible();
  await expect(page.getByText("Summarize", { exact: true })).toBeVisible();
  // This spec deliberately delays the response 5.2s to exercise the loader,
  // so the post-result assertions need more than the 5s default.
  await expect(
    page.getByRole("heading", { name: "Every sentence carries the paper it came from." }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Answer cost")).toBeVisible();
  await page.getByRole("tab", { name: "Papers", exact: true }).click();
  await expect(page.getByText(/^PMID \d+/).first()).toBeVisible();
});

test("fake backend streams the progress stages", async ({ request }) => {
  const response = await request.post(`${api}/query/stream`, {
    data: { query, session_id: "playwright-stages", user_id: "demo-user", personalize: true },
  });
  expect(response.ok()).toBe(true);
  const events = (await response.text())
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => JSON.parse(line.slice(5).trim()));
  const stages = events.filter((event) => event.type === "stage").map((event) => event.stage);
  expect(stages.filter((stage) => stage !== "refine_query")).toEqual([
    "hyde_expand",
    "retrieval",
    "relevance_check",
    "summarize",
    "citation_check",
  ]);
  expect(stages.every((stage) => [
    "hyde_expand", "retrieval", "relevance_check", "refine_query", "summarize", "citation_check",
  ].includes(stage))).toBe(true);
});

test("query citation contract state renders a source link", async ({ page }) => {
  await page.route(`${api}/query/stream`, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "done", result: queryResult() })}\n\n`,
    });
  });
  await page.goto("/");
  await submit(page);
  // The marginal-citation redesign dropped the <aside> wrapper; the Sources
  // block is plain divs now, so scope by the heading instead of the element.
  await expect(page.getByText("Sources", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('a[href*="pubmed.ncbi.nlm.nih.gov"]').first()).toBeVisible();
});

test("fake backend personalization off renders the neutral memory state", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("checkbox", { name: "Personalize with memory" }).uncheck({ force: true });
  await submit(page);
  await expect(page.getByText(/This answer is unpersonalized/)).toBeVisible();
  await page.getByRole("tab", { name: "Papers" }).click();
  await expect(page.getByText("Seen before")).toHaveCount(0);
  await expect(page.getByText(/Builds on your thread/)).toHaveCount(0);
});

test("fake backend makes the same query visibly different when memory is enabled", async ({ page }) => {
  await page.goto("/");
  const personalize = page.getByRole("checkbox", { name: "Personalize with memory" });
  await personalize.uncheck({ force: true });
  await submit(page);
  await page.getByRole("tab", { name: "Papers" }).click();
  const coldPmids = await page.getByText(/^PMID \d+/).allTextContents();

  await personalize.check({ force: true });
  await submit(page);
  await page.getByRole("tab", { name: "Papers" }).click();
  const warmPmids = await page.getByText(/^PMID \d+/).allTextContents();

  expect(coldPmids.length).toBeGreaterThan(0);
  expect(warmPmids).not.toEqual(coldPmids);
});

test("seen-paper filtering banner renders for the contract state", async ({ page }) => {
  await page.route(`${api}/query/stream`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: `data: ${JSON.stringify({ type: "done", result: queryResult({ seenFiltered: 2 }) })}\n\n`,
    });
  });
  await page.goto("/");
  await submit(page, "seen papers query");
  await expect(page.getByText("2 papers you've already read were filtered out.")).toBeVisible();
});

test("cost route renders four panels and the zero-ledger state", async ({ page }) => {
  // The redesign moved this dashboard from /economy to its own /cost route
  // (§07) and replaced the panel <h2>s with `eyebrow` labels, so these are
  // text assertions rather than role=heading ones.
  await page.goto("/cost");
  await expect(page.getByText("Median cost per query")).toBeVisible();
  await expect(page.getByText("Spend by stage")).toBeVisible();
  await expect(page.getByText("Spend over time")).toBeVisible();
  await expect(page.getByText("Ask the ledger")).toBeVisible();
  await expect(
    page.getByText("Ledger reachable but no priced rows in this window. Cost is unavailable, not zero."),
  ).toBeVisible();
  await expect(page.getByText("which pipeline step is most expensive?")).toBeVisible();
  await page.getByRole("button", { name: "how many calls degraded?" }).click();
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText(/Cortex Analyst is unavailable/)).toBeVisible();
});

test("fake backend forget clears the visible profile", async ({ page, request }) => {
  await request.post(`${api}/query`, {
    data: { query, session_id: "playwright-forget", user_id: "demo-user", personalize: true },
  });
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  await expect(page.getByText("Papers read")).toBeVisible();
  await page.getByRole("button", { name: "Reset profile and start cold" }).click();
  await expect(page.getByText("None yet")).toBeVisible();
  await expect(page.getByText(/No context distilled yet/)).toBeVisible();
});

test("profile panel preserves distilled context verbatim", async ({ page }) => {
  const context = "Focuses on asymmetric cortical metabolism; prefers primary imaging evidence.";
  await page.route(`${api}/memory/profile?*`, (route) => fulfillJson(route, {
    user_id: "demo-user",
    specialty: "Nuclear medicine",
    conditions_explored: ["Corticobasal syndrome"],
    query_count: 4,
    distilled_context: context,
    seen_pmid_count: 12,
  }));
  await page.goto("/");
  await expect(page.getByText(context, { exact: true })).toBeVisible();
});

test("health footer shows four ports including a red failure", async ({ page }) => {
  await page.route(`${api}/health`, (route) => fulfillJson(route, {
    status: "degraded",
    ports: {
      retrieval: { ok: true, detail: "ready" },
      llm: { ok: true, detail: "ready" },
      memory: { ok: false, detail: "down" },
      ledger: { ok: true, detail: "ready" },
    },
  }));
  await page.goto("/");
  const health = page.getByLabel("Backend health");
  await expect(health.locator(":scope > span")).toHaveCount(4);
  // The light redesign dropped the pink failure fill: a down port is now a
  // warn-bordered white dot (health-footer.tsx:31), not a filled colour chip.
  await expect(health.locator('span[title="down"] > span').first()).toHaveClass(/border-warn/);
});
