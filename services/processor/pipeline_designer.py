"""Visual Pipeline Designer backend.

Defines stream processing topologies as DAGs of nodes.
Each node: source, transform, or sink.
Open-source: inspired by Apache Flink/ksqlDB visual pipelines.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineNode:
    node_id: str
    node_type: str  # source, transform, sink
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    position: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    status: str = "stopped"


@dataclass
class PipelineTopology:
    topology_id: str
    name: str
    description: str = ""
    nodes: list[PipelineNode] = field(default_factory=list)
    edges: list[dict[str, str]] = field(default_factory=list)
    enabled: bool = False

    def add_node(self, node: PipelineNode) -> None:
        self.nodes.append(node)

    def remove_node(self, node_id: str) -> bool:
        for i, n in enumerate(self.nodes):
            if n.node_id == node_id:
                self.nodes.pop(i)
                self.edges = [e for e in self.edges if e["from"] != node_id and e["to"] != node_id]
                return True
        return False

    def connect(self, from_id: str, to_id: str) -> None:
        self.edges.append({"from": from_id, "to": to_id})
        for n in self.nodes:
            if n.node_id == from_id:
                n.outputs.append(to_id)
            if n.node_id == to_id:
                n.inputs.append(from_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topology_id": self.topology_id,
            "name": self.name,
            "description": self.description,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                    "name": n.name,
                    "config": n.config,
                    "inputs": n.inputs,
                    "outputs": n.outputs,
                    "position": n.position,
                    "status": n.status,
                }
                for n in self.nodes
            ],
            "edges": self.edges,
            "enabled": self.enabled,
        }


class PipelineRegistry:
    """In-memory registry of pipeline topologies."""

    def __init__(self):
        self._topologies: dict[str, PipelineTopology] = {}

    def create(self, name: str, description: str = "") -> PipelineTopology:
        tid = f"pipeline-{uuid.uuid4().hex[:8]}"
        topo = PipelineTopology(topology_id=tid, name=name, description=description)
        self._topologies[tid] = topo
        return topo

    def get(self, topology_id: str) -> PipelineTopology | None:
        return self._topologies.get(topology_id)

    def list_all(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self._topologies.values()]

    def delete(self, topology_id: str) -> bool:
        if topology_id in self._topologies:
            del self._topologies[topology_id]
            return True
        return False


# Global registry
pipeline_registry = PipelineRegistry()
