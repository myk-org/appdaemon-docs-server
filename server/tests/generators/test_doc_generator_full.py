"""High-coverage tests for AppDaemonDocGenerator using synthetic ParsedFile."""

from server.generators.doc_generator import AppDaemonDocGenerator
from server.parsers.appdaemon_parser import (
    ParsedFile,
    ClassInfo,
    MethodInfo,
    StateListener,
    MQTTListener,
    ServiceCall,
    TimeSchedule,
    DeviceRelationship,
    AutomationFlow,
    PerformancePattern,
    MethodAction,
    PersonCentricPattern,
    HelperInjectionPattern,
    ErrorHandlingPattern,
    ConstantHierarchy,
)


def build_method(name: str, is_callback: bool = False) -> MethodInfo:
    # Create a method with multiple actions to exercise summaries and flow
    actions = [
        MethodAction(action_type="conditional_logic", description="if", line_number=10),
        MethodAction(
            action_type="device_action", description="turn_on", line_number=11, entities_involved=["Home.Kitchen.Light"]
        ),
        MethodAction(action_type="logging", description="log", line_number=12),
    ]
    perf = PerformancePattern(
        has_timing=True,
        threshold_ms=300,
        start_variable="perf_start",
        log_pattern="[Exec: {perf_time_ms:.1f}ms]",
        alert_pattern=None,
        line_number=9,
    )
    return MethodInfo(
        name=name,
        args=["self", "entity", "attribute", "old", "new", "kwargs"] if is_callback else ["self"],
        decorators=["@decorator"] if not is_callback else [],
        docstring=f"Doc for {name}",
        is_callback=is_callback,
        line_number=5,
        source_code="def x(): pass",
        actions=actions,
        performance_pattern=perf,
        conditional_count=1,
        loop_count=0,
        notification_count=0,
        device_action_count=1,
    )


def fake_parsed_file(tmp_path) -> ParsedFile:
    # Build class info
    listeners = [
        StateListener(
            callback_method="on_change",
            entity="sensor.temp",
            old_state=None,
            new_state="on",
            duration=10,
            kwargs={},
            line_number=1,
        )
    ]
    mqtt = [
        MQTTListener(
            callback_method="on_mqtt",
            topic="home/topic",
            namespace="mqtt",
            kwargs={},
            line_number=2,
            qos=1,
            retain=False,
        )
    ]
    services = [
        ServiceCall(
            service_domain="homeassistant",
            service_name="turn_on",
            entity_id="light.kitchen",
            data={},
            line_number=3,
            method_name="helper",
        )
    ]
    schedules = [
        TimeSchedule(
            callback_method="tick",
            schedule_type="run_every",
            time_spec=10,
            kwargs={},
            line_number=4,
            interval=10,
            delay=None,
        )
    ]
    relationships = [
        DeviceRelationship(
            trigger_entity="sensor.motion",
            target_entity="light.kitchen",
            relationship_type="controls",
            line_number=5,
            condition=None,
            method_name="on_change",
        )
    ]
    flows = [
        AutomationFlow(
            flow_type="conditional",
            conditions=["x>1"],
            actions=["turn_on"],
            entities_involved=["Home.Kitchen.Light"],
            line_number=6,
            method_name="on_change",
        )
    ]

    methods = [build_method("initialize"), build_method("on_change", is_callback=True), build_method("helper")]

    class_info = ClassInfo(
        name="KitchenAutomation",
        base_classes=["hass.Hass"],
        docstring="Class docstring",
        methods=methods,
        state_listeners=listeners,
        mqtt_listeners=mqtt,
        service_calls=services,
        time_schedules=schedules,
        device_relationships=relationships,
        automation_flows=flows,
        imports=[],
        constants_used=["Home.Kitchen.Light", "Persons.Alice.telegram"],
        initialize_code="self.listen_state(self.on_change, 'sensor.temp')",
        line_number=1,
    )

    person = PersonCentricPattern(
        person_entities=["Persons.Alice"],
        notification_channels=["Persons.Alice.telegram"],
        presence_detection=["Persons.Alice.tracker"],
        device_tracking=["Persons.Alice.phone"],
        personalized_settings=["Persons.Alice.good_night"],
    )
    helpers = HelperInjectionPattern(
        has_helpers_injection=True,
        helper_methods_used=["send_notify", "log_action"],
        initialization_helpers=["helpers"],
        dependency_injection=["AppDaemon dependency injection"],
    )
    errors = ErrorHandlingPattern(
        has_try_catch=True,
        error_notification=True,
        recovery_mechanisms=["retry mechanism"],
        alert_patterns=["warning"],
        logging_on_error=True,
    )
    hierarchy = ConstantHierarchy(
        hierarchical_constants={
            "Home": ["Home.Kitchen.Light"],
            "Persons": ["Persons.Alice.telegram"],
        },
        person_constants=["Persons.Alice.telegram"],
        device_constants=["Home.Kitchen.Light"],
        action_constants=["Actions.Some.Action"],
        general_constants=["General.Config"],
    )

    pf = ParsedFile(
        file_path=str(tmp_path / "kitchen.py"),
        imports=["from x import y"],
        classes=[class_info],
        constants_used={"Home.Kitchen.Light", "Persons.Alice.telegram"},
        module_docstring="Module docstring",
        all_mqtt_topics=["home/topic"],
        all_entities=["sensor.temp"],
        all_service_calls=["homeassistant.turn_on"],
        complexity_score=5,
        app_dependencies=[],
        person_centric_patterns=person,
        helper_injection_patterns=helpers,
        error_handling_patterns=errors,
        constant_hierarchy=hierarchy,
    )
    return pf


def test_generate_documentation_with_all_sections(tmp_path):
    generator = AppDaemonDocGenerator(str(tmp_path))
    pf = fake_parsed_file(tmp_path)

    md = generator.generate_documentation(pf)

    # Check for many sections to ensure breadth of execution
    assert "## Technical Overview" in md
    assert "## Logic Flow Diagram" in md
    assert "## API Documentation" in md
    assert "## Configuration" in md
    assert "## Integration Points" in md
    assert "## Person-Centric Automation" in md
    assert "## Helper Injection Patterns" in md
    assert "## Error Handling & Recovery" in md
    assert "## Configuration Hierarchy" in md
