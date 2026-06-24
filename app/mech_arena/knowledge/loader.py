"""
Loads all markdown files from the knowledge directory recursively.
Designed to handle hundreds or thousands of files efficiently.
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

CHUNK_SIZE = 600      # characters per chunk
CHUNK_OVERLAP = 100   # overlap between consecutive chunks


@dataclass
class KnowledgeChunk:
    """A single searchable chunk of content from a knowledge file."""
    source: str       # relative path from knowledge root
    category: str     # top-level folder (mechs, weapons, etc.)
    title: str        # from first # heading or filename
    content: str      # the text of this chunk
    chunk_index: int  # which chunk within the source file


def _derive_title(path: Path, content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _get_category(path: Path, base: Path) -> str:
    try:
        parts = path.relative_to(base).parts
        return parts[0] if len(parts) > 1 else "general"
    except ValueError:
        return "general"


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping character chunks, breaking on newlines."""
    if len(text) <= CHUNK_SIZE:
        return [text.strip()] if text.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            newline_pos = text.rfind("\n", start, end)
            if newline_pos > start:
                end = newline_pos
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end - CHUNK_OVERLAP
        if start >= len(text):
            break

    return chunks


def _iter_markdown_files(base_dir: Path) -> Iterator[Path]:
    """Recursively yield all .md files under base_dir, sorted for determinism."""
    if not base_dir.exists():
        logger.warning("Knowledge directory does not exist: %s", base_dir)
        return
    for root, dirs, files in os.walk(base_dir):
        dirs.sort()
        for fname in sorted(files):
            if fname.lower().endswith(".md"):
                yield Path(root) / fname


def load_knowledge_chunks(base_dir: Path) -> list[KnowledgeChunk]:
    """
    Walk base_dir, read every .md file, chunk its content.
    Returns a flat list of KnowledgeChunk objects ready for indexing.
    """
    chunks: list[KnowledgeChunk] = []
    file_count = 0

    for md_path in _iter_markdown_files(base_dir):
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace").strip()
            if not content:
                continue

            file_count += 1
            title = _derive_title(md_path, content)
            category = _get_category(md_path, base_dir)
            source = str(md_path.relative_to(base_dir))

            for i, chunk_content in enumerate(_chunk_text(content)):
                chunks.append(KnowledgeChunk(
                    source=source,
                    category=category,
                    title=title,
                    content=chunk_content,
                    chunk_index=i,
                ))
        except Exception as e:
            logger.error("Failed to load %s: %s", md_path, e)

    logger.info(
        "Knowledge loader: %d files → %d chunks (dir=%s)",
        file_count, len(chunks), base_dir,
    )
    return chunks
