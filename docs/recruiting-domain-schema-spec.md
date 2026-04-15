# Recruiting Domain Schema Spec

## Purpose

This document defines a concrete domain schema for the recruiting and job strategy domain within a three-layer LLM Wiki MCP server.

It specifies:

- Fact entities
- Interpretation record families
- Personal record families
- key relationships
- freshness guidance

The recruiting domain is treated as a batch-oriented but mutable domain. It usually does not require sub-second transactional behavior, but it does require strong normalization, deduplication, and provenance.

## Domain Assumptions

- job data is ingested from APIs, ATS platforms, company career pages, and public job boards
- most updates are acceptable on a daily or twice-daily cadence
- regional, language, visa, and seniority differences matter materially
- users ask both factual questions and strategy questions

## Layer 1: Fact

### Fact Principles

Recruiting Fact records should capture observable labor market data and normalized source state.

They should not directly store:

- generalized market claims
- candidate-specific advice
- speculative conclusions

### Fact Entity Types

#### `job_posting`

Represents one canonical job posting.

Suggested fields:

```json
{
  "id": "job_posting_123",
  "entity_type": "job_posting",
  "canonical_key": "greenhouse:posting:abc123",
  "attributes": {
    "title": "Backend Engineer",
    "employment_type": "full_time",
    "seniority": "mid",
    "remote_policy": "hybrid",
    "status": "active",
    "posted_at": "2026-04-10T00:00:00Z",
    "expires_at": null,
    "source_url": "https://..."
  }
}
```

#### `company`

Canonical company record.

Suggested fields:

```json
{
  "id": "company_42",
  "entity_type": "company",
  "attributes": {
    "name": "Example Labs",
    "normalized_name": "example labs",
    "industry": "software",
    "size_band": "51_200",
    "hq_location_id": "location_tokyo"
  }
}
```

#### `role`

Canonical role family or standardized role.

Suggested fields:

```json
{
  "id": "role_backend_engineer",
  "entity_type": "role",
  "attributes": {
    "display_name": "Backend Engineer",
    "family": "software_engineering",
    "specialization": "backend"
  }
}
```

#### `skill`

Standardized skill dictionary item.

Suggested fields:

```json
{
  "id": "skill_python",
  "entity_type": "skill",
  "attributes": {
    "name": "Python",
    "category": "language"
  }
}
```

#### `location`

Normalized geographic location.

Suggested fields:

```json
{
  "id": "location_tokyo",
  "entity_type": "location",
  "attributes": {
    "country": "JP",
    "region": "Tokyo",
    "city": "Tokyo"
  }
}
```

#### `compensation_range`

Compensation observation tied to a posting or company.

Suggested fields:

```json
{
  "id": "comp_100",
  "entity_type": "compensation_range",
  "attributes": {
    "currency": "JPY",
    "min_amount": 7000000,
    "max_amount": 10000000,
    "period": "year"
  }
}
```

#### `language_requirement`

Language requirement observation.

Suggested fields:

```json
{
  "id": "lang_req_1",
  "entity_type": "language_requirement",
  "attributes": {
    "language": "ja",
    "level": "business"
  }
}
```

#### `visa_requirement`

Visa or sponsorship-related observation.

Suggested fields:

```json
{
  "id": "visa_req_1",
  "entity_type": "visa_requirement",
  "attributes": {
    "sponsorship_available": true,
    "restriction_notes": "..."
  }
}
```

#### `source_snapshot`

Represents fetched source state and versioning metadata.

Suggested fields:

```json
{
  "id": "source_snap_123",
  "entity_type": "source_snapshot",
  "attributes": {
    "connector": "greenhouse",
    "fetched_at": "2026-04-15T08:00:00Z",
    "content_hash": "sha256:..."
  }
}
```

### Fact Relations

Recommended relations:

- `job_posting -> company` via `posted_by`
- `job_posting -> role` via `has_role`
- `job_posting -> skill` via `requires_skill`
- `job_posting -> location` via `located_in`
- `job_posting -> compensation_range` via `offers_compensation`
- `job_posting -> language_requirement` via `requires_language`
- `job_posting -> visa_requirement` via `requires_visa_policy`
- `job_posting -> source_snapshot` via `observed_in`

## Layer 2: Interpretation

### Interpretation Principles

Interpretation captures shared meaning about the recruiting market.

It should be:

- evidence-based
- refreshable
- segmented
- not user-specific

### Interpretation Subject Axes

Most recruiting interpretations should be grouped by one or more of:

- role family
- specialization
- region
- seniority
- company segment
- skill cluster
- hiring channel

### Interpretation Families

#### `market_trend`

Examples:

- backend hiring trend in Tokyo startups
- demand growth for LLM production experience
- compensation trend for senior data engineers in Seoul

