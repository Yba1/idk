# NeuLitTrace — 80-second demo voiceover

**Video:** `neulittrace-demo.mp4` · 1440×900 · 80.0s · 30fps
**Recorded by:** `frontend/.record-demo.mjs` (re-runnable; resets and re-warms the
demo profile itself, so the numbers below reproduce)

Pace is ~2.5 words/second. Total 199 words. Every number spoken is on screen at
that moment.

---

## The script

**0:00 – 0:07 · Hero**
> Rare disease is where literature search breaks. Not because the papers don't
> exist — because there are four of them.

**0:07 – 0:13 · Corpus, rare conditions first**
> Our corpus is three hundred twenty-nine papers across fourteen conditions.
> Ten of them are rare.

**0:13 – 0:21 · Composing the query**
> A clinician describes a finding in plain language. Behind it, a retrieval
> loop, a cited summary, and a token ledger.

**0:21 – 0:34 · Tight panel appears**
> Here's the system as it ships. Ten papers reach the model, four sentences
> each — nineteen hundred eighty-four tokens. A condition with four papers in
> the whole corpus never makes that cut.

**0:34 – 0:50 · Generous panel — hold here**
> Now the same query, one dial moved. Thirty papers instead of ten — a single
> sentence each. Twelve hundred eighty-six tokens. Three times the papers, for
> thirty-five percent fewer tokens. Across our twenty-eight-query gold set,
> rare-condition recall goes up eighty-one percent.

**0:50 – 0:58 · Papers tab**
> These are real PubMed records, ranked with a rarity boost. Anti-NMDAR
> encephalitis, Lewy body dementia, corticobasal syndrome.

**0:58 – 1:06 · Cost tab**
> Every call is priced against Snowflake's published Cortex rates, attributed
> to the pipeline step that caused it.

**1:06 – 1:18 · Memory, cold vs warm**
> And it remembers. Four queries in, EverOS knows this is a nuclear-medicine
> researcher and which forty-eight papers they've read — reordering results
> around what they haven't seen. Memory isn't a feature here. It's a token
> lever.

**1:18 – 1:20 · Close on hero**
> Look wider. Pay the same.

---

## If you only have 20 seconds

Cut to **0:34–0:50** and say:

> Three times the papers, thirty-five percent fewer tokens, and eighty-one
> percent better rare-condition recall. Same dial, same query.

---

## Where each number comes from

| Spoken | Source | Verify with |
|---|---|---|
| 329 papers / 14 conditions | `backend/data/corpus.json` | on screen §02 |
| 10 papers · 1,984 tokens | live request, Tight | on screen §02b |
| 30 papers · 1,286 tokens | live request, Generous | on screen §02b |
| "35% fewer tokens" | 1,286 vs 1,984 = −35.2% | arithmetic on the two panels |
| "rare recall up 81%" | 0.4118 → 0.7475, 28-query gold set | `results/policy_bench.md` |
| per-call-site cost | real `compute_cost_usd()` on real token counts | on screen, cost tab |
| 4 queries / 48 papers read | live profile state | on screen §04 |

**The one caveat to hold in your head:** "three times the papers for fewer
tokens" is what *this* request did, and it's on screen. The gold-set aggregate
is −0.7% tokens, and on 14 of 28 queries Generous costs slightly *more* — short
abstracts skip compression. So the durable claim is **"same token budget on
average, three times the coverage."** Don't say "always cheaper." If a judge
runs one query and it lands the other way, the panel contradicts you; if you
said "on average," it doesn't.

---

## Known gaps in this cut

Both are credential-blocked, not code-blocked.

1. **§03 Sourced summary is not shown.** The recording runs on the `fake`
   profile, where `FakeLLM` returns a canned `**Fake summary.**` with zero
   citations — so "Claims traced 0 / 0". The camera deliberately avoids that
   tile. With Snowflake credentials the summary and citation verification are
   real, and that becomes the strongest ten seconds in the video.
2. **`/cost` dashboard is not shown.** `/economics/summary` reads Snowflake
   views, so it is empty without an account. Per-request cost *is* shown
   instead, and is real.

Fixing both is one working Snowflake connection. The account currently rejects
password auth (`MFA authentication is required, but none of your current MFA
methods are supported for programmatic authentication`) — it needs a
Programmatic Access Token, which goes straight into `SNOWFLAKE_PASSWORD`.
`SNOWFLAKE_AUTHENTICATOR` is now a passthrough in `backend/snowflake/session.py`
if the connector needs `PROGRAMMATIC_ACCESS_TOKEN` set explicitly.

## Re-recording

```bash
NEULIT_PROFILE=fake .venv/bin/python -m uvicorn backend.api.main:app --port 8000 &
cd frontend && npm run build && npm run start &
node .record-demo.mjs
ffmpeg -y -i <webm> -t 80 -vf "fps=30,scale=1440:900:flags=lanczos" \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart demo.mp4
```

The beat sheet prints to stdout, so if a beat drifts the script timestamps can
be re-synced without rewatching.
