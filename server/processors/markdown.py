"""Markdown processor for rendering documentation with caching."""

import logging

import markdown

logger = logging.getLogger(__name__)

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
        self._cache: dict[tuple[str, int], str] = {}
        self._max_cache_size = 128
        # Track access order for true LRU eviction
        self._access_order: list[tuple[str, int]] = []

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

        # Check cache first
        if cache_key in self._cache:
            # Update access order for LRU
            self._access_order.remove(cache_key)
            self._access_order.append(cache_key)
            return self._cache[cache_key]

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Reset markdown instance for clean processing
            self.md.reset()
            html_content = str(self.md.convert(content))

            # Cache the result with true LRU eviction
            if len(self._cache) >= self._max_cache_size:
                # Remove least recently used entry (true LRU)
                lru_key = self._access_order.pop(0)
                del self._cache[lru_key]

            self._cache[cache_key] = html_content
            self._access_order.append(cache_key)
            return html_content

        except Exception as e:
            logger.error(f"Error processing markdown file {file_path}: {e}")
            raise
