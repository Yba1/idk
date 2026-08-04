import json
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"


def load_corpus():
    return json.loads(CORPUS_PATH.read_text())


def test_corpus_has_papers_for_every_condition():
    corpus = load_corpus()
    conditions_present = {paper["condition"] for paper in corpus}
    assert len(conditions_present) == 14, f"only {len(conditions_present)} conditions have papers"


def test_corpus_has_both_rare_and_common_papers():
    corpus = load_corpus()
    rarities = {paper["rarity"] for paper in corpus}
    assert rarities == {"rare", "common"}


def test_corpus_covers_flagship_demo_condition():
    corpus = load_corpus()
    scalp_angiosarcoma = [p for p in corpus if p["condition"] == "Scalp angiosarcoma"]
    alzheimers = [p for p in corpus if p["condition"] == "Alzheimer's disease probable typical FDG-PET pattern"]
    assert len(scalp_angiosarcoma) >= 3, "need enough scalp angiosarcoma papers for the naive-vs-rarity demo contrast"
    assert len(alzheimers) >= 3, "need enough common-condition papers to bury the rare case in naive ranking"


def test_corpus_total_within_planned_range():
    corpus = load_corpus()
    assert 150 <= len(corpus) <= 600, f"corpus size {len(corpus)} outside the planned ~200-500 range"
