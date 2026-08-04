---
title: "Data Model: Corpus Records"
---

# Data Model: Corpus Records

NeuLitTrace's corpus is a fixed collection of 329 papers spanning 14 conditions (10 rare, 4 common), sourced from PubMed. The corpus stays fixed for the duration of a query.

<img src="/diagrams/data-model.svg" alt="NeuLitTrace data model diagram" style="width:100%; max-width:1300px; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Overview

This page documents the two record types that make up the corpus itself: `Condition` and `Paper`. A `Condition` defines a diagnosis and its rarity classification; the corpus contains many `Paper` records, each linked to a condition by string matching on `Condition.name`. For the records produced per-query (search loop trace, summary, API response), see [Data Model: API Schemas](/data-model-schemas).

## Record Types

### Condition

A `Condition` represents one diagnosis in the corpus scope. Each condition defines its own PubMed search strategy, expected brain regions, and rarity classification.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Canonical condition name, e.g. "Scalp angiosarcoma" |
| `rarity` | string | Either "rare" or "common" |
| `pubmed_query` | string | Search query used to retrieve initial candidate papers for this condition |
| `region_literature` | string | Plain-language description of the typical brain or imaging region associated with this condition |
| `atlas_label` | string | Comma-separated atlas region labels (from Harvard-Oxford), used for the 3D viewer |
| `target_count` | integer | Desired number of papers to retrieve during corpus construction |
| `overlaps_with` | list of strings | Condition names that can be radiologically confused with this condition, for differential-diagnosis flagging (defaults to empty) |

### Paper

A `Paper` is one record in the corpus. Each paper is linked to exactly one condition via its `condition` field (string matching, not a foreign key ID). The paper data comes from PubMed metadata and includes full abstract text for summary generation.

| Field | Type | Description |
|-------|------|-------------|
| `pmid` | string | PubMed identifier, e.g. "40902156" |
| `title` | string | Paper title from PubMed |
| `abstract` | string | Full abstract text; used as primary content for LLM summarization |
| `condition` | string | Condition name this paper belongs to; must match a condition's `name` field exactly |
| `rarity` | string | Inherited from the condition; "rare" or "common" |
| `region_literature` | string | Inherited from the condition |
| `atlas_label` | string | Inherited from the condition |
| `overlaps_with` | list of strings | Inherited from the condition; candidate conditions for differential diagnosis |

## Extending the Corpus

The 14-condition scope was set deliberately for this build to keep retrieval quality and evaluation numbers verifiable end to end. Adding a condition is a small, mechanical change, since the corpus is fetched automatically rather than hand-curated:

1. Add one entry to `CONDITIONS` in `backend/app/corpus/conditions.py`: a name, rarity, a PubMed search query, the literature-described brain region, a matching Harvard-Oxford atlas label, and a target paper count. This is the only step that takes real judgment, since the atlas label has to match a real Harvard-Oxford region name for the brain visualization to be accurate.
2. Run `python -m backend.app.corpus.build_corpus`. It fetches the abstracts from PubMed's E-utilities API automatically and rewrites `corpus.json`, no manual data entry required.
3. Bump the condition count in `backend/tests/test_corpus_coverage.py`, the data-integrity check for corpus size.

No schema changes or pipeline rewrite required. The near-term path to a larger corpus is adding more entries to `CONDITIONS`, and extending the fetch beyond PubMed to Orphanet for rare-disease-specific literature a PubMed query alone may miss.

## Related Documentation

- [Data Model: API Schemas](/data-model-schemas): records produced per query from these corpus records
- [API Reference](/api-reference): full request/response contract for each route that carries these records
- [Architecture](/architecture): where each stage of the data flow runs in the system
