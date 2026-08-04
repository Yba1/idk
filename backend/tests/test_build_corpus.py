import json
from unittest.mock import patch
from backend.app.corpus.conditions import Condition
from backend.app.corpus.build_corpus import build_corpus

FAKE_CONDITION = Condition(
    name="Test condition", rarity="rare", pubmed_query="test query",
    region_literature="Test region", atlas_label="Test Atlas Label",
    target_count=2,
)


def test_build_corpus_tags_each_paper_with_condition_metadata(tmp_path):
    with patch("backend.app.corpus.build_corpus.search_pmids", return_value=["1", "2"]), \
         patch("backend.app.corpus.build_corpus.fetch_abstracts",
               return_value=[{"pmid": "1", "title": "T1", "abstract": "A1"},
                             {"pmid": "2", "title": "T2", "abstract": "A2"}]), \
         patch("backend.app.corpus.build_corpus.time.sleep"):
        out_path = tmp_path / "corpus.json"
        result = build_corpus([FAKE_CONDITION], out_path)

    assert len(result) == 2
    assert result[0]["condition"] == "Test condition"
    assert result[0]["rarity"] == "rare"
    assert result[0]["atlas_label"] == "Test Atlas Label"
    saved = json.loads(out_path.read_text())
    assert saved == result
