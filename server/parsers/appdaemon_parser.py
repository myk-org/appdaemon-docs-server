"""
AppDaemon Automation Parser

This module parses AppDaemon Python automation files and extracts structured
information about classes, methods, state listeners, MQTT patterns, device
relationships, automation flows, and configuration usage.
It uses AST parsing to safely analyze code without executing it.
"""

import ast
import os
import logging
import re
import yaml  # type: ignore[import-untyped]
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MethodAction:
    """Represents a specific action within a method."""

    action_type: str  # "conditional_logic", "loop_iteration", "notification", "logging", "device_action", "api_call", "performance_timer"
    description: str
    line_number: int
    entities_involved: list[str] = field(default_factory=list)


@dataclass
class PerformancePattern:
    """Information about performance monitoring patterns."""

    has_timing: bool
    threshold_ms: int | None
    start_variable: str | None
    log_pattern: str | None
    alert_pattern: str | None
    line_number: int


@dataclass
class MethodInfo:
    """Information about a method in an AppDaemon class."""

    name: str
    args: list[str]
    decorators: list[str]
    docstring: str | None
    is_callback: bool
    line_number: int
    source_code: str
    # Enhanced analysis
    actions: list[MethodAction] = field(default_factory=list)
    performance_pattern: PerformancePattern | None = None
    conditional_count: int = 0
    loop_count: int = 0
    notification_count: int = 0
    device_action_count: int = 0


@dataclass
class StateListener:
    """Information about a state listener configuration."""

    callback_method: str
    entity: str | None
    old_state: str | None
    new_state: str | None
    duration: int | None
    kwargs: dict[str, Any]
    line_number: int


@dataclass
class MQTTListener:
    """Information about an MQTT listener configuration."""

    callback_method: str
    topic: str | None
    namespace: str | None
    kwargs: dict[str, Any]
    line_number: int
    qos: int | None = None
    retain: bool | None = None


@dataclass
class ServiceCall:
    """Information about a Home Assistant service call."""

    service_domain: str
    service_name: str
    entity_id: str | None
    data: dict[str, Any]
    line_number: int
    method_name: str | None = None  # The method making the call


@dataclass
class TimeSchedule:
    """Information about time-based automation schedules."""

    callback_method: str
    schedule_type: str  # 'run_daily', 'run_at', 'run_every', 'run_in'
    time_spec: str | int | None  # Time specification
    kwargs: dict[str, Any]
    line_number: int
    interval: int | None = None  # For run_every
    delay: int | None = None  # For run_in


@dataclass
class DeviceRelationship:
    """Information about relationships between devices."""

    trigger_entity: str
    target_entity: str
    relationship_type: str  # 'controls', 'monitors', 'triggers'
    line_number: int
    condition: str | None = None
    method_name: str | None = None


@dataclass
class AutomationFlow:
    """Information about automation logic flow."""

    flow_type: str  # 'conditional', 'sequence', 'loop'
    conditions: list[str]
    actions: list[str]
    entities_involved: list[str]
    line_number: int
    method_name: str
    description: str | None = None


@dataclass
class ClassInfo:
    """Information about an AppDaemon automation class."""

    name: str
    base_classes: list[str]
    docstring: str | None
    methods: list[MethodInfo]
    state_listeners: list[StateListener]
    mqtt_listeners: list[MQTTListener]
    service_calls: list[ServiceCall]
    time_schedules: list[TimeSchedule]
    device_relationships: list[DeviceRelationship]
    automation_flows: list[AutomationFlow]
    imports: list[str]
    constants_used: list[str]
    initialize_code: str | None
    line_number: int


@dataclass
class AppDependency:
    """Information about app dependency from apps.yaml."""

    app_name: str
    module_name: str
    class_name: str
    dependencies: list[str] = field(default_factory=list)


@dataclass
class PersonCentricPattern:
    """Information about person-centric automation patterns."""

    person_entities: list[str] = field(default_factory=list)
    notification_channels: list[str] = field(default_factory=list)
    presence_detection: list[str] = field(default_factory=list)
    device_tracking: list[str] = field(default_factory=list)
    personalized_settings: list[str] = field(default_factory=list)


@dataclass
class HelperInjectionPattern:
    """Information about helper injection patterns."""

    has_helpers_injection: bool = False
    helper_methods_used: list[str] = field(default_factory=list)
    initialization_helpers: list[str] = field(default_factory=list)
    dependency_injection: list[str] = field(default_factory=list)


@dataclass
class ErrorHandlingPattern:
    """Information about error handling patterns."""

    has_try_catch: bool = False
    error_notification: bool = False
    recovery_mechanisms: list[str] = field(default_factory=list)
    alert_patterns: list[str] = field(default_factory=list)
    logging_on_error: bool = False


@dataclass
class ConstantHierarchy:
    """Information about hierarchical constant usage."""

    hierarchical_constants: dict[str, list[str]] = field(default_factory=dict)
    person_constants: list[str] = field(default_factory=list)
    device_constants: list[str] = field(default_factory=list)
    action_constants: list[str] = field(default_factory=list)
    general_constants: list[str] = field(default_factory=list)


@dataclass
class ParsedFile:
    """Complete parsed information from an AppDaemon file."""

    file_path: str
    imports: list[str]
    classes: list[ClassInfo]
    constants_used: set[str]
    module_docstring: str | None
    # Aggregated information from all classes
    all_mqtt_topics: list[str] = field(default_factory=list)
    all_entities: list[str] = field(default_factory=list)
    all_service_calls: list[str] = field(default_factory=list)
    complexity_score: int = 0
    # Enhanced analysis results
    app_dependencies: list[AppDependency] = field(default_factory=list)
    person_centric_patterns: PersonCentricPattern = field(default_factory=PersonCentricPattern)
    helper_injection_patterns: HelperInjectionPattern = field(default_factory=HelperInjectionPattern)
    error_handling_patterns: ErrorHandlingPattern = field(default_factory=ErrorHandlingPattern)
    constant_hierarchy: ConstantHierarchy = field(default_factory=ConstantHierarchy)
    # Mapping from code constant path (e.g., "Home.Kitchen.Light") to resolved value (e.g., "light.kitchen")
    constant_value_map: dict[str, str] = field(default_factory=dict)


