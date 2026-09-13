import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evals.groundtruth.golden import candidates, review
from evals.groundtruth.golden.articles import split_articles
from evals.groundtruth.golden.schema import GoldenItem, Passage, load_golden, save_golden

TEXT = "TÍTULO I Art. 1º O processo. § 1º Detalhe. Art. 2º A ação. Art. 3º Fim."


def test_split_articles_returns_contiguous_spans_starting_at_art():
    arts = split_articles(TEXT)
    assert [a.header for a in arts] == ["Art. 1º", "Art. 2º", "Art. 3º"]
    assert TEXT[arts[0].start:arts[0].end] == "Art. 1º O processo. § 1º Detalhe. "
    assert arts[1].start == arts[0].end
    assert arts[-1].end == len(TEXT)


def test_golden_item_rejects_empty_passage():
    with pytest.raises(ValueError):
        GoldenItem(id="x", question="q?", category="conceito",
                   passages=[Passage(doc_id="cpc", start=10, end=10)],
                   source_article="Art. 1º", reviewed_by="yago", reviewed_at="2026-09-13")


def test_round_trip_jsonl(tmp_path):
    item = GoldenItem(id="cpc-0001", question="Qual o prazo?", category="fato_pontual",
                      passages=[Passage(doc_id="cpc", start=0, end=20)],
                      source_article="Art. 1º", reviewed_by="yago", reviewed_at="2026-09-13")
    path = tmp_path / "g.jsonl"
    save_golden([item], path)
    assert load_golden(path) == [item]
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["category"] == "fato_pontual"


# ---------------------------------------------------------------------------
# candidates.py: the model response must never override trusted article metadata
# ---------------------------------------------------------------------------

def _fake_openai_client(content: str):
    """Stand in for openai.OpenAI: chat.completions.create returns a fixed JSON string."""
    def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_ask_rejects_model_response_that_overrides_trusted_article_fields():
    poisoned = json.dumps({
        "question": "Qual o prazo?",
        "category": "conceito",
        "doc_id": "cpc",
        "start": 0,
        "end": 999999,
    })
    client = _fake_openai_client(poisoned)
    with pytest.raises(ValidationError):
        candidates.ask(client, "artigo de teste")


