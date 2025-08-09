"""
AppDaemon Documentation Generator

This module generates comprehensive markdown documentation with interactive
Cytoscape.js diagrams (no Mermaid) from parsed AppDaemon automation files.
It creates standardized documentation with technical overviews and flow charts.
"""

from pathlib import Path
from typing import Any
from types import SimpleNamespace
import os
import datetime

from server.parsers.appdaemon_parser import ClassInfo, ParsedFile
import json
from urllib.parse import quote
from server.generators.flow_extractors import try_code2flow_on_source


class AppDaemonDocGenerator:
    """Generates markdown documentation for AppDaemon automation files."""

    def __init__(self, docs_dir: str | None = None) -> None:
        """Initialize the documentation generator."""
        self.constants_map = self._load_constants_map()
        self.docs_dir = Path(docs_dir) if docs_dir else None
        # Simple i18n hook (English default)
        self._strings = {
            "quick_facts": "Quick Facts",
            "triggers_conditions_actions": "Triggers, Conditions, and Actions",
            "triggers": "Triggers",
            "conditions": "Conditions",
            "actions": "Actions",
            "schedules": "Schedules",
            "entities": "Entities",
            "reads": "Reads (monitors)",
            "writes": "Writes (controls)",
            "author_notes": "Author Notes",
            "app_config": "App Configuration (apps.yaml)",
            "source": "Source",
        }

    def generate_documentation(self, parsed_file: ParsedFile) -> str:
        """
        Generate complete markdown documentation for a parsed AppDaemon file.

        Args:
            parsed_file: Parsed information from an AppDaemon file

        Returns:
            Complete markdown documentation string
        """
        file_name = Path(parsed_file.file_path).stem
        # Keep a reference for entity resolution during generation
        self._current_parsed_file: ParsedFile | None = parsed_file

        sections = []

        # Title and overview
        sections.append(self._generate_header(file_name, parsed_file))

        # Technical overview
        sections.append(self._generate_technical_overview(parsed_file))

        # Architecture diagram removed - replaced with enhanced technical overview

        # Quick facts
        sections.append(self._generate_quick_facts(parsed_file))

        # Triggers → Conditions → Actions
        sections.append(self._generate_triggers_conditions_actions(parsed_file))

        # Time schedules
        sections.append(self._generate_schedules_section(parsed_file))

        # Entities (reads/writes)
        sections.append(self._generate_entities_read_write(parsed_file))

        # Author notes (class docstrings)
        notes = self._generate_author_notes(parsed_file)
        if notes:
            sections.append(notes)

        # apps.yaml configuration examples
        cfg = self._generate_app_configuration_snippet(parsed_file)
        if cfg:
            sections.append(cfg)

        # Generate logic flow diagrams for key methods (Cytoscape JSON embedded)
        sections.append(self._generate_logic_flow_diagrams(parsed_file))

        # Call graph overview removed per product direction

        # API documentation removed for streamlined docs

        # Configuration section
        sections.append(self._generate_enhanced_configuration_section(parsed_file))

        # Integration points removed for generic docs

        # Enhanced sections for new analysis patterns
        sections.append(self._generate_app_dependencies_section(parsed_file))

        sections.append(self._generate_error_handling_section(parsed_file))

        output: str = "\n\n".join(sections)
        # Clear the reference to avoid leaking state between calls
        self._current_parsed_file = None
        return output

    # Call graph generation removed

    @staticmethod
    def _wrap_expandable(summary_html: str, body_html: str) -> str:
        """Create a consistent expandable block.

        Args:
            summary_html: HTML to display in the <summary> element (no surrounding tags added).
            body_html: Inner HTML content for the expanded area.

        Returns:
            A standardized <details> block with consistent indentation styling.
        """
        return (
            f"<details><summary>{summary_html}</summary>\n\n"
            f'<div style="margin-left: 16px;">\n{body_html}\n</div>\n'
            f"</details>\n"
        )

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

        # Last updated from source file mtime
        try:
            mtime = os.path.getmtime(parsed_file.file_path)
            dt = datetime.datetime.fromtimestamp(mtime)
            header += f"> **Last Updated:** `{dt.isoformat(timespec='seconds')}`\n\n"
        except Exception:
            pass

        header += "## Overview\n\n"

        if parsed_file.module_docstring:
            header += f"{parsed_file.module_docstring}\n\n"
        else:
            header += f"Automation module for {title.lower()} management in the smart home system.\n\n"

        return header

    def _resolve_entity(self, entity: Any, parsed_file: ParsedFile | None = None) -> str:
        """Resolve code constant to real entity ID using parser mapping; fallback to original."""
        pf = parsed_file or getattr(self, "_current_parsed_file", None)
        try:
            if isinstance(entity, str) and pf is not None:
                mapping = getattr(pf, "constant_value_map", {}) or {}
                resolved = mapping.get(entity, entity)
                return str(resolved)
            return str(entity) if entity is not None else ""
        except Exception:
            return str(entity) if entity is not None else ""

    def _generate_technical_overview(self, parsed_file: ParsedFile) -> str:
        """Generate enhanced technical overview with collapsible sections."""
        section = "## Technical Overview\n\n"

        # Architecture bullet points like climate.md
        section += "### Architecture\n\n"

        # Count state listeners across all classes
        total_listeners = sum(len(cls.state_listeners) for cls in parsed_file.classes)
        initialization_details = self._get_initialization_details(parsed_file)
        if initialization_details:
            summary = f"<strong>Initialization:</strong> {total_listeners} state listeners configured"
            section += self._wrap_expandable(summary, initialization_details)
        else:
            section += f"- **Initialization:** {total_listeners} state listeners configured\n"

        # Count methods across all classes
        total_methods = sum(len(cls.methods) for cls in parsed_file.classes)
        methods_details = self._get_methods_details(parsed_file)
        if methods_details:
            summary = f"<strong>Methods:</strong> {total_methods} total methods"
            section += self._wrap_expandable(summary, methods_details)
        else:
            section += f"- **Methods:** {total_methods} total methods\n"

        # Count callback methods
        total_callbacks = sum(len([m for m in cls.methods if m.is_callback]) for cls in parsed_file.classes)
        callbacks_details = self._get_callbacks_details(parsed_file)
        if callbacks_details:
            summary = f"<strong>Callbacks:</strong> {total_callbacks} callback methods"
            section += self._wrap_expandable(summary, callbacks_details)
        else:
            section += f"- **Callbacks:** {total_callbacks} callback methods\n"

        # Performance monitoring detection (single line, avoid duplication)
        perf_added = False
        for class_info in parsed_file.classes:
            for method in class_info.methods:
                if method.performance_pattern and method.performance_pattern.has_timing:
                    threshold = method.performance_pattern.threshold_ms
                    threshold_text = f" ({threshold}ms threshold)" if threshold else ""
                    section += f"- **Performance:** Real-time monitoring enabled{threshold_text}\n"
                    perf_added = True
                    break
            else:
                continue
            if perf_added:
                break

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
                section += f"- **{self._resolve_entity(listener.entity)}**\n"
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
                        section += f"  - **Entity**: {self._resolve_entity(service.entity_id)}\n"
                    if service.data:
                        section += f"  - **Data**: {service.data}\n"
                section += "\n"

        # Device Relationships
        if class_info.device_relationships:
            section += "### Device Relationships\n\n"
            section += "This class manages the following device interactions:\n\n"

            for rel in class_info.device_relationships:
                section += f"- **{self._resolve_entity(rel.trigger_entity)}** {rel.relationship_type} **{self._resolve_entity(rel.target_entity)}**\n"
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
                        resolved_entities = [self._resolve_entity(ent) for ent in flow.entities_involved[:3]]
                        section += f"  - **Entities**: {', '.join(resolved_entities)}\n"
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
        """Generate flow diagram (Cytoscape) showing automation logic."""
        section = f"### {class_info.name} Automation Flow\n\n"

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        prev_id: str | None = None
        nid = 0
        for listener in class_info.state_listeners:
            label = (listener.callback_method or "callback").replace("_", " ")
            cur_id = f"n{nid}"
            nid += 1
            nodes.append({"data": {"id": cur_id, "label": label, "type": "action"}})
            if prev_id:
                edges.append({"data": {"id": f"e{nid}", "source": prev_id, "target": cur_id}})
            prev_id = cur_id

        if nodes:
            payload = quote(json.dumps({"elements": {"nodes": nodes, "edges": edges}}))
            section += (
                '<div class="cytoscape-wrapper">'
                '<div class="cytoscape-diagram" data-graph="' + payload + '"></div>'
                "</div>\n\n"
            )

        return section

    def _generate_configuration_section(self, parsed_file: ParsedFile) -> str:
        """Generate configuration and integration details."""
        section = "## Configuration\n\n"

        section += "### Required Entities\n\n"
        section += "This automation requires the following Home Assistant entities to be configured:\n\n"

        # Group constants by category (generic namespaces)
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
                # Keep entity rendering generic; the actual domain is project-specific
                section += f"- **{entity}**\n"
            section += "\n"

        section += "### Dependencies\n\n"
        section += "- **AppDaemon**: Automation runtime\n"
        section += "- **Home Assistant**: Platform integration\n"
        # Keep this section generic; specific helper or infrastructure modules vary by project

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
        """Generate logic flow diagrams for key methods using Cytoscape."""
        section = "## Logic Flow Diagram\n\n"

        # Collect callback methods with actions
        callback_methods: list[Any] = []
        for class_info in parsed_file.classes:
            for method in class_info.methods:
                if method.is_callback and method.actions:
                    callback_methods.append(method)
        callback_methods = callback_methods[:5]

        if not callback_methods:
            return section

        # Build a single graph with subflows per method, including triggers ➜ conditions ➜ actions
        elements_nodes: list[dict[str, Any]] = []
        elements_edges: list[dict[str, Any]] = []
        nid = 0
        for mi, method in enumerate(callback_methods):
            # If code2flow is available and we have source, prefer extractor output
            extracted = (
                try_code2flow_on_source(getattr(method, "source_code", ""))
                if getattr(method, "source_code", None)
                else None
            )
            if extracted and extracted.nodes:
                idmap: dict[str, str] = {}
                for n in extracted.nodes:
                    old = n["data"]["id"]
                    new = f"m{mi}_{old}"
                    idmap[old] = new
                    elements_nodes.append({"data": {"id": new, "label": n["data"].get("label", old), "type": "action"}})
                for e in extracted.edges:
                    s = idmap.get(e["data"]["source"], f"m{mi}_{e['data']['source']}")
                    t = idmap.get(e["data"]["target"], f"m{mi}_{e['data']['target']}")
                    elements_edges.append({"data": {"id": f"e{nid}", "source": s, "target": t}})
                    nid += 1
                # Prepend triggers
                triggers = []
                for cls in parsed_file.classes:
                    for l in cls.state_listeners:
                        if l.callback_method == method.name:
                            parts = []
                            if l.entity:
                                parts.append(self._resolve_entity(l.entity, parsed_file))
                            if l.old_state or l.new_state:
                                parts.append(f"{l.old_state or '*'}→{l.new_state or '*'}")
                            label = " | ".join(parts) if parts else "State change"
                            if label and label not in triggers:
                                triggers.append(label)
                if triggers:
                    t_id = f"t_{mi}"
                    elements_nodes.append({"data": {"id": t_id, "label": "\n".join(triggers), "type": "trigger"}})
                    first = extracted.nodes[0]["data"]["id"]
                    elements_edges.append({
                        "data": {"id": f"e{nid}", "source": t_id, "target": f"m{mi}_{first}", "label": "on"}
                    })
                    nid += 1
                continue

            # Method entry node ensures connectivity even if no explicit triggers were detected
            m_id = f"s_{mi}"
            elements_nodes.append({
                "data": {
                    "id": m_id,
                    "label": f"{method.name}()",
                    "type": "method",
                    "title": f"Callback {method.name}()",
                }
            })
            prev = m_id
            # Triggers from state listeners
            triggers = []
            for cls in parsed_file.classes:
                for l in cls.state_listeners:
                    if l.callback_method == method.name:
                        parts = []
                        if l.entity:
                            parts.append(self._resolve_entity(l.entity, parsed_file))
                        if l.old_state or l.new_state:
                            parts.append(f"{l.old_state or '*'}→{l.new_state or '*'}")
                        if l.duration:
                            parts.append(f"after {l.duration}s")
                        label = " | ".join(parts) if parts else "State change"
                        if label and label not in triggers:
                            triggers.append(label)
            # Add trigger node (summarized)
            if triggers:
                t_id = f"t_{mi}"
                elements_nodes.append({
                    "data": {
                        "id": t_id,
                        "label": "\n".join(triggers),
                        "type": "trigger",
                        "title": f"Triggers for {method.name}()",
                    }
                })
                elements_edges.append({"data": {"id": f"e{nid}", "source": prev, "target": t_id, "label": "on"}})
                nid += 1
                prev = t_id

            # Optional combined condition node
            # Collect short natural-language conditions (extracted earlier into automation_flows)
            conds: list[str] = []
            for cls in parsed_file.classes:
                for flow in getattr(cls, "automation_flows", []):
                    if flow.method_name == method.name and flow.conditions:
                        for c in flow.conditions[:2]:
                            if c not in conds:
                                conds.append(c)
            if conds:
                c_id = f"c_{mi}"
                c_label = "\nAND\n".join(conds[:2])
                elements_nodes.append({
                    "data": {"id": c_id, "label": c_label, "type": "condition", "title": " and ".join(conds)}
                })
                if prev is not None:
                    elements_edges.append({"data": {"id": f"e{nid}", "source": prev, "target": c_id, "label": "when"}})
                    nid += 1
                prev = c_id

            for ai, action in enumerate(getattr(method, "actions", [])):
                # Short label for node; richer details go into tooltip title
                label = action.description.split("(")[0][:36].strip()
                title = action.description
                extra = []
                if getattr(action, "entities_involved", None):
                    extra.append(", ".join(action.entities_involved[:2]))
                if extra:
                    label += "\n" + " | ".join(extra)
                n_id = f"m{mi}_a{ai}"
                elements_nodes.append({"data": {"id": n_id, "label": label, "title": title, "type": "action"}})
                if prev is not None:
                    edge_label = "then" if prev and str(prev).startswith("c_") else "next"
                    elements_edges.append({
                        "data": {"id": f"e{nid}", "source": prev, "target": n_id, "label": edge_label}
                    })
                    nid += 1
                prev = n_id

        graph = {"elements": {"nodes": elements_nodes, "edges": elements_edges}}
        payload = quote(json.dumps(graph))
        section += (
            '<div class="cy-legend">'
            '<span class="lg lg-trigger">Trigger</span>'
            '<span class="lg lg-condition">Condition</span>'
            '<span class="lg lg-action">Action</span>'
            "</div>"
            '<div class="cytoscape-wrapper">'
            '<div class="cytoscape-diagram" data-graph="' + payload + '"></div>'
            "</div>\n\n"
        )

        return section

    # Removed: _generate_enhanced_api_documentation (not used)

    def _generate_enhanced_configuration_section(self, parsed_file: ParsedFile) -> str:
        """Generate configuration section matching climate.md format."""
        section = "## Configuration\n\n"

        section += "### State Listeners\n\n"

        # List all state listeners across all classes with resolved entity names
        for class_info in parsed_file.classes:
            if class_info.state_listeners:
                for listener in class_info.state_listeners:
                    section += (
                        f"- **{self._resolve_entity(listener.entity, parsed_file)}**: `{listener.callback_method}()`\n"
                    )

        if not any(cls.state_listeners for cls in parsed_file.classes):
            section += "No state listeners configured.\n"

        section += "\n"

        return section

    def _generate_quick_facts(self, parsed_file: ParsedFile) -> str:
        """Top summary with counts and basic info."""
        triggers = sum(len(c.state_listeners) for c in parsed_file.classes)
        schedules = sum(len(c.time_schedules) for c in parsed_file.classes)
        service_calls = sum(len(c.service_calls) for c in parsed_file.classes)
        methods = sum(len(c.methods) for c in parsed_file.classes)

        # Entities touched
        entities: set[str] = set()
        for c in parsed_file.classes:
            for l in c.state_listeners:
                if l.entity:
                    entities.add(self._resolve_entity(l.entity, parsed_file))
            for s in c.service_calls:
                if s.entity_id:
                    entities.add(self._resolve_entity(s.entity_id, parsed_file))
            for r in c.device_relationships:
                entities.add(self._resolve_entity(r.trigger_entity, parsed_file))
                entities.add(self._resolve_entity(r.target_entity, parsed_file))
            for f in c.automation_flows:
                for e in f.entities_involved:
                    entities.add(self._resolve_entity(e, parsed_file))

        section = "## Quick Facts\n\n"
        section += f"- **Triggers**: {triggers}\n"
        section += f"- **Actions**: {service_calls}\n"
        section += f"- **Schedules**: {schedules}\n"
        section += f"- **Methods**: {methods}\n"
        section += f"- **Entities touched**: {len({e for e in entities if e})}\n\n"
        return section

    def _generate_triggers_conditions_actions(self, parsed_file: ParsedFile) -> str:
        """Render triggers, conditions and actions in tabular form."""
        lines: list[str] = []
        lines.append(f"## {self._t('triggers_conditions_actions')}\n")

        # Triggers
        lines.append(f"### {self._t('triggers')}\n")
        lines.append(f"Entity | Transition | Duration | Callback | {self._t('source')}")
        lines.append("---|---|---|---|---")
        for c in parsed_file.classes:
            for l in c.state_listeners:
                ent = self._resolve_entity(l.entity, parsed_file) if l.entity else ""
                trans = ""
                if l.old_state or l.new_state:
                    trans = f"{l.old_state or '*'} → {l.new_state or '*'}"
                dur = str(l.duration) if l.duration is not None else ""
                cb = l.callback_method or ""
                src = self._source_link(parsed_file.file_path, l.line_number)
                lines.append(f"`{ent}` | `{trans}` | `{dur}` | `{cb}` | {src}")
        lines.append("")

        # Conditions (per method)
        lines.append(f"### {self._t('conditions')}\n")
        lines.append(f"Method | Conditions | {self._t('source')}")
        lines.append("---|---|---")
        for c in parsed_file.classes:
            for f in c.automation_flows:
                conds = ", ".join(f.conditions) if f.conditions else "(none)"
                src = self._source_link(parsed_file.file_path, f.line_number)
                lines.append(f"`{f.method_name}()` | {conds} | {src}")
        lines.append("")

        # Actions
        lines.append(f"### {self._t('actions')}\n")
        lines.append(f"Method | Service | Entity | Data | {self._t('source')}")
        lines.append("---|---|---|---|---")
        for c in parsed_file.classes:
            for s in c.service_calls:
                method = s.method_name or ""
                service = f"{s.service_domain}.{s.service_name}"
                ent = self._resolve_entity(s.entity_id, parsed_file) if s.entity_id else ""
                data = s.data or {}
                src = self._source_link(parsed_file.file_path, s.line_number)
                lines.append(f"`{method}()` | `{service}` | `{ent}` | `{data}` | {src}")
        lines.append("")

        return "\n".join(lines)

    def _generate_schedules_section(self, parsed_file: ParsedFile) -> str:
        lines: list[str] = []
        lines.append(f"## {self._t('schedules')}\n")
        lines.append(f"Type | Callback | Spec/Interval/Delay | {self._t('source')}")
        lines.append("---|---|---|---")
        for c in parsed_file.classes:
            for t in c.time_schedules:
                spec = (
                    t.time_spec
                    if t.time_spec is not None
                    else (t.interval if t.interval is not None else t.delay or "")
                )
                src = self._source_link(parsed_file.file_path, t.line_number)
                lines.append(f"`{t.schedule_type}` | `{t.callback_method}()` | `{spec}` | {src}")
        lines.append("")
        return "\n".join(lines)

    def _generate_entities_read_write(self, parsed_file: ParsedFile) -> str:
        """List read vs write entities for this app."""
        reads: set[str] = set()
        writes: set[str] = set()

        for c in parsed_file.classes:
            # Reads
            for l in c.state_listeners:
                if l.entity:
                    reads.add(self._resolve_entity(l.entity, parsed_file))
            for f in c.automation_flows:
                for e in f.entities_involved:
                    reads.add(self._resolve_entity(e, parsed_file))

            # Writes
            for s in c.service_calls:
                if s.entity_id:
                    writes.add(self._resolve_entity(s.entity_id, parsed_file))
                # Also check data.entity_id
                try:
                    if isinstance(s.data, dict) and "entity_id" in s.data:
                        ent = s.data["entity_id"]
                        if isinstance(ent, str):
                            writes.add(self._resolve_entity(ent, parsed_file))
                        elif isinstance(ent, list):
                            for item in ent:
                                writes.add(self._resolve_entity(item, parsed_file))
                except Exception:
                    pass
            for r in c.device_relationships:
                writes.add(self._resolve_entity(r.target_entity, parsed_file))

        # Filter unresolved placeholders, namespaced constants and service names
        def is_real_entity(name: str) -> bool:
            if not name:
                return False
            if any(name.startswith(prefix) for prefix in ("Home.", "Persons.", "Actions.", "General.")):
                return False
            if name.startswith("_"):
                return False
            if "/" in name:
                return False
            if "." not in name:
                return False
            domain, rest = name.split(".", 1)
            allowed_domains = {
                "alarm_control_panel",
                "binary_sensor",
                "button",
                "camera",
                "climate",
                "cover",
                "device_tracker",
                "fan",
                "group",
                "humidifier",
                "dehumidifier",
                "input_boolean",
                "input_number",
                "input_select",
                "light",
                "lock",
                "media_player",
                "number",
                "person",
                "remote",
                "scene",
                "script",
                "select",
                "sensor",
                "siren",
                "sun",
                "switch",
                "vacuum",
                "water_heater",
                "weather",
                "wled",
            }
            if domain not in allowed_domains:
                return False
            # Heuristic: filter out common service verbs mistakenly treated as entities
            service_verbs = {
                "turn_on",
                "turn_off",
                "toggle",
                "open_cover",
                "close_cover",
                "set_temperature",
                "open",
                "close",
                "lock",
                "unlock",
                "play_media",
                "volume_set",
            }
            second = rest.split(".", 1)[0]
            if second in service_verbs:
                return False
            return True

        reads = {e for e in reads if is_real_entity(e)}
        writes = {e for e in writes if is_real_entity(e)}

        lines: list[str] = [f"## {self._t('entities')}\n"]
        lines.append(f"### {self._t('reads')}\n")
        if reads:
            for e in sorted(reads):
                lines.append(f"- `{e}`")
        else:
            lines.append("- (none)")
        lines.append("")

        lines.append(f"### {self._t('writes')}\n")
        if writes:
            for e in sorted(writes):
                lines.append(f"- `{e}`")
        else:
            lines.append("- (none)")
        lines.append("")

        return "\n".join(lines)

    def _generate_author_notes(self, parsed_file: ParsedFile) -> str:
        notes: list[str] = []
        for cls in parsed_file.classes:
            if cls.docstring:
                notes.append(f"#### {cls.name}\n\n{cls.docstring.strip()}\n")
        if not notes:
            return ""
        return f"## {self._t('author_notes')}\n\n" + "\n\n".join(notes)

    def _generate_app_configuration_snippet(self, parsed_file: ParsedFile) -> str:
        deps = getattr(parsed_file, "app_dependencies", [])
        if not deps:
            return ""
        lines: list[str] = [f"## {self._t('app_config')}\n"]
        for dep in deps:
            app = getattr(dep, "app_name", "my_app")
            module = getattr(dep, "module_name", Path(parsed_file.file_path).stem)
            clazz = getattr(dep, "class_name", parsed_file.classes[0].name if parsed_file.classes else "")
            lines.append("```yaml")
            lines.append(f"{app}:")
            lines.append(f"  module: {module}")
            if clazz:
                lines.append(f"  class: {clazz}")
            lines.append("  # ... your options here ...")
            lines.append("````\n")
        return "\n".join(lines)

    def _t(self, key: str) -> str:
        return self._strings.get(key, key)

    def _source_link(self, file_path: str, line_number: int | None) -> str:
        try:
            stem = Path(file_path).stem
            if line_number is None:
                return f'<a href="#" class="source-link" data-module="{stem}">view</a>'
            return f'<a href="#" class="source-link" data-module="{stem}" data-line="{line_number}">L{line_number}</a>'
        except Exception:
            return "view"

    # (Removed) _generate_entities_involved_section

    # Removed: _generate_integration_points_section (not used)

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

        # Handle common abbreviations generically
        for before, after in [("Ac", "AC"), ("Ir", "IR"), ("Tv", "TV"), ("Api", "API")]:
            title = title.replace(before, after)

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
        html_parts: list[str] = []

        multiple_classes = len(parsed_file.classes) > 1

        for class_info in parsed_file.classes:
            section_parts: list[str] = []

            labeled_sections: list[tuple[str, str]] = []

            # State listeners
            if class_info.state_listeners:
                items = []
                for listener in class_info.state_listeners:
                    resolved_entity = self._resolve_entity(listener.entity, parsed_file)
                    cb = listener.callback_method or ""
                    cb_text = cb if cb.startswith("self.") else f"self.{cb}"
                    items.append(f'<li><code>listen_state({cb_text}, "{resolved_entity}")</code></li>')
                labeled_sections.append(("State listeners", "<ul>" + "\n".join(items) + "</ul>"))

            # MQTT listeners
            if class_info.mqtt_listeners:
                items = []
                for mqtt in class_info.mqtt_listeners:
                    items.append(f'<li><code>listen_event(self.{mqtt.callback_method}, "{mqtt.topic}")</code></li>')
                labeled_sections.append(("MQTT listeners", "<ul>" + "\n".join(items) + "</ul>"))

            # Time schedules
            if class_info.time_schedules:
                items = []
                for schedule in class_info.time_schedules:
                    if schedule.schedule_type == "run_daily":
                        items.append(
                            f'<li><code>run_daily(self.{schedule.callback_method}, "{schedule.time_spec}")</code></li>'
                        )
                    elif schedule.schedule_type == "run_every":
                        items.append(
                            f"<li><code>run_every(self.{schedule.callback_method}, {schedule.interval})</code></li>"
                        )
                    else:
                        items.append(f"<li><code>{schedule.schedule_type}(self.{schedule.callback_method})</code></li>")
                labeled_sections.append(("Time schedules", "<ul>" + "\n".join(items) + "</ul>"))

            # If only one section exists, show items without heading; otherwise include headings
            if labeled_sections:
                if len(labeled_sections) == 1:
                    section_parts.append(labeled_sections[0][1])
                else:
                    for label, content in labeled_sections:
                        section_parts.append(f"<div><em>{label}</em></div>\n{content}")

            if section_parts:
                # Only prefix class name when documenting multiple classes
                if multiple_classes:
                    html_parts.append(f"<div><strong>{class_info.name}</strong></div>\n" + "\n".join(section_parts))
                else:
                    html_parts.append("\n".join(section_parts))

        return "\n".join(html_parts).strip()

    def _get_methods_details(self, parsed_file: ParsedFile) -> str:
        """Generate detailed methods information for collapsible section."""
        items: list[str] = []

        for class_info in parsed_file.classes:
            for method in class_info.methods:
                if method.name == "initialize":
                    items.append(f"<li><code>{method.name}()</code> - AppDaemon initialization</li>")
                elif method.is_callback:
                    # Include callbacks to match the total count
                    action_summary = self._create_method_action_summary(method)
                    items.append(f"<li><code>{method.name}()</code> - Event callback ({action_summary})</li>")
                else:
                    action_summary = self._create_method_action_summary(method)
                    purpose = action_summary if action_summary != "Processing" else "Helper method"
                    items.append(f"<li><code>{method.name}()</code> - {purpose}</li>")

        if not items:
            return ""
        return "<ul>\n" + "\n".join(items) + "\n</ul>"

    def _get_callbacks_details(self, parsed_file: ParsedFile) -> str:
        """Generate detailed callbacks information for collapsible section."""
        items: list[str] = []

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

                    items.append(f"<li><code>{method.name}()</code> - {action_summary}{entity_text}</li>")

        if not items:
            return ""
        return "<ul>\n" + "\n".join(items) + "\n</ul>"

    def _generate_app_dependencies_section(self, parsed_file: ParsedFile) -> str:
        """Generate app dependencies section from apps.yaml analysis."""
        app_dependencies = getattr(parsed_file, "app_dependencies", None)
        if not app_dependencies:
            return ""

        section = "## App Dependencies\n\n"
        section += "### App Configuration\n\n"
        section += "This module may be referenced by project configuration (e.g., `apps.yaml`) with the following app instances:\n\n"

        for dep in app_dependencies:
            section += f"#### {dep.app_name}\n\n"
            section += f"- **Module**: `{dep.module_name}`\n"
            section += f"- **Class**: `{dep.class_name}`\n"

            if getattr(dep, "dependencies", None):
                section += f"- **Dependencies**: {', '.join(dep.dependencies)}\n"
            else:
                section += "- **Dependencies**: None\n"
            section += "\n"

        return section

    # Removed: _generate_person_centric_section (not used)

    # Removed: _generate_helper_injection_section (not used)

    def _generate_error_handling_section(self, parsed_file: ParsedFile) -> str:
        """Generate error handling patterns section."""
        # Access via getattr to avoid AttributeError if attribute is missing
        patterns = getattr(parsed_file, "error_handling_patterns", SimpleNamespace())

        has_try_catch = getattr(patterns, "has_try_catch", False)
        error_notification = getattr(patterns, "error_notification", False)
        recovery_mechanisms = getattr(patterns, "recovery_mechanisms", [])

        if not (has_try_catch or error_notification or recovery_mechanisms):
            return ""

        section = "## Error Handling & Recovery\n\n"
        section += "This automation implements comprehensive error handling:\n\n"

        if has_try_catch:
            section += "### Exception Handling\n"
            section += "- **Try-Catch Blocks**: Structured exception handling prevents automation failures\n"
            section += "- **Graceful Degradation**: Automation continues operating despite individual failures\n\n"

        if error_notification:
            section += "### Error Notifications\n"
            section += "- **Alert System**: Automatic notifications when errors occur\n"

            # Only mention specific transports if explicitly detected
            transports = [t.lower() for t in getattr(patterns, "notification_transports", [])]
            if "telegram" in transports:
                section += "- **Telegram Integration**: Real-time error alerts to administrators\n"
            elif transports:
                readable = ", ".join(sorted({t.capitalize() for t in transports}))
                section += f"- **Transports**: {readable}\n"
            else:
                section += "- **Delivery**: Supports configured notification transports\n"

            section += "\n"

        logging_on_error = getattr(patterns, "logging_on_error", False)
        if logging_on_error:
            section += "### Error Logging\n"
            section += "- **Detailed Logging**: Comprehensive error information for debugging\n"
            section += "- **Performance Tracking**: Error impact on system performance\n\n"

        if recovery_mechanisms:
            section += "### Recovery Mechanisms\n"
            for recovery in recovery_mechanisms:
                section += f"- **{recovery}**: Automatic recovery strategies\n"
            section += "\n"

        alert_patterns = getattr(patterns, "alert_patterns", [])
        if alert_patterns:
            section += "### Alert Patterns\n"
            for alert in alert_patterns:
                section += f"- **{alert}**: Proactive monitoring and alerting\n"
            section += "\n"

        return section

    # Removed: _generate_constant_hierarchy_section (not used)