class AppDaemonParser:
    """Parser for AppDaemon automation Python files."""

    def __init__(self, apps_yaml_path: str | Path | None = None) -> None:
        """Initialize the parser."""
        self.logger = logging.getLogger(__name__)
        self.current_file = ""
        self.source_lines: list[str] = []
        self.apps_yaml_path = Path(apps_yaml_path) if apps_yaml_path else None
        self.apps_config: dict[str, Any] = {}
        self._load_apps_config()
        # Cache for imported module constant maps to avoid re-parsing
        self._module_const_cache: dict[str, dict[str, str]] = {}
        # APPS_DIR root (for locating const.py and other local modules)
        try:
            apps_dir_env = os.getenv("APPS_DIR", "")
        except Exception:
            apps_dir_env = ""
        self._apps_dir: Path | None = (
            Path(os.path.expandvars(os.path.expanduser(apps_dir_env))).resolve() if apps_dir_env else None
        )

        # Enhanced parsing patterns
        self.service_patterns = {
            # AppDaemon service calls
            "turn_on",
            "turn_off",
            "toggle",
            "set_state",
            "set_value",
            "call_service",
            "notify",
            "fire_event",
        }

        self.time_patterns = {"run_daily", "run_at", "run_every", "run_in", "cancel_timer"}

        self.mqtt_patterns = {"listen_event", "mqtt_send", "mqtt_subscribe"}

        # Pre-compiled regex patterns for performance analysis
        self.threshold_patterns = [
            re.compile(r"perf_time_ms\s*>\s*(\d+)"),
            re.compile(r"execution_time\s*>\s*(\d+)"),
            re.compile(r"duration\s*>\s*(\d+)"),
        ]

        self.log_patterns = [
            re.compile(r"\[Exec:.*perf_time.*\]", re.IGNORECASE),
            re.compile(r"Execution time:", re.IGNORECASE),
            re.compile(r"Performance:", re.IGNORECASE),
        ]

    def parse_file(self, file_path: str | Path) -> ParsedFile:
        """
        Parse an AppDaemon automation file.

        Args:
            file_path: Path to the Python file to parse

        Returns:
            ParsedFile containing all extracted information
        """
        file_path = Path(file_path)
        self.current_file = str(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.source_lines = content.splitlines()

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            raise ValueError(f"Syntax error in {file_path}: {e}")

        # Extract module-level information
        module_docstring = ast.get_docstring(tree)
        imports = self._extract_imports(tree)
        classes = []
        constants_used = set()

        # Find all classes in the module
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._parse_class(node)
                classes.append(class_info)
                constants_used.update(class_info.constants_used)

        # Aggregate information from all classes
        all_mqtt_topics = []
        all_entities = []
        all_service_calls = []
        complexity_score = 0

        for class_info in classes:
            # Collect MQTT topics
            for mqtt_listener in class_info.mqtt_listeners:
                if mqtt_listener.topic:
                    all_mqtt_topics.append(mqtt_listener.topic)

            # Collect entities
            for listener in class_info.state_listeners:
                if listener.entity:
                    all_entities.append(listener.entity)

            for relationship in class_info.device_relationships:
                all_entities.extend([relationship.trigger_entity, relationship.target_entity])

            # Collect service calls
            for service_call in class_info.service_calls:
                service_name = f"{service_call.service_domain}.{service_call.service_name}"
                all_service_calls.append(service_name)

            # Calculate complexity score
            complexity_score += (
                len(class_info.methods) * 2
                + len(class_info.state_listeners) * 3
                + len(class_info.mqtt_listeners) * 2
                + len(class_info.time_schedules) * 2
                + len(class_info.automation_flows) * 5
            )

        # Extract constant value assignments at module scope (e.g., Home.X = "domain.entity")
        # and class-nested constants (e.g., class Home: class Kitchen: Light = "light.kitchen")
        # Constants from this module
        local_map = self._extract_constant_value_map(tree)
        local_class_map = self._extract_class_constant_value_map(tree)
        # Constants from imported project modules
        imported_maps = self._extract_imported_constant_maps(file_path=file_path, tree=tree)
        # Constants from APPS_DIR/const.py (global project constants)
        const_map: dict[str, str] = {}
        if self._apps_dir:
            const_py = self._apps_dir / "const.py"
            if const_py.exists():
                try:
                    const_map = self._extract_constant_map_from_path(const_py)
                except Exception:
                    const_map = {}
        # Merge precedence: const.py -> imported -> local -> local class
        merged_map: dict[str, str] = {}
        merged_map.update(const_map)
        for m in imported_maps:
            merged_map.update(m)
        merged_map.update(local_map)
        merged_map.update(local_class_map)
        # Add per-class self.<Nested>.* constants (e.g., self.State.ON -> "on")
        self_scoped_map = self._extract_self_class_constant_value_map(tree)
        merged_map.update(self_scoped_map)
        constant_value_map = merged_map

        # Resolve constants in listeners and service calls using the extracted map
        for class_info in classes:
            # Resolve state listener entity constants
            for listener in class_info.state_listeners:
                if isinstance(listener.entity, str) and listener.entity in constant_value_map:
                    listener.entity = constant_value_map[listener.entity]

            # Resolve service call entity_id constants
            for svc in class_info.service_calls:
                if isinstance(svc.entity_id, str) and svc.entity_id in constant_value_map:
                    svc.entity_id = constant_value_map[svc.entity_id]

                # Resolve service path constants (e.g., Actions.Cover.close -> cover.close_cover)
                combined = f"{svc.service_domain}.{svc.service_name}" if svc.service_domain and svc.service_name else ""
                if combined in constant_value_map:
                    resolved_path = constant_value_map[combined]
                    if isinstance(resolved_path, str):
                        # Accept both "domain.service" and "domain/service"
                        path = resolved_path.replace("/", ".")
                        if "." in path:
                            domain, service = path.split(".", 1)
                            svc.service_domain = domain
                            svc.service_name = service

                # Resolve entity_id inside data payload
                try:
                    if isinstance(svc.data, dict) and "entity_id" in svc.data:
                        ent = svc.data["entity_id"]
                        if isinstance(ent, str) and ent in constant_value_map:
                            svc.data["entity_id"] = constant_value_map[ent]
                        elif isinstance(ent, list):
                            new_list: list[str] = []
                            for item in ent:
                                if isinstance(item, str) and item in constant_value_map:
                                    new_list.append(constant_value_map[item])
                                else:
                                    new_list.append(item)
                            svc.data["entity_id"] = new_list
                except Exception:
                    pass

            # Resolve device relationship entity constants
            for rel in class_info.device_relationships:
                if isinstance(rel.trigger_entity, str) and rel.trigger_entity in constant_value_map:
                    rel.trigger_entity = constant_value_map[rel.trigger_entity]
                if isinstance(rel.target_entity, str) and rel.target_entity in constant_value_map:
                    rel.target_entity = constant_value_map[rel.target_entity]

            # Resolve automation flow entities
            for flow in class_info.automation_flows:
                resolved: list[str] = []
                for ent in flow.entities_involved:
                    if isinstance(ent, str) and ent in constant_value_map:
                        resolved.append(constant_value_map[ent])
                    else:
                        resolved.append(ent)
                flow.entities_involved = resolved

                # Resolve constants inside textual conditions
                if flow.conditions:
                    resolved_conditions: list[str] = []
                    for cond in flow.conditions:
                        cond_resolved = self._resolve_constants_in_text(cond, constant_value_map)
                        cond_natural = self._naturalize_condition(cond_resolved)
                        resolved_conditions.append(cond_natural)
                    flow.conditions = resolved_conditions

                # Resolve constants inside textual actions
                if flow.actions:
                    resolved_actions: list[str] = []
                    for act in flow.actions:
                        resolved_actions.append(self._resolve_constants_in_text(act, constant_value_map))
                    flow.actions = resolved_actions

        # Enhanced analysis
        app_dependencies = self._extract_app_dependencies(file_path)
        person_centric_patterns = self._analyze_person_centric_patterns(classes, constants_used)
        helper_injection_patterns = self._analyze_helper_injection_patterns(classes)
        error_handling_patterns = self._analyze_error_handling_patterns(classes)
        constant_hierarchy = self._analyze_constant_hierarchy(constants_used)

        return ParsedFile(
            file_path=str(file_path),
            imports=imports,
            classes=classes,
            constants_used=constants_used,
            module_docstring=module_docstring,
            all_mqtt_topics=list(set(all_mqtt_topics)),
            all_entities=list(set(all_entities)),
            all_service_calls=list(set(all_service_calls)),
            complexity_score=complexity_score,
            app_dependencies=app_dependencies,
            person_centric_patterns=person_centric_patterns,
            helper_injection_patterns=helper_injection_patterns,
            error_handling_patterns=error_handling_patterns,
            constant_hierarchy=constant_hierarchy,
            constant_value_map=constant_value_map,
        )

    def _extract_self_class_constant_value_map(self, tree: ast.Module) -> dict[str, str]:
        """Extract nested class constants defined inside automation classes and expose them
        under a self.* key space so expressions like self.State.ON can be resolved.

        Example:
            class MyApp:
                class State:
                    ON = "on"
        -> "self.State.ON": "on"
        """
        mapping: dict[str, str] = {}

        def walk_nested(cls: ast.ClassDef, prefix: str) -> None:
            for item in cls.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if (
                            isinstance(target, ast.Name)
                            and isinstance(item.value, ast.Constant)
                            and isinstance(item.value.value, str)
                        ):
                            mapping[f"self.{prefix}.{target.id}"] = item.value.value
                elif isinstance(item, ast.AnnAssign):
                    if (
                        isinstance(item.target, ast.Name)
                        and isinstance(item.value, ast.Constant)
                        and isinstance(item.value.value, str)
                    ):
                        mapping[f"self.{prefix}.{item.target.id}"] = item.value.value
                elif isinstance(item, ast.ClassDef):
                    walk_nested(item, f"{prefix}.{item.name}")

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                # Only nested class scopes under automation classes should be considered; start at one level down
                for inner in node.body:
                    if isinstance(inner, ast.ClassDef):
                        walk_nested(inner, inner.name)

        return mapping

    def _resolve_constants_in_text(self, text: str, mapping: dict[str, str]) -> str:
        """Replace occurrences of constant paths with resolved values inside a text snippet.

        Uses regex word-boundary-like guards to avoid replacing inside larger identifiers.
        """
        try:
            # Replace longer keys first to avoid partial overlaps
            for key in sorted(mapping.keys(), key=len, reverse=True):
                pattern = r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])"
                text = re.sub(pattern, mapping[key], text)
            return text
        except Exception:
            return text

    def _strip_quotes(self, s: str) -> str:
        if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
            return s[1:-1]
        return s

    def _naturalize_condition(self, cond: str) -> str:
        """Convert a resolved condition string into a simple natural sentence."""
        try:
            c = cond.strip()
            # Normalize leading keyword
            lead = ""
            if c.startswith("if "):
                c = c[3:]
                lead = "when "
            elif c.startswith("elif "):
                c = c[5:]
                lead = "or when "

            # For-loops → friendlier phrasing
            m = re.match(r"^for\s+(.*?)\s+in\s*(.*)$", c)
            if m:
                target = m.group(1).strip()
                source = m.group(2).strip()
                if target and source:
                    return f"for each {target} in {source}"
                if target and not source:
                    return f"for each {target}"
                if not target and source:
                    return f"for each item in {source}"
                return "for each item"
            # Edge cases: 'for X in' or 'for  in Y' or just 'for X'
            if c.startswith("for "):
                rest = c[4:].strip()
                if rest.endswith(" in"):
                    rest = rest[:-3].strip()
                    return f"for each {rest}" if rest else "for each item"
                if rest.startswith("in "):
                    return f"for each item in {rest[3:].strip()}"
                return f"for each {rest}" if rest else "for each item"

            # Fallback symbol replacements if any leftovers
            fallback = {
                "self.State.ON": "on",
                "self.State.OFF": "off",
                "self.Area.HOME": "home",
                "self.Area.NOT_HOME": "not_home",
            }
            for k, v in fallback.items():
                c = c.replace(k, v)

            # Pattern: self.get_state(entity) == value
            m = re.match(r"self\.get_state\((.+)\)\s*==\s*(.+)$", c)
            if m:
                ent = m.group(1).strip()
                val = self._strip_quotes(m.group(2).strip())
                return f"{lead}{ent} is {val}"

            m = re.match(r"self\.get_state\((.+)\)\s*!=\s*(.+)$", c)
            if m:
                ent = m.group(1).strip()
                val = self._strip_quotes(m.group(2).strip())
                return f"{lead}{ent} is not {val}"

            # hasattr(obj, 'Attr')
            m = re.match(r"hasattr\(([^,]+),\s*'([^']+)'\)", c)
            if m:
                obj = m.group(1).strip()
                attr = m.group(2).strip()
                return f"{lead}{obj} has {attr}"

            # name equality
            m = re.match(r"(.+)\s*==\s*(.+)$", c)
            if m:
                left = m.group(1).strip()
                right = self._strip_quotes(m.group(2).strip())
                if left.endswith(".name"):
                    subj = left[:-5]
                    return f"{lead}{subj} is {right}"
                return f"{lead}{left} equals {right}"

            # membership
            m = re.match(r"(.+)\s+in\s+(.+)$", c)
            if m:
                left = m.group(1).strip()
                right = m.group(2).strip()
                return f"{lead}{left} in {right}"

            # negation
            if c.startswith("not "):
                return f"{lead}not {c[4:].strip()}"

            # Default: prepend lead if any
            return (lead + c).strip()
        except Exception:
            return cond

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """Extract import statements from the AST."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(f"from {module} import {', '.join(names)}")

        return imports

    def _parse_class(self, class_node: ast.ClassDef) -> ClassInfo:
        """Parse a class definition and extract all relevant information."""
        # Basic class information
        name = class_node.name
        base_classes = [self._get_name(base) for base in class_node.bases]
        docstring = ast.get_docstring(class_node)

        # Find methods and analyze them
        methods = []
        state_listeners = []
        mqtt_listeners = []
        service_calls = []
        time_schedules = []
        device_relationships = []
        automation_flows = []
        initialize_code = None
        constants_used = []

        # Build a map of method name -> AST node to allow limited inlining of helper methods
        self._current_class_method_nodes: dict[str, ast.FunctionDef] = {
            n.name: n for n in class_node.body if isinstance(n, ast.FunctionDef)
        }

        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                method_info = self._parse_method(node)
                methods.append(method_info)

                # Special handling for initialize method
                if method_info.name == "initialize":
                    initialize_code = method_info.source_code
                    # Extract various listeners and patterns from initialize method
                    listeners = self._extract_state_listeners(node)
                    state_listeners.extend(listeners)

                    mqtt_list = self._extract_mqtt_listeners(node)
                    mqtt_listeners.extend(mqtt_list)

                    time_sched = self._extract_time_schedules(node)
                    time_schedules.extend(time_sched)

                # Extract patterns from all methods
                method_service_calls = self._extract_service_calls(node)
                service_calls.extend(method_service_calls)

                method_relationships = self._extract_device_relationships(node)
                device_relationships.extend(method_relationships)

                method_flows = self._extract_automation_flows(node)
                automation_flows.extend(method_flows)

        # Find all constant references in the class
        for node in ast.walk(class_node):  # type: ignore[assignment]
            if isinstance(node, ast.Attribute):
                const_ref = self._extract_constant_reference(node)
                if const_ref:
                    constants_used.append(const_ref)

        return ClassInfo(
            name=name,
            base_classes=base_classes,
            docstring=docstring,
            methods=methods,
            state_listeners=state_listeners,
            mqtt_listeners=mqtt_listeners,
            service_calls=service_calls,
            time_schedules=time_schedules,
            device_relationships=device_relationships,
            automation_flows=automation_flows,
            imports=[],  # Will be filled at file level
            constants_used=list(set(constants_used)),
            initialize_code=initialize_code,
            line_number=class_node.lineno,
        )

    def _parse_method(self, method_node: ast.FunctionDef) -> MethodInfo:
        """Parse a method definition with detailed body analysis."""
        name = method_node.name
        args = [arg.arg for arg in method_node.args.args]
        decorators = [self._get_name(dec) for dec in method_node.decorator_list]
        docstring = ast.get_docstring(method_node)

        # Check if this looks like a callback method
        is_callback = self._is_callback_method(method_node, args)

        # Extract source code
        start_line = method_node.lineno - 1
        end_line = method_node.end_lineno if method_node.end_lineno else start_line + 1
        source_code = "\n".join(self.source_lines[start_line:end_line])

        # Enhanced method body analysis
        actions = self._analyze_method_actions(method_node)
        performance_pattern = self._analyze_performance_pattern(method_node)

        # Count different types of operations
        conditional_count = len([a for a in actions if a.action_type == "conditional_logic"])
        loop_count = len([a for a in actions if a.action_type == "loop_iteration"])
        notification_count = len([a for a in actions if a.action_type == "notification"])
        device_action_count = len([a for a in actions if a.action_type == "device_action"])

        return MethodInfo(
            name=name,
            args=args,
            decorators=decorators,
            docstring=docstring,
            is_callback=is_callback,
            line_number=method_node.lineno,
            source_code=source_code,
            actions=actions,
            performance_pattern=performance_pattern,
            conditional_count=conditional_count,
            loop_count=loop_count,
            notification_count=notification_count,
            device_action_count=device_action_count,
        )

    def _is_callback_method(self, method_node: ast.FunctionDef, args: list[str]) -> bool:
        """
        Determine if a method is likely a callback based on its signature.
        AppDaemon callbacks typically have (entity, attribute, old, new, kwargs) signature.
        """
        if len(args) < 5:
            return False

        # Check for common callback parameter names
        expected_params = ["entity", "attribute", "old", "new", "kwargs"]
        return args[1:6] == expected_params or args[-5:] == expected_params

    def _extract_state_listeners(self, method_node: ast.FunctionDef) -> list[StateListener]:
        """Extract listen_state calls from a method (typically initialize)."""
        listeners = []
        alias_map = self._build_alias_map(method_node)

        for node in ast.walk(method_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "listen_state":
                listener = self._parse_listen_state_call(node, alias_map)
                if listener:
                    listeners.append(listener)

        return listeners

    def _parse_listen_state_call(
        self, call_node: ast.Call, alias_map: dict[str, str] | None = None
    ) -> StateListener | None:
        """Parse a listen_state method call."""
        args = call_node.args
        kwargs = {kw.arg: self._get_value(kw.value) for kw in call_node.keywords}

        if len(args) < 2:
            return None

        callback_method = self._get_name(args[0])
        entity = self._get_value(args[1]) if len(args) > 1 else None
        if isinstance(entity, str) and alias_map and entity in alias_map:
            entity = alias_map[entity]

        return StateListener(
            callback_method=callback_method,
            entity=entity,
            old_state=kwargs.get("old"),
            new_state=kwargs.get("new"),
            duration=kwargs.get("duration"),
            kwargs={k: v for k, v in kwargs.items() if k is not None},
            line_number=call_node.lineno,
        )

    def _extract_mqtt_listeners(self, method_node: ast.FunctionDef) -> list[MQTTListener]:
        """Extract MQTT listeners from a method (typically initialize)."""
        listeners = []

        for node in ast.walk(method_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "listen_event":
                    # Check if this is an MQTT listener
                    kwargs = {kw.arg: self._get_value(kw.value) for kw in node.keywords}
                    if kwargs.get("namespace") == "mqtt" or any("mqtt" in str(arg) for arg in node.args):
                        listener = self._parse_mqtt_listener_call(node)
                        if listener:
                            listeners.append(listener)

        return listeners

    def _parse_mqtt_listener_call(self, call_node: ast.Call) -> MQTTListener | None:
        """Parse an MQTT listen_event call."""
        args = call_node.args
        kwargs = {kw.arg: self._get_value(kw.value) for kw in call_node.keywords}

        if len(args) < 1:
            return None

        callback_method = self._get_name(args[0])
        topic = kwargs.get("topic") or (self._get_value(args[1]) if len(args) > 1 else None)

        return MQTTListener(
            callback_method=callback_method,
            topic=topic,
            namespace=kwargs.get("namespace"),
            kwargs={k: v for k, v in kwargs.items() if k is not None},
            line_number=call_node.lineno,
            qos=kwargs.get("qos"),
            retain=kwargs.get("retain"),
        )

    def _extract_service_calls(self, method_node: ast.FunctionDef) -> list[ServiceCall]:
        """Extract Home Assistant service calls from a method."""
        service_calls = []
        alias_map = self._build_alias_map(method_node)

        for node in ast.walk(method_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

                # call_service method (handle before generic direct methods)
                if method_name == "call_service":
                    service_call = self._parse_call_service_call(node, method_node.name, alias_map)
                    if service_call:
                        service_calls.append(service_call)

                # Direct AppDaemon service methods
                elif method_name in self.service_patterns:
                    service_call = self._parse_direct_service_call(node, method_name, method_node.name, alias_map)
                    if service_call:
                        service_calls.append(service_call)

        return service_calls

    def _parse_direct_service_call(
        self, call_node: ast.Call, method_name: str, containing_method: str, alias_map: dict[str, str] | None = None
    ) -> ServiceCall | None:
        """Parse direct service calls like turn_on, turn_off, etc."""
        args = call_node.args
        kwargs = {kw.arg: self._get_value(kw.value) for kw in call_node.keywords}

        # Map method names to service domains
        service_mapping = {
            "turn_on": ("homeassistant", "turn_on"),
            "turn_off": ("homeassistant", "turn_off"),
            "toggle": ("homeassistant", "toggle"),
            "set_state": ("homeassistant", "set_state"),
            "notify": ("notify", "notify"),
        }

        if method_name not in service_mapping:
            return ServiceCall(
                service_domain="unknown",
                service_name=method_name,
                entity_id=self._resolve_alias_value(self._get_value(args[0]) if args else None, alias_map),
                data={k: v for k, v in kwargs.items() if k is not None},
                line_number=call_node.lineno,
                method_name=containing_method,
            )

        domain, service = service_mapping[method_name]
        entity_id = self._resolve_alias_value(self._get_value(args[0]) if args else kwargs.get("entity_id"), alias_map)

        return ServiceCall(
            service_domain=domain,
            service_name=service,
            entity_id=entity_id,
            data={k: v for k, v in kwargs.items() if k is not None},
            line_number=call_node.lineno,
            method_name=containing_method,
        )

    def _parse_call_service_call(
        self, call_node: ast.Call, containing_method: str, alias_map: dict[str, str] | None = None
    ) -> ServiceCall | None:
        """Parse call_service method calls."""
        args = call_node.args
        kwargs = {kw.arg: self._get_value(kw.value) for kw in call_node.keywords}

        if len(args) < 1:
            return None

        service_path = self._get_value(args[0])
        if not service_path or "." not in str(service_path):
            return None

        domain, service = str(service_path).split(".", 1)

        return ServiceCall(
            service_domain=domain,
            service_name=service,
            entity_id=self._resolve_alias_value(kwargs.get("entity_id"), alias_map),
            data={k: v for k, v in kwargs.items() if k is not None},
            line_number=call_node.lineno,
            method_name=containing_method,
        )

    def _extract_time_schedules(self, method_node: ast.FunctionDef) -> list[TimeSchedule]:
        """Extract time-based scheduling calls from a method."""
        schedules = []

        for node in ast.walk(method_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

                if method_name in self.time_patterns:
                    schedule = self._parse_time_schedule_call(node, method_name)
                    if schedule:
                        schedules.append(schedule)

        return schedules

    def _parse_time_schedule_call(self, call_node: ast.Call, schedule_type: str) -> TimeSchedule | None:
        """Parse time scheduling method calls."""
        args = call_node.args
        kwargs = {kw.arg: self._get_value(kw.value) for kw in call_node.keywords}

        if len(args) < 1:
            return None

        callback_method = self._get_name(args[0])

        # Extract time specification based on schedule type
        time_spec = None
        interval = None
        delay = None

        if schedule_type in ["run_daily", "run_at"] and len(args) > 1:
            time_spec = self._get_value(args[1])
        elif schedule_type == "run_every" and len(args) > 2:
            time_spec = self._get_value(args[1])
            interval = self._get_value(args[2])
        elif schedule_type == "run_in" and len(args) > 1:
            delay = self._get_value(args[1])

        return TimeSchedule(
            callback_method=callback_method,
            schedule_type=schedule_type,
            time_spec=time_spec,
            kwargs={k: v for k, v in kwargs.items() if k is not None},
            line_number=call_node.lineno,
            interval=interval,
            delay=delay,
        )

    def _extract_device_relationships(self, method_node: ast.FunctionDef) -> list[DeviceRelationship]:
        """Extract device relationships from method logic."""
        relationships = []

        # Look for patterns where one entity affects another
        for node in ast.walk(method_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

                if method_name in self.service_patterns:
                    # Find entities being controlled
                    args = node.args if hasattr(node, "args") else []
                    if args:
                        target_entity = self._get_value(args[0])

                        # Look for trigger entity in method parameters or context
                        trigger_entity = self._infer_trigger_entity(method_node)

                        if trigger_entity and target_entity:
                            relationships.append(
                                DeviceRelationship(
                                    trigger_entity=trigger_entity,
                                    target_entity=target_entity,
                                    relationship_type="controls",
                                    line_number=node.lineno,
                                    method_name=method_node.name,
                                )
                            )

        return relationships

    def _infer_trigger_entity(self, method_node: ast.FunctionDef) -> str | None:
        """Infer the trigger entity from method signature and context."""
        # Check if method looks like a callback (has entity parameter)
        if len(method_node.args.args) >= 2:
            # Second arg (after self) is often the entity in callbacks
            return "inferred_from_callback"

        # Look for patterns in method name
        method_name = method_node.name.lower()
        if "motion" in method_name:
            return "motion_sensor"
        elif "door" in method_name:
            return "door_sensor"
        elif "temperature" in method_name:
            return "temperature_sensor"

        return None

    def _extract_automation_flows(self, method_node: ast.FunctionDef) -> list[AutomationFlow]:
        """Extract automation logic flows from method code."""
        flows = []

        # Look for conditional logic (if statements)
        for node in ast.walk(method_node):
            if isinstance(node, ast.If):
                flow = self._parse_conditional_flow(node, method_node.name)
                if flow:
                    flows.append(flow)
            elif isinstance(node, ast.For) or isinstance(node, ast.While):
                flow = self._parse_loop_flow(node, method_node.name)
                if flow:
                    flows.append(flow)

        return flows

    def _parse_conditional_flow(self, if_node: ast.If, method_name: str) -> AutomationFlow | None:
        """Parse conditional logic flow from if statement."""
        conditions = []
        actions = []
        entities_involved = []

        # Extract condition
        condition_text = self._extract_condition_text(if_node.test)
        if condition_text:
            conditions.append(f"if {condition_text}")

        # Extract actions from if body
        for stmt in if_node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                action = self._extract_action_text(stmt.value)
                if action:
                    actions.append(action)

        # Handle elif/else blocks
        for stmt in if_node.orelse:
            if isinstance(stmt, ast.If):
                elif_text = self._extract_condition_text(stmt.test)
                if elif_text:
                    conditions.append(f"elif {elif_text}")
                for sub in stmt.body:
                    if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                        action = self._extract_action_text(sub.value)
                        if action:
                            actions.append(action)
            else:
                # Else branch may contain direct calls; collect them as actions
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    action = self._extract_action_text(stmt.value)
                    if action:
                        actions.append(action)

        # Extract entities from conditions and actions
        entities_involved = self._extract_entities_from_flow(if_node)

        if conditions or actions:
            return AutomationFlow(
                flow_type="conditional",
                conditions=conditions,
                actions=actions,
                entities_involved=entities_involved,
                line_number=if_node.lineno,
                method_name=method_name,
            )

        return None

    def _parse_loop_flow(self, loop_node: ast.For | ast.While, method_name: str) -> AutomationFlow | None:
        """Parse loop logic flow."""
        conditions = []
        actions = []
        entities_involved = []

        if isinstance(loop_node, ast.For):
            flow_type = "sequence"
            # Extract iteration target
            target = self._extract_condition_text(loop_node.target)
            iter_source = self._extract_condition_text(loop_node.iter)
            conditions.append(f"for {target} in {iter_source}")
        else:
            flow_type = "loop"
            # Extract while condition
            condition_text = self._extract_condition_text(loop_node.test)
            if condition_text:
                conditions.append(f"while {condition_text}")

        # Extract actions from loop body
        for stmt in loop_node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                action = self._extract_action_text(stmt.value)
                if action:
                    actions.append(action)

        entities_involved = self._extract_entities_from_flow(loop_node)

        if conditions or actions:
            return AutomationFlow(
                flow_type=flow_type,
                conditions=conditions,
                actions=actions,
                entities_involved=entities_involved,
                line_number=loop_node.lineno,
                method_name=method_name,
            )

        return None

    def _analyze_method_actions(self, method_node: ast.FunctionDef) -> list[MethodAction]:
        """Analyze method body to extract detailed action sequence."""
        actions: list[MethodAction] = []

        # Traverse only the direct body of the method to get the main flow
        for stmt in method_node.body:
            self._analyze_statement_for_actions(stmt, actions)

        return actions

    def _analyze_statement_for_actions(self, stmt: ast.stmt, actions: list[MethodAction]) -> None:
        """Recursively analyze statements to extract actions."""
        # Conditional logic (if statements)
        if isinstance(stmt, ast.If):
            actions.append(
                MethodAction(
                    action_type="conditional_logic",
                    description="Conditional logic",
                    line_number=stmt.lineno,
                    entities_involved=self._extract_entities_from_node(stmt.test),
                )
            )

            # Analyze the body of the if statement
            for sub_stmt in stmt.body:
                self._analyze_statement_for_actions(sub_stmt, actions)

            # Analyze else clause if present
            for sub_stmt in stmt.orelse:
                self._analyze_statement_for_actions(sub_stmt, actions)

        # Loop iterations
        elif isinstance(stmt, (ast.For, ast.While)):
            description = "Loop iteration"

            actions.append(
                MethodAction(
                    action_type="loop_iteration",
                    description=description,
                    line_number=stmt.lineno,
                    entities_involved=self._extract_entities_from_node(stmt),
                )
            )

            # Analyze loop body
            for sub_stmt in stmt.body:
                self._analyze_statement_for_actions(sub_stmt, actions)

        # Expression statements (method calls)
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call_node = stmt.value
            if isinstance(call_node.func, ast.Attribute):
                method_name = call_node.func.attr

                # Inline simple helper method calls inside callbacks to capture downstream actions
                # e.g., update_sensors() -> _send_request() -> call_service(...)
                try:
                    if (
                        isinstance(call_node.func.value, ast.Name)
                        and call_node.func.value.id == "self"
                        and method_name.startswith("_")
                        and hasattr(self, "_current_class_method_nodes")
                        and method_name in self._current_class_method_nodes
                    ):
                        callee = self._current_class_method_nodes[method_name]
                        for sub in callee.body:
                            self._analyze_statement_for_actions(sub, actions)
                except Exception:
                    pass

                # Detect different types of actions
                if "notify" in method_name.lower() or "send_notify" in method_name.lower():
                    actions.append(
                        MethodAction(
                            action_type="notification",
                            description="Notification: send_notify",
                            line_number=stmt.lineno,
                            entities_involved=self._extract_entities_from_call_args(call_node),
                        )
                    )

                elif method_name == "log":
                    actions.append(MethodAction(action_type="logging", description="Logging", line_number=stmt.lineno))

                elif method_name in {"turn_on", "turn_off", "toggle", "call_service", "set_state"}:
                    entities = self._extract_entities_from_call_args(call_node)
                    actions.append(
                        MethodAction(
                            action_type="device_action",
                            description=f"Device action: {method_name}",
                            line_number=stmt.lineno,
                            entities_involved=entities,
                        )
                    )

        # Assignment statements (performance timing)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                target_name = self._get_name(target)
                if "perf_start" in target_name:
                    actions.append(
                        MethodAction(
                            action_type="performance_timer",
                            description="Start Performance Timer",
                            line_number=stmt.lineno,
                        )
                    )
                elif "perf_time" in target_name:
                    actions.append(
                        MethodAction(
                            action_type="performance_timer",
                            description="Log Performance Metrics",
                            line_number=stmt.lineno,
                        )
                    )

    def _extract_entities_from_node(self, node: ast.AST) -> list[str]:
        """Extract entity references from any AST node."""
        entities = []
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                entity_ref = self._extract_constant_reference(child)
                if entity_ref:
                    entities.append(entity_ref)
        return list(set(entities))

    def _extract_entities_from_call_args(self, call_node: ast.Call) -> list[str]:
        """Extract entity references from method call arguments."""
        entities = []
        for arg in call_node.args:
            entities.extend(self._extract_entities_from_node(arg))
        for keyword in call_node.keywords:
            entities.extend(self._extract_entities_from_node(keyword.value))
        return list(set(entities))

    def _extract_condition_text(self, test_node: ast.AST) -> str:
        """Extract readable text from a condition (if/while test) node."""
        return self._expr_to_text(test_node)

    def _extract_action_text(self, call_node: ast.Call) -> str:
        """Extract readable text from action call."""
        func_text = self._expr_to_text(call_node.func)
        args_text = ", ".join(self._expr_to_text(arg) for arg in call_node.args)
        return f"{func_text}({args_text})"

    # --- Expression pretty-printer helpers ---
    def _expr_to_text(self, node: ast.AST) -> str:
        """Convert an AST expression into a concise, human-readable string."""
        try:
            if isinstance(node, ast.Constant):
                return repr(node.value)
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                return f"{self._expr_to_text(node.value)}.{node.attr}"
            if isinstance(node, ast.Subscript):
                base = self._expr_to_text(node.value)
                sl = getattr(node, "slice", None)
                sl_text = self._expr_to_text(sl) if sl is not None else ""
                return f"{base}[{sl_text}]"
            # ast.Index was removed in Python 3.9, handled by ast.Subscript directly now
            if isinstance(node, ast.Slice):
                lower = self._expr_to_text(node.lower) if node.lower else ""
                upper = self._expr_to_text(node.upper) if node.upper else ""
                step = self._expr_to_text(node.step) if node.step else ""
                core = f"{lower}:{upper}"
                return f"{core}:{step}" if step else core
            if isinstance(node, ast.Call):
                func = self._expr_to_text(node.func)
                args = ", ".join(self._expr_to_text(a) for a in node.args)
                return f"{func}({args})"
            if isinstance(node, ast.UnaryOp):
                op = self._unary_op_to_text(node.op)
                return f"{op}{self._expr_to_text(node.operand)}"
            if isinstance(node, ast.BinOp):
                left = self._expr_to_text(node.left)
                op = self._bin_op_to_text(node.op)
                right = self._expr_to_text(node.right)
                return f"({left} {op} {right})"
            if isinstance(node, ast.BoolOp):
                bool_op_text = self._bool_op_to_text(node.op)
                return f" {bool_op_text} ".join(self._expr_to_text(v) for v in node.values)
            if isinstance(node, ast.Compare):
                left = self._expr_to_text(node.left)
                cmp_parts: list[str] = []
                for cmp_op, comp in zip(node.ops, node.comparators):
                    cmp_parts.append(f"{self._cmp_op_to_text(cmp_op)} {self._expr_to_text(comp)}")
                return f"{left} {' '.join(cmp_parts)}"
            if isinstance(node, ast.JoinedStr):  # f-string
                fparts: list[str] = []
                for v in node.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        fparts.append(v.value)
                    elif isinstance(v, ast.FormattedValue):
                        fparts.append("{" + self._expr_to_text(v.value) + "}")
                return "f'" + "".join(fparts) + "'"
            return self._get_name(node)
        except Exception:
            return self._get_name(node)

    def _bool_op_to_text(self, op: ast.boolop) -> str:
        return "and" if isinstance(op, ast.And) else ("or" if isinstance(op, ast.Or) else type(op).__name__.lower())

    def _unary_op_to_text(self, op: ast.unaryop) -> str:
        if isinstance(op, ast.Not):
            return "not "
        if isinstance(op, ast.USub):
            return "-"
        if isinstance(op, ast.UAdd):
            return "+"
        if isinstance(op, ast.Invert):
            return "~"
        return type(op).__name__

    def _bin_op_to_text(self, op: ast.operator) -> str:
        mapping = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.MatMult: "@",
            ast.Div: "/",
            ast.Mod: "%",
            ast.Pow: "**",
            ast.FloorDiv: "//",
            ast.BitOr: "|",
            ast.BitAnd: "&",
            ast.BitXor: "^",
            ast.LShift: "<<",
            ast.RShift: ">>",
        }
        for k, v in mapping.items():
            if isinstance(op, k):
                return v
        return type(op).__name__

    def _cmp_op_to_text(self, op: ast.cmpop) -> str:
        mapping = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.Is: "is",
            ast.IsNot: "is not",
            ast.In: "in",
            ast.NotIn: "not in",
        }
        for k, v in mapping.items():
            if isinstance(op, k):
                return v
        return type(op).__name__

    def _extract_entities_from_flow(self, node: ast.AST) -> list[str]:
        """Extract entity references from flow logic."""
        entities = []

        for child_node in ast.walk(node):
            if isinstance(child_node, ast.Attribute):
                entity_ref = self._extract_constant_reference(child_node)
                if entity_ref:
                    entities.append(entity_ref)

        return list(set(entities))

    def _extract_constant_reference(self, node: ast.Attribute) -> str | None:
        """Extract constant references like Home.Kitchen.Light or Persons.user."""

        def get_full_attr_name(node: ast.AST) -> str:
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                return f"{get_full_attr_name(node.value)}.{node.attr}"
            return ""

        full_name = get_full_attr_name(node)

        # Filter for known constant patterns
        if any(full_name.startswith(prefix) for prefix in ["Home.", "Persons.", "Actions.", "General."]):
            return full_name

        return None

    def _extract_constant_value_map(self, tree: ast.AST) -> dict[str, str]:
        """Extract assignments of the form Namespace.Sub.property = "value" into a map.

        This allows resolving code constants like Home.Kitchen.Light to actual entity ids
        such as light.kitchen, when defined in the same module.
        """
        mapping: dict[str, str] = {}

        def full_attr(n: ast.AST) -> str:
            if isinstance(n, ast.Name):
                return n.id
            if isinstance(n, ast.Attribute):
                return f"{full_attr(n.value)}.{n.attr}"
            return ""

        def eval_str(node: ast.AST) -> str | None:
            # Try to statically evaluate a string-like value
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.JoinedStr):
                parts: list[str] = []
                for v in node.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        parts.append(v.value)
                    elif isinstance(v, ast.FormattedValue):
                        # Best-effort: ignore formatted part (keeps static content)
                        inner = eval_str(v.value)
                        if inner is not None:
                            parts.append(inner)
                return "".join(parts)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                left = eval_str(node.left)
                right = eval_str(node.right)
                if left is not None and right is not None:
                    return left + right
            return None

        for node in ast.walk(tree):
            # Simple assignments like Home.Kitchen.Light = "light.kitchen"
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute):
                    key = full_attr(node.targets[0])
                    sval = eval_str(node.value)
                    if isinstance(sval, str):
                        mapping[key] = sval
            # Annotated assignment: Home.Alarm: str = "alarm_control_panel.home"
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Attribute):
                    sval = eval_str(node.value) if node.value is not None else None
                    if isinstance(sval, str):
                        key = full_attr(node.target)
                        mapping[key] = sval
            # Calls like setattr(Home.Kitchen, "Light", "light.kitchen")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr":
                try:
                    obj, attr_name, value = node.args[0], node.args[1], node.args[2]
                    base = full_attr(obj)
                    aname = eval_str(attr_name)
                    sval = eval_str(value)
                    if base and isinstance(aname, str) and isinstance(sval, str):
                        mapping[f"{base}.{aname}"] = sval
                except Exception:
                    pass

        return mapping

    def _extract_class_constant_value_map(self, tree: ast.Module) -> dict[str, str]:
        """Extract class-nested constants for patterns like:
        class Home:
            class Kitchen:
                Light = "light.kitchen"
        -> "Home.Kitchen.Light": "light.kitchen"
        """
        mapping: dict[str, str] = {}

        def walk_class(cls: ast.ClassDef, prefix: str) -> None:
            current_prefix = f"{prefix}.{cls.name}" if prefix else cls.name
            for item in cls.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if (
                            isinstance(target, ast.Name)
                            and isinstance(item.value, ast.Constant)
                            and isinstance(item.value.value, str)
                        ):
                            mapping[f"{current_prefix}.{target.id}"] = item.value.value
                elif isinstance(item, ast.AnnAssign):
                    if (
                        isinstance(item.target, ast.Name)
                        and isinstance(item.value, ast.Constant)
                        and isinstance(item.value.value, str)
                    ):
                        mapping[f"{current_prefix}.{item.target.id}"] = item.value.value
                elif isinstance(item, ast.ClassDef):
                    walk_class(item, current_prefix)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                walk_class(node, prefix="")

        return mapping

    def _extract_imported_constant_maps(
        self, file_path: Path, tree: ast.AST, depth: int = 0, visited: set[str] | None = None
    ) -> list[dict[str, str]]:
        """Extract constant maps from imported modules by statically resolving module files.

        Attempts to resolve only local project files relative to the current module directory.
        Limits recursion depth to avoid excessive traversal.
        """
        if visited is None:
            visited = set()

        if depth > 2:
            return []

        current_dir = Path(file_path).parent
        modules: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name:
                        modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.append(node.module)

        collected: list[dict[str, str]] = []

        for mod in modules:
            if mod in visited:
                continue
            visited.add(mod)

            candidate = self._find_module_file(mod, current_dir)
            if not candidate or not candidate.exists():
                # Heuristic: look for sibling const.py/constants.py
                if any(tok in mod.lower() for tok in ("const", "constants")):
                    for name in ("const.py", "constants.py"):
                        alt = current_dir / name
                        if alt.exists():
                            candidate = alt
                            break
            # Try APPS_DIR/const.py for modules named 'const' when not found
            if (not candidate or not candidate.exists()) and self._apps_dir:
                if mod.split(".")[-1].lower() in ("const", "constants"):
                    alt = self._apps_dir / "const.py"
                    if alt.exists():
                        candidate = alt
            if not candidate or not candidate.exists():
                continue

            key = str(candidate.resolve())
            if key in self._module_const_cache:
                collected.append(self._module_const_cache[key])
                continue

            try:
                cmap = self._extract_constant_map_from_path(candidate)
                # Recurse into that module's imports (bounded)
                other_source = candidate.read_text(encoding="utf-8")
                other_tree = ast.parse(other_source)
                submaps = self._extract_imported_constant_maps(candidate, other_tree, depth + 1, visited)
                merged: dict[str, str] = {}
                for sm in submaps:
                    merged.update(sm)
                merged.update(cmap)
                self._module_const_cache[key] = merged
                collected.append(merged)
            except Exception:
                # Ignore any issues with imported modules; best-effort resolution
                continue

        return collected

    def _find_module_file(self, module_name: str, base_dir: Path) -> Path | None:
        """Resolve a python module name to a file path within the project tree.

        Tries relative to current file directory.
        """
        rel = Path(*module_name.split("."))
        # Try module.py
        cand = base_dir / (str(rel) + ".py")
        if cand.exists():
            return cand
        # Try package/__init__.py
        cand = base_dir / rel / "__init__.py"
        if cand.exists():
            return cand
        # Try project root heuristic
        try:
            project_root = Path(__file__).resolve().parents[2]
            alt = project_root / (str(rel) + ".py")
            if alt.exists():
                return alt
        except Exception:
            pass
        # Try APPS_DIR
        if self._apps_dir:
            alt = self._apps_dir / (str(rel) + ".py")
            if alt.exists():
                return alt
            pkg = self._apps_dir / rel / "__init__.py"
            if pkg.exists():
                return pkg
        return None

    def _extract_constant_map_from_path(self, path: Path) -> dict[str, str]:
        """Parse a module file and extract constant map using the same AST logic."""
        source = path.read_text(encoding="utf-8")
        other_tree = ast.parse(source)
        mapping = self._extract_constant_value_map(other_tree)
        class_mapping = self._extract_class_constant_value_map(other_tree)
        merged: dict[str, str] = {}
        merged.update(mapping)
        merged.update(class_mapping)
        return merged

    def _get_name(self, node: ast.AST) -> str:
        """Get the name from various AST node types."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return ""

    def _get_value(self, node: ast.AST) -> Any:
        """Extract value from AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_name(node)
        elif isinstance(node, ast.List):
            return [self._get_value(elt) for elt in node.elts]
        elif isinstance(node, ast.Dict):
            return {
                self._get_value(k) if k is not None else None: self._get_value(v)
                for k, v in zip(node.keys, node.values)
            }
        return None

    def _build_alias_map(self, method_node: ast.FunctionDef) -> dict[str, str]:
        """Build a simple alias map inside a method for patterns like:
        entity = Home.Kitchen.Light
        self.turn_on(entity)
        """
        alias_map: dict[str, str] = {}
        try:
            for stmt in method_node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    target = stmt.targets[0]
                    value = stmt.value
                    if isinstance(target, ast.Name):
                        key = target.id
                        resolved_value = self._get_value(value)
                        if isinstance(resolved_value, str):
                            alias_map[key] = resolved_value
        except Exception:
            pass
        return alias_map

    def _resolve_alias_value(self, value: Any, alias_map: dict[str, str] | None) -> Any:
        if isinstance(value, str) and alias_map and value in alias_map:
            return alias_map[value]
        return value

    def _load_apps_config(self) -> None:
        """Load apps.yaml configuration if available."""
        if self.apps_yaml_path and self.apps_yaml_path.exists():
            try:
                with open(self.apps_yaml_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        self.apps_config = loaded
                    elif loaded is None:
                        self.logger.warning(
                            "apps.yaml at %s is empty; expected a mapping (dict). Ignoring.",
                            self.apps_yaml_path,
                        )
                    else:
                        self.logger.warning(
                            "apps.yaml at %s contains a %s; expected a mapping (dict). Ignoring.",
                            self.apps_yaml_path,
                            type(loaded).__name__,
                        )
            except Exception as e:
                self.logger.error(
                    "Failed to load apps.yaml configuration from %s: %s", self.apps_yaml_path, str(e), exc_info=True
                )
                self.apps_config = {}

    def _extract_app_dependencies(self, file_path: Path) -> list[AppDependency]:
        """Extract app dependencies from apps.yaml configuration."""
        dependencies: list[AppDependency] = []

        # Get module name from file path
        module_name = file_path.stem

        # Find all apps that use this module
        # Guard: apps_config must expose .items() to iterate key/value pairs
        items_method = getattr(self.apps_config, "items", None)
        if not callable(items_method):
            self.logger.warning(
                "apps.yaml root is %s; expected a mapping (dict). Skipping dependency extraction.",
                type(self.apps_config).__name__,
            )
            return dependencies

        for app_name, app_config in items_method():
            if isinstance(app_config, dict) and app_config.get("module") == module_name:
                # Ensure dependencies is always a list of strings
                deps_value = app_config.get("dependencies", [])
                if isinstance(deps_value, str):
                    dependencies_list = [deps_value]
                elif isinstance(deps_value, list):
                    dependencies_list = deps_value
                else:
                    dependencies_list = []

                dep = AppDependency(
                    app_name=app_name,
                    module_name=app_config.get("module", module_name),
                    class_name=app_config.get("class", ""),
                    dependencies=dependencies_list,
                )
                dependencies.append(dep)

        return dependencies

    def _analyze_person_centric_patterns(
        self, classes: list[ClassInfo], constants_used: set[str]
    ) -> PersonCentricPattern:
        """Analyze person-centric automation patterns."""
        pattern = PersonCentricPattern()

        # Use sets to collect unique values, then convert to lists
        person_entities_set: set[str] = set()
        notification_channels_set: set[str] = set()
        presence_detection_set: set[str] = set()
        device_tracking_set: set[str] = set()
        personalized_settings_set: set[str] = set()

        # Look for person-related constants
        for const in constants_used:
            if const.startswith("Persons."):
                person_entities_set.add(const)

                # Categorize by type
                if "telegram" in const.lower():
                    notification_channels_set.add(const)
                elif "tracker" in const.lower() or "presence" in const.lower() or "home_sensor" in const.lower():
                    presence_detection_set.add(const)
                elif "device_tracker" in const.lower() or "phone" in const.lower() or "watch" in const.lower():
                    device_tracking_set.add(const)
                elif "good_night" in const.lower() or "battery_monitor" in const.lower():
                    personalized_settings_set.add(const)

        # Convert sets to sorted lists for deterministic output
        pattern.person_entities = sorted(list(person_entities_set))
        pattern.notification_channels = sorted(list(notification_channels_set))
        pattern.presence_detection = sorted(list(presence_detection_set))
        pattern.device_tracking = sorted(list(device_tracking_set))
        pattern.personalized_settings = sorted(list(personalized_settings_set))

        return pattern

    def _analyze_helper_injection_patterns(self, classes: list[ClassInfo]) -> HelperInjectionPattern:
        """Analyze helper injection patterns in initialization."""
        pattern = HelperInjectionPattern()

        # Use sets to collect unique values, then convert to lists
        helper_methods_set: set[str] = set()
        dependency_injection_set: set[str] = set()

        for class_info in classes:
            # Check initialization code for helper patterns
            if class_info.initialize_code:
                source = class_info.initialize_code.lower()

                if "helpers" in source:
                    pattern.has_helpers_injection = True

                    # Extract helper methods being used
                    helper_patterns = [
                        "send_notify",
                        "notify_telegram",
                        "log_action",
                        "get_state_with_retry",
                        "wait_for_state",
                        "check_condition",
                        "format_message",
                        "parse_entity",
                    ]

                    for helper_method in helper_patterns:
                        if helper_method in source:
                            helper_methods_set.add(helper_method)

                # Look for dependency injection patterns
                if "dependencies" in source or "self.get_app(" in source:
                    dependency_injection_set.add("AppDaemon dependency injection")

        # Convert sets to sorted lists for deterministic output
        pattern.helper_methods_used = sorted(list(helper_methods_set))
        pattern.dependency_injection = sorted(list(dependency_injection_set))

        return pattern

    def _analyze_error_handling_patterns(self, classes: list[ClassInfo]) -> ErrorHandlingPattern:
        """Analyze error handling and recovery patterns."""
        pattern = ErrorHandlingPattern()

        # Use sets to collect unique values, then convert to lists
        recovery_mechanisms_set: set[str] = set()
        alert_patterns_set: set[str] = set()

        for class_info in classes:
            for method in class_info.methods:
                source = method.source_code.lower()

                # Check for try-catch blocks
                if "try:" in source and ("except" in source or "finally" in source):
                    pattern.has_try_catch = True

                # Check for error notifications
                if "error" in source and ("notify" in source or "telegram" in source):
                    pattern.error_notification = True

                # Check for logging on errors
                if "error" in source and "log" in source:
                    pattern.logging_on_error = True

                # Look for recovery mechanisms
                recovery_keywords = ["retry", "fallback", "recover", "backup", "alternative"]
                for keyword in recovery_keywords:
                    if keyword in source:
                        recovery_mechanisms_set.add(f"{keyword} mechanism in {method.name}")

                # Look for alert patterns
                if "alert" in source or "warning" in source:
                    alert_patterns_set.add(f"Alert pattern in {method.name}")

        # Convert sets to sorted lists for deterministic output
        pattern.recovery_mechanisms = sorted(list(recovery_mechanisms_set))
        pattern.alert_patterns = sorted(list(alert_patterns_set))

        return pattern

    def _analyze_constant_hierarchy(self, constants_used: set[str]) -> ConstantHierarchy:
        """Analyze hierarchical constant usage patterns."""
        hierarchy = ConstantHierarchy()

        # Use sets to collect unique values, then convert to lists
        person_constants_set: set[str] = set()
        device_constants_set: set[str] = set()
        action_constants_set: set[str] = set()
        general_constants_set: set[str] = set()

        for const in constants_used:
            parts = const.split(".")
            if len(parts) >= 2:
                prefix = parts[0]

                # Initialize hierarchy if not exists
                if prefix not in hierarchy.hierarchical_constants:
                    hierarchy.hierarchical_constants[prefix] = []
                hierarchy.hierarchical_constants[prefix].append(const)

                # Categorize by type using sets
                if prefix == "Persons":
                    person_constants_set.add(const)
                elif prefix == "Home":
                    device_constants_set.add(const)
                elif prefix == "Actions":
                    action_constants_set.add(const)
                elif prefix == "General":
                    general_constants_set.add(const)

        # Convert sets to sorted lists for deterministic output
        hierarchy.person_constants = sorted(list(person_constants_set))
        hierarchy.device_constants = sorted(list(device_constants_set))
        hierarchy.action_constants = sorted(list(action_constants_set))
        hierarchy.general_constants = sorted(list(general_constants_set))

        # Sort the hierarchical_constants lists as well
        for prefix in hierarchy.hierarchical_constants:
            hierarchy.hierarchical_constants[prefix] = sorted(list(set(hierarchy.hierarchical_constants[prefix])))

        return hierarchy

    def _analyze_performance_pattern(self, method_node: ast.FunctionDef) -> PerformancePattern | None:
        """Analyze method for performance monitoring patterns."""
        has_timing = False
        threshold_ms = None
        start_variable = None
        log_pattern = None
        alert_pattern = None
        line_number = method_node.lineno

        # Look for performance timing patterns in method source
        if method_node.end_lineno:
            source_text = "\n".join(self.source_lines[method_node.lineno - 1 : method_node.end_lineno])
        else:
            source_text = "\n".join(self.source_lines[method_node.lineno - 1 : method_node.lineno + 10])

        # Enhanced performance pattern detection
        if "perf_start" in source_text or "time.time()" in source_text:
            has_timing = True
            start_variable = "perf_start"

        # Look for specific threshold patterns (300ms is common in this codebase)
        for pattern in self.threshold_patterns:
            match = pattern.search(source_text)
            if match:
                threshold_ms = int(match.group(1))
                break

        # Default threshold if timing detected but no specific threshold found
        if has_timing and threshold_ms is None:
            if "300" in source_text:
                threshold_ms = 300

        # Check for performance alert patterns
        alert_patterns = ["PERFORMANCE ALERT", "⚠️", "performance warning", "slow execution", "execution exceeded"]

        for alert in alert_patterns:
            if alert.lower() in source_text.lower():
                alert_pattern = f"⚠️ {alert.upper()}"
                break

        # Check for execution logging patterns
        for pattern in self.log_patterns:
            if pattern.search(source_text):
                log_pattern = "[Exec: {perf_time_ms:.1f}ms]"
                break

        if has_timing:
            return PerformancePattern(
                has_timing=has_timing,
                threshold_ms=threshold_ms,
                start_variable=start_variable,
                log_pattern=log_pattern,
                alert_pattern=alert_pattern,
                line_number=line_number,
            )

        return None


def parse_appdaemon_file(file_path: str | Path, apps_yaml_path: str | Path | None = None) -> ParsedFile:
    """
    Convenience function to parse an AppDaemon file.

    Args:
        file_path: Path to the Python file to parse
        apps_yaml_path: Optional path to apps.yaml configuration file

    Returns:
        ParsedFile containing all extracted information
    """
    parser = AppDaemonParser(apps_yaml_path=apps_yaml_path)
    return parser.parse_file(file_path)
