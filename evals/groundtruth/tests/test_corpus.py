import hashlib
import json
import re

from evals.groundtruth.config import CORPUS_MANIFEST, load_corpus
from evals.groundtruth.corpus.build_corpus import SOURCES, html_to_text, normalize

SAMPLE_HTML = b"""<html><head><meta charset="windows-1252"></head><body>
<p>Art. 1\xba  O processo civil ser\xe1 ordenado.</p>
<p><strike>Art. 2\xba Revogado texto antigo.</strike></p>
<p>Art. 2\xba   A a\xe7\xe3o   segue.</p>
</body></html>"""


def test_normalize_collapses_all_whitespace_like_agno_clean_text():
    assert normalize("a\n\n b\t\tc   d") == "a b c d"
    assert normalize(normalize("x \n y")) == normalize("x \n y")


def test_html_to_text_decodes_latin1_and_drops_struck_text():
    text = html_to_text(SAMPLE_HTML)
    assert "ação" in text
    assert "Revogado texto antigo" not in text
    assert text == "Art. 1º O processo civil será ordenado. Art. 2º A ação segue."


def test_html_to_text_forced_windows1252_avoids_windows1250_misdetection():
    # The real Planalto pages declare no charset at all. Without an explicit
    # from_encoding, BeautifulSoup's own detection guessed windows-1250 for
    # all four downloaded documents (verified via soup.original_encoding),
    # not windows-1252 -- corrupting accented letters in a way the
    # UTF-8-as-Latin1 mojibake check above does not catch (e.g. real corpus
    # symptom: "Presidência" -> "Presidęncia", "º" -> "ş").
    word = "Presidência"
    body_bytes = word.encode("windows-1252")
    html_no_charset = b"<html><body><p>" + body_bytes + b"</p></body></html>"

    text = html_to_text(html_no_charset, from_encoding="windows-1252")
    assert text == word

    # Reproduce the actual windows-1250 artifact from the same bytes, rather
    # than guessing at what corruption looks like.
    windows_1250_artifact = body_bytes.decode("windows-1250")
    assert windows_1250_artifact != word  # sanity: the encodings really do diverge
    assert windows_1250_artifact not in text


def test_committed_corpus_matches_manifest_and_has_articles():
    corpus = load_corpus()
    manifest = json.loads(CORPUS_MANIFEST.read_text(encoding="utf-8"))
    assert set(corpus) == {s["doc_id"] for s in SOURCES} == {m["doc_id"] for m in manifest["documents"]}
    for entry in manifest["documents"]:
        text = corpus[entry["doc_id"]]
        text_bytes = text.encode("utf-8")
        assert text == normalize(text)
        assert len(text) == entry["chars"]
        assert len(text_bytes) == entry["bytes"]
        assert hashlib.sha256(text_bytes).hexdigest() == entry["sha256"]
        assert len(re.findall(r"\bArt\. ?\d+", text)) >= 50
        # Detect UTF-8-decoded-as-Latin1 mojibake (e.g. "ã" -> "Ã£", "ç" -> "Ã§").
        # A bare "Ã" is not itself a defect: uppercase Portuguese legitimately
        # renders "ção" as "ÇÃO" (e.g. "APLICAÇÃO"), which is a standalone,
        # correctly-decoded "Ã" followed by "O".
        assert "Ã£" not in text
        assert "Ã§" not in text
