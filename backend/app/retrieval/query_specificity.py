"""Deterministic query-specificity check (no LLM call): flags queries that
name none of modality, symptom/sign, or brain region, so the UI can nudge
for more detail without blocking the best-match result already found.
"""
from __future__ import annotations

import re

MODALITY_TERMS = [
    "pet", "fdg", "fdg-pet", "spect", "dat-spect", "datscan", "mri", "fmri",
    "ct", "dti", "pib", "amyloid pet", "tau pet", "eeg",
]

REGION_TERMS = [
    "parietal", "temporal", "frontal", "occipital", "hippocamp", "basal ganglia",
    "thalamus", "cerebellum", "cerebellar", "brainstem", "striatum", "putamen",
    "caudate", "substantia nigra", "cortex", "cortical", "subcortical", "insula",
    "precuneus", "cingulate", "amygdala", "midbrain", "pons",
]

SYMPTOM_TERMS = [
    "apraxia", "aphasia", "ataxia", "tremor", "rigidity", "bradykinesia",
    "dementia", "hypometabolism", "hypermetabolism", "dysarthria", "dysphagia",
    "dystonia", "myoclonus", "seizure", "memory loss", "hallucination",
    "parkinsonism", "dysautonomia", "hyperdensity", "hypodensity", "atrophy",
    "gait disturbance", "cognitive decline", "neuropathy", "spasticity",
]

_ALL_TERMS = MODALITY_TERMS + REGION_TERMS + SYMPTOM_TERMS


def is_query_too_generic(query: str) -> bool:
    normalized = query.lower()
    return not any(re.search(rf"\b{re.escape(term)}", normalized) for term in _ALL_TERMS)


def build_example_query(region_literature: str) -> str:
    """Turn a condition's region_literature into a worked example query,
    grounded in the same literature-derived region text already shown in
    the case-context panel (not a newly invented clinical claim).
    """
    region = region_literature.split(";")[0].split(",")[0].strip()
    if region and region[0].isupper() and not region.isupper():
        region = region[0].lower() + region[1:]
    return f"{region} hypometabolism on FDG-PET with a relevant clinical sign"
