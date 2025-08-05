"""Documentation service for managing documentation files and metadata."""

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from server.processors.markdown import MarkdownProcessor

logger = logging.getLogger(__name__)

# Constants for timeout values
TITLE_EXTRACTION_MAX_BYTES = 1000
TITLE_EXTRACTION_MAX_LINES = 10


class DocumentationService:
    """Service for managing documentation files and metadata."""

    def __init__(self, docs_dir: Path, markdown_processor: "MarkdownProcessor") -> None:
        """
        Initialize the documentation service.

        Args:
            docs_dir: Path to the documentation directory
            markdown_processor: Markdown processor instance
        """
        self.docs_dir = docs_dir
        self.markdown_processor = markdown_processor

    async def get_file_list(self) -> list[dict[str, str | int]]:
        """
        Get list of available documentation files with metadata.

        Returns:
            List of file metadata dictionaries
        """
        if not self.docs_dir.exists():
            return []

        files: list[dict[str, str | int]] = []
        for file_path in self.docs_dir.glob("*.md"):
            try:
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "stem": file_path.stem,
                    "size": stat.st_size,
                    "modified": int(stat.st_mtime),
                    "title": await self.extract_title(file_path),
                })
            except Exception as e:
                logger.warning(f"Error reading file {file_path}: {e}")
                # Preserve original exception for better debugging
                logger.debug(f"Full exception details for {file_path}", exc_info=True)
                continue

        # Sort by name for consistent ordering
        return sorted(files, key=lambda x: str(x["name"]))

    async def extract_title(self, file_path: Path) -> str:
        """
        Extract title from markdown file (first H1 header or filename).

        Args:
            file_path: Path to markdown file

        Returns:
            Extracted or fallback title
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                line_count = 0
                for line in f:
                    line = line.strip()
                    if line.startswith("# "):
                        return line[2:].strip()
                    line_count += 1
                    # Stop after first 10 lines to avoid reading entire file
                    if line_count >= TITLE_EXTRACTION_MAX_LINES:
                        break
        except Exception:
            pass

        # Fallback to filename without extension
        return file_path.stem.replace("_", " ").replace("-", " ").title()

    async def get_file_content(self, filename: str) -> tuple[str, str]:
        """
        Get processed markdown content for a specific file.

        Args:
            filename: Name of the markdown file

        Returns:
            Tuple of (html_content, title)

        Raises:
            HTTPException: If file not found or processing error
        """
        if not filename.endswith(".md"):
            filename += ".md"

        file_path = self.docs_dir / filename

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail=f"Documentation file '{filename}' not found")

        try:
            # Get file hash for cache invalidation using more robust hash calculation
            stat = file_path.stat()
            hash_input = f"{file_path}-{stat.st_mtime}-{stat.st_size}"
            content_hash = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)

            # Process markdown with caching
            html_content = self.markdown_processor.process_file(str(file_path), content_hash)
            title = await self.extract_title(file_path)

            return html_content, title

        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing documentation file: {str(e)}") from e
