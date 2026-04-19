# Jobs-Wiki REST Renewal Prompt

Use this prompt in Jobs-Wiki when preparing the migration from the current StrataWiki wrapper integration to the future HTTP/REST integration.

```text
You are updating Jobs-Wiki to prepare for StrataWiki REST integration.

Important: do not assume the HTTP migration is already complete.

Current facts:
- the current stable StrataWiki integration path is still the wrapper at `/Users/yebin/workSpace/stratawiki-runtime/bin/stratawiki-jobswiki.sh`
- the preferred external write contract is still `validate_domain_proposal_batch` followed by `ingest_domain_proposal_batch`
- profile provisioning still happens through `upsert_profile_context`
- Personal query still happens through `query_personal_knowledge`
- background interpretation builds exist, but worker-backed polling should not be assumed unless the target environment confirms it

Migration posture:
- keep the wrapper path working
- prepare a dual-mode integration layer that can switch between wrapper mode and HTTP mode
- do not remove the wrapper mode until StrataWiki confirms REST parity

Read these StrataWiki documents first:
- `docs/http-rest-contract-spec.md`
- `docs/jobs-wiki-rest-integration-guide.md`

Jobs-Wiki implementation goals:
1. isolate all StrataWiki calls behind one integration client
2. support both wrapper mode and future HTTP mode
3. keep the current `DomainProposalBatch` write flow unchanged at the semantic level
4. keep profile sync before Personal query
5. make retry behavior explicit for write operations
6. avoid direct DB access to StrataWiki in every mode

Recommended Jobs-Wiki config split:
- current wrapper mode:
  - `STRATAWIKI_CLI_WRAPPER`
  - `JOBS_WIKI_STRATAWIKI_DOMAIN_PACK_PATHS`
  - `JOBS_WIKI_STRATAWIKI_ACTIVE_DOMAIN_PACKS`
- future HTTP mode:
  - `STRATAWIKI_BASE_URL`
  - `STRATAWIKI_API_TOKEN`

What to implement now in Jobs-Wiki:
- one StrataWiki client abstraction
- one wrapper-backed implementation using the current local runtime
- one placeholder HTTP-backed implementation behind a feature flag
- shared request models for:
  - proposal validation
  - proposal ingest
  - profile sync
  - Personal query
  - interpretation build

What not to do yet:
- do not assume the final HTTP endpoint names without checking the StrataWiki contract doc
- do not remove wrapper integration
- do not add direct SQL or schema coupling to StrataWiki tables
- do not make browser-specific assumptions like CORS unless the StrataWiki side explicitly adds them

Deliverables:
- updated Jobs-Wiki integration client abstraction
- dual-mode configuration
- migration notes explaining current mode versus future HTTP mode
- no breaking changes to the current wrapper-backed path
```
