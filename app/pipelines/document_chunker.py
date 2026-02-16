"""Document chunking for SEC filings."""

import logging
import re
from typing import Optional

from app.models.document import DocumentChunk, ParsedDocument

logger = logging.getLogger(__name__)


class SemanticChunker:
    """Chunk documents with paragraph-aware splitting for RAG retrieval."""

    def __init__(
        self,
        chunk_size: int = 500,  # Target words per chunk
        chunk_overlap: int = 50,  # Overlap in words
        min_chunk_size: int = 100,  # Minimum chunk size
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, doc: ParsedDocument) -> list[DocumentChunk]:
        """
        Split document into overlapping, paragraph-aware chunks.

        Chunks each section separately to preserve context.
        Content not covered by any section is chunked as "other".
        """
        if not doc.document_id:
            raise ValueError("ParsedDocument.document_id must be set before chunking")

        chunks = []

        if doc.sections:
            # Chunk each named section separately
            for section_name, section_content in doc.sections.items():
                section_chunks = self._chunk_text(
                    section_content, doc.document_id, section_name
                )
                chunks.extend(section_chunks)
        else:
            # No sections found — chunk the entire content
            chunks = self._chunk_text(doc.content, doc.document_id, None)

        # Re-index chunks sequentially
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        return chunks

    def _chunk_text(
        self, text: str, doc_id: str, section: Optional[str]
    ) -> list[DocumentChunk]:
        """
        Split text into overlapping chunks on paragraph boundaries.

        Strategy:
        1. Split text into paragraphs (double newline or significant whitespace).
        2. Accumulate paragraphs until the target chunk_size is reached.
        3. When the target is exceeded, finalize the chunk and start a new one
           with overlap by re-including the last few paragraphs.
        """
        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return []

        chunks = []
        chunk_index = 0
        current_paragraphs = []
        current_word_count = 0
        char_offset = 0  # Track position in original text

        for para in paragraphs:
            para_words = len(para.split())

            # If adding this paragraph exceeds target, finalize current chunk
            if current_word_count + para_words > self.chunk_size and current_paragraphs:
                chunk_content = "\n\n".join(current_paragraphs)
                chunks.append(
                    DocumentChunk(
                        document_id=doc_id,
                        chunk_index=chunk_index,
                        content=chunk_content,
                        section=section,
                        start_char=char_offset,
                        end_char=char_offset + len(chunk_content),
                        word_count=current_word_count,
                    )
                )
                chunk_index += 1

                # Overlap: keep trailing paragraphs whose total <= chunk_overlap
                overlap_paragraphs = []
                overlap_words = 0
                for p in reversed(current_paragraphs):
                    p_words = len(p.split())
                    if overlap_words + p_words > self.chunk_overlap:
                        break
                    overlap_paragraphs.insert(0, p)
                    overlap_words += p_words

                char_offset += len(chunk_content) - len("\n\n".join(overlap_paragraphs))
                current_paragraphs = overlap_paragraphs
                current_word_count = overlap_words

            current_paragraphs.append(para)
            current_word_count += para_words

        # Finalize last chunk
        if current_paragraphs:
            chunk_content = "\n\n".join(current_paragraphs)
            # Merge tiny final chunk into previous if possible
            if current_word_count < self.min_chunk_size and chunks:
                prev = chunks[-1]
                merged = prev.content + "\n\n" + chunk_content
                chunks[-1] = DocumentChunk(
                    document_id=doc_id,
                    chunk_index=prev.chunk_index,
                    content=merged,
                    section=section,
                    start_char=prev.start_char,
                    end_char=prev.start_char + len(merged),
                    word_count=len(merged.split()),
                )
            else:
                chunks.append(
                    DocumentChunk(
                        document_id=doc_id,
                        chunk_index=chunk_index,
                        content=chunk_content,
                        section=section,
                        start_char=char_offset,
                        end_char=char_offset + len(chunk_content),
                        word_count=current_word_count,
                    )
                )

        return chunks

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split text into paragraphs, preserving meaningful boundaries.

        SEC filings cleaned by _clean_sec_text use single newlines between
        paragraphs. We split on double newlines first, then fall back to
        single newlines if the result is too coarse.
        """
        # Try double-newline split first
        raw = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in raw if p.strip()]

        # If we got very few large paragraphs, split on single newlines
        if len(paragraphs) <= 3 and any(len(p.split()) > 600 for p in paragraphs):
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        return paragraphs
