from backend.app.retrieval.bm25_index import BM25Index

PAPERS = [
    {"pmid": "1", "title": "Scalp angiosarcoma PET", "abstract": "Focal FDG uptake at scalp tumor site."},
    {"pmid": "2", "title": "Alzheimer's disease FDG-PET", "abstract": "Bilateral temporal parietal hypometabolism."},
    {"pmid": "3", "title": "Scalp lesion case report", "abstract": "Rare vascular scalp tumor with PET avidity."},
]


def test_search_ranks_matching_papers_higher():
    index = BM25Index(PAPERS)
    results = index.search("scalp tumor PET uptake", top_k=3)
    top_pmids = [paper["pmid"] for paper, score in results[:2]]
    assert "1" in top_pmids
    assert "3" in top_pmids
    assert results[0][1] >= results[-1][1]


def test_search_respects_top_k():
    index = BM25Index(PAPERS)
    results = index.search("PET", top_k=1)
    assert len(results) == 1
