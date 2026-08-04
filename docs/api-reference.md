---
title: API Reference
---

# API Reference

This page documents the live FastAPI route table as of the current build. All routes are served from `http://localhost:8000` by default in local development.

## Overview

CORS is restricted to the `FRONTEND_ORIGIN` environment variable, which defaults to `http://localhost:3000`. For the full shape definitions of nested types like `CitationOut`, `TraceEntryOut`, and other response objects, refer to the [Data Model: API Schemas](/data-model-schemas) page.

## Endpoints

### `GET /health`

Simple, publicly accessible health check.

Request:
```json
GET /health
```

Response:
```json
{
  "status": "ok"
}
```

### `POST /query`

Main entry point for querying rare findings across the corpus. Rate limited to 10 requests per minute per client.

Request:
```json
{
  "query": "string (1-500 characters)"
}
```

Response:
```json
{
  "summary_text": "string",
  "citations": [
    {
      "marker": "[1]",
      "pmid": "string",
      "title": "string",
      "condition": "string"
    }
  ],
  "trace": [
    {
      "iteration": 1,
      "retrieved_pmids": ["string"],
      "relevant": true,
      "confidence": 0.85,
      "note": "string",
      "relevant_count": 5,
      "total_count": 12
    }
  ],
  "low_confidence": false,
  "degraded": false,
  "no_match": false,
  "suggested_conditions": [
    {
      "name": "string",
      "paper_count": 42
    }
  ],
  "flagged_claims": [
    {}
  ],
  "case_context": {
    "condition_name": "string",
    "rarity": "string",
    "region_literature": "string",
    "atlas_label": "string",
    "corpus_paper_count": 150,
    "imaging_findings": "string or null",
    "teaching_point": "string or null"
  },
  "differential": [
    {
      "condition_name": "string",
      "marker": "[2]",
      "pmid": "string"
    }
  ]
}
```

**Behavior notes:**
- `degraded: true` indicates the underlying LLM call failed after retries; the frontend should display a degraded-state UI and treat `summary_text` as unverified.
- `low_confidence: true` means the search loop's relevance check did not strongly confirm a match; `summary_text` is still usable but will be prefixed with a disclaimer sentence.
- `no_match: true` means the search loop found no papers surviving the relevance check for this query; `suggested_conditions` will contain up to 3 nearby conditions in the corpus as alternatives.
- `case_context` is only populated when the summary call succeeds (not `degraded`).
- Differential items list alternate conditions the model proposed and independently verified against the cited abstract.

### `POST /query/stream`

Streaming variant of `/query` returning server-sent events instead of a single JSON response. Same request body and rate limit (10 per minute) as `POST /query`.

Request:
```json
{
  "query": "string (1-500 characters)"
}
```

Response (as `text/event-stream`):
```
data: {"type": "stage", "stage": "hyde_expand", "iteration": 1}

data: {"type": "stage", "stage": "retrieval", "iteration": 1}

data: {"type": "stage", "stage": "relevance_check", "iteration": 1}

data: {"type": "done", "result": {...QueryResponse object...}}
```

**Behavior notes:**
- Each frame is one of three types: `stage` events track pipeline progress through stages like `hyde_expand`, `retrieval`, `relevance_check`, `refine_query`, `compress`, `summarize`, or `citation_check` (optionally with an `iteration` counter).
- The final `done` frame contains the complete `QueryResponse` object with the same shape as `POST /query`.
- An `error` frame will be emitted with a `message` string if an unhandled exception occurs server-side.

### `GET /demo-contrast`

Demonstrates the effect of rarity weighting on retrieval rankings. Returns a fixed comparison for a single demo query and stays freely accessible.

Request:
```json
GET /demo-contrast
```

Response:
```json
{
  "query": "string",
  "naive": [
    {
      "pmid": "string",
      "title": "string",
      "condition": "string",
      "rarity": "string"
    }
  ],
  "weighted": [
    {
      "pmid": "string",
      "title": "string",
      "condition": "string",
      "rarity": "string"
    }
  ],
  "rare_case_pmid": "string"
}
```

**Behavior notes:**
- `naive` shows the top results from the same hybrid BM25 and vector search with the rarity boost multiplier turned off.
- `weighted` shows the same query with the rarity boost multiplier applied, highlighting how rare cases surface higher in the ranking.
- Useful for educational and UI demonstration purposes.

### `GET /conditions`

