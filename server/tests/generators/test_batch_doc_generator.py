"""Tests for batch documentation generator."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from server.generators.batch_doc_generator import BatchDocGenerator


class TestBatchDocGenerator:
    """Test cases for BatchDocGenerator class."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            apps_dir = temp_path / "apps"
            docs_dir = temp_path / "docs"
            apps_dir.mkdir()

            yield apps_dir, docs_dir

    @pytest.fixture
    def generator(self, temp_dirs):
        """Create a BatchDocGenerator instance for testing."""
        apps_dir, docs_dir = temp_dirs
        return BatchDocGenerator(apps_dir, docs_dir)

    def test_init_with_paths(self, temp_dirs):
        """Test BatchDocGenerator initialization with Path objects."""
        apps_dir, docs_dir = temp_dirs
        generator = BatchDocGenerator(apps_dir, docs_dir)

        assert generator.apps_dir == apps_dir
        assert generator.docs_dir == docs_dir
        assert docs_dir.exists()  # Should be created
        assert generator.doc_generator is not None

    def test_init_with_strings(self, temp_dirs):
        """Test BatchDocGenerator initialization with string paths."""
        apps_dir, docs_dir = temp_dirs
        generator = BatchDocGenerator(str(apps_dir), str(docs_dir))

        assert generator.apps_dir == apps_dir
        assert generator.docs_dir == docs_dir
        assert docs_dir.exists()  # Should be created

    def test_find_automation_files_empty_dir(self, generator):
        """Test finding automation files in empty directory."""
        files = generator.find_automation_files()
        assert files == []

    def test_find_automation_files_with_automation_files(self, generator, temp_dirs):
        """Test finding automation files with valid automation files."""
        apps_dir, _ = temp_dirs

        # Create automation files
        (apps_dir / "automation1.py").write_text("# Automation 1")
        (apps_dir / "automation2.py").write_text("# Automation 2")
        (apps_dir / "my_module.py").write_text("# My Module")

        files = generator.find_automation_files()
        assert len(files) == 3
        assert all(f.suffix == ".py" for f in files)
        assert sorted([f.name for f in files]) == ["automation1.py", "automation2.py", "my_module.py"]

    def test_find_automation_files_excludes_infrastructure(self, generator, temp_dirs):
        """Test that infrastructure files are excluded."""
        apps_dir, _ = temp_dirs

        # Create automation files
        (apps_dir / "automation1.py").write_text("# Automation 1")
        (apps_dir / "automation2.py").write_text("# Automation 2")

        # Create infrastructure files (should be excluded)
        (apps_dir / "const.py").write_text("# Constants")
        (apps_dir / "infra.py").write_text("# Infrastructure")
        (apps_dir / "utils.py").write_text("# Utils")
        (apps_dir / "__init__.py").write_text("# Init")
        (apps_dir / "apps.py").write_text("# Apps")
        (apps_dir / "configuration.py").write_text("# Configuration")
        (apps_dir / "secrets.py").write_text("# Secrets")

        # Create non-Python files (should be excluded)
        (apps_dir / "readme.txt").write_text("# Readme")
        (apps_dir / "config.yaml").write_text("# Config")

        files = generator.find_automation_files()
        assert len(files) == 2
        assert sorted([f.name for f in files]) == ["automation1.py", "automation2.py"]

    def test_find_automation_files_returns_sorted(self, generator, temp_dirs):
        """Test that automation files are returned in sorted order."""
        apps_dir, _ = temp_dirs

        # Create files in non-alphabetical order
        (apps_dir / "z_automation.py").write_text("# Z Automation")
        (apps_dir / "a_automation.py").write_text("# A Automation")
        (apps_dir / "m_automation.py").write_text("# M Automation")

        files = generator.find_automation_files()
        file_names = [f.name for f in files]
        assert file_names == sorted(file_names)

    def test_generate_single_file_docs_success(self, generator):
        """Test successful generation of single file documentation."""
        test_file = Path("/tmp/test_automation.py")

        mock_parsed_file = Mock()
        mock_docs = "# Test Documentation\n\nGenerated docs content"

        with patch("server.generators.batch_doc_generator.parse_appdaemon_file", return_value=mock_parsed_file):
            with patch.object(generator.doc_generator, "generate_documentation", return_value=mock_docs):
                docs, success = generator.generate_single_file_docs(test_file)

                assert success is True
                assert docs == mock_docs

    def test_generate_single_file_docs_failure(self, generator):
        """Test handling of errors during single file documentation generation."""
        test_file = Path("/tmp/test_automation.py")

        with patch("server.generators.batch_doc_generator.parse_appdaemon_file", side_effect=Exception("Parse error")):
            docs, success = generator.generate_single_file_docs(test_file)

            assert success is False
            assert "Error Generating Documentation" in docs
            assert str(test_file) in docs
            assert "Parse error" in docs

    def test_generate_all_docs_empty_directory(self, generator):
        """Test generate_all_docs with no automation files."""
        with patch("builtins.print"):  # Suppress print statements
            results = generator.generate_all_docs()

            assert results["total_files"] == 0
            assert results["successful"] == 0
            assert results["failed"] == 0
            assert results["skipped"] == 0
            assert results["generated_files"] == []
            assert results["failed_files"] == []
            assert results["skipped_files"] == []

    def test_generate_all_docs_successful_generation(self, generator, temp_dirs):
        """Test generate_all_docs with successful file generation."""
        apps_dir, docs_dir = temp_dirs

        # Create test automation files
        (apps_dir / "automation1.py").write_text("# Automation 1")
        (apps_dir / "automation2.py").write_text("# Automation 2")

        mock_docs = "# Generated Documentation\n\nContent here"

        with patch.object(generator, "generate_single_file_docs", return_value=(mock_docs, True)):
            with patch("builtins.print"):  # Suppress print statements
                results = generator.generate_all_docs()

                assert results["total_files"] == 2
                assert results["successful"] == 2
                assert results["failed"] == 0
                assert results["skipped"] == 0
                assert len(results["generated_files"]) == 2
                assert results["failed_files"] == []
                assert results["skipped_files"] == []

                # Check that files were actually written
                assert (docs_dir / "automation1.md").exists()
                assert (docs_dir / "automation2.md").exists()
                assert (docs_dir / "automation1.md").read_text() == mock_docs

    def test_generate_all_docs_with_failures(self, generator, temp_dirs):
        """Test generate_all_docs with some file generation failures."""
        apps_dir, docs_dir = temp_dirs

        # Create test automation files
        (apps_dir / "good_automation.py").write_text("# Good Automation")
        (apps_dir / "bad_automation.py").write_text("# Bad Automation")

        def mock_generate_single_file(file_path):
            if "good" in file_path.name:
                return "# Good Documentation", True
            else:
                return "# Error Documentation", False

        with patch.object(generator, "generate_single_file_docs", side_effect=mock_generate_single_file):
            with patch("builtins.print"):  # Suppress print statements
                results = generator.generate_all_docs()

                assert results["total_files"] == 2
                assert results["successful"] == 1
                assert results["failed"] == 1
                assert results["skipped"] == 0
                assert len(results["generated_files"]) == 1
                assert len(results["failed_files"]) == 1

    def test_generate_all_docs_skip_existing(self, generator, temp_dirs):
        """Test generate_all_docs skipping existing documentation files."""
        apps_dir, docs_dir = temp_dirs

        # Create test automation files
        (apps_dir / "automation1.py").write_text("# Automation 1")
        (apps_dir / "automation2.py").write_text("# Automation 2")

        # Create existing documentation file
        (docs_dir / "automation1.md").write_text("# Existing docs")

        mock_docs = "# New Documentation"

        with patch.object(generator, "generate_single_file_docs", return_value=(mock_docs, True)):
            with patch("builtins.print"):  # Suppress print statements
                results = generator.generate_all_docs(force_regenerate=False)

                assert results["total_files"] == 2
                assert results["successful"] == 1  # Only automation2.py
                assert results["failed"] == 0
                assert results["skipped"] == 1  # automation1.py skipped
                assert len(results["skipped_files"]) == 1

    def test_generate_all_docs_force_regenerate(self, generator, temp_dirs):
        """Test generate_all_docs with force_regenerate=True."""
        apps_dir, docs_dir = temp_dirs

        # Create test automation files
        (apps_dir / "automation1.py").write_text("# Automation 1")

        # Create existing documentation file
        existing_content = "# Existing docs"
        (docs_dir / "automation1.md").write_text(existing_content)

        mock_docs = "# New Documentation"

        with patch.object(generator, "generate_single_file_docs", return_value=(mock_docs, True)):
            with patch("builtins.print"):  # Suppress print statements
                results = generator.generate_all_docs(force_regenerate=True)

                assert results["total_files"] == 1
                assert results["successful"] == 1
                assert results["failed"] == 0
                assert results["skipped"] == 0

                # Check that file was overwritten
                assert (docs_dir / "automation1.md").read_text() == mock_docs

    def test_generate_all_docs_with_progress_callback(self, generator, temp_dirs):
        """Test generate_all_docs with progress callback."""
        apps_dir, docs_dir = temp_dirs

        # Create test automation files
        (apps_dir / "automation1.py").write_text("# Automation 1")
        (apps_dir / "automation2.py").write_text("# Automation 2")

        mock_docs = "# Generated Documentation"
        progress_calls = []

        def progress_callback(current, total, filename, stage):
            progress_calls.append((current, total, filename, stage))

        with patch.object(generator, "generate_single_file_docs", return_value=(mock_docs, True)):
            with patch("builtins.print"):  # Suppress print statements
                results = generator.generate_all_docs(progress_callback=progress_callback)

                assert results["successful"] == 2

                # Check that progress callback was called
                assert len(progress_calls) > 0

                # Check specific callback stages
                stages = [call[3] for call in progress_calls]
                assert "checking" in stages
                assert "generating" in stages
                assert "completed" in stages

    def test_generate_all_docs_progress_callback_skip(self, generator, temp_dirs):
        """Test progress callback when files are skipped."""
        apps_dir, docs_dir = temp_dirs

        # Create test automation file
        (apps_dir / "automation1.py").write_text("# Automation 1")

        # Create existing documentation file
        (docs_dir / "automation1.md").write_text("# Existing docs")

        progress_calls = []

        def progress_callback(current, total, filename, stage):
            progress_calls.append((current, total, filename, stage))

        with patch("builtins.print"):  # Suppress print statements
            results = generator.generate_all_docs(force_regenerate=False, progress_callback=progress_callback)

            assert results["skipped"] == 1

            # Check that skipped stage was reported
            stages = [call[3] for call in progress_calls]
            assert "skipped" in stages

    def test_generate_all_docs_output_file_encoding(self, generator, temp_dirs):
        """Test that output files are written with UTF-8 encoding."""
        apps_dir, docs_dir = temp_dirs

        # Create test automation file
        (apps_dir / "automation1.py").write_text("# Automation 1")

        mock_docs = "# Generated Documentation\n\nWith unicode: café 🚀"

        with patch.object(generator, "generate_single_file_docs", return_value=(mock_docs, True)):
            with patch("builtins.print"):  # Suppress print statements
                results = generator.generate_all_docs()

                assert results["successful"] == 1

                # Check that file was written with correct encoding
                output_file = docs_dir / "automation1.md"
                assert output_file.exists()
                content = output_file.read_text(encoding="utf-8")
                assert content == mock_docs
                assert "café 🚀" in content

    def test_docs_directory_creation(self, temp_dirs):
        """Test that docs directory is created if it doesn't exist."""
        apps_dir, docs_dir = temp_dirs

        # Remove docs directory
        if docs_dir.exists():
            docs_dir.rmdir()

        # Create generator - should create docs directory
        BatchDocGenerator(apps_dir, docs_dir)

        assert docs_dir.exists()
        assert docs_dir.is_dir()

    def test_doc_generator_integration(self, generator):
        """Test integration with AppDaemonDocGenerator."""
        # Verify that the doc generator is properly initialized
        assert generator.doc_generator is not None
        assert hasattr(generator.doc_generator, "generate_documentation")

    def test_generate_all_docs_return_structure(self, generator):
        """Test that generate_all_docs returns proper structure even with no files."""
        with patch("builtins.print"):  # Suppress print statements
            results = generator.generate_all_docs()

            # Check all required keys are present
            required_keys = [
                "total_files",
                "successful",
                "failed",
                "skipped",
                "generated_files",
                "failed_files",
                "skipped_files",
            ]
            for key in required_keys:
                assert key in results

            # Check types
            assert isinstance(results["total_files"], int)
            assert isinstance(results["successful"], int)
            assert isinstance(results["failed"], int)
            assert isinstance(results["skipped"], int)
            assert isinstance(results["generated_files"], list)
            assert isinstance(results["failed_files"], list)
            assert isinstance(results["skipped_files"], list)