def test_candidates_main_refuses_to_regenerate_existing_round_without_force(tmp_path, monkeypatch, capsys):
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text(
        json.dumps({"candidate_id": "r1-cpc-000", "doc_id": "cpc", "start": 0, "end": 10,
                    "header": "Art. 1", "question": "Q?", "category": "conceito"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(candidates, "CANDIDATES", candidates_path)
    monkeypatch.setattr(candidates, "load_dotenv", lambda: None)
    monkeypatch.setattr(candidates, "load_corpus", lambda: {"cpc": "x" * 100})

    def must_not_be_called(*args, **kwargs):
        raise AssertionError("OpenAI must not be constructed when the round is refused")

    monkeypatch.setattr(candidates, "OpenAI", must_not_be_called)

    candidates.main(1, force=False)

    assert "force" in capsys.readouterr().out
    assert candidates_path.read_text(encoding="utf-8").count("\n") == 1  # nothing appended


# ---------------------------------------------------------------------------
# review.py: helpers shared by the tests below
# ---------------------------------------------------------------------------

def _make_input(answers):
    """A scripted stand-in for input(): pops the next answer, raising if the script runs out."""
    it = iter(answers)
    return lambda prompt="": next(it)


def _setup_review(tmp_path, monkeypatch, corpus, candidate_rows):
    candidates_path = tmp_path / "candidates.jsonl"
    candidates_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidate_rows),
        encoding="utf-8",
    )
    decisions_path = tmp_path / "decisions.jsonl"
    golden_path = tmp_path / "golden_set.jsonl"
    monkeypatch.setattr(review, "CANDIDATES", candidates_path)
    monkeypatch.setattr(review, "DECISIONS", decisions_path)
    monkeypatch.setattr(review, "GOLDEN_SET", golden_path)
    monkeypatch.setattr(review, "load_corpus", lambda: corpus)
    return candidates_path, decisions_path, golden_path


def test_review_refuses_candidate_with_out_of_bounds_span(tmp_path, monkeypatch, capsys):
    corpus = {"cpc": "Art. 1 texto curto."}
    bad = {"candidate_id": "bad-1", "doc_id": "cpc", "start": 0, "end": 9999,
           "header": "Art. 1", "question": "Q?", "category": "conceito"}
    _, decisions_path, golden_path = _setup_review(tmp_path, monkeypatch, corpus, [bad])

    review.main("yago", input_fn=_make_input([]))  # must never reach a prompt

    out = capsys.readouterr().out
    assert "refusing" in out and "bad-1" in out
    assert not decisions_path.exists()
    assert not golden_path.exists()


def test_review_reprompts_on_invalid_category(tmp_path, monkeypatch, capsys):
    corpus = {"cpc": "Art. 1 " + "texto " * 10}
    good = {"candidate_id": "cand-1", "doc_id": "cpc", "start": 0, "end": len(corpus["cpc"]),
            "header": "Art. 1", "question": "Q?", "category": "conceito"}
    _, _, golden_path = _setup_review(tmp_path, monkeypatch, corpus, [good])

    review.main("yago", input_fn=_make_input(["c", "nao_existe", "procedimento", "a"]))

    assert "unknown category" in capsys.readouterr().out
    items = load_golden(golden_path)
    assert len(items) == 1
    assert items[0].category == "procedimento"


def test_review_forces_valid_category_before_accepting_a_candidate_with_invalid_initial_category(
    tmp_path, monkeypatch, capsys,
):
    # A candidate loaded straight from the file with an invalid category (a hand-edited or legacy
    # candidates.jsonl, since candidates.py now types the field so this cannot come from a fresh
    # run) must not crash the tool when the reviewer presses "a" directly, without ever pressing
    # "c" first. Without the fix, GoldenItem(..., category="invalida") raises ValidationError here
    # and the review session dies; with the fix, pressing "a" forces a valid category first.
    corpus = {"cpc": "Art. 1 " + "texto " * 10}
    bad_category = {"candidate_id": "cand-1", "doc_id": "cpc", "start": 0, "end": len(corpus["cpc"]),
                     "header": "Art. 1", "question": "Q?", "category": "invalida"}
    _, _, golden_path = _setup_review(tmp_path, monkeypatch, corpus, [bad_category])

    review.main("yago", input_fn=_make_input(["a", "conceito"]))

    assert "not valid" in capsys.readouterr().out
    items = load_golden(golden_path)
    assert len(items) == 1
    assert items[0].category == "conceito"


def test_review_golden_set_and_decisions_journal_never_disagree_after_accept(tmp_path, monkeypatch):
    corpus = {"cpc": "Art. 1 " + "texto " * 10}
    span = len(corpus["cpc"])
    first = {"candidate_id": "cand-1", "doc_id": "cpc", "start": 0, "end": span,
             "header": "Art. 1", "question": "Q1?", "category": "conceito"}
    candidates_path, decisions_path, golden_path = _setup_review(tmp_path, monkeypatch, corpus, [first])

    review.main("yago", input_fn=_make_input(["a"]))
    golden_items = load_golden(golden_path)
    decisions = [json.loads(l) for l in decisions_path.read_text(encoding="utf-8").splitlines()]
    accepted_in_journal = {d["candidate_id"] for d in decisions if d["decision"] == "a"}
    assert {item.id for item in golden_items} == accepted_in_journal

    # Now prove this holds because of ORDER, not luck: if saving the golden set fails, the
    # decisions journal must never end up claiming a decision the golden set does not have.
    second = {"candidate_id": "cand-2", "doc_id": "cpc", "start": 0, "end": span,
              "header": "Art. 1", "question": "Q2?", "category": "conceito"}
    with candidates_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(second) + "\n")

    def boom(items, path):
        raise RuntimeError("disk full")

    monkeypatch.setattr(review, "save_golden", boom)
    with pytest.raises(RuntimeError):
        review.main("yago", input_fn=_make_input(["a"]))

    decisions_after = {json.loads(l)["candidate_id"] for l in decisions_path.read_text(encoding="utf-8").splitlines()}
    assert "cand-2" not in decisions_after


def test_review_duplicate_candidate_id_presented_only_once(tmp_path, monkeypatch):
    corpus = {"cpc": "Art. 1 " + "texto " * 10}
    row = {"candidate_id": "dup-1", "doc_id": "cpc", "start": 0, "end": len(corpus["cpc"]),
           "header": "Art. 1", "question": "Q?", "category": "conceito"}
    _, decisions_path, _ = _setup_review(tmp_path, monkeypatch, corpus, [row, row])

    # Only ONE answer is queued: if the duplicate were shown twice, the second input_fn call
    # would raise StopIteration and fail this test.
    review.main("yago", input_fn=_make_input(["r"]))

    decisions = [json.loads(l) for l in decisions_path.read_text(encoding="utf-8").splitlines()]
    assert len(decisions) == 1


def test_review_prints_message_for_unknown_command(tmp_path, monkeypatch, capsys):
    corpus = {"cpc": "Art. 1 " + "texto " * 10}
    row = {"candidate_id": "cand-x", "doc_id": "cpc", "start": 0, "end": len(corpus["cpc"]),
           "header": "Art. 1", "question": "Q?", "category": "conceito"}
    _setup_review(tmp_path, monkeypatch, corpus, [row])

    review.main("yago", input_fn=_make_input(["z", "r"]))

    assert "unknown command" in capsys.readouterr().out
