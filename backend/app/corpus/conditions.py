"""The fixed 14-condition corpus scope from plan/problem_and_research.md's
Corpus Scope table. Do not add conditions here without updating that table
first - it is the source of truth this file transcribes.
"""
from dataclasses import dataclass, field


@dataclass
class Condition:
    name: str
    rarity: str  # "rare" | "common"
    pubmed_query: str
    region_literature: str
    atlas_label: str
    target_count: int
    overlaps_with: list[str] = field(default_factory=list)


CONDITIONS: list[Condition] = [
    Condition("Scalp angiosarcoma", "rare",
              "scalp angiosarcoma AND PET AND case report",
              "Frontoparietal scalp; frontal and parietal cortex involvement",
              "Precentral Gyrus, Postcentral Gyrus", 25),
    Condition("Primary progressive aphasia semantic variant", "rare",
              "semantic variant primary progressive aphasia AND PET AND case report",
              "Anterior temporal lobe; temporal poles",
              "Superior Temporal Gyrus, Middle Temporal Gyrus", 25),
    Condition("Corticobasal syndrome", "rare",
              "corticobasal syndrome AND PET AND case report",
              "Contralateral frontoparietal cortex; superior parietal lobule",
              "Superior Frontal Gyrus, Superior Parietal Lobule", 25),
    Condition("Progressive supranuclear palsy", "rare",
              "progressive supranuclear palsy AND PET AND case report",
              "Midbrain; globus pallidus; frontal lobe",
              "Frontal Medial Cortex; Pallidum (subcortical); Brain-Stem (subcortical)", 25),
    Condition("Frontotemporal dementia", "rare",
              "frontotemporal dementia AND PET AND case report",
              "Anterior temporal cortex; inferior frontal gyrus",
              "Inferior Frontal Gyrus, Superior Temporal Gyrus", 25),
    Condition("Creutzfeldt-Jakob disease", "rare",
              "Creutzfeldt-Jakob disease AND PET AND case report",
              "Parietal-occipital junction; lateral occipital cortex",
              "Lateral Occipital Cortex, Superior Parietal Lobule", 25),
    Condition("Dementia with Lewy bodies", "rare",
              "dementia with Lewy bodies AND PET AND case report",
              "Occipital cortex; parietal regions",
              "Lateral Occipital Cortex, Angular Gyrus", 25),
    Condition("Anti-NMDA receptor encephalitis", "rare",
              "anti-NMDA receptor encephalitis AND PET AND case report",
              "Insular cortex; medial temporal lobes; basal ganglia involvement",
              "Insular Cortex, Superior Temporal Gyrus; Caudate (subcortical)", 25),
    Condition("Primary angiitis of CNS", "rare",
              "primary angiitis of the central nervous system AND PET AND case report",
              "Multiple cortical regions depending on vessel involvement",
              "Middle Cerebral Artery territory (Inferior Frontal Gyrus, Superior Parietal Lobule)", 25),
    Condition("Neurolymphomatosis CNS involvement", "rare",
              "neurolymphomatosis CNS AND PET AND case report",
              "Leptomeningeal involvement; cranial nerves",
              "Cingulate Gyrus (for leptomeningeal surface inflammation)", 25),
    Condition("Alzheimer's disease probable typical FDG-PET pattern", "common",
              "Alzheimer's disease AND FDG-PET",
              "Temporal and parietal regions; medial temporal lobes",
              "Superior Temporal Gyrus, Superior Parietal Lobule", 40,
              overlaps_with=["Primary progressive aphasia semantic variant",
                             "Frontotemporal dementia", "Creutzfeldt-Jakob disease",
                             "Primary angiitis of CNS"]),
    Condition("Temporal lobe epilepsy interictal FDG-PET", "common",
              "temporal lobe epilepsy AND interictal AND FDG-PET",
              "Mesial temporal lobes; lateral temporal cortex",
              "Superior Temporal Gyrus, Middle Temporal Gyrus", 40,
              overlaps_with=["Primary progressive aphasia semantic variant",
                             "Frontotemporal dementia", "Anti-NMDA receptor encephalitis"]),
    Condition("Acute ischemic stroke MCA territory acute phase", "common",
              "acute ischemic stroke AND middle cerebral artery AND PET",
              "Frontal, temporal, and parietal regions (MCA territory)",
              "Inferior Frontal Gyrus, Superior Parietal Lobule", 40,
              overlaps_with=["Frontotemporal dementia", "Corticobasal syndrome",
                             "Creutzfeldt-Jakob disease", "Primary angiitis of CNS"]),
    Condition("Parkinson's disease motor form later stage", "common",
              "Parkinson's disease AND PET AND basal ganglia",
              "Frontal cortex; globus pallidus; basal ganglia",
              "Frontal Medial Cortex, Pallidum (subcortical)", 40,
              overlaps_with=["Progressive supranuclear palsy"]),
]
