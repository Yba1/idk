"""NCBI E-utils client for the one-time corpus fetch (Step 2.5). No API key
required but rate-limited to ~3 req/sec without one, hence the sleep between
calls in build_corpus.py's caller loop, not in these low-level functions.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from urllib.parse import quote
from urllib.request import Request, urlopen

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NeuLitTrace/1.0"


def search_pmids(query: str, retmax: int) -> list[str]:
    url = f"{ESEARCH_URL}?db=pubmed&term={quote(query)}&retmax={retmax}&retmode=json"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["esearchresult"]["idlist"]


def fetch_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    ids = ",".join(pmids)
    url = f"{EFETCH_URL}?db=pubmed&id={ids}&rettype=abstract&retmode=xml"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)
    papers = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        title_el = article.find(".//ArticleTitle")
        abstract_el = article.find(".//AbstractText")
        if pmid_el is None or title_el is None or abstract_el is None:
            continue
        papers.append({
            "pmid": pmid_el.text or "",
            "title": title_el.text or "",
            "abstract": abstract_el.text or "",
        })
    return papers
