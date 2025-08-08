"""
AppDaemon Automation Parser

This module parses AppDaemon Python automation files and extracts structured
information about classes, methods, state listeners, MQTT patterns, device
relationships, automation flows, and configuration usage.
It uses AST parsing to safely analyze code without executing it.
"""

import ast
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


class AppDaemonParser:
    """Parser for AppDaemon automation Python files."""

    def __init__(self, apps_yaml_path: str | Path | None = None) -> None:
        """Initialize the parser."""
        self.current_file = ""
        self.source_lines: list[str] = []
        self.apps_yaml_path = Path(apps_yaml_path) if apps_yaml_path else None
        self.apps_config: dict[str, Any] = {}
        self._load_apps_config()

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
        )

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

        for node in ast.walk(method_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "listen_state":
                listener = self._parse_listen_state_call(node)
                if listener:
                    listeners.append(listener)

        return listeners

    def _parse_listen_state_call(self, call_node: ast.Call) -> StateListener | None:
        """Parse a listen_state method call."""
        args = call_node.args
        kwargs = {kw.arg: self._get_value(kw.value) for kw in call_node.keywords}

        if len(args) < 2:
            return None

        callback_method = self._get_name(args[0])
        entity = self._get_value(args[1]) if len(args) > 1 else None

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

        for node in ast.walk(method_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

                # Direct AppDaemon service methods
                if method_name in self.service_patterns:
                    service_call = self._parse_direct_service_call(node, method_name, method_node.name)
                    if service_call:
                        service_calls.append(service_call)

                # call_service method
                elif method_name == "call_service":
                    service_call = self._parse_call_service_call(node, method_node.name)
                    if service_call:
                        service_calls.append(service_call)

        return service_calls

    def _parse_direct_service_call(
        self, call_node: ast.Call, method_name: str, containing_method: str
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
                entity_id=self._get_value(args[0]) if args else None,
                data={k: v for k, v in kwargs.items() if k is not None},
                line_number=call_node.lineno,
                method_name=containing_method,
            )

        domain, service = service_mapping[method_name]
        entity_id = self._get_value(args[0]) if args else kwargs.get("entity_id")

        return ServiceCall(
            service_domain=domain,
            service_name=service,
            entity_id=entity_id,
            data={k: v for k, v in kwargs.items() if k is not None},
            line_number=call_node.lineno,
            method_name=containing_method,
        )

    def _parse_call_service_call(self, call_node: ast.Call, containing_method: str) -> ServiceCall | None:
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
            entity_id=kwargs.get("entity_id"),
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
            conditions.append(condition_text)

        # Extract actions from if body
        for stmt in if_node.body:
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
            target = self._get_name(loop_node.target)
            iter_source = self._get_name(loop_node.iter)
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
        """Extract readable text from condition node."""
        if isinstance(test_node, ast.Compare):
            left = self._get_name(test_node.left)
            ops = [type(op).__name__ for op in test_node.ops]
            comparators = [self._get_name(comp) for comp in test_node.comparators]
            return f"{left} {' '.join(ops)} {' '.join(comparators)}"
        elif isinstance(test_node, ast.BoolOp):
            op = type(test_node.op).__name__.lower()
            values = [self._extract_condition_text(val) for val in test_node.values]
            return f" {op} ".join(values)
        else:
            return self._get_name(test_node)

    def _extract_action_text(self, call_node: ast.Call) -> str:
        """Extract readable text from action call."""
        if isinstance(call_node.func, ast.Attribute):
            method = call_node.func.attr
            args = [self._get_name(arg) for arg in call_node.args]
            return f"{method}({', '.join(args)})"
        return self._get_name(call_node.func)

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

    def _load_apps_config(self) -> None:
        """Load apps.yaml configuration if available."""
        if self.apps_yaml_path and self.apps_yaml_path.exists():
            try:
                with open(self.apps_yaml_path, "r", encoding="utf-8") as f:
                    self.apps_config = yaml.safe_load(f) or {}
            except Exception:
                self.apps_config = {}

    def _extract_app_dependencies(self, file_path: Path) -> list[AppDependency]:
        """Extract app dependencies from apps.yaml configuration."""
        dependencies = []

        # Get module name from file path
        module_name = file_path.stem

        # Find all apps that use this module
        for app_name, app_config in self.apps_config.items():
            if isinstance(app_config, dict) and app_config.get("module") == module_name:
                dep = AppDependency(
                    app_name=app_name,
                    module_name=app_config.get("module", module_name),
                    class_name=app_config.get("class", ""),
                    dependencies=app_config.get("dependencies", []),
                )
                dependencies.append(dep)

        return dependencies

    def _analyze_person_centric_patterns(
        self, classes: list[ClassInfo], constants_used: set[str]
    ) -> PersonCentricPattern:
        """Analyze person-centric automation patterns."""
        pattern = PersonCentricPattern()

        # Look for person-related constants
        for const in constants_used:
            if const.startswith("Persons."):
                pattern.person_entities.append(const)

                # Categorize by type
                if "telegram" in const.lower():
                    pattern.notification_channels.append(const)
                elif "tracker" in const.lower() or "presence" in const.lower() or "home_sensor" in const.lower():
                    pattern.presence_detection.append(const)
                elif "device_tracker" in const.lower() or "phone" in const.lower() or "watch" in const.lower():
                    pattern.device_tracking.append(const)
                elif "good_night" in const.lower() or "battery_monitor" in const.lower():
                    pattern.personalized_settings.append(const)

        return pattern

    def _analyze_helper_injection_patterns(self, classes: list[ClassInfo]) -> HelperInjectionPattern:
        """Analyze helper injection patterns in initialization."""
        pattern = HelperInjectionPattern()

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
                            pattern.helper_methods_used.append(helper_method)

                # Look for dependency injection patterns
                if "dependencies" in source or "self.get_app(" in source:
                    pattern.dependency_injection.append("AppDaemon dependency injection")

        return pattern

    def _analyze_error_handling_patterns(self, classes: list[ClassInfo]) -> ErrorHandlingPattern:
        """Analyze error handling and recovery patterns."""
        pattern = ErrorHandlingPattern()

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
                        pattern.recovery_mechanisms.append(f"{keyword} mechanism in {method.name}")

                # Look for alert patterns
                if "alert" in source or "warning" in source:
                    pattern.alert_patterns.append(f"Alert pattern in {method.name}")

        return pattern

    def _analyze_constant_hierarchy(self, constants_used: set[str]) -> ConstantHierarchy:
        """Analyze hierarchical constant usage patterns."""
        hierarchy = ConstantHierarchy()

        for const in constants_used:
            parts = const.split(".")
            if len(parts) >= 2:
                prefix = parts[0]

                # Initialize hierarchy if not exists
                if prefix not in hierarchy.hierarchical_constants:
                    hierarchy.hierarchical_constants[prefix] = []
                hierarchy.hierarchical_constants[prefix].append(const)

                # Categorize by type
                if prefix == "Persons":
                    hierarchy.person_constants.append(const)
                elif prefix == "Home":
                    hierarchy.device_constants.append(const)
                elif prefix == "Actions":
                    hierarchy.action_constants.append(const)
                elif prefix == "General":
                    hierarchy.general_constants.append(const)

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
        threshold_patterns = [r"perf_time_ms\s*>\s*(\d+)", r"execution_time\s*>\s*(\d+)", r"duration\s*>\s*(\d+)"]

        for pattern in threshold_patterns:
            match = re.search(pattern, source_text)
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
        log_patterns = [r"\[Exec:\s*\{.*perf_time.*\}\]", r"Execution time:", r"Performance:"]

        for pattern in log_patterns:
            if re.search(pattern, source_text, re.IGNORECASE):
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
