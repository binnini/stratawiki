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
    contract_status: str | None = None
    recommended_for_external_clients: bool | None = None

    def export_schema(self) -> dict[str, object]:
        schema = {
            "name": self.name,
            "group": self.group,
            "status": self.status,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "input_schema": self.input_schema,
        }
        if self.contract_status is not None:
            schema["contract_status"] = self.contract_status
        if self.recommended_for_external_clients is not None:
            schema["recommended_for_external_clients"] = self.recommended_for_external_clients
        return schema
