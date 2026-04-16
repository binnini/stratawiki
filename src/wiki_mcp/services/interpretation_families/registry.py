from __future__ import annotations

from wiki_mcp.schemas.interpretation_record import InterpretationRecord
from wiki_mcp.schemas.snapshot_ref import SnapshotRef
from wiki_mcp.services.interpretation_families.base import (
    InterpretationBuildContext,
    InterpretationFamilyBuilder,
)
from wiki_mcp.services.interpretation_families.company_candidate_profile_pattern import (
    CompanyCandidateProfilePatternBuilder,
)
from wiki_mcp.services.interpretation_families.company_hiring_pattern import (
    CompanyHiringPatternBuilder,
)


class InterpretationFamilyRegistry:
    """Kind-aware registry for shared interpretation family builders."""

    def __init__(self, builders: list[InterpretationFamilyBuilder]) -> None:
        self._builders = builders
        self._builders_by_family = {builder.family: builder for builder in builders}

    def build_records(
        self,
        context: InterpretationBuildContext,
    ) -> list[InterpretationRecord]:
        records: list[InterpretationRecord] = []
        for builder in self._builders:
            record = builder.build_record(context)
            if record is not None:
                records.append(record)
        return records

    def build_rendered_artifact(
        self,
        record: InterpretationRecord,
        *,
        snapshot_ref: SnapshotRef,
    ) -> dict[str, object]:
        builder = self._builders_by_family.get(record["kind"])
        if builder is None:
            raise ValueError(
                f"No interpretation family builder is registered for kind {record['kind']!r}."
            )
        return builder.build_rendered_artifact(record, snapshot_ref=snapshot_ref)


def build_default_interpretation_family_registry() -> InterpretationFamilyRegistry:
    return InterpretationFamilyRegistry(
        [
            CompanyHiringPatternBuilder(),
            CompanyCandidateProfilePatternBuilder(),
        ]
    )
