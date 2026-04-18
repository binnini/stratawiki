from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    group: str
    status: str
    description: str
    entrypoint: str
    input_schema: dict[str, object]

    def export_schema(self) -> dict[str, object]:
        return {
            "name": self.name,
            "group": self.group,
            "status": self.status,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "input_schema": self.input_schema,
        }
