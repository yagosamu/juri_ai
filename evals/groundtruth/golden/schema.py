from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

Category = Literal["fato_pontual", "conceito", "procedimento"]
ReviewMode = Literal["human_full", "human_blind_calibration", "human_flagged", "human_unflagged", "judge_pass"]


class Passage(BaseModel):
    doc_id: str
    start: int
    end: int

    @model_validator(mode="after")
    def non_empty(self):
        if self.end <= self.start or self.start < 0:
            raise ValueError(f"empty passage {self.doc_id}[{self.start}:{self.end}]")
        return self


class GoldenItem(BaseModel):
    id: str
    question: str
    category: Category
    passages: list[Passage]
    source_article: str
    reviewed_by: str
    reviewed_at: str
    review_mode: ReviewMode
    notes: str = ""

    @model_validator(mode="after")
    def has_passage(self):
        if not self.passages:
            raise ValueError("golden item needs at least one passage")
        return self


def load_golden(path: Path) -> list[GoldenItem]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenItem.model_validate_json(line) for line in lines if line.strip()]


def save_golden(items: list[GoldenItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(i.model_dump_json() + "\n" for i in items), encoding="utf-8")
