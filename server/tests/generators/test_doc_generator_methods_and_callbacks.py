"""Tests for doc generator methods and callbacks details branches."""

from types import SimpleNamespace

from server.generators.doc_generator import AppDaemonDocGenerator
from server.parsers.appdaemon_parser import (
    ParsedFile,
    ClassInfo,
    MethodInfo,
)


def make_parsed_with_methods(tmp_path):
    methods = [
        MethodInfo(
            name="initialize",
            args=["self"],
            decorators=[],
            docstring=None,
            is_callback=False,
            line_number=1,
            source_code="def initialize(): pass",
        ),
        MethodInfo(
            name="on_event",
            args=["self", "entity", "attribute", "old", "new", "kwargs"],
            decorators=[],
            docstring=None,
            is_callback=True,
            line_number=2,
            source_code="def on_event(): pass",
            actions=[],
            conditional_count=0,
            loop_count=0,
            notification_count=0,
            device_action_count=0,
        ),
    ]
    cls = ClassInfo(
        name="C",
        base_classes=[],
        docstring=None,
        methods=methods,
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
    return ParsedFile(
        file_path=str(tmp_path / "c.py"), imports=[], classes=[cls], constants_used=set(), module_docstring=""
    )


def test_methods_details_lists_include_initialize_and_callbacks(tmp_path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    pf = make_parsed_with_methods(tmp_path)

    details = gen._get_methods_details(pf)
    assert "initialize()" in details
    # Ensure callbacks included in details list
    assert "on_event()" in details


def test_callbacks_details_include_entities_when_present(tmp_path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    pf = make_parsed_with_methods(tmp_path)

    # Attach a listener to link entity to callback for branch coverage
    cls = pf.classes[0]
    listener = SimpleNamespace(callback_method="on_event", entity="sensor.x")
    cls.state_listeners = [listener]

    details = gen._get_callbacks_details(pf)
    assert "on_event()" in details
    assert "sensor.x" in details
