"""Branch coverage tests for AppDaemonDocGenerator internals."""

from pathlib import Path

from server.generators.doc_generator import AppDaemonDocGenerator
from server.parsers.appdaemon_parser import (
    ParsedFile,
    ClassInfo,
    MethodInfo,
    StateListener,
    ServiceCall,
    TimeSchedule,
    DeviceRelationship,
    AutomationFlow,
    MethodAction,
)


def build_rich_class() -> ClassInfo:
    methods = [
        MethodInfo(
            name="initialize",
            args=["self"],
            decorators=[],
            docstring="init",
            is_callback=False,
            line_number=1,
            source_code="def initialize(): pass",
            actions=[],
            conditional_count=0,
            loop_count=0,
            notification_count=0,
            device_action_count=0,
        ),
        MethodInfo(
            name="on_change",
            args=["self", "entity", "attribute", "old", "new", "kwargs"],
            decorators=[],
            docstring="cb",
            is_callback=True,
            line_number=2,
            source_code="def on_change(): pass",
            actions=[
                MethodAction(action_type="logging", description="log", line_number=3),
            ],
            conditional_count=0,
            loop_count=0,
            notification_count=0,
            device_action_count=0,
        ),
        MethodInfo(
            name="helper",
            args=["self"],
            decorators=["@dec"],
            docstring=None,
            is_callback=False,
            line_number=4,
            source_code="def helper(): pass",
            actions=[],
            conditional_count=0,
            loop_count=0,
            notification_count=0,
            device_action_count=0,
        ),
    ]
    listeners = [
        StateListener(
            callback_method="on_change",
            entity="sensor.x",
            old_state="off",
            new_state="on",
            duration=5,
            kwargs={"extra": 1},
            line_number=5,
        )
    ]
    services = [
        ServiceCall(
            service_domain="light",
            service_name="turn_on",
            entity_id="light.kitchen",
            data={"brightness": 100},
            line_number=6,
            method_name="helper",
        )
    ]
    schedules = [
        TimeSchedule(
            callback_method="tick",
            schedule_type="run_every",
            time_spec=10,
            kwargs={},
            line_number=7,
            interval=10,
            delay=1,
        )
    ]
    relationships = [
        DeviceRelationship(
            trigger_entity="sensor.x",
            target_entity="light.kitchen",
            relationship_type="controls",
            line_number=8,
            condition="x>1",
            method_name="on_change",
        )
    ]
    flows = [
        AutomationFlow(
            flow_type="conditional",
            conditions=["x>1"],
            actions=["turn_on"],
            entities_involved=["light.kitchen"],
            line_number=9,
            method_name="on_change",
        )
    ]
    return ClassInfo(
        name="Rich",
        base_classes=["hass.Hass"],
        docstring="Doc",
        methods=methods,
        state_listeners=listeners,
        mqtt_listeners=[],
        service_calls=services,
        time_schedules=schedules,
        device_relationships=relationships,
        automation_flows=flows,
        imports=[],
        constants_used=[],
        initialize_code=None,
        line_number=1,
    )


def test_generate_class_documentation_rich_sections(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    cls = build_rich_class()
    out = gen._generate_class_documentation(cls)
    # Hit various sections
    assert "### State Listeners" in out
    assert "### Time Schedules" in out
    assert "### Service Calls" in out
    assert "### Device Relationships" in out
    assert "### Automation Flows" in out
    assert "### Methods" in out
    assert "Decorators" in out


def test_generate_configuration_section_groups_constants(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    pf = ParsedFile(
        file_path=str(tmp_path / "f.py"),
        imports=[],
        classes=[],
        constants_used={"Home.Kitchen.Light", "Persons.Alice.telegram", "Other"},
        module_docstring="",
    )
    out = gen._generate_configuration_section(pf)
    assert "## Configuration" in out
    # Category headings emitted
    assert "#### Home" in out or "#### Persons" in out


def test_generate_logic_flow_diagrams_with_callbacks(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    cls = build_rich_class()
    pf = ParsedFile(
        file_path=str(tmp_path / "f.py"),
        imports=[],
        classes=[cls],
        constants_used=set(),
        module_docstring="",
    )
    out = gen._generate_logic_flow_diagrams(pf)
    # Should include a Cytoscape container when callbacks with actions exist
    assert 'class="cytoscape-diagram"' in out


def test_initialization_details_multiple_sections(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    cls = build_rich_class()
    # Add a run_daily schedule to vary branches
    cls.time_schedules.append(
        TimeSchedule(
            callback_method="daily",
            schedule_type="run_daily",
            time_spec="08:00:00",
            kwargs={},
            line_number=10,
            interval=None,
            delay=None,
        )
    )
    pf = ParsedFile(
        file_path=str(tmp_path / "f.py"),
        imports=[],
        classes=[cls],
        constants_used=set(),
        module_docstring="",
    )
    details = gen._get_initialization_details(pf)
    assert "State listeners" in details or "Time schedules" in details
