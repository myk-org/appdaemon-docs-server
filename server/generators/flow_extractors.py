"""
Adapters for extracting control-flow/call-graph information from mature tools.

We integrate with:
- code2flow: function/method-level control-flow summaries (DOT output)

All integrations are optional. If a tool is not installed, the adapter returns None.
This ensures the server runs without extra dependencies while allowing enhanced
diagrams when extras are available (see pyproject optional group: flow_extract).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re


@dataclass
class CytoscapeGraph:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


def _parse_dot_to_cytoscape(dot_text: str) -> CytoscapeGraph:
    """Very small DOT parser for node/edge with labels.

    This is intentionally minimal and tolerant; it picks up patterns like:
        n1 [label="X"];
        n1 -> n2;
    and converts them into Cytoscape-compatible elements.
    """
    node_re = re.compile(r"^(\w+)\s*\[label=\"(?P<label>[^\"]+)\".*\];?")
    edge_re = re.compile(r"^(\w+)\s*->\s*(\w+)")

    id_to_label: dict[str, str] = {}
    edges: list[dict[str, Any]] = []

    for raw in dot_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = node_re.match(line)
        if m:
            node_id = m.group(1)
            id_to_label[node_id] = m.group("label")
            continue
        m = edge_re.match(line)
        if m:
            src, dst = m.group(1), m.group(2)
            edges.append({"data": {"id": f"e_{src}_{dst}", "source": src, "target": dst}})

    nodes = [{"data": {"id": nid, "label": lbl}} for nid, lbl in id_to_label.items()]
    return CytoscapeGraph(nodes=nodes, edges=edges)


def try_code2flow_on_source(source_code: str, func_name: str | None = None) -> CytoscapeGraph | None:
    """Attempt to run code2flow on a snippet to get DOT then convert to Cytoscape.

    This uses code2flow if available as a library. If not installed, returns None.
    """
    # Try importing lazily to avoid hard dependency
    try:
        import importlib

        c2f = importlib.import_module("code2flow")
    except Exception:
        return None

    try:
        if hasattr(c2f, "make_dot"):
            dot = getattr(c2f, "make_dot")(source_code, language="py")
            if isinstance(dot, bytes):
                dot = dot.decode("utf-8", errors="ignore")
            return _parse_dot_to_cytoscape(str(dot))
    except Exception:
        return None

    return None
