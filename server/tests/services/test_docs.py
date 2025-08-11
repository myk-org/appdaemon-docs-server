"""Tests for documentation service."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from server.services.docs import DocumentationService


class TestDocumentationService:
    """Test cases for DocumentationService class."""

    @pytest.fixture
    def mock_markdown_processor(self):
        """Create a mock markdown processor for testing."""
        processor = Mock()
        processor.process_file.return_value = "<h1>Test HTML</h1><p>Content</p>"
        return processor

    @pytest.fixture
    def temp_docs_dir(self):
        """Create a temporary docs directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)

            # Create test markdown files
            (docs_dir / "test1.md").write_text("# Test 1\n\nContent of test 1")
            (docs_dir / "test2.md").write_text("# Test 2\n\nContent of test 2")
            (docs_dir / "no_header.md").write_text("Just content without header")

            yield docs_dir

    @pytest.fixture
    def service(self, temp_docs_dir, mock_markdown_processor):
        """Create a DocumentationService instance for testing."""
        return DocumentationService(temp_docs_dir, mock_markdown_processor)

    def test_init(self, temp_docs_dir, mock_markdown_processor):
        """Test DocumentationService initialization."""
        service = DocumentationService(temp_docs_dir, mock_markdown_processor)
        assert service.docs_dir == temp_docs_dir
        assert service.markdown_processor == mock_markdown_processor

    @pytest.mark.asyncio
    async def test_get_file_list_success(self, service, temp_docs_dir):
        """Test getting file list successfully."""
        files = await service.get_file_list()

        assert len(files) == 3
        assert all(isinstance(f, dict) for f in files)

        # Check required fields
        for file_info in files:
            assert "name" in file_info
            assert "stem" in file_info
            assert "size" in file_info
            assert "modified" in file_info
            assert "title" in file_info

        # Check sorting by name
        names = [f["name"] for f in files]
        assert names == sorted(names)

    @pytest.mark.asyncio
    async def test_get_file_list_nonexistent_dir(self, mock_markdown_processor):
        """Test getting file list from nonexistent directory."""
        nonexistent_dir = Path("/nonexistent/directory")
        service = DocumentationService(nonexistent_dir, mock_markdown_processor)

        files = await service.get_file_list()
        assert files == []

    @pytest.mark.asyncio
    async def test_get_file_list_empty_dir(self, mock_markdown_processor):
        """Test getting file list from empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir)
            service = DocumentationService(empty_dir, mock_markdown_processor)

            files = await service.get_file_list()
            assert files == []

    @pytest.mark.asyncio
    async def test_get_file_list_with_error_files(self, mock_markdown_processor):
        """Test getting file list when some files have errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)

            # Create valid file
            (docs_dir / "valid.md").write_text("# Valid File")

            # Create file that will cause permission error
            problem_file = docs_dir / "problem.md"
            problem_file.write_text("# Problem File")

            service = DocumentationService(docs_dir, mock_markdown_processor)

            # Mock file stat to raise exception for problem file
            original_stat = Path.stat

            def mock_stat(self, follow_symlinks=True):
                if self.name == "problem.md":
                    raise PermissionError("Permission denied")
                return original_stat(self, follow_symlinks=follow_symlinks)

            with patch.object(Path, "stat", mock_stat):
                with patch("server.services.docs.logger") as mock_logger:
                    files = await service.get_file_list()

                    # Should return only valid file
                    assert len(files) == 1
                    assert files[0]["name"] == "valid.md"

                    # Should log warning
                    mock_logger.warning.assert_called_once()
                    mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_title_when_header_present(self, service):
        """Test extracting title from file with H1 header."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Main Title\n\nSome content\n## Subtitle")
            temp_path = Path(f.name)

        try:
            title = await service.extract_title(temp_path)
            assert title == "Main Title"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_extract_title_when_no_header(self, service):
        """Test extracting title from file without H1 header."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Just some content\nNo headers here")
            temp_path = Path(f.name)

        try:
            title = await service.extract_title(temp_path)
            # Should use filename as fallback
            expected = temp_path.stem.replace("_", " ").replace("-", " ").title()
            assert title == expected
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_extract_title_when_header_after_limit(self, service):
        """Test extracting title when header appears after line limit."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            # Write more than 10 lines before header
            for i in range(12):
                f.write(f"Line {i}\n")
            f.write("# Late Header\n")
            temp_path = Path(f.name)

        try:
            title = await service.extract_title(temp_path)
            # Should use filename as fallback since header is too late
            expected = temp_path.stem.replace("_", " ").replace("-", " ").title()
            assert title == expected
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_extract_title_when_file_open_raises(self, service):
        """Test extracting title when file cannot be read."""
        nonexistent_file = Path("/nonexistent/file.md")
        title = await service.extract_title(nonexistent_file)
        assert title == "File"

    @pytest.mark.asyncio
    async def test_extract_title_with_unicode_characters(self, service):
        """Test extracting title with unicode characters."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Unicode Title 🚀 with café\n\nContent")
            temp_path = Path(f.name)

        try:
            title = await service.extract_title(temp_path)
            assert title == "Unicode Title 🚀 with café"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_get_file_content_success(self, service):
        """Test getting file content successfully."""
        html_content, title = await service.get_file_content("test1.md")

        assert html_content == "<h1>Test HTML</h1><p>Content</p>"
        assert title == "Test 1"

        # Verify markdown processor was called
        service.markdown_processor.process_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_file_content_without_extension(self, service):
        """Test getting file content without .md extension."""
        html_content, title = await service.get_file_content("test1")

        assert html_content == "<h1>Test HTML</h1><p>Content</p>"
        assert title == "Test 1"

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, service):
        """Test getting content for non-existent file."""
        with pytest.raises(HTTPException) as exc_info:
            await service.get_file_content("nonexistent.md")

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_file_content_directory(self, service, temp_docs_dir):
        """Test getting content when filename is actually a directory."""
        # Create a directory with .md extension
        dir_path = temp_docs_dir / "directory.md"
        dir_path.mkdir()

        with pytest.raises(HTTPException) as exc_info:
            await service.get_file_content("directory.md")

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_file_content_processing_error(self, service):
        """Test getting content when markdown processing fails."""
        service.markdown_processor.process_file.side_effect = Exception("Processing error")

        with pytest.raises(HTTPException) as exc_info:
            await service.get_file_content("test1.md")

        assert exc_info.value.status_code == 500
        assert "Error processing documentation file" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_file_content_hash_calculation(self, service, temp_docs_dir):
        """Test that content hash is calculated correctly for caching."""
        # First call
        await service.get_file_content("test1.md")

        # Verify hash was calculated and passed to processor
        args, kwargs = service.markdown_processor.process_file.call_args
        file_path, content_hash = args

        assert isinstance(content_hash, int)
        assert file_path.endswith("test1.md")

    @pytest.mark.asyncio
    async def test_get_file_content_logging_on_error(self, service):
        """Test that processing errors are logged."""
        service.markdown_processor.process_file.side_effect = Exception("Test error")

        with patch("server.services.docs.logger") as mock_logger:
            with pytest.raises(HTTPException):
                await service.get_file_content("test1.md")

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_title_handles_constants_fallback(self, service):
        """Test that title extraction respects defined constants."""
        from server.services.docs import TITLE_EXTRACTION_MAX_LINES

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            # Write exactly at the limit
            for i in range(TITLE_EXTRACTION_MAX_LINES):
                f.write(f"Line {i}\n")
            f.write("# Header at limit\n")
            temp_path = Path(f.name)

        try:
            title = await service.extract_title(temp_path)
            # Should use filename as fallback since we hit the limit
            expected = temp_path.stem.replace("_", " ").replace("-", " ").title()
            assert title == expected
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_get_file_list_file_metadata(self, service, temp_docs_dir):
        """Test that file metadata is correctly populated."""
        files = await service.get_file_list()

        for file_info in files:
            assert isinstance(file_info["name"], str)
            assert file_info["name"].endswith(".md")
            assert isinstance(file_info["stem"], str)
            assert not file_info["stem"].endswith(".md")
            assert isinstance(file_info["size"], int)
            assert file_info["size"] > 0
            assert isinstance(file_info["modified"], int)
            assert file_info["modified"] > 0
            assert isinstance(file_info["title"], str)
            assert len(file_info["title"]) > 0