Suggested fields:

```json
{
  "kind": "market_trend",
  "subject_type": "market_segment",
  "subject_id": "backend_japan_midlevel",
  "claim": "Production LLM experience is increasingly requested.",
  "confidence": 0.81
}
```

#### `skill_gap_pattern`

Examples:

- users from analytics backgrounds often lack systems design signals
- backend transitions require stronger deployment and data modeling evidence

#### `role_transition_risk`

Examples:

- data analyst to backend engineer transition risk in Tokyo startups
- junior frontend to platform engineering transition difficulty

#### `regional_opportunity_summary`

Examples:

- Tokyo startup opportunities for bilingual backend engineers
- Singapore demand for data platform engineers

#### `company_hiring_pattern`

Examples:

- company segment prefers take-home assignments
- mid-size SaaS firms emphasize production debugging experience

#### `compensation_interpretation`

Examples:

- salary compression for junior roles in a given region
- compensation premium for bilingual infrastructure engineers

#### `constraint_summary`

Examples:

- visa sponsorship constraints by region
- language requirement intensity by company segment

### Interpretation Relations

Recommended relations:

- `market_trend supports skill_gap_pattern`
- `regional_opportunity_summary refines market_trend`
- `constraint_summary contradicts opportunity claim`
- `role_transition_risk depends_on skill_gap_pattern`

### Interpretation Freshness

Recommended default freshness:

- market-wide trend summaries: 24 hours
- company-specific hiring pattern summaries: 12 to 24 hours
- compensation interpretations: 24 hours
- role-transition patterns: 24 to 72 hours depending on evidence density

## Layer 3: Personal

### Personal Principles

Personal records are user-scoped.

They should reflect:

- profile
- goals
- time horizon
- risk tolerance
- target market

They must not become the only storage location for reusable market knowledge.

### Personal Record Families

#### `career_transition_plan`

Examples:

- 12-week transition plan from analyst to backend engineer
- six-month relocation and language preparation plan

#### `application_priority_list`

Examples:

- ranked target companies
- weekly application shortlist

#### `interview_preparation_tree`

Examples:

- backend systems prep plan
- company-specific interview prep nodes

#### `profile_gap_analysis`

Examples:

- skill and signaling gaps versus target role family
- mismatch between current background and desired segment

#### `portfolio_strategy`

Examples:

- project recommendations to improve interview conversion
- repository and writing plan for role transition

#### `weekly_action_plan`

Examples:

- applications to submit
- projects to polish
- interview practice milestones

### Personal Anchors

Personal records should anchor to:

- relevant `market_trend`
- relevant `skill_gap_pattern`
- relevant `regional_opportunity_summary`
- evidence facts when useful

Example:

```json
{
  "anchors": [
    "interp_market_tokyo_backend",
    "interp_skill_gap_backend_transition",
    "job_posting_123"
  ]
}
```

## User Profile for Recruiting

Suggested profile shape:

```json
{
  "user_id": "user_42",
  "domain": "recruiting",
  "goals": [
    "transition_to_backend",
    "move_to_tokyo"
  ],
  "preferences": {
    "target_regions": ["tokyo", "remote_japan"],
    "target_seniority": "mid",
    "salary_floor_jpy": 9000000
  },
  "attributes": {
    "years_experience": 4,
    "current_role": "data_analyst",
    "skills": ["python", "sql", "analytics"],
    "languages": ["en", "ja_n3"]
  }
}
```

## Common Query Patterns

### Fact-Oriented Queries

- show active Tokyo backend postings requiring Python
- list companies offering visa sponsorship for data engineers
- find compensation ranges for mid-level backend roles in Japan

### Interpretation-Oriented Queries

- what skills are trending for backend roles in Tokyo startups
- how strong is the demand for production LLM experience
- what constraints matter most for relocation-focused candidates

### Personal-Oriented Queries

- what should I prioritize this month for a backend transition
- which portfolio project would improve my profile fastest
- which companies should I target given my current background

## Recommended Initial Recruiting Implementation

Start narrow.

Recommended first slice:

- Fact: `job_posting`, `company`, `role`, `skill`, `location`
- Interpretation: `market_trend`, `skill_gap_pattern`, `regional_opportunity_summary`
- Personal: `career_transition_plan`, `profile_gap_analysis`, `weekly_action_plan`

This is enough to support a strong job-strategy use case without over-modeling the domain in version one.

## Schema Evolution Guidance

Recruiting data schemas will evolve quickly.

Plan for:

- company alias merges
- role taxonomy refinement
- skill normalization changes
- new interpretation families

Therefore:

- every record family should carry a `schema_version`
- renderers should tolerate previous versions for a migration window
- Personal regeneration should prefer upstream snapshots over long-lived copied text
