"""
AppDaemon Documentation Generator

This module generates comprehensive markdown documentation with Mermaid diagrams
from parsed AppDaemon automation files. It creates standardized documentation
with technical overviews, architecture diagrams, and flow charts.
"""

from pathlib import Path
from typing import Any

from server.generators.diagram_generator import create_architecture_diagram, create_method_flow_diagram, quick_flow
from server.parsers.appdaemon_parser import ClassInfo, ParsedFile, parse_appdaemon_file


class AppDaemonDocGenerator:
    """Generates markdown documentation for AppDaemon automation files."""

    def __init__(self, docs_dir: str | None = None) -> None:
        """Initialize the documentation generator."""
        self.constants_map = self._load_constants_map()
        self.docs_dir = Path(docs_dir) if docs_dir else None

    def generate_documentation(self, parsed_file: ParsedFile) -> str:
        """
        Generate complete markdown documentation for a parsed AppDaemon file.

        Args:
            parsed_file: Parsed information from an AppDaemon file

        Returns:
            Complete markdown documentation string
        """
        file_name = Path(parsed_file.file_path).stem

        sections = []

        # Title and overview
        sections.append(self._generate_header(file_name, parsed_file))

        # Technical overview
        sections.append(self._generate_technical_overview(parsed_file))

        # Architecture diagram removed - replaced with enhanced technical overview

        # Generate logic flow diagrams for key methods
        sections.append(self._generate_logic_flow_diagrams(parsed_file))

        # API documentation
        sections.append(self._generate_enhanced_api_documentation(parsed_file))

        # Configuration section
        sections.append(self._generate_enhanced_configuration_section(parsed_file))

        # Performance monitoring section
        sections.append(self._generate_performance_monitoring_section(parsed_file))

        # Integration points
        sections.append(self._generate_integration_points_section(parsed_file))

        # Remove old sections as they are replaced by enhanced versions
        pass

        return "\n\n".join(sections)

    def _generate_header(self, file_name: str, parsed_file: ParsedFile) -> str:
        """Generate the header section matching climate.md format."""
        title = self._format_title(file_name)

        # Find the main class for header info
        main_class = parsed_file.classes[0] if parsed_file.classes else None

        header = f"# {title}\n\n"

        # Add documentation file path
        if self.docs_dir:
            doc_path = self.docs_dir / f"{file_name}.md"
            header += f"> **Documentation:** `{doc_path}`  \n"
        else:
            header += f"> **Documentation:** `apps/docs/{file_name}.md`  \n"

        if main_class:
            header += f"> **Class:** `{main_class.name}`  \n"
            if main_class.base_classes:
                header += f"> **Base Classes:** `{', '.join(main_class.base_classes)}`  \n"
            header += f"> **Module:** `{Path(parsed_file.file_path).name}`\n\n"
        else:
            header += "\n"

        header += "## Overview\n\n"

        if parsed_file.module_docstring:
            header += f"{parsed_file.module_docstring}\n\n"
        else:
            header += f"Automation module for {title.lower()} management in the smart home system.\n\n"

        return header

    def _generate_technical_overview(self, parsed_file: ParsedFile) -> str:
        """Generate enhanced technical overview with collapsible sections."""
        section = "## Technical Overview\n\n"

        # Architecture bullet points like climate.md
        section += "### Architecture\n"
        section += "- **Type:** AppDaemon Automation Module\n"
        section += "- **Pattern:** Event-driven state machine\n"
        section += "- **Integration:** Home Assistant API & MQTT\n"

        # Count state listeners across all classes
        total_listeners = sum(len(cls.state_listeners) for cls in parsed_file.classes)
        initialization_details = self._get_initialization_details(parsed_file)
        section += f"- **Initialization:** {total_listeners} state listeners configured"
        if initialization_details:
            section += f"\n  <details>\n  <summary>Show Details</summary>\n\n{initialization_details}\n  </details>\n"
        else:
            section += "\n"

        # Count methods across all classes
        total_methods = sum(len(cls.methods) for cls in parsed_file.classes)
        methods_details = self._get_methods_details(parsed_file)
        section += f"- **Methods:** {total_methods} total methods"
        if methods_details:
            section += f"\n  <details>\n  <summary>Show Details</summary>\n\n{methods_details}\n  </details>\n"
        else:
            section += "\n"

        # Count callback methods
        total_callbacks = sum(len([m for m in cls.methods if m.is_callback]) for cls in parsed_file.classes)
        callbacks_details = self._get_callbacks_details(parsed_file)
        section += f"- **Callbacks:** {total_callbacks} callback methods"
        if callbacks_details:
            section += f"\n  <details>\n  <summary>Show Details</summary>\n\n{callbacks_details}\n  </details>\n"
        else:
            section += "\n"

        # Performance monitoring detection
        has_performance_monitoring = any(
            any(m.performance_pattern and m.performance_pattern.has_timing for m in cls.methods)
            for cls in parsed_file.classes
        )
        if has_performance_monitoring:
            # Find the threshold from any method that has performance monitoring
            threshold = None
            for cls in parsed_file.classes:
                for method in cls.methods:
                    if method.performance_pattern and method.performance_pattern.threshold_ms:
                        threshold = method.performance_pattern.threshold_ms
                        break
                if threshold:
                    break

            threshold_text = f" ({threshold}ms threshold)" if threshold else ""
            section += f"- **Performance:** Real-time monitoring enabled{threshold_text}\n"

        return section

    def _generate_architecture_diagram(self, parsed_file: ParsedFile) -> str:
        """Generate architecture diagram matching climate.md format."""
        section = "## Architecture Diagram\n\n"

        # Use the enhanced diagram generator
        diagram_md = create_architecture_diagram(parsed_file)
        section += f"```mermaid\n{diagram_md}\n```\n\n"

        return section

    def _generate_class_documentation(self, class_info: ClassInfo) -> str:
        """Generate detailed documentation for a specific class."""
        section = f"## {class_info.name}\n"

        if class_info.docstring:
            section += f"{class_info.docstring}\n\n"

        # Class details
        section += f"**Inheritance**: {' → '.join(class_info.base_classes + [class_info.name])}\n\n"

        # State listeners
        if class_info.state_listeners:
            section += "### State Listeners\n\n"
            section += "This class monitors the following entity state changes:\n\n"

            for listener in class_info.state_listeners:
                section += f"- **{listener.entity}**\n"
                section += f"  - **Callback**: `{listener.callback_method}()`\n"

                if listener.old_state and listener.new_state:
                    section += f"  - **Trigger**: `{listener.old_state}` → `{listener.new_state}`\n"
                elif listener.new_state:
                    section += f"  - **Trigger**: Any → `{listener.new_state}`\n"
                elif listener.old_state:
                    section += f"  - **Trigger**: `{listener.old_state}` → Any\n"

                if listener.duration:
                    section += f"  - **Duration**: {listener.duration} seconds\n"

                if listener.kwargs:
                    extra_kwargs = {k: v for k, v in listener.kwargs.items() if k not in ["old", "new", "duration"]}
                    if extra_kwargs:
                        section += f"  - **Additional**: {extra_kwargs}\n"
                section += "\n"

        # MQTT Listeners
        if class_info.mqtt_listeners:
            section += "### MQTT Listeners\n\n"
            section += "This class listens to the following MQTT topics:\n\n"

            for mqtt in class_info.mqtt_listeners:
                section += f"- **Topic**: `{mqtt.topic}`\n"
                section += f"  - **Callback**: `{mqtt.callback_method}()`\n"
                section += f"  - **Namespace**: `{mqtt.namespace or 'default'}`\n"
                if mqtt.qos:
                    section += f"  - **QoS**: {mqtt.qos}\n"
                if mqtt.kwargs:
                    extra_kwargs = {k: v for k, v in mqtt.kwargs.items() if k not in ["topic", "namespace", "qos"]}
                    if extra_kwargs:
                        section += f"  - **Additional**: {extra_kwargs}\n"
                section += "\n"

        # Time Schedules
        if class_info.time_schedules:
            section += "### Time Schedules\n\n"
            section += "This class uses the following time-based automation:\n\n"

            for schedule in class_info.time_schedules:
                section += f"- **{schedule.schedule_type.replace('_', ' ').title()}**: `{schedule.callback_method}()`\n"
                if schedule.time_spec:
                    section += f"  - **Time**: {schedule.time_spec}\n"
                if schedule.interval:
                    section += f"  - **Interval**: Every {schedule.interval} seconds\n"
                if schedule.delay:
                    section += f"  - **Delay**: {schedule.delay} seconds\n"
                if schedule.kwargs:
                    section += f"  - **Parameters**: {schedule.kwargs}\n"
                section += "\n"

        # Service Calls
        if class_info.service_calls:
            section += "### Service Calls\n\n"
            section += "This class makes the following Home Assistant service calls:\n\n"

            # Group by service domain
            services_by_domain: dict[str, list[Any]] = {}
            for service in class_info.service_calls:
                domain = service.service_domain
                if domain not in services_by_domain:
                    services_by_domain[domain] = []
                services_by_domain[domain].append(service)

            for domain, services in services_by_domain.items():
                section += f"**{domain.title()} Domain:**\n"
                for service in services:
                    section += f"- `{service.service_domain}.{service.service_name}`"
                    if service.method_name:
                        section += f" (called from `{service.method_name}()`)"
                    section += "\n"
                    if service.entity_id:
                        section += f"  - **Entity**: {service.entity_id}\n"
                    if service.data:
                        section += f"  - **Data**: {service.data}\n"
                section += "\n"

        # Device Relationships
        if class_info.device_relationships:
            section += "### Device Relationships\n\n"
            section += "This class manages the following device interactions:\n\n"

            for rel in class_info.device_relationships:
                section += f"- **{rel.trigger_entity}** {rel.relationship_type} **{rel.target_entity}**\n"
                if rel.condition:
                    section += f"  - **Condition**: {rel.condition}\n"
                if rel.method_name:
                    section += f"  - **Method**: `{rel.method_name}()`\n"
                section += "\n"

        # Automation Flows
        if class_info.automation_flows:
            section += "### Automation Flows\n\n"
            section += "This class implements the following automation logic patterns:\n\n"

            # Group by flow type
            flows_by_type: dict[str, list[Any]] = {}
            for flow in class_info.automation_flows:
                flow_type = flow.flow_type
                if flow_type not in flows_by_type:
                    flows_by_type[flow_type] = []
                flows_by_type[flow_type].append(flow)

            for flow_type, flows in flows_by_type.items():
                section += f"**{flow_type.title()} Logic:**\n"
                for flow in flows[:3]:  # Limit to first 3 per type
                    section += f"- In `{flow.method_name}()`: "
                    section += f"{len(flow.conditions)} conditions, {len(flow.actions)} actions\n"
                    if flow.conditions:
                        section += f"  - **Conditions**: {', '.join(flow.conditions[:2])}\n"
                    if flow.actions:
                        section += f"  - **Actions**: {', '.join(flow.actions[:2])}\n"
                    if flow.entities_involved:
                        section += f"  - **Entities**: {', '.join(flow.entities_involved[:3])}\n"
                if len(flows) > 3:
                    section += f"  - ... and {len(flows) - 3} more {flow_type} flows\n"
                section += "\n"

        # Methods
        section += "### Methods\n\n"
        for method in class_info.methods:
            section += f"#### `{method.name}({', '.join(method.args)})`\n\n"

            if method.docstring:
                section += f"{method.docstring}\n\n"
            elif method.is_callback:
                section += "Callback method triggered by state changes. Handles automation logic when monitored entities change state.\n\n"
            elif method.name == "initialize":
                section += "AppDaemon initialization method. Sets up state listeners and configures the automation.\n\n"
            else:
                section += f"Helper method for {class_info.name} automation logic.\n\n"

            if method.decorators:
                section += f"**Decorators**: {', '.join(method.decorators)}\n\n"

        return section

    def _generate_automation_flow_diagram(self, class_info: ClassInfo) -> str:
        """Generate flow diagram showing automation logic."""
        section = f"### {class_info.name} Automation Flow\n\n"

        # Create a flow diagram based on state listeners and callbacks
        steps = []

        # Group listeners by entity for better visualization
        entity_groups: dict[str, list[Any]] = {}
        for listener in class_info.state_listeners:
            if listener.entity:
                if listener.entity not in entity_groups:
                    entity_groups[listener.entity] = []
                entity_groups[listener.entity].append(listener)

        step_id = 0
        for entity, listeners in entity_groups.items():
            # Sensor trigger
            entity_name = entity.split(".")[-1].replace("_", " ").title()
            steps.append({"id": f"sensor_{step_id}", "label": f"{entity_name}\\nState Change", "style": "SENSOR"})

            # Decision point if multiple conditions
            if len(listeners) > 1:
                steps.append({
                    "id": f"decision_{step_id}",
                    "label": "Check\\nConditions",
                    "style": "DECISION",
                    "shape": "diamond",
                })

            # Actions for each listener
            for i, listener in enumerate(listeners):
                action_label = listener.callback_method.replace("_", " ").title()
                if listener.duration:
                    action_label += f"\\n(after {listener.duration}s)"

                steps.append({"id": f"action_{step_id}_{i}", "label": action_label, "style": "ACTION"})

            step_id += 1

        if steps:
            flow_diagram = quick_flow(steps)
            section += f"```mermaid\n{flow_diagram}\n```\n\n"

        return section

    def _generate_configuration_section(self, parsed_file: ParsedFile) -> str:
        """Generate configuration and integration details."""
        section = "## Configuration\n\n"

        section += "### Required Entities\n\n"
        section += "This automation requires the following Home Assistant entities to be configured:\n\n"

        # Group constants by category
        entity_groups: dict[str, list[str]] = {}
        for const in sorted(parsed_file.constants_used):
            if "." in const:
                parts = const.split(".")
                category = parts[0] if len(parts) > 1 else "Other"
                if category not in entity_groups:
                    entity_groups[category] = []
                entity_groups[category].append(const)

        for category, entities in entity_groups.items():
            section += f"#### {category}\n\n"
            for entity in entities:
                # Extract likely entity ID from constant path
                entity_parts = entity.split(".")
                if len(entity_parts) >= 2:
                    likely_domain = self._guess_entity_domain(entity_parts[-1])
                    section += f"- **{entity}**: `{likely_domain}.{entity_parts[-1].lower()}`\n"
                else:
                    section += f"- **{entity}**\n"
            section += "\n"

        section += "### Dependencies\n\n"
        section += "- **AppDaemon**: Home Assistant automation platform\n"
        section += "- **Home Assistant**: Core smart home platform\n"

        if "Helpers" in str(parsed_file.imports):
            section += "- **Helpers**: Utility functions from `utils.py`\n"

        for imp in parsed_file.imports:
            if "const" in imp.lower():
                section += "- **Constants**: Device and room configurations from `const.py`\n"
            elif "infra" in imp.lower():
                section += "- **Infrastructure**: Base classes from `infra.py`\n"

        return section

    def _generate_api_reference(self, parsed_file: ParsedFile) -> str:
        """Generate API reference documentation."""
        section = "## API Reference\n\n"

        for class_info in parsed_file.classes:
            section += f"### {class_info.name} Class\n\n"

            # Constructor
            init_method = next((m for m in class_info.methods if m.name == "initialize"), None)
            if init_method:
                section += "#### Initialization\n\n"
                section += "```python\n"
                section += "# AppDaemon calls initialize() automatically\n"
                if init_method.source_code:
                    # Show key parts of initialization
                    lines = init_method.source_code.split("\n")
                    relevant_lines = [line for line in lines if "listen_state" in line or "helpers" in line.lower()][:5]
                    for line in relevant_lines:
                        section += f"{line.strip()}\n"
                section += "```\n\n"

            # Public methods (non-private, non-initialize)
            public_methods = [m for m in class_info.methods if not m.name.startswith("_") and m.name != "initialize"]

            if public_methods:
                section += "#### Public Methods\n\n"
                for method in public_methods:
                    section += f"##### `{method.name}({', '.join(method.args[1:])})`\n\n"  # Skip 'self'

                    if method.docstring:
                        section += f"{method.docstring}\n\n"

                    if method.is_callback:
                        section += "**Type**: State change callback\n\n"
                        section += "**Parameters**:\n"
                        if len(method.args) >= 5:
                            section += "- `entity`: Entity ID that triggered the state change\n"
                            section += "- `attribute`: Attribute that changed (usually 'state')\n"
                            section += "- `old`: Previous state value\n"
                            section += "- `new`: New state value\n"
                            section += "- `kwargs`: Additional parameters from listener configuration\n\n"

                    section += "---\n\n"

        return section

    def _generate_logic_flow_diagrams(self, parsed_file: ParsedFile) -> str:
        """Generate logic flow diagrams for key methods like climate.md."""
        section = "## Logic Flow Diagram\n\n"

        # Find a callback method with actions to diagram
        for class_info in parsed_file.classes:
            for method in class_info.methods:
                if method.is_callback and method.actions:
                    section += f"### {method.name}() Flow\n\n"
                    diagram = create_method_flow_diagram(method)
                    section += f"```mermaid\n{diagram}\n```\n\n"
                    break  # Only show one method flow for now
            if "Flow" in section:
                break

        return section

    def _generate_enhanced_api_documentation(self, parsed_file: ParsedFile) -> str:
        """Generate API documentation section matching climate.md format."""
        section = "## API Documentation\n\n"

        section += "### Methods\n\n"

        for class_info in parsed_file.classes:
            for method in class_info.methods:
                section += f"#### `{method.name}()`\n\n"

                if method.name == "initialize":
                    section += "**Purpose:** Module initialization and listener setup  \n"
                    section += "**Parameters:** None  \n"
                    section += "**Returns:** None\n\n"
                    section += f"Sets up {len(class_info.state_listeners)} state listeners for automation triggers.\n\n"

                elif method.is_callback:
                    section += "**Purpose:** Event callback handler  \n"
                    section += "**Parameters:**\n"
                    section += "- `entity`: Entity that triggered the event\n"
                    section += "- `attribute`: Changed attribute name\n"
                    section += "- `old`: Previous state value\n"
                    section += "- `new`: New state value\n"
                    section += "- `kwargs`: Additional callback parameters\n\n"

                    # Create actions summary like climate.md
                    action_summary = self._create_method_action_summary(method)
                    section += f"**Actions:** {action_summary}  \n"

                    if method.performance_pattern and method.performance_pattern.has_timing:
                        threshold = method.performance_pattern.threshold_ms or 300
                        section += f"**Performance:** Real-time monitoring with {threshold}ms threshold alerts\n\n"
                    else:
                        section += "\n"

                else:
                    # Utility methods
                    if method.conditional_count > 0 or method.actions:
                        action_summary = self._create_method_action_summary(method)
                        section += f"**Purpose:** {action_summary}\n\n"
                    else:
                        section += "**Purpose:** Helper method\n\n"

        # Add utility methods section if any exist
        utility_methods = []
        for class_info in parsed_file.classes:
            for method in class_info.methods:
                if not method.is_callback and method.name != "initialize" and not method.name.startswith("_"):
                    utility_methods.append(method)

        if utility_methods:
            section += "### Utility Methods\n\n"
            for method in utility_methods:
                section += f"#### `{method.name}({', '.join(method.args)})`\n\n"
                action_summary = self._create_method_action_summary(method)
                section += f"**Purpose:** {action_summary}\n\n"

        return section

    def _generate_enhanced_configuration_section(self, parsed_file: ParsedFile) -> str:
        """Generate configuration section matching climate.md format."""
        section = "## Configuration\n\n"

        section += "### State Listeners\n\n"

        # List all state listeners across all classes
        for class_info in parsed_file.classes:
            if class_info.state_listeners:
                for listener in class_info.state_listeners:
                    section += f"- **{listener.entity}**: `{listener.callback_method}()`\n"

        if not any(cls.state_listeners for cls in parsed_file.classes):
            section += "No state listeners configured.\n"

        section += "\n"

        return section

    def _generate_performance_monitoring_section(self, parsed_file: ParsedFile) -> str:
        """Generate performance monitoring section like climate.md."""
        section = "## Performance Monitoring\n\n"

        # Check if any methods have performance monitoring
        has_monitoring = any(
            any(m.performance_pattern and m.performance_pattern.has_timing for m in cls.methods)
            for cls in parsed_file.classes
        )

        if has_monitoring:
            section += "This automation includes real-time performance monitoring:\n\n"

            # Find threshold
            threshold = 300  # default
            for cls in parsed_file.classes:
                for method in cls.methods:
                    if method.performance_pattern and method.performance_pattern.threshold_ms:
                        threshold = method.performance_pattern.threshold_ms
                        break

            section += "- **Timing:** Each callback execution is measured\n"
            section += f"- **Threshold:** {threshold}ms alert threshold for critical operations\n"
            section += "- **Logging:** Performance metrics logged with each action\n"
            section += "- **Pattern:** Execute device actions first, then logging operations\n\n"

            section += "### Performance-First Design\n\n"
            section += "```python\n"
            section += "# ✅ CORRECT - Action first, then logging\n"
            section += "self.turn_on(entity)                    # Execute immediately\n"
            section += "state = self.get_state(entity)          # Log after action\n"
            section += 'self.log(f"Action completed: {state}")\n\n'
            section += "# ❌ INCORRECT - Logging delays action\n"
            section += "state_before = self.get_state(entity)   # Unnecessary delay\n"
            section += "self.turn_on(entity)                    # Delayed execution\n"
            section += "```\n\n"
        else:
            section += "No performance monitoring detected in this module.\n\n"

        return section

    def _generate_integration_points_section(self, parsed_file: ParsedFile) -> str:
        """Generate integration points section like climate.md."""
        section = "## Integration Points\n\n"

        section += "### External Dependencies\n"

        # Count different types of constants used
        const_types: dict[str, list[str]] = {}
        for const in parsed_file.constants_used:
            if "." in const:
                prefix = const.split(".")[0]
                if prefix not in const_types:
                    const_types[prefix] = []
                const_types[prefix].append(const)

        for const_type, constants in const_types.items():
            if const_type in ["Home", "Persons", "Actions", "General"]:
                section += f"- **{const_type}:** Configuration and device references\n"

        section += "- **Infrastructure:** Base class with Home Assistant API\n"
        section += "- **Utilities:** Helper functions for notifications and communication\n\n"

        section += "### Home Assistant Integration\n"
        section += "- **API:** Native AppDaemon plugin integration\n"
        section += "- **States:** Real-time entity state monitoring\n"
        section += "- **Actions:** Direct device control commands\n\n"

        # Check for MQTT usage
        has_mqtt = any(cls.mqtt_listeners for cls in parsed_file.classes)
        if has_mqtt:
            section += "### MQTT Integration\n"
            section += "- **Protocol:** Direct MQTT communication for supported devices\n"
            section += "- **Topics:** Device-specific MQTT topics for state and control\n\n"

        return section

    def _create_method_action_summary(self, method: Any) -> str:
        """Create action summary for a method like in climate.md."""
        action_parts = []

        if method.conditional_count > 0:
            action_parts.append("Conditional logic")
        if method.loop_count > 0:
            action_parts.append("Loop iteration")
        if method.notification_count > 0:
            action_parts.append("Notification: send_notify")
        if any(a.action_type == "logging" for a in method.actions):
            action_parts.append("Logging")
        if method.device_action_count > 0:
            action_parts.append("Device action")

        return " | ".join(action_parts) if action_parts else "Processing"

    def _format_title(self, file_name: str) -> str:
        """Convert filename to readable title."""
        title = file_name.replace("_", " ").title()

        # Handle common abbreviations
        title = title.replace("Ac", "AC")
        title = title.replace("Ir", "IR")
        title = title.replace("Tv", "TV")
        title = title.replace("Api", "API")

        return title

    def _guess_entity_domain(self, entity_name: str) -> str:
        """Guess the Home Assistant domain from entity name."""
        entity_lower = entity_name.lower()

        if "sensor" in entity_lower or "temperature" in entity_lower:
            return "sensor"
        elif "switch" in entity_lower or "plug" in entity_lower:
            return "switch"
        elif "light" in entity_lower or "bulb" in entity_lower:
            return "light"
        elif "cover" in entity_lower or "curtain" in entity_lower:
            return "cover"
        elif "climate" in entity_lower or "ac" in entity_lower:
            return "climate"
        elif "binary" in entity_lower or "motion" in entity_lower or "door" in entity_lower:
            return "binary_sensor"
        elif "camera" in entity_lower:
            return "camera"
        elif "lock" in entity_lower:
            return "lock"
        else:
            return "sensor"  # Default fallback

    def _load_constants_map(self) -> dict[str, str]:
        """Load mapping of constants to actual entity IDs (could be enhanced to read const.py)."""
        # This could be enhanced to actually parse const.py and build a real mapping
        return {}

    def _get_initialization_details(self, parsed_file: ParsedFile) -> str:
        """Generate detailed initialization information for collapsible section."""
        details = ""

        for class_info in parsed_file.classes:
            if class_info.state_listeners:
                for listener in class_info.state_listeners:
                    details += f'  - `listen_state({listener.callback_method}, "{listener.entity}")`\n'

            if class_info.mqtt_listeners:
                for mqtt in class_info.mqtt_listeners:
                    details += f'  - `listen_event({mqtt.callback_method}, "{mqtt.topic}")`\n'

            if class_info.time_schedules:
                for schedule in class_info.time_schedules:
                    if schedule.schedule_type == "run_daily":
                        details += f'  - `run_daily({schedule.callback_method}, "{schedule.time_spec}")`\n'
                    elif schedule.schedule_type == "run_every":
                        details += f"  - `run_every({schedule.callback_method}, {schedule.interval})`\n"
                    else:
                        details += f"  - `{schedule.schedule_type}({schedule.callback_method})`\n"

        return details.strip()

    def _get_methods_details(self, parsed_file: ParsedFile) -> str:
        """Generate detailed methods information for collapsible section."""
        details = ""

        for class_info in parsed_file.classes:
            for method in class_info.methods:
                if method.name == "initialize":
                    details += f"  - `{method.name}()` - AppDaemon initialization\n"
                elif method.is_callback:
                    # Skip callbacks here, they have their own section
                    continue
                else:
                    action_summary = self._create_method_action_summary(method)
                    purpose = action_summary if action_summary != "Processing" else "Helper method"
                    details += f"  - `{method.name}()` - {purpose}\n"

        return details.strip()

    def _get_callbacks_details(self, parsed_file: ParsedFile) -> str:
        """Generate detailed callbacks information for collapsible section."""
        details = ""

        for class_info in parsed_file.classes:
            for method in class_info.methods:
                if method.is_callback:
                    action_summary = self._create_method_action_summary(method)
                    # Find the entities this callback handles
                    entities = []
                    for listener in class_info.state_listeners:
                        if listener.callback_method == method.name:
                            entities.append(listener.entity)

                    entity_text = f" - {', '.join([e for e in entities[:2] if e is not None])}" if entities else ""
                    if len(entities) > 2:
                        entity_text += f" (+{len(entities) - 2} more)"

                    details += f"  - `{method.name}()` - {action_summary}{entity_text}\n"

        return details.strip()


def generate_appdaemon_docs(file_path: str | Path, output_path: str | Path | None = None) -> str:
    """
    Generate documentation for an AppDaemon file.

    Args:
        file_path: Path to the AppDaemon Python file
        output_path: Optional path to save the generated documentation

    Returns:
        Generated markdown documentation
    """

    # Parse the file
    parsed_file = parse_appdaemon_file(file_path)

    # Generate documentation
    generator = AppDaemonDocGenerator()
    docs = generator.generate_documentation(parsed_file)

    # Save if output path provided
    if output_path:
        Path(output_path).write_text(docs, encoding="utf-8")

    return docs
