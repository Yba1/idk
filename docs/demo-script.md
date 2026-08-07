# NeuLitTrace — 80-second demo voiceover

**Video:** `neulittrace-demo.mp4` · 1440×900 · 79.9s · 30fps
**Recorder:** `frontend/tests/record-demo.mjs` — resets and re-warms the demo
profile over the API before capture, so the numbers below reproduce.

Pace ~2.5 words/second. 201 words. Every number spoken is on screen at that
moment.

---

## The script

**0:00 – 0:07 · Hero**
> Rare disease is where literature search breaks. Not because the papers don't
> exist — because there are four of them.

**0:07 – 0:13 · Corpus, rare conditions first**
> Three hundred twenty-nine papers, fourteen conditions. Ten of them rare.

**0:13 – 0:22 · Composing the query**
> A clinician describes a finding in plain language. Behind it: a retrieval
> loop, a cited summary, and a token ledger.

**0:22 – 0:33 · Tight panel**
> Here's the system as it ships. Ten papers reach the model, four sentences
> each — nineteen eighty-four tokens. A condition with four papers in the whole
> corpus never makes that cut.

**0:33 – 0:47 · Generous panel — the money shot, hold here**
> Same query. One dial moved. Thirty papers instead of ten, one sentence each —
> twelve eighty-six tokens. Three times the papers, thirty-five percent fewer
> tokens. Across our twenty-eight-query gold set, rare-condition recall goes up
> eighty-one percent.

**0:47 – 0:55 · Sourced summary**
> Every sentence carries the paper it came from. Four claims, four citations,
> each one verified against its source abstract before you see it.

**0:55 – 1:01 · Papers**
> Twenty-nine of thirty candidates were rare-weighted. Anti-NMDAR encephalitis,
> Lewy body dementia, frontotemporal dementia.

**1:01 – 1:06 · Cost**
> One and a half cents, priced against Snowflake's published Cortex rates and
> attributed to the pipeline step that caused it.

**1:06 – 1:15 · Memory**
> And it remembers. EverOS knows this is a nuclear-medicine researcher and what
> they've already read — reordering results around what's new. Memory isn't a
> feature here. It's a token lever.

**1:15 – 1:20 · Close**
> Look wider. Pay the same.

---

## If you only have 20 seconds

Cut to **0:33–0:47**:

> Three times the papers, thirty-five percent fewer tokens, eighty-one percent
> better rare-condition recall. Same dial, same query.

---

## Where each number comes from

| Spoken | Source |
|---|---|
| 329 papers / 14 conditions | `backend/data/corpus.json`, on screen §02 |
| 10 papers · 1,984 tokens | live request, Tight — on screen §02b |
| 30 papers · 1,286 tokens | live request, Generous — on screen §02b |
| "35% fewer tokens" | 1,286 vs 1,984 = −35.2% |
| "rare recall up 81%" | 0.4118 → 0.7475, 28-query gold set — `results/policy_bench.md` |
| "4 claims, 4 citations, verified" | on screen: Claims traced 4 / 4, All verified |
| "29 of 30 rare-weighted" | on screen, §03 stat row |
| "one and a half cents" | on screen: Answer cost $0.0142 |

**The one caveat to hold in your head:** "three times the papers for fewer
tokens" is what *this* request did, and it's on screen. The gold-set aggregate
is −0.7% tokens, and on 14 of 28 queries Generous costs slightly *more* — short
abstracts skip compression. So the durable claim is **"same token budget on
average, three times the coverage."** Don't say "always cheaper": if a judge
runs one query and it lands the other way, the panel contradicts you.

---

## What generated the summary in this cut

The recording runs on the `fake` profile — no Snowflake credentials on this
machine (the account rejects password auth; it needs a Programmatic Access
Token).

On that profile the `summary` and `citation_check` call sites are served by a
**deterministic local extractor** in `backend/contracts/fakes.py`, not a
language model. It parses the numbered abstracts out of the prompt the pipeline
actually sent, picks the sentence from each with the highest query overlap, and
emits it under that paper's real `[N]` marker. The verifier then checks each
claim's wording back against the abstract it cites.

So every sentence on screen is a **verbatim sentence from a real PubMed
abstract that was really retrieved for that query**, and every citation resolves
to that paper's real PMID. Nothing is invented. But it is extraction, not
generation — with credentials configured this call site goes to Cortex COMPLETE
and none of that code runs.

**If a judge asks "what wrote that summary?"** — say exactly that: *"On the
offline profile it's an extractive stand-in over the real retrieved abstracts;
with our Snowflake account connected it's Cortex."* That answer is short, true,
and costs you nothing.

Still not shown: the `/cost` dashboard, because `/economics/summary` reads
Snowflake views and is empty without an account. Per-request cost is shown
instead, and is real.

---

## Re-recording

```bash
NEULIT_PROFILE=fake .venv/bin/python -m uvicorn backend.api.main:app --port 8000 &
cd frontend && npm run build && npm run start &
node tests/record-demo.mjs          # prints a beat sheet
ffmpeg -y -i <webm> -vf "fps=30,scale=1440:900:flags=lanczos" \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart demo.mp4
```

The beat sheet prints to stdout, so if a beat drifts the timestamps above can be
re-synced without rewatching.
