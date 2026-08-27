"""A deliberately small, inspectable document retrieval pipeline."""

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentChunk:
    source: str
    title: str
    text: str
    vector: dict[str, float]


def _tokens(text: str) -> list[str]:
    """Turn text into normalized terms used by the local embeddings."""
    return re.findall(r"[a-z0-9]+", text.lower())


def split_title(raw: str) -> tuple[str, str]:
    """Separate a leading Markdown heading from the document body."""
    lines = raw.strip().splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        return lines[0].lstrip("# ").strip(), "\n".join(lines[1:])
    return "", raw


def load_and_chunk(
    folders: list[Path], chunk_words: int = 90
) -> list[tuple[str, str, str]]:
    """Load Markdown documents and split their bodies into overlapping chunks.

    The heading is kept out of the chunk body so answers do not run the title
    into the first sentence; it is returned separately for display and scoring.
    """
    chunks: list[tuple[str, str, str]] = []
    for folder in folders:
        for path in sorted(folder.glob("*.md")):
            title, body = split_title(path.read_text(encoding="utf-8"))
            words = body.split()
            step = max(1, chunk_words - 20)
            for start in range(0, len(words), step):
                text = " ".join(words[start : start + chunk_words])
                if text:
                    chunks.append((path.name, title, text))
    return chunks


class SimpleRetriever:
    """Create TF-IDF embeddings in memory and retrieve by cosine similarity."""

    def __init__(self, folders: list[Path]):
        raw_chunks = load_and_chunk(folders)
        # The title is embedded with the body so heading-only wording such as
        # "work from home" still retrieves its document.
        tokenized = [
            _tokens(f"{title} {text}") for _, title, text in raw_chunks
        ]
        document_count = max(1, len(tokenized))
        document_frequency = Counter(
            token for terms in tokenized for token in set(terms)
        )
        self.idf = {
            token: math.log((document_count + 1) / (count + 1)) + 1
            for token, count in document_frequency.items()
        }
        self.chunks = [
            DocumentChunk(source, title, text, self._embed_terms(terms))
            for (source, title, text), terms in zip(
                raw_chunks, tokenized, strict=True
            )
        ]

    def _embed_terms(self, terms: list[str]) -> dict[str, float]:
        counts = Counter(terms)
        total = max(1, len(terms))
        return {
            token: (count / total) * self.idf.get(token, 1.0)
            for token, count in counts.items()
        }

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        dot_product = sum(value * right.get(term, 0) for term, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return dot_product / (left_norm * right_norm)

    def search(self, query: str, limit: int = 3) -> list[dict[str, object]]:
        query_vector = self._embed_terms(_tokens(query))
        ranked = sorted(
            (
                (self._cosine(query_vector, chunk.vector), chunk)
                for chunk in self.chunks
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        return [
            {
                "source": chunk.source,
                "title": chunk.title,
                "text": chunk.text,
                "score": round(score, 3),
            }
            for score, chunk in ranked[:limit]
            if score >= 0.08
        ]
