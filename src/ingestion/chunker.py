"""Markdown chunker for FastAPI documentation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter
import tiktoken

_tokenizer = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    """Return number of tokens in text."""
    return len(_tokenizer.encode(text))

@dataclass 
class Chunk:
    """A piece of text ready to be embedded and stored."""
    text: str
    source_file: str
    title: str
    section: str
    chunk_index: int

    @property
    def embedding_text(self) -> str:
        """Text we actually pass to the embedding model.

        We prepend title and section to add semantic context, which
        helps the embedding model produce more relevant vectors.
        """
        return f"{self.title} > {self.section}\n\n{self.text}"

# Patterns to clean from markdown before chunking
_HTML_BLOCK_RE = re.compile(r"<[^>]+>", re.DOTALL)
_INCLUDE_RE = re.compile(r"\{\*.*?\*\}", re.DOTALL)
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_HEADING_ANCHOR_RE = re.compile(r"\s*\{\s*#[^}]+\}\s*$")


def clean_markdown(text: str) -> str:
    """Strip HTML, include directives, and collapse extra newlines."""
    text = _INCLUDE_RE.sub("[Code example omitted]", text)
    text = _HTML_BLOCK_RE.sub("", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def extract_title(text: str, fallback: str) -> str:
    """Get the H1 title from markdown, or use fallback."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            return _HEADING_ANCHOR_RE.sub("", title).strip()
    return fallback


def read_markdown_file(path: Path) -> tuple[str, str]:
    """Read a .md file, return (title, cleaned_content)."""
    post = frontmatter.load(path)
    content = post.content
    title = extract_title(content, fallback=path.stem)
    return title, clean_markdown(content)

MAX_TOKENS_PER_CHUNK = 500
OVERLAP_TOKENS = 100
MIN_TOKENS_PER_CHUNK = 30
HARD_MAX_TOKENS = 1000

def split_into_sections(content: str, default_title: str) -> list[tuple[str, str]]:
    """Split markdown into sections by H2 headers.

    Returns a list of (section_title, section_text) tuples.
    Text before the first H2 belongs to a default 'Introduction' section.
    """
    sections: list[tuple[str, str]] = []
    current_title = "Introduction"
    current_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            # Save the previous section before starting a new one
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            # Start new section, strip anchor from header
            heading = stripped[3:].strip()
            current_title = _HEADING_ANCHOR_RE.sub("", heading).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Don't forget the last section
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))

    # Drop empty sections
    return [(t, txt) for t, txt in sections if txt]

def split_by_tokens(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Split text into chunks by token count with overlap.

    Used when a section is too large to fit in a single chunk.
    Splits at paragraph boundaries when possible.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_chunk_paragraphs: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        # A single paragraph longer than max_tokens - emit as its own chunk
        # (rare; usually a giant code block)
        # A single paragraph longer than max_tokens
        if para_tokens > max_tokens:
            if current_chunk_paragraphs:
                chunks.append("\n\n".join(current_chunk_paragraphs))
                current_chunk_paragraphs = []
                current_tokens = 0
            # If it fits in HARD_MAX, emit as a single oversized chunk
            if para_tokens <= HARD_MAX_TOKENS:
                chunks.append(para)
            else:
                # Force-split by lines
                chunks.extend(_force_split_by_lines(para, max_tokens))
            continue
        # Will adding this paragraph exceed the limit?
        if current_tokens + para_tokens > max_tokens and current_chunk_paragraphs:
            chunks.append("\n\n".join(current_chunk_paragraphs))
            # Start new chunk with overlap: keep tail paragraphs
            current_chunk_paragraphs, current_tokens = _build_overlap(
                current_chunk_paragraphs, overlap
            )

        current_chunk_paragraphs.append(para)
        current_tokens += para_tokens

    # Don't forget the last partial chunk
    if current_chunk_paragraphs:
        chunks.append("\n\n".join(current_chunk_paragraphs))

    return chunks


def _build_overlap(paragraphs: list[str], overlap_budget: int) -> tuple[list[str], int]:
    """Take the tail paragraphs that fit into the overlap budget."""
    tail: list[str] = []
    tail_tokens = 0
    for para in reversed(paragraphs):
        para_tokens = count_tokens(para)
        if tail_tokens + para_tokens > overlap_budget:
            break
        tail.insert(0, para)
        tail_tokens += para_tokens
    return tail, tail_tokens

def _force_split_by_lines(text: str, max_tokens: int) -> list[str]:
    """Last-resort splitting for oversized paragraphs (huge code blocks)."""
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line + "\n")
        if current_tokens + line_tokens > max_tokens and current:
            chunks.append("\n".join(current))
            current = []
            current_tokens = 0
        current.append(line)
        current_tokens += line_tokens

    if current:
        chunks.append("\n".join(current))
    return chunks

def chunk_markdown_file(path: Path) -> list[Chunk]:
    """Read a markdown file and produce a list of chunks ready for embedding."""
    title, content = read_markdown_file(path)
    sections = split_into_sections(content, default_title=title)

    relative_path = str(path.relative_to(path.parents[len(path.parents) - 2]))
    # ^ Hacky way to get "tutorial/first-steps.md" from full path.
    # We'll improve this once we have a proper ingest script.

    chunks: list[Chunk] = []
    chunk_index = 0

    for section_title, section_text in sections:
        section_tokens = count_tokens(section_text)

        if section_tokens <= MAX_TOKENS_PER_CHUNK:
            # Section fits as a single chunk
            chunks.append(Chunk(
                text=section_text,
                source_file=relative_path,
                title=title,
                section=section_title,
                chunk_index=chunk_index,
            ))
            chunk_index += 1
        else:
            # Split section into smaller chunks
            for piece in split_by_tokens(
                section_text,
                max_tokens=MAX_TOKENS_PER_CHUNK,
                overlap=OVERLAP_TOKENS,
            ):
                chunks.append(Chunk(
                    text=piece,
                    source_file=relative_path,
                    title=title,
                    section=section_title,
                    chunk_index=chunk_index,
                ))
                chunk_index += 1
    chunks = [c for c in chunks if count_tokens(c.text) >= MIN_TOKENS_PER_CHUNK]
    return chunks