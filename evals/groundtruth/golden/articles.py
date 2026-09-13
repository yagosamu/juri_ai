import re
from dataclasses import dataclass

ARTICLE_RE = re.compile(r"\bArt\. ?\d+[ºo°]?(?:-[A-Z])?")


@dataclass(frozen=True)
class Article:
    header: str
    start: int
    end: int


def split_articles(text: str) -> list[Article]:
    """Split normalized statute text into article spans. Text before the first article is dropped."""
    matches = list(ARTICLE_RE.finditer(text))
    articles = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        articles.append(Article(header=m.group(0).strip(), start=m.start(), end=end))
    return articles