Retrieves the full list of the 14 fixed conditions in the corpus. Freely accessible.

Request:
```json
GET /conditions
```

Response:
```json
[
  {
    "name": "string",
    "rarity": "string",
    "region_literature": "string",
    "atlas_label": "string",
    "overlaps_with": ["string"]
  }
]
```

**Behavior notes:**
- Each condition object includes the brain atlas label used for regional visualization and a list of related conditions that share similar anatomical regions.

### `GET /atlas`

Returns a self-contained interactive HTML page showing the default Harvard-Oxford cortical atlas in its default, unhighlighted view. Rate limited to 20 requests per minute.

Request:
```json
GET /atlas
```

Response:
```html
<!DOCTYPE html>
<html>
  <head>
    <title>Brain Atlas</title>
    <!-- nilearn-rendered interactive atlas view -->
  </head>
  <body>
    <!-- interactive atlas widget -->
  </body>
</html>
```

**Behavior notes:**
- The response is a self-contained `text/html` page with embedded JavaScript; all assets are inlined.
- On any internal error, returns a plain-language fallback HTML body (status 200, not an error status) with the text "Atlas view unavailable" and the standing disclaimer: "Location reference from literature, not a diagnostic read."
- Always includes the disclaimer that location markers reflect literature descriptions, not clinical diagnosis.

### `GET /atlas/query`

Returns an interactive atlas page with the anatomical regions for every condition cited in a query's result highlighted together, each in its own color. Rate limited to 20 requests per minute. Built by `getAtlasQueryUrl()` in `frontend/src/lib/api.ts`, called once a query result's citations resolve to a deduped set of condition names.

Request:
```json
GET /atlas/query?conditions=Scalp%20angiosarcoma,Primary%20angiitis%20of%20CNS
```

Response:
```html
<!DOCTYPE html>
<html>
  <head>
    <title>Brain Atlas</title>
    <!-- nilearn-rendered atlas with one highlighted region per cited condition -->
  </head>
  <body>
    <!-- interactive atlas widget with per-region hover text -->
  </body>
</html>
```

**Behavior notes:**
- `conditions` is a comma-separated, URL-encoded list of condition names; each is matched against the known condition list and resolved to an anatomical region.
- Results for the same set of conditions are cached in memory (keyed by the sorted, deduplicated region set) so repeated views of the same result don't re-render the atlas.
- If no condition in the list resolves to a region, or the parameter is empty, falls back to the same default view as `GET /atlas`.
- If every resolved region is subcortical or midbrain (which the cortical surface render cannot show), falls back to the same default view as `GET /atlas` rather than rendering an all-background scene.
- On any internal error, returns the same fallback body as `GET /atlas` (status 200, not an error) with the text "Atlas view unavailable" and the standing disclaimer.
- Always includes the disclaimer that location markers reflect literature descriptions, not clinical diagnosis.

### `GET /atlas/{condition_name}`

Returns an interactive atlas page with the anatomical region associated with the given condition highlighted in orange (#FF5A2B). Rate limited to 20 requests per minute.

Request:
```json
GET /atlas/Scalp%20angiosarcoma
```

Response:
```html
<!DOCTYPE html>
<html>
  <head>
    <title>Brain Atlas: Condition Name</title>
    <!-- nilearn-rendered atlas with highlighted region -->
  </head>
  <body>
    <!-- interactive atlas widget with hover text -->
  </body>
</html>
```

**Behavior notes:**
- `condition_name` is URL-encoded and matched against the known condition list (case-sensitive).
- The highlighted region comes from the condition's `atlas_label` field and is drawn from the Harvard-Oxford cortical or subcortical atlas.
- If the condition name is unrecognized or the region cannot be located in either atlas, returns the same fallback body as `GET /atlas` (status 200, not an error) with the text "Atlas view unavailable" and the standing disclaimer.
- Hover text on the highlighted region displays the condition name and anatomical location.
- The response is self-contained with all assets inlined.
- Always includes the disclaimer that the location is a reference from literature, not a diagnostic interpretation.

## Related Documentation

- [Data Model: API Schemas](/data-model-schemas): full shape definitions for `CitationOut`, `TraceEntryOut`, and other nested response objects
- [Architecture](/architecture): request flow behind these routes
- [LLM Egress Paths](/architecture-llm-paths): reliability behavior (retries, timeouts, degraded state) for the LLM calls behind these routes
