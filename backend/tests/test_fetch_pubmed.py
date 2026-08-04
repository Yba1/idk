from unittest.mock import patch, MagicMock
from backend.app.corpus.fetch_pubmed import search_pmids, fetch_abstracts

ESEARCH_JSON = b'{"esearchresult": {"idlist": ["111", "222"]}}'
EFETCH_XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>111</PMID>
      <Article>
        <ArticleTitle>A rare case report</ArticleTitle>
        <Abstract><AbstractText>Patient presented with focal uptake.</AbstractText></Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


def test_search_pmids_parses_idlist():
    fake_resp = MagicMock()
    fake_resp.read.return_value = ESEARCH_JSON
    fake_resp.__enter__.return_value = fake_resp
    with patch("backend.app.corpus.fetch_pubmed.urlopen", return_value=fake_resp):
        ids = search_pmids("scalp angiosarcoma AND PET", retmax=2)
    assert ids == ["111", "222"]


def test_fetch_abstracts_parses_xml():
    fake_resp = MagicMock()
    fake_resp.read.return_value = EFETCH_XML
    fake_resp.__enter__.return_value = fake_resp
    with patch("backend.app.corpus.fetch_pubmed.urlopen", return_value=fake_resp):
        papers = fetch_abstracts(["111"])
    assert papers == [{
        "pmid": "111",
        "title": "A rare case report",
        "abstract": "Patient presented with focal uptake.",
    }]
