"""
Token-aware text chunker for RAG document indexing.

Strategy: sliding window over tiktoken-encoded tokens with overlap.
This guarantees each chunk is at most `target_tokens` tokens and
that adjacent chunks share `overlap_tokens` for context continuity.

Why token-based (not character-based):
- LLM context limits are in tokens, not characters
- Consistent chunk sizes → predictable embedding quality
- No wasted space from oversized chunks
"""

from dataclasses import dataclass, field

import tiktoken


@dataclass
class Chunk:
    content: str
    token_count: int
    chunk_index: int
    metadata: dict = field(default_factory=dict)


class TextChunker:
    """
    Splits text into overlapping token-window chunks.

    Usage:
        chunker = TextChunker(target_tokens=512, overlap_tokens=64)
        chunks = chunker.chunk(text)
    """

    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        model: str = "gpt-4o",
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.step = max(target_tokens - overlap_tokens, 64)
        try:
            self.enc = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback for unknown models
            self.enc = tiktoken.get_encoding("cl100k_base")

    def chunk(self, text: str, metadata: dict | None = None) -> list[Chunk]:
        """
        Chunk `text` into overlapping token windows.

        Args:
            text: Raw text to split.
            metadata: Base metadata merged into each chunk's metadata.

        Returns:
            List of Chunk objects in order.
        """
        if not text or not text.strip():
            return []

        base_meta = metadata or {}
        tokens = self.enc.encode(text)

        if not tokens:
            return []

        chunks: list[Chunk] = []
        idx = 0

        while idx < len(tokens):
            window = tokens[idx : idx + self.target_tokens]
            chunk_text = self.enc.decode(window)

            # Skip whitespace-only windows
            if chunk_text.strip():
                chunks.append(
                    Chunk(
                        content=chunk_text,
                        token_count=len(window),
                        chunk_index=len(chunks),
                        metadata={**base_meta},
                    )
                )

            if idx + self.target_tokens >= len(tokens):
                break
            idx += self.step

        return chunks


def parse_file_content(file_bytes: bytes, file_type: str) -> str:
    """
    Extract plain text from uploaded file bytes.

    Supported types: application/pdf, text/plain, text/markdown, text/*.
    Falls back to UTF-8 decode for unknown text types.
    """
    if file_type == "application/pdf":
        return _parse_pdf(file_bytes)
    # All text variants (text/plain, text/markdown, text/x-python, etc.)
    return file_bytes.decode("utf-8", errors="replace")


def _parse_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using pypdf."""
    import io

    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("pypdf is required for PDF parsing. Add it to dependencies.")

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(f"[Page {i + 1}]\n{page_text}")
    return "\n\n".join(pages)
