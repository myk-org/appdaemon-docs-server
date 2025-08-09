"""Edge-case coverage for AppDaemonDocGenerator internals."""

from pathlib import Path

from server.generators.doc_generator import AppDaemonDocGenerator
from server.parsers.appdaemon_parser import (
    ParsedFile,
    ClassInfo,
    MethodInfo,
    AppDependency,
    ErrorHandlingPattern,
)


def test_generate_architecture_diagram_wrapper(tmp_path: Path):
    # Architecture diagram generation method was removed; ensure generator can still operate
    gen = AppDaemonDocGenerator(str(tmp_path))
    pf = ParsedFile(file_path=str(tmp_path / "a.py"), imports=[], classes=[], constants_used=set(), module_docstring="")
    overview = gen._generate_technical_overview(pf)
    assert "## Technical Overview" in overview


def test_app_dependencies_section(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    deps = [
        AppDependency(app_name="app1", module_name="m1", class_name="C1"),
        AppDependency(app_name="app2", module_name="m2", class_name="C2", dependencies=["app1"]),
    ]
    pf = ParsedFile(
        file_path=str(tmp_path / "x.py"),
        imports=[],
        classes=[],
        constants_used=set(),
        module_docstring="",
        app_dependencies=deps,
    )
    out = gen._generate_app_dependencies_section(pf)
    assert "App Dependencies" in out
    assert "app1" in out and "app2" in out


def test_empty_sections_return_empty(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    pf = ParsedFile(
        file_path=str(tmp_path / "x.py"),
        imports=[],
        classes=[],
        constants_used=set(),
        module_docstring="",
        error_handling_patterns=ErrorHandlingPattern(),
    )
    # Error handling empty returns empty as well
    assert gen._generate_error_handling_section(pf) == ""


def test_generate_enhanced_api_docs_helper_method_branch(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    cls = ClassInfo(
        name="X",
        base_classes=[],
        docstring=None,
        methods=[
            MethodInfo(
                name="helper",
                args=["self", "a"],
                decorators=[],
                docstring=None,
                is_callback=False,
                line_number=1,
                source_code="def helper(a): pass",
                actions=[],
                conditional_count=0,
                loop_count=0,
                notification_count=0,
                device_action_count=0,
            )
        ],
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
    _ = ParsedFile(
        file_path=str(tmp_path / "x.py"), imports=[], classes=[cls], constants_used=set(), module_docstring=""
    )
    out = gen._generate_class_documentation(cls)
    assert "Helper method" in out


def test_generate_logic_flow_diagrams_no_callbacks(tmp_path: Path):
    gen = AppDaemonDocGenerator(str(tmp_path))
    pf = ParsedFile(file_path=str(tmp_path / "x.py"), imports=[], classes=[], constants_used=set(), module_docstring="")
    out = gen._generate_logic_flow_diagrams(pf)
    assert "## Logic Flow Diagram" in out
