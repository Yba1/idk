---
title: "Data Model: API Schemas"
---

# Data Model: API Schemas

These records flow through a single query: from the search loop, through summary generation, into the API response returned to the frontend. For the fixed corpus records they draw from (`Condition`, `Paper`), see [Data Model: Corpus Records](/data-model-corpus).

## Overview

1. When a query arrives, the search loop retrieves papers and produces `LoopTraceEntry` records (one per iteration).
2. Retrieved papers are passed to summary generation, which produces a `SourcedSummary`.
3. The `SourcedSummary` is mapped to a `QueryResponse` (along with trace and context data), which is returned to the frontend.
4. The frontend displays the summary, citations, differential diagnoses, and loop trace to the user.

## Record Types

The search loop runs up to two iterations to retrieve papers relevant to a given query. Each iteration produces a trace entry describing what was retrieved and whether it passed the relevance check.

### LoopTraceEntry

One `LoopTraceEntry` captures the result of a single search loop iteration. Multiple entries (typically up to 2) appear together in the final API response, allowing the frontend to visualize the retrieval process.

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | integer | Iteration number (1-indexed) |
| `retrieved_pmids` | list of strings | PMIDs retrieved in this iteration before relevance filtering |
| `relevant` | boolean | Whether the LLM relevance check confirmed this iteration's papers matched the query |
| `confidence` | float | Relevance confidence score (0.0 to 1.0); used to flag low-confidence summaries |
| `note` | string | Plain-text note describing the iteration's outcome or strategy |
| `relevant_count` | integer | Number of papers deemed relevant by the relevance check (defaults to 0) |
| `total_count` | integer | Total number of papers in this iteration before relevance filtering (defaults to 0) |

Once the search loop completes, the retrieved papers are fed into summary generation, which produces a `SourcedSummary`. This internal record is then shaped into the API response schemas that the frontend consumes.

### SourcedSummary (internal)

A `SourcedSummary` is generated from the list of papers the search loop returned. It serves as the internal interchange point between summary generation and the API handler, and its fields map directly onto `QueryResponse` fields.

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | The final summary text, including any prepended disclaimers (low-confidence, sparse coverage) |
| `citations` | list of dicts | List of citations in order; each has `marker` ("[1]", "[2]", ...), `pmid`, and `title`. Positionally indexed to the papers list: `citations[i]` corresponds to `papers[i]` |
| `raw_text` | string | The summary text before any disclaimer was prepended (defaults to empty string) |
| `degraded` | boolean | Whether the LLM call failed or timed out, meaning no usable summary was produced |
| `original_tokens` | integer | Token count of the raw abstracts before compression (defaults to 0) |
| `compressed_tokens` | integer | Token count after Paritok compression (defaults to 0) |
| `imaging_findings` | string or null | Brief description of imaging findings and uptake pattern, extracted from the LLM's JSON response (null if not stated in abstracts) |
| `teaching_point` | string or null | Closing clinical insight (null if not included by the LLM; the prompt also instructs the LLM to null this when imaging_findings is null, but that pairing isn't enforced in code) |
| `differential_candidates` | list of dicts | Differential diagnoses extracted from the LLM's JSON response; each has `condition_name` and `marker` (the citation it references). Limited to 0-3 items (defaults to empty) |

### QueryResponse (API response)

`QueryResponse` is the top-level Pydantic model returned by `POST /query`. It includes the summary, citations, trace, and metadata about the search and generation process.

| Field | Type | Description |
|-------|------|-------------|
| `summary_text` | string | The final summary text (matches `SourcedSummary.text`) |
| `citations` | list of CitationOut | Numbered citations referenced in the summary |
| `trace` | list of TraceEntryOut | Search loop iteration records, allowing the frontend to show retrieval flow |
| `low_confidence` | boolean | Whether the relevance check's confidence was below the passing threshold; summarization proceeded anyway |
| `degraded` | boolean | Whether the LLM summarization call failed, meaning the summary is empty and unreliable |
| `no_match` | boolean | Whether no papers matched the query at all; defaults to false |
| `suggested_conditions` | list of SuggestedConditionOut | Alternative conditions to try when `no_match` is true; defaults to empty |
| `flagged_claims` | list of dicts | Per-claim citation verification results for every cited sentence, including ones marked `supported`; used by the frontend to surface unsupported/uncited/invalid-marker claims. Defaults to empty |
| `case_context` | CaseContextOut or null | Contextual information about the condition the papers address (null if degraded) |
| `differential` | list of DifferentialItemOut | Differential diagnoses with citations, extracted from the summary; defaults to empty |

### CitationOut

Represents one citation in the summary.

| Field | Type | Description |
|-------|------|-------------|
| `marker` | string | Citation marker, e.g. "[1]", "[2]" |
| `pmid` | string | PubMed identifier |
| `title` | string | Paper title |
| `condition` | string | Condition name this paper belongs to |

### TraceEntryOut

Mirrors `LoopTraceEntry` 1:1 at the API boundary.

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | integer | Iteration number (1-indexed) |
| `retrieved_pmids` | list of strings | PMIDs retrieved in this iteration |
| `relevant` | boolean | Whether this iteration passed the relevance check |
| `confidence` | float | Relevance confidence score |
| `note` | string | Plain-text note on the iteration's outcome |
| `relevant_count` | integer | Number of papers deemed relevant (defaults to 0) |
| `total_count` | integer | Total papers in this iteration before filtering (defaults to 0) |

### SuggestedConditionOut

Returned in `suggested_conditions` when the search failed entirely, offering nearby conditions in the corpus to try instead.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Condition name |
| `paper_count` | integer | Number of papers in the corpus for this condition |

### CaseContextOut

Clinical context extracted from the best-matching paper's condition record. Populated when summarization succeeds.

| Field | Type | Description |
|-------|------|-------------|
| `condition_name` | string | The condition name |
| `rarity` | string | "rare" or "common" |
| `region_literature` | string | Plain-language description of typical imaging regions |
| `atlas_label` | string | Atlas region labels for the 3D viewer |
| `corpus_paper_count` | integer | Number of papers in the corpus for this condition |
| `imaging_findings` | string or null | Imaging findings summary (matches `SourcedSummary.imaging_findings`) |
| `teaching_point` | string or null | Clinical teaching point (matches `SourcedSummary.teaching_point`) |

### DifferentialItemOut

A differential diagnosis extracted from the summary, with the citation supporting it.

| Field | Type | Description |
|-------|------|-------------|
| `condition_name` | string | Alternate condition name |
| `marker` | string | Citation marker, e.g. "[2]" |
| `pmid` | string | PubMed identifier of the supporting paper |

## Related Documentation

- [Data Model: Corpus Records](/data-model-corpus): the fixed `Condition` and `Paper` records these schemas are built from
- [API Reference](/api-reference): full request/response contract for each route that carries these records
- [Search Loop](/search-loop): how `LoopTraceEntry` records are produced
