import { expect, test, type Page } from "@playwright/test";

/* Retrieval-policy toggle, end to end against the real backend on the fake
 * profile. Deliberately unmocked: the whole claim is that the numbers on
 * screen are measured server-side on that request, so asserting against a
 * canned fixture would test nothing worth testing. */

const api = "http://localhost:8000";
const query = "corticobasal syndrome frontoparietal cortex PET";

async function run(page: Page, policy: "Default" | "Tight" | "Generous") {
  await page.goto("/");
  await page.getByRole("radio", { name: policy, exact: true }).click();
  await page.getByPlaceholder(/asymmetric parietal/i).fill(query);
  await page.getByRole("button", { name: "Search", exact: true }).click();
}

/** Reads the stat tiles out of the §02b panel. */
async function panelStats(page: Page) {
  const panel = page.getByTestId("policy-panel");
  await expect(panel).toBeVisible({ timeout: 30_000 });
  const num = async (id: string) =>
    Number((await page.getByTestId(id).innerText()).replace(/[^\d.]/g, ""));
  return {
    label: await panel.getAttribute("data-policy"),
    papers: await num("policy-papers"),
    sentences: await num("policy-sentences"),
    tokens: await num("policy-tokens"),
    pct: await num("policy-reduction"),
  };
}

test.describe.configure({ mode: "serial" });

test("default path sends no policy and renders no policy panel", async ({ page }) => {
  const bodies: string[] = [];
  await page.route(`${api}/query/stream`, async (route) => {
    bodies.push(route.request().postData() ?? "");
    await route.continue();
  });

  await run(page, "Default");
  await expect(
    page.getByRole("heading", { name: /Every sentence carries the paper/i }),
  ).toBeVisible({ timeout: 30_000 });

  // The field must be absent, not null: an absent key keeps the request
  // byte-identical to what every pre-policy caller sent.
  expect(bodies).toHaveLength(1);
  expect(JSON.parse(bodies[0])).not.toHaveProperty("policy");
  await expect(page.getByText("Retrieval breadth ·")).toHaveCount(0);
});

test("generous reports 30 papers and its own measured compression", async ({ page }) => {
  await run(page, "Generous");
  const { papers, pct } = await panelStats(page);

  expect(papers).toBe(30);
  // Measured on this request, not a stored figure -- so assert the shape
  // (heavy compression at one sentence per paper) rather than an exact value.
  expect(pct).toBeGreaterThan(50);
  expect(pct).toBeLessThan(100);
});

test("tight reports 10 papers and compresses less per paper", async ({ page }) => {
  await run(page, "Tight");
  const { papers, pct } = await panelStats(page);

  expect(papers).toBe(10);
  expect(pct).toBeGreaterThan(0);
  // 4 sentences kept vs generous's 1: strictly gentler compression.
  expect(pct).toBeLessThan(50);
});

test("generous puts 3x the papers in the prompt for roughly the same tokens", async ({ page }) => {
  // Two full pipeline runs in one test, and the generous arm compresses 30
  // abstracts rather than 10 -- the default 30s budget is not enough.
  test.setTimeout(120_000);

  await run(page, "Tight");
  const tight = await panelStats(page);

  await run(page, "Generous");
  const generous = await panelStats(page);

  expect(generous.papers).toBe(tight.papers * 3);

  // Iso-cost is a GOLD-SET AGGREGATE (-0.69% over 28 queries), not a per-query
  // guarantee: generous is the more expensive arm on 14 of those 28, ranging
  // 0.795x to 1.382x with a 0.992x median, because compress_abstract refuses
  // to trim abstracts under 3 sentences and a 30-paper set contains more of
  // them. Asserting `<=` here would be asserting a claim the measurement does
  // not support. The 1.5x band is the real per-query envelope plus headroom.
  expect(generous.tokens).toBeLessThan(tight.tokens * 1.5);
});

test("an unknown policy is rejected by the API, not silently defaulted", async ({ request }) => {
  const response = await request.post(`${api}/query`, {
    data: { query, session_id: "pw-policy", user_id: "demo-user", personalize: false, policy: "genrous" },
  });
  expect(response.status()).toBe(422);
  expect(await response.text()).toContain("unknown retrieval policy");
});
