"""
Unified Mermaid Diagram Generator for AppDaemon Documentation

This module provides standardized functions to generate consistent Mermaid diagrams
across all AppDaemon automation documentation with unified styling and structure.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DiagramType(Enum):
    """Supported diagram types with standardized configurations."""

    FLOWCHART = "flowchart"
    SEQUENCE = "sequenceDiagram"
    STATE = "stateDiagram-v2"
    ARCHITECTURE = "graph"


class NodeStyle(Enum):
    """Predefined node styles with consistent color schemes matching climate.md quality."""

    SENSOR = "fill:#e3f2fd,stroke:#1976d2,stroke-width:2px"
    ACTION = "fill:#e8f5e8,stroke:#388e3c,stroke-width:2px"
    DECISION = "fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px"
    WARNING = "fill:#fff3e0,stroke:#f57c00,stroke-width:2px"
    ERROR = "fill:#ffebee,stroke:#d32f2f,stroke-width:2px"
    PROCESSING = "fill:#e1f5fe,stroke:#0277bd,stroke-width:2px"
    COMMUNICATION = "fill:#fce4ec,stroke:#c2185b,stroke-width:2px"
    TIMING = "fill:#f1f8e9,stroke:#689f38,stroke-width:2px"
    # Enhanced styles for climate.md quality
    INITIALIZATION = "fill:#f1f8e9,stroke:#689f38,stroke-width:2px"
    CALLBACK = "fill:#e1f5fe,stroke:#0277bd,stroke-width:2px"
    PERFORMANCE = "fill:#f1f8e9,stroke:#689f38,stroke-width:2px"
    CONDITIONAL = "fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px"
    LOGGING = "fill:#e1f5fe,stroke:#0277bd,stroke-width:2px"
    NOTIFICATION = "fill:#fce4ec,stroke:#c2185b,stroke-width:2px"


@dataclass
class DiagramNode:
    """Represents a node in a Mermaid diagram."""

    id: str
    label: str
    style: NodeStyle | None = None
    shape: str = "rect"  # rect, diamond, circle, etc.


@dataclass
class DiagramEdge:
    """Represents an edge/connection in a Mermaid diagram."""

    from_node: str
    to_node: str
    label: str | None = None
    style: str | None = None


@dataclass
class DiagramSubgraph:
    """Represents a subgraph for organizing related nodes."""

    id: str
    title: str
    nodes: list[DiagramNode]


class MermaidDiagramGenerator:
    """Unified generator for consistent Mermaid diagrams."""

    def __init__(self) -> None:
        """Initialize the diagram generator with standard configurations."""
        self.reset()

    def reset(self) -> None:
        """Reset the generator for a new diagram."""
        self.nodes: list[DiagramNode] = []
        self.edges: list[DiagramEdge] = []
        self.subgraphs: list[DiagramSubgraph] = []
        self.styles: list[str] = []

    def add_node(
        self, id: str, label: str, style: NodeStyle | None = None, shape: str = "rect"
    ) -> "MermaidDiagramGenerator":
        """Add a node to the diagram."""
        self.nodes.append(DiagramNode(id, label, style, shape))
        return self

    def add_edge(self, from_node: str, to_node: str, label: str | None = None) -> "MermaidDiagramGenerator":
        """Add an edge between two nodes."""
        self.edges.append(DiagramEdge(from_node, to_node, label))
        return self

    def add_subgraph(self, id: str, title: str, nodes: list[DiagramNode]) -> "MermaidDiagramGenerator":
        """Add a subgraph to organize related nodes."""
        self.subgraphs.append(DiagramSubgraph(id, title, nodes))
        return self

    def generate_flowchart(self, direction: str = "TD") -> str:
        """Generate a standardized flowchart diagram."""
        lines = [f"flowchart {direction}"]

        # Add subgraphs
        for subgraph in self.subgraphs:
            lines.append(f'    subgraph {subgraph.id} ["{subgraph.title}"]')
            for node in subgraph.nodes:
                node_def = self._format_node(node)
                lines.append(f"        {node_def}")
            lines.append("    end")
            lines.append("")

        # Add standalone nodes
        standalone_nodes = [n for n in self.nodes if not any(n in sg.nodes for sg in self.subgraphs)]
        for node in standalone_nodes:
            node_def = self._format_node(node)
            lines.append(f"    {node_def}")

        if standalone_nodes:
            lines.append("")

        # Add edges
        for edge in self.edges:
            edge_def = self._format_edge(edge)
            lines.append(f"    {edge_def}")

        if self.edges:
            lines.append("")

        # Add styling
        lines.append("    %% Styling")
        for node in self.nodes:
            if node.style:
                lines.append(f"    style {node.id} {node.style.value}")

        return "\n".join(lines)

    def generate_sequence_diagram(self, participants: list[str]) -> str:
        """Generate a standardized sequence diagram."""
        lines = ["sequenceDiagram"]

        # Add participants
        for participant in participants:
            lines.append(f"    participant {participant}")

        lines.append("")

        # Add interactions
        for edge in self.edges:
            if edge.label:
                lines.append(f"    {edge.from_node}->>{edge.to_node}: {edge.label}")
            else:
                lines.append(f"    {edge.from_node}->>{edge.to_node}: Action")

        return "\n".join(lines)

    def generate_state_diagram(self) -> str:
        """Generate a standardized state diagram."""
        lines = ["stateDiagram-v2"]
        lines.append("    [*] --> Initial")

        # Add state transitions
        for edge in self.edges:
            if edge.label:
                lines.append(f"    {edge.from_node} --> {edge.to_node} : {edge.label}")
            else:
                lines.append(f"    {edge.from_node} --> {edge.to_node}")

        # Add state descriptions
        for node in self.nodes:
            if node.label != node.id:
                lines.append(f"    {node.id} : {node.label}")

        return "\n".join(lines)

    def _format_node(self, node: DiagramNode) -> str:
        """Format a node for Mermaid syntax."""
        if node.shape == "diamond":
            return f"{node.id}{{{node.label}}}"
        elif node.shape == "circle":
            return f"{node.id}(({node.label}))"
        elif node.shape == "round":
            return f"{node.id}({node.label})"
        else:  # rectangle
            return f'{node.id}["{node.label}"]'

    def _format_edge(self, edge: DiagramEdge) -> str:
        """Format an edge for Mermaid syntax."""
        if edge.label:
            return f'{edge.from_node} -->|"{edge.label}"| {edge.to_node}'
        else:
            return f"{edge.from_node} --> {edge.to_node}"


# Universal diagram creation function
def create_diagram(config: dict[str, Any]) -> str:
    """
    Create any diagram from a simple configuration dictionary.

    Args:
        config: Dictionary containing:
            - type: "flowchart", "sequence", "state"
            - direction: "TD", "LR", "TB" (for flowchart)
            - sections: List of {title, nodes: [{id, label, style, shape}]}
            - connections: List of {from, to, label}

    Returns:
        Mermaid diagram string
    """
    generator = MermaidDiagramGenerator()
    diagram_type = config.get("type", "flowchart")

    # Add sections (subgraphs)
    for section in config.get("sections", []):
        nodes = []
        for node_config in section["nodes"]:
            style = getattr(NodeStyle, node_config.get("style", "PROCESSING"))
            node = DiagramNode(node_config["id"], node_config["label"], style, node_config.get("shape", "rect"))
            nodes.append(node)
        generator.add_subgraph(section.get("id", "section"), section["title"], nodes)

    # Add standalone nodes
    for node_config in config.get("nodes", []):
        style = getattr(NodeStyle, node_config.get("style", "PROCESSING"))
        generator.add_node(node_config["id"], node_config["label"], style, node_config.get("shape", "rect"))

    # Add connections
    for conn in config.get("connections", []):
        generator.add_edge(conn["from"], conn["to"], conn.get("label"))

    if diagram_type == "flowchart":
        direction = config.get("direction", "TD")
        return generator.generate_flowchart(direction)
    elif diagram_type == "sequence":
        participants = config.get("participants", [])
        return generator.generate_sequence_diagram(participants)
    elif diagram_type == "state":
        return generator.generate_state_diagram()

    return generator.generate_flowchart()


# Enhanced diagram generation functions for climate.md quality
def create_architecture_diagram(parsed_file: Any) -> str:
    """Create a complex architecture diagram like the one in climate.md."""
    generator = MermaidDiagramGenerator()

    # Create initialization section
    init_nodes = []
    for i, class_info in enumerate(parsed_file.classes):
        init_nodes.append(DiagramNode(id=f"init_{i}", label="initialize()", style=NodeStyle.INITIALIZATION))

    if init_nodes:
        generator.add_subgraph("initialization", "Initialization", init_nodes)

    # Create callbacks section
    callback_nodes = []
    for i, class_info in enumerate(parsed_file.classes):
        for j, method in enumerate(class_info.methods):
            if method.is_callback:
                # Create action summary for method
                action_summary = _create_action_summary(method)
                callback_nodes.append(
                    DiagramNode(
                        id=f"callback_{i}_{j}", label=f"{method.name}()<br/>{action_summary}", style=NodeStyle.CALLBACK
                    )
                )

    if callback_nodes:
        generator.add_subgraph("callbacks", "Event Callbacks", callback_nodes)

    return generator.generate_flowchart("TD")


def create_method_flow_diagram(method_info: Any) -> str:
    """Create a detailed flow diagram for a specific method."""
    generator = MermaidDiagramGenerator()

    # Create nodes for each action in the method
    for i, action in enumerate(method_info.actions):
        style = _get_action_style(action.action_type)
        shape = "diamond" if action.action_type == "conditional_logic" else "rect"

        node_id = f"step_{i}"
        label = action.description.replace(":", "")
        if action.action_type == "conditional_logic":
            label = "Decision Point"

        generator.add_node(node_id, label, style, shape)

        # Connect to previous step
        if i > 0:
            generator.add_edge(f"step_{i - 1}", node_id)

    diagram = generator.generate_flowchart("TD")

    # Add the styling comment
    diagram += "\n\n    %% Styling"

    return diagram


def _create_action_summary(method_info: Any) -> str:
    """Create a summary of actions for a method like in climate.md."""
    action_types = []

    if method_info.conditional_count > 0:
        action_types.append("Conditional logic")
    if method_info.loop_count > 0:
        action_types.append("Loop iteration")
    if method_info.notification_count > 0:
        action_types.append("Notification: send_notify")
    if any(a.action_type == "logging" for a in method_info.actions):
        action_types.append("Logging")
    if method_info.device_action_count > 0:
        action_types.append("Device action")

    return " | ".join(action_types) if action_types else "Processing"


def _get_action_style(action_type: str) -> NodeStyle:
    """Get appropriate style for action type."""
    style_map = {
        "conditional_logic": NodeStyle.CONDITIONAL,
        "loop_iteration": NodeStyle.PROCESSING,
        "notification": NodeStyle.NOTIFICATION,
        "logging": NodeStyle.LOGGING,
        "device_action": NodeStyle.ACTION,
        "api_call": NodeStyle.PROCESSING,
        "performance_timer": NodeStyle.PERFORMANCE,
    }
    return style_map.get(action_type, NodeStyle.PROCESSING)


# Quick helper for common patterns
def quick_flow(steps: list[dict[str, Any]]) -> str:
    """
    Quick flowchart from simple step list.

    Args:
        steps: List of {label, style?, shape?, connections?}

    Example:
        quick_flow([
            {"label": "Door Opens", "style": "SENSOR"},
            {"label": "Check Motion?", "style": "DECISION", "shape": "diamond"},
            {"label": "Turn Light ON", "style": "ACTION"}
        ])
    """
    config: dict[str, Any] = {"type": "flowchart", "nodes": [], "connections": []}

    for i, step in enumerate(steps):
        node_id = step.get("id", f"step_{i}")
        config["nodes"].append({
            "id": node_id,
            "label": step["label"],
            "style": step.get("style", "PROCESSING"),
            "shape": step.get("shape", "rect"),
        })

        # Auto-connect sequential steps
        if i > 0:
            prev_id = steps[i - 1].get("id", f"step_{i - 1}")
            config["connections"].append({"from": prev_id, "to": node_id, "label": step.get("connection_label")})

    return create_diagram(config)


if __name__ == "__main__":
    # Example 1: Simple sequential flow
    print("=== Quick Flow Example ===")
    print("```mermaid")
    print(
        quick_flow([
            {"label": "Door Opens", "style": "SENSOR"},
            {"label": "Check Motion?", "style": "DECISION", "shape": "diamond"},
            {"label": "Turn Light ON", "style": "ACTION"},
            {"label": "Log Event", "style": "COMMUNICATION"},
        ])
    )
    print("```\n")

    # Example 2: Complex diagram with sections
    print("=== Complex Diagram Example ===")
    print("```mermaid")
    entrance_config = {
        "type": "flowchart",
        "direction": "TD",
        "sections": [
            {
                "id": "opening",
                "title": "Door Opening",
                "nodes": [
                    {"id": "door_open", "label": "Door Sensor<br/>OFF → ON", "style": "SENSOR"},
                    {"id": "light_on", "label": "Turn Light ON", "style": "ACTION"},
                ],
            },
            {
                "id": "closing",
                "title": "Door Closing",
                "nodes": [
                    {"id": "door_close", "label": "Door Sensor<br/>ON → OFF", "style": "SENSOR"},
                    {"id": "timer", "label": "30s Timer", "style": "TIMING"},
                    {"id": "motion_check", "label": "Motion?", "style": "DECISION", "shape": "diamond"},
                ],
            },
        ],
        "connections": [
            {"from": "door_open", "to": "light_on"},
            {"from": "door_close", "to": "timer"},
            {"from": "timer", "to": "motion_check"},
            {"from": "motion_check", "to": "light_on", "label": "Motion Detected"},
        ],
    }
    print(create_diagram(entrance_config))
    print("```")
