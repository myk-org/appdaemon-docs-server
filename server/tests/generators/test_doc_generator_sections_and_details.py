"""Targeted tests for internal sections of AppDaemonDocGenerator."""

from server.generators.doc_generator import AppDaemonDocGenerator
from server.parsers.appdaemon_parser import (
    ParsedFile,
    ClassInfo,
    MethodInfo,
    StateListener,
    MQTTListener,
    TimeSchedule,
)


def make_class_info() -> ClassInfo:
    listeners = [
        StateListener(
            callback_method="on",
            entity="binary_sensor.door",
            old_state=None,
            new_state="on",
            duration=None,
            kwargs={},
            line_number=1,
        )
    ]
    mqtt = [MQTTListener(callback_method="on_mqtt", topic="t", namespace="mqtt", kwargs={}, line_number=2)]
    schedules = [
        TimeSchedule(callback_method="tick", schedule_type="run_in", time_spec=None, kwargs={}, line_number=3, delay=5)
    ]
    methods = [
        MethodInfo(
            name="initialize",
            args=["self"],
            decorators=[],
            docstring="init",
            is_callback=False,
            line_number=1,
            source_code="def initialize(): pass",
        ),
    ]
    return ClassInfo(
        name="Test",
        base_classes=["Base"],
        docstring="Doc",
        methods=methods,
        state_listeners=listeners,
        mqtt_listeners=mqtt,
        service_calls=[],
        time_schedules=schedules,
        device_relationships=[],
        automation_flows=[],
        imports=[],
        constants_used=["Home.Room.Light"],
        initialize_code="self.listen_state(self.on, 'binary_sensor.door')",
        line_number=1,
    )


def test_generate_class_documentation_and_config_section(tmp_path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    cls = make_class_info()
    out = gen._generate_class_documentation(cls)
    assert "### State Listeners" in out
    assert "### MQTT Listeners" in out
    assert "### Time Schedules" in out

    pf = ParsedFile(
        file_path=str(tmp_path / "x.py"),
        imports=[],
        classes=[cls],
        constants_used={"Home.Room.Light"},
        module_docstring="",
    )
    cfg = gen._generate_configuration_section(pf)
    assert "### Required Entities" in cfg


def test_generate_automation_flow_diagram_with_single_class(tmp_path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    cls = make_class_info()
    out = gen._generate_automation_flow_diagram(cls)
    # May be empty if no grouped entities; ensure it returns a string
    assert isinstance(out, str)
