"""Download public Brazilian federal statutes from Planalto and normalize them.

Statutes are public domain (Lei 9.610/1998, art. 8, IV). Raw HTML is kept in
corpus/raw (gitignored); normalized text in corpus/docs is committed.
Normalization mirrors agno.knowledge.chunking.strategy.ChunkingStrategy.clean_text
so that chunk text is always an exact substring of the stored document.

Usage (repo root):
    .venv/Scripts/python.exe -m evals.groundtruth.corpus.build_corpus
    .venv/Scripts/python.exe -m evals.groundtruth.corpus.build_corpus --from-raw   # skip download
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from evals.groundtruth.config import CORPUS_DOCS_DIR, CORPUS_MANIFEST

RAW_DIR = Path(__file__).resolve().parent / "raw"

SOURCES = [
    {"doc_id": "cpc", "title": "Lei 13.105/2015 - Codigo de Processo Civil",
     "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13105.htm",
     "encoding": "windows-1252"},
    {"doc_id": "cdc", "title": "Lei 8.078/1990 - Codigo de Defesa do Consumidor",
     "url": "https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm",
     "encoding": "windows-1252"},
    {"doc_id": "lgpd", "title": "Lei 13.709/2018 - Lei Geral de Protecao de Dados",
     "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm",
     "encoding": "windows-1252"},
    {"doc_id": "clt", "title": "Decreto-Lei 5.452/1943 - Consolidacao das Leis do Trabalho",
     "url": "https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452.htm",
     "encoding": "windows-1252"},
]
LICENSE = "Public domain: Lei 9.610/1998, art. 8, IV (texts of laws are not protected)"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; juri_ai groundtruth corpus builder)"}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def html_to_text(html: bytes, from_encoding: str | None = None) -> str:
    kwargs = {"from_encoding": from_encoding} if from_encoding else {}
    soup = BeautifulSoup(html, "html.parser", **kwargs)
    for tag in soup.find_all(["strike", "s", "del", "script", "style"]):
        tag.decompose()
    return normalize(soup.get_text(" "))


def download(url: str) -> bytes:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.content


def build(from_raw: bool) -> None:
    RAW_DIR.mkdir(exist_ok=True)
    CORPUS_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch and convert every source fully in memory first. Nothing under
    # corpus/docs or manifest.json is written until every source has
    # succeeded, so a failure partway through never leaves stale committed
    # output beside freshly written output.
    texts = {}
    documents = []
    for source in SOURCES:
        raw_path = RAW_DIR / f"{source['doc_id']}.htm"
        if not from_raw:
            raw_path.write_bytes(download(source["url"]))
        if not raw_path.exists():
            sys.exit(f"Missing {raw_path}. Download {source['url']} in a browser, save it there, rerun with --from-raw")
        text = html_to_text(raw_path.read_bytes(), from_encoding=source.get("encoding"))
        text_bytes = text.encode("utf-8")
        texts[source["doc_id"]] = text
        documents.append({
            **source,
            "chars": len(text),
            "bytes": len(text_bytes),
            "articles": len(re.findall(r"\bArt\. ?\d+", text)),
            "sha256": hashlib.sha256(text_bytes).hexdigest(),
            "fetched_at": dt.date.today().isoformat(),
        })
        print(f"{source['doc_id']}: {len(text)} chars, {documents[-1]['articles']} articles")

    # Only now, with every source converted successfully, write user-visible output.
    for source in SOURCES:
        (CORPUS_DOCS_DIR / f"{source['doc_id']}.txt").write_text(texts[source["doc_id"]], encoding="utf-8")
    CORPUS_MANIFEST.write_text(
        json.dumps({"license": LICENSE, "documents": documents}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-raw", action="store_true")
    build(parser.parse_args().from_raw)
