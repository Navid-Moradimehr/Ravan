"""Digital Twin Integration — map live data to 3D plant visualization.

Links asset tags to digital twin entities (nodes in a 3D scene).
Open-source: compatible with Three.js, Babylon.js, or USD/USDZ.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TwinEntity:
    entity_id: str
    name: str
    asset_id: str
    tag_bindings: dict[str, str] = field(default_factory=dict)
    position: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    rotation: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    scale: dict[str, float] = field(default_factory=lambda: {"x": 1, "y": 1, "z": 1})
    model_url: str = ""
    status: str = "unknown"
    last_values: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "asset_id": self.asset_id,
            "tag_bindings": self.tag_bindings,
            "position": self.position,
            "rotation": self.rotation,
            "scale": self.scale,
            "model_url": self.model_url,
            "status": self.status,
            "last_values": self.last_values,
        }


class DigitalTwinScene:
    """Scene graph for a digital twin plant model."""

    def __init__(self, scene_id: str, name: str):
        self.scene_id = scene_id
        self.name = name
        self._entities: dict[str, TwinEntity] = {}

    def add_entity(self, entity: TwinEntity) -> None:
        self._entities[entity.entity_id] = entity

    def remove_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    def update_value(self, entity_id: str, tag: str, value: float) -> bool:
        entity = self._entities.get(entity_id)
        if not entity:
            return False
        entity.last_values[tag] = value
        # Simple status logic
        if tag in entity.tag_bindings:
            bound_tag = entity.tag_bindings[tag]
            if "temperature" in bound_tag.lower() and value > 80:
                entity.status = "warning"
            elif "vibration" in bound_tag.lower() and value > 7:
                entity.status = "critical"
            else:
                entity.status = "normal"
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "entities": [e.to_dict() for e in self._entities.values()],
        }


# Sample scene with pump assets
def create_demo_scene() -> DigitalTwinScene:
    scene = DigitalTwinScene("plant-01", "Demo Plant")
    for i in range(1, 4):
        scene.add_entity(TwinEntity(
            entity_id=f"pump-{i:02d}",
            name=f"Pump {i}",
            asset_id=f"Pump-{i:02d}",
            tag_bindings={
                "temperature": f"Pump-{i:02d}.Temperature",
                "vibration": f"Pump-{i:02d}.Vibration",
                "pressure": f"Pump-{i:02d}.Pressure",
            },
            position={"x": i * 2.0, "y": 0, "z": 0},
            model_url="/models/pump.glb",
        ))
    return scene


# Global demo scene
demo_scene = create_demo_scene()
