"""Tests for markdown processor module."""

import os
import tempfile
from unittest.mock import patch

import pytest

from server.processors.markdown import MarkdownProcessor


class TestMarkdownProcessor:
    """Test cases for MarkdownProcessor class."""

    @pytest.fixture
    def processor(self):
        """Create a MarkdownProcessor instance for testing."""
        return MarkdownProcessor()

    @pytest.fixture
    def temp_markdown_file(self):
        """Create a temporary markdown file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Header\n\nThis is a test markdown file.\n\n```python\nprint('hello')\n```")
            temp_path = f.name

        yield temp_path

        # Cleanup
        os.unlink(temp_path)

    def test_init(self, processor):
        """Test MarkdownProcessor initialization."""
        assert processor.md is not None
        assert processor._cache == {}
        assert processor._max_cache_size == 128
        # Access order list removed; LRU is handled by OrderedDict move_to_end

    def test_process_file_happy_path(self, processor, temp_markdown_file):
        """Test basic markdown file processing."""
        result = processor.process_file(temp_markdown_file, 123)

        assert isinstance(result, str)
        assert "<h1" in result
        assert "Test Header" in result
        assert "This is a test markdown file." in result
        assert "<code>" in result or "highlight" in result  # Code highlighting

    def test_process_file_caching(self, processor, temp_markdown_file):
        """Test that identical requests are cached."""
        # First call
        result1 = processor.process_file(temp_markdown_file, 123)
        assert len(processor._cache) == 1
        # Internal access order list removed in implementation

        # Second call with same hash should use cache
        result2 = processor.process_file(temp_markdown_file, 123)
        assert result1 == result2
        assert len(processor._cache) == 1
        # Internal access order list removed in implementation

    def test_process_file_cache_invalidation(self, processor, temp_markdown_file):
        """Test that different content hashes invalidate cache."""
        # First call
        result1 = processor.process_file(temp_markdown_file, 123)
        assert len(processor._cache) == 1

        # Second call with different hash
        result2 = processor.process_file(temp_markdown_file, 456)
        assert len(processor._cache) == 2
        assert result1 == result2  # Content should be same since file didn't change

    def test_process_file_lru_eviction(self, processor, temp_markdown_file):
        """Test LRU cache eviction when max size is reached."""
        # Set small cache size for testing
        processor._max_cache_size = 2

        # Fill cache to max capacity
        processor.process_file(temp_markdown_file, 1)
        processor.process_file(temp_markdown_file, 2)
        assert len(processor._cache) == 2

        # Add one more - should evict LRU
        processor.process_file(temp_markdown_file, 3)
        assert len(processor._cache) == 2
        assert (temp_markdown_file, 1) not in processor._cache
        assert (temp_markdown_file, 2) in processor._cache
        assert (temp_markdown_file, 3) in processor._cache

    def test_process_file_lru_access_order(self, processor, temp_markdown_file):
        """Test that accessing cached items updates LRU order."""
        processor._max_cache_size = 2

        # Add two items
        processor.process_file(temp_markdown_file, 1)
        processor.process_file(temp_markdown_file, 2)

        # Access first item (should move to end of LRU)
        processor.process_file(temp_markdown_file, 1)

        # Add third item - should evict item 2 (now LRU)
        processor.process_file(temp_markdown_file, 3)
        assert (temp_markdown_file, 2) not in processor._cache
        assert (temp_markdown_file, 1) in processor._cache
        assert (temp_markdown_file, 3) in processor._cache

    def test_process_file_not_found(self, processor):
        """Test processing non-existent file raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            processor.process_file("/nonexistent/file.md", 123)

    def test_process_file_permission_error(self, processor):
        """Test processing file with permission issues."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test")
            temp_path = f.name

        try:
            # Remove read permissions
            os.chmod(temp_path, 0o000)

            with pytest.raises(PermissionError):
                processor.process_file(temp_path, 123)
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_path, 0o644)
            os.unlink(temp_path)

    def test_process_file_unicode_content(self, processor):
        """Test processing file with unicode content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Unicode Test 🚀\n\nThis has unicode: café, naïve, 中文")
            temp_path = f.name

        try:
            result = processor.process_file(temp_path, 123)
            assert "Unicode Test 🚀" in result
            assert "café" in result
            assert "中文" in result
        finally:
            os.unlink(temp_path)

    def test_markdown_extensions_loaded(self, processor):
        """Test that markdown extensions are properly loaded."""
        # Test code highlighting extension
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("```python\nprint('hello')\n```")
            temp_path = f.name

        try:
            result = processor.process_file(temp_path, 123)
            # Should contain highlighted code
            assert "highlight" in result or "codehilite" in result
        finally:
            os.unlink(temp_path)

        # Test table extension
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("| Column 1 | Column 2 |\n|----------|----------|\n| Value 1  | Value 2  |")
            temp_path = f.name

        try:
            result = processor.process_file(temp_path, 123)
            assert "<table>" in result
            assert "<th>" in result
            assert "<td>" in result
        finally:
            os.unlink(temp_path)

    def test_process_file_logging_on_error(self, processor):
        """Test that errors are properly logged."""
        with patch("server.processors.markdown.logger") as mock_logger:
            with pytest.raises(FileNotFoundError):
                processor.process_file("/nonexistent/file.md", 123)

            mock_logger.error.assert_called_once()

    def test_markdown_reset_between_calls(self, processor):
        """Test that markdown instance is reset between calls."""
        # This test ensures that markdown state doesn't leak between conversions

        # First conversion with TOC
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Header 1\n## Header 2\n### Header 3")
            temp_path1 = f.name

        # Second conversion without TOC structure
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Just plain text")
            temp_path2 = f.name

        try:
            result1 = processor.process_file(temp_path1, 1)
            result2 = processor.process_file(temp_path2, 2)

            # Results should be independent
            assert "Header 1" in result1
            assert "Header 1" not in result2
            assert "plain text" in result2
        finally:
            os.unlink(temp_path1)
            os.unlink(temp_path2)

    def test_cache_key_uniqueness(self, processor, temp_markdown_file):
        """Test that cache keys are unique for different file paths."""
        # Create another temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Different content")
            temp_path2 = f.name

        try:
            # Process both files with same hash
            processor.process_file(temp_markdown_file, 123)
            processor.process_file(temp_path2, 123)

            # Should have two cache entries
            assert len(processor._cache) == 2

            # Cache keys should be different
            keys = list(processor._cache.keys())
            assert keys[0] != keys[1]
        finally:
            os.unlink(temp_path2)
