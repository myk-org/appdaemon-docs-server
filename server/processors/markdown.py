"""Markdown processor for rendering documentation with caching."""

import logging
import os
import threading
from collections import OrderedDict

import markdown

logger = logging.getLogger(__name__)

# Security: Maximum file size to prevent DoS attacks (10MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Markdown configuration for optimal rendering
MARKDOWN_EXTENSIONS = [
    "codehilite",
    "toc",
    "tables",
    "fenced_code",
    "markdown.extensions.attr_list",
    "markdown.extensions.def_list",
    "markdown.extensions.footnotes",
]

MARKDOWN_EXTENSION_CONFIGS = {
    "codehilite": {
        "css_class": "highlight",
        "use_pygments": True,
        "noclasses": False,
    },
    "toc": {
        "title": "Table of Contents",
        "anchorlink": True,
    },
}


class MarkdownProcessor:
    """High-performance markdown processor with caching."""

    def __init__(self) -> None:
        """Initialize markdown processor with optimized configuration."""
        self.md = markdown.Markdown(
            extensions=MARKDOWN_EXTENSIONS,
            extension_configs=MARKDOWN_EXTENSION_CONFIGS,
        )
        # LRU cache implemented with OrderedDict for O(1) updates and eviction
        self._cache: OrderedDict[tuple[str, int], str] = OrderedDict()
        self._max_cache_size = 128
        # Synchronization for thread-safe processing and cache access
        self._lock = threading.Lock()

    def process_file(self, file_path: str, content_hash: int) -> str:
        """
        Process markdown file with instance caching for performance.

        Args:
            file_path: Path to the markdown file
            content_hash: Hash of file content for cache invalidation

        Returns:
            Rendered HTML content
        """
        cache_key = (file_path, content_hash)

        try:
            with self._lock:
                # Check cache first
                if cache_key in self._cache:
                    # Update access order for LRU
                    self._cache.move_to_end(cache_key)
                    return self._cache[cache_key]

            # Check file size before reading to prevent DoS attacks
            try:
                file_size = os.path.getsize(file_path)
                if file_size > MAX_FILE_SIZE_BYTES:
                    raise ValueError(f"File {file_path} is too large ({file_size} bytes, max {MAX_FILE_SIZE_BYTES})")
            except OSError as e:
                raise ValueError(f"Cannot access file {file_path}: {e}") from e

            # Read and render outside of lock for I/O, but protect the shared Markdown instance
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            with self._lock:
                # Second cache check under lock to avoid duplicate work if another
                # thread cached the result after we released the lock for I/O
                if cache_key in self._cache:
                    self._cache.move_to_end(cache_key)
                    return self._cache[cache_key]

                # Reset markdown instance for clean processing
                self.md.reset()
                html_content = str(self.md.convert(content))

                # Cache the result with true LRU eviction
                if len(self._cache) >= self._max_cache_size:
                    # Remove least recently used entry (true LRU)
                    self._cache.popitem(last=False)

                self._cache[cache_key] = html_content
                return html_content

        except Exception as e:
            logger.error(f"Error processing markdown file {file_path}: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear the internal render cache safely."""
        with self._lock:
            self._cache.clear()
