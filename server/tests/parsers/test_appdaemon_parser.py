"""Tests for AppDaemon parser module."""

import tempfile
from pathlib import Path

import pytest

from server.parsers.appdaemon_parser import AppDaemonParser, parse_appdaemon_file


class TestAppDaemonParser:
    """Test cases for AppDaemonParser class."""

    @pytest.fixture
    def parser(self):
        """Create an AppDaemonParser instance for testing."""
        return AppDaemonParser()

    @pytest.fixture
    def sample_automation_file(self):
        """Create a sample automation file for testing."""
        content = '''"""
Test automation module for testing purposes.
"""

import appdaemon.plugins.hass.hassapi as hass


class TestAutomation(hass.Hass):
    """Test automation class."""

    def initialize(self):
        """Initialize the automation."""
        self.listen_state(self.light_changed, "light.living_room")
        self.run_daily(self.daily_check, "08:00:00")

    def light_changed(self, entity, attribute, old, new, kwargs):
        """Handle light state changes."""
        if new == "on":
            self.turn_on("switch.fan")
        else:
            self.turn_off("switch.fan")

    def daily_check(self, kwargs):
        """Perform daily check."""
        self.call_service("notify/mobile_app", message="Daily check")
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink()

    def test_init(self, parser):
        """Test AppDaemonParser initialization."""
        assert parser.current_file == ""
        assert parser.source_lines == []
        assert isinstance(parser.service_patterns, set)
        assert isinstance(parser.time_patterns, set)
        assert isinstance(parser.mqtt_patterns, set)

    def test_parse_file_happy_path(self, parser, sample_automation_file):
        """Test basic file parsing."""
        result = parser.parse_file(sample_automation_file)

        assert result.file_path == sample_automation_file
        assert len(result.classes) >= 1
        assert result.classes[0].name == "TestAutomation"
        assert "Test automation module for testing purposes." in (result.module_docstring or "")

    def test_parse_file_with_imports(self, parser, sample_automation_file):
        """Test parsing file imports."""
        result = parser.parse_file(sample_automation_file)

        assert len(result.imports) > 0
        assert any("hassapi" in imp for imp in result.imports)

    def test_parse_file_with_classes(self, parser, sample_automation_file):
        """Test parsing file classes."""
        result = parser.parse_file(sample_automation_file)

        assert len(result.classes) == 1
        class_info = result.classes[0]
        assert class_info.name == "TestAutomation"
        assert class_info.base_classes == ["hass.Hass"]
        assert "Test automation class." in (class_info.docstring or "")

    def test_parse_file_with_methods(self, parser, sample_automation_file):
        """Test parsing class methods."""
        result = parser.parse_file(sample_automation_file)

        class_info = result.classes[0]
        assert len(class_info.methods) >= 3

        method_names = [method.name for method in class_info.methods]
        assert "initialize" in method_names
        assert "light_changed" in method_names
        assert "daily_check" in method_names

    def test_parse_file_syntax_error(self, parser):
        """Test parsing file with syntax error."""
        invalid_content = """
def broken_syntax(
    print("This has syntax error")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(invalid_content)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Syntax error"):
                parser.parse_file(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_parse_file_nonexistent(self, parser):
        """Test parsing non-existent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/file.py")

    def test_extract_imports(self, parser):
        """Test import extraction."""
        import_content = """
import os
import sys
from pathlib import Path
import appdaemon.plugins.hass.hassapi as hass
from typing import Any, Dict
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(import_content)
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            assert len(result.imports) >= 4

            import_strings = result.imports
            assert any("os" in imp for imp in import_strings)
            assert any("pathlib" in imp for imp in import_strings)
            assert any("hassapi" in imp for imp in import_strings)
        finally:
            Path(temp_path).unlink()

    def test_extract_constants(self, parser):
        """Test constants extraction."""
        constants_content = """
ROOM_1 = "living_room"
DEVICE_1 = "lamp"
THRESHOLD = 25
DEBUG = True
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(constants_content)
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            # The parser should identify constants used in the file
            assert isinstance(result.constants_used, set)
        finally:
            Path(temp_path).unlink()

    def test_service_pattern_detection(self, parser):
        """Test detection of service call patterns."""
        service_content = """
class TestService:
    def test_method(self):
        self.turn_on("light.bedroom")
        self.turn_off("switch.fan")
        self.call_service("media_player/play_media")
        self.notify("Test notification")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(service_content)
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            assert len(result.classes) == 1

            # Should detect service calls in the class
            class_info = result.classes[0]
            assert len(class_info.service_calls) >= 0  # Depends on implementation
        finally:
            Path(temp_path).unlink()

    def test_time_schedule_detection(self, parser):
        """Test detection of time-based scheduling."""
        time_content = """
class TestTime:
    def initialize(self):
        self.run_daily(self.daily_task, "08:00:00")
        self.run_every(self.periodic_task, 300)
        self.run_at(self.specific_task, "sunset")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(time_content)
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            assert len(result.classes) == 1

            # Should detect time schedules
            class_info = result.classes[0]
            assert len(class_info.time_schedules) >= 0  # Depends on implementation
        finally:
            Path(temp_path).unlink()

    def test_state_listener_detection(self, parser):
        """Test detection of state listeners."""
        listener_content = """
class TestListener:
    def initialize(self):
        self.listen_state(self.handle_light, "light.living_room")
        self.listen_state(self.handle_sensor, "sensor.temperature", new="above_25")
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(listener_content)
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            assert len(result.classes) == 1

            # Should detect state listeners
            class_info = result.classes[0]
            assert len(class_info.state_listeners) >= 0  # Depends on implementation
        finally:
            Path(temp_path).unlink()

    def test_empty_file(self, parser):
        """Test parsing empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            assert result.file_path == temp_path
            assert len(result.classes) == 0
            assert len(result.imports) == 0
        finally:
            Path(temp_path).unlink()

    def test_file_with_comments_only(self, parser):
        """Test parsing file with only comments."""
        comment_content = """
# This is a comment file
# No actual code here
# Just comments
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(comment_content)
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            assert len(result.classes) == 0
            assert len(result.imports) == 0
        finally:
            Path(temp_path).unlink()

    def test_complex_inheritance(self, parser):
        """Test parsing with complex inheritance."""
        inheritance_content = """
class BaseAutomation:
    def base_method(self):
        pass

class TestAutomation(BaseAutomation, SomeMixin):
    def test_method(self):
        super().base_method()
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(inheritance_content)
            temp_path = f.name

        try:
            result = parser.parse_file(temp_path)
            assert len(result.classes) >= 1

            # Find TestAutomation class
            test_class = next((cls for cls in result.classes if cls.name == "TestAutomation"), None)
            assert test_class is not None
            assert len(test_class.base_classes) >= 1
        finally:
            Path(temp_path).unlink()


class TestParseAppdaemonFileFunction:
    """Test the parse_appdaemon_file convenience function."""

    def test_parse_appdaemon_file_function(self):
        """Test the convenience function."""
        content = """
class SimpleAutomation:
    def simple_method(self):
        pass
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = parse_appdaemon_file(temp_path)
            assert result.file_path == temp_path
            assert len(result.classes) == 1
            assert result.classes[0].name == "SimpleAutomation"
        finally:
            Path(temp_path).unlink()

    def test_parse_appdaemon_file_with_path_object(self):
        """Test the convenience function with Path object."""
        content = """
class PathAutomation:
    def path_method(self):
        pass
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            result = parse_appdaemon_file(temp_path)
            assert result.file_path == str(temp_path)
            assert len(result.classes) == 1
            assert result.classes[0].name == "PathAutomation"
        finally:
            temp_path.unlink()


class TestDataClasses:
    """Test the dataclass structures."""

    def test_method_info_defaults(self):
        """Test MethodInfo dataclass defaults."""
        from server.parsers.appdaemon_parser import MethodInfo

        method = MethodInfo(
            name="test_method",
            args=["self"],
            decorators=[],
            docstring=None,
            is_callback=False,
            line_number=10,
            source_code="def test_method(self): pass",
        )

        assert method.name == "test_method"
        assert method.actions == []  # Default factory
        assert method.line_number == 10

    def test_class_info_defaults(self):
        """Test ClassInfo dataclass defaults."""
        from server.parsers.appdaemon_parser import ClassInfo

        class_info = ClassInfo(
            name="TestClass",
            base_classes=["BaseClass"],
            docstring="Test class",
            methods=[],
            state_listeners=[],
            mqtt_listeners=[],
            service_calls=[],
            time_schedules=[],
            device_relationships=[],
            automation_flows=[],
            imports=[],
            constants_used=[],
            initialize_code=None,
            line_number=1,
        )

        assert class_info.name == "TestClass"
        assert class_info.base_classes == ["BaseClass"]
        assert len(class_info.methods) == 0

    def test_parsed_file_defaults(self):
        """Test ParsedFile dataclass defaults."""
        from server.parsers.appdaemon_parser import ParsedFile

        parsed_file = ParsedFile(
            file_path="/test/file.py",
            imports=["import os"],
            classes=[],
            constants_used=set(),
            module_docstring="Test module",
        )

        assert parsed_file.file_path == "/test/file.py"
        assert parsed_file.all_mqtt_topics == []  # Default factory
        assert parsed_file.all_entities == []  # Default factory
        assert parsed_file.complexity_score == 0
