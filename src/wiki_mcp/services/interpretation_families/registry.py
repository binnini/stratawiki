from __future__ import annotations

from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.services.interpretation_families.base import (
    InterpretationFamilyBuilder,
    InterpretationProposalContext,
)


class InterpretationFamilyRegistry:
    """Registry for interpretation family proposal builders."""

    def __init__(self, builders: list[InterpretationFamilyBuilder] | None = None) -> None:
        self._builders = list(builders or [])
        self._builders_by_family = {builder.family: builder for builder in self._builders}

    def register(self, builder: InterpretationFamilyBuilder) -> None:
        self._builders.append(builder)
        self._builders_by_family[builder.family] = builder

    def build_proposals(
        self,
        context: InterpretationProposalContext,
    ) -> list[InterpretationRecord]:
        proposals: list[InterpretationRecord] = []
        if context.family:
            builder = self._builders_by_family.get(context.family)
            if builder is None:
                return []
            proposal = builder.build_proposal(context)
            if proposal is not None:
                proposals.append(proposal)
            return proposals

        for builder in self._builders:
            proposal = builder.build_proposal(context)
            if proposal is not None:
                proposals.append(proposal)
        return proposals

    def get(self, family: str) -> InterpretationFamilyBuilder | None:
        return self._builders_by_family.get(family)

    def list_builders(self) -> list[InterpretationFamilyBuilder]:
        return list(self._builders)
