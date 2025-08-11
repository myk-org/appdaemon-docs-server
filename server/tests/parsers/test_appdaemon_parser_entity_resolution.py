"""Tests for resolving code constants to real entity ids in parser."""

import textwrap
from pathlib import Path

from server.parsers.appdaemon_parser import AppDaemonParser


def write_file(path: Path, content: str) -> Path:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_constant_value_map_and_resolution(tmp_path: Path):
    # Define constants in module and use them in listeners and service calls
    py = write_file(
        tmp_path / "m.py",
        """
        Home = type("X", (), {})()
        Home.Kitchen = type("Y", (), {})()
        Home.Kitchen.Light = "light.kitchen"
        Persons = type("P", (), {})()
        Persons.Alice = type("PA", (), {})()
        Persons.Alice.telegram = "notify.telegram"

        class A:
            def initialize(self):
                self.listen_state(self.on, Home.Kitchen.Light)

            def on(self, entity, attribute, old, new, kwargs):
                self.call_service("homeassistant.turn_on", entity_id=Home.Kitchen.Light)
        """,
    )

    parser = AppDaemonParser()
    pf = parser.parse_file(py)

    # Map is extracted
    assert pf.constant_value_map.get("Home.Kitchen.Light") == "light.kitchen"
    # Entity in listener resolved
    cls = pf.classes[0]
    assert cls.state_listeners[0].entity == "light.kitchen"
    # Service call entity resolved
    assert any(sc.entity_id == "light.kitchen" for sc in cls.service_calls)
