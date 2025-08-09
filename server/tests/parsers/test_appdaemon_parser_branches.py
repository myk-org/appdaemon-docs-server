"""Branch tests for AppDaemonParser focusing on configuration and extraction paths."""

import textwrap
from pathlib import Path

from server.parsers.appdaemon_parser import AppDaemonParser


def write_file(path: Path, content: str) -> Path:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_extract_app_dependencies_handles_non_mapping_root(tmp_path: Path):
    # Create a non-dict apps.yaml (list) to exercise the warning branch
    apps_yaml = write_file(tmp_path / "apps.yaml", "- not-a-mapping\n- still-not\n")
    parser = AppDaemonParser(apps_yaml)

    # Create a simple module file
    py = write_file(
        tmp_path / "m.py",
        """
        class X:
            def initialize(self):
                pass
        """,
    )

    # Should parse without raising and dependencies should be empty
    pf = parser.parse_file(py)
    assert pf.app_dependencies == []


def test_parse_file_collects_entities_topics_services(tmp_path: Path):
    apps_yaml = write_file(tmp_path / "apps.yaml", "app1:\n  module: m\n  class: X\n")
    parser = AppDaemonParser(apps_yaml)

    py = write_file(
        tmp_path / "m.py",
        """
        class X:
            def initialize(self):
                self.listen_state(self.on, "sensor.temp", new="on", duration=5)
                self.listen_event(self.on_mqtt, namespace="mqtt", topic="t/1")
                self.run_every(self.tick, 10, 10)

            def on(self, entity, attribute, old, new, kwargs):
                self.turn_on("light.kitchen")
                self.call_service("notify.notify", entity_id="light.kitchen")
        """,
    )

    pf = parser.parse_file(py)

    # Aggregates
    assert "sensor.temp" in pf.all_entities
    assert "t/1" in pf.all_mqtt_topics
    assert any(s.startswith("homeassistant.") or s.startswith("notify.") for s in pf.all_service_calls)
