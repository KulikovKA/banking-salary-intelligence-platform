# Dependency graph and execution modes

Top-level `deps` in WORK_INDEX describe full WORK acceptance. `offline_checkpoint.deps` describe only the admitted offline checkpoint. A completed checkpoint does not complete the WORK block or satisfy G1/G2. All original task IDs remain in TASK_INDEX.

## Offline graph (G0-OFFLINE)

```mermaid
flowchart TD
  W02[WORK-02 offline: INF-001, INF-002, DB-001]
  W03[WORK-03 offline: STO-001, NET-001, JOB-001]
  W04[WORK-04 offline: HTML-001, PDF-001, DB-002, TXT-001, VER-001]
  W05[WORK-05 offline: adapter scaffolds and QA-001 harness]
  W06[WORK-06 offline: schema/facts/review/publication on synthetic corpus]
  W07[WORK-07 offline: search/comparison on synthetic corpus]
  W08[WORK-08 offline: Fake LLM/API/UI on synthetic corpus]
  W09[WORK-09 offline: evaluation harness only]
  W02 --> W03 --> W04
  W04 --> W05
  W04 --> W06 --> W07 --> W08 --> W09
  W06 --> W08
```

Each checkpoint requires G0-OFFLINE. Offline/test/CI has no external ingestion requests, including redirects, subresources, parser, or browser renderer. Fake transport is allowed. Preserve full acceptance dependencies, except WORK-01 is removed from WORK-02; offline graph alone does not complete any WORK block.

## Live and acceptance graph

```mermaid
flowchart LR
  SRC[SRC-001: per-source policy decision] --> LIVE[G0-LIVE exact host/path]
  LIVE --> FETCH[Allowed retrieval]
  FETCH --> CONTENT[Content acceptance and immutable evidence]
  CONTENT --> ING[WORK-05 real adapter checks]
  ING --> G1[G1: all 4 banks, 3 distinct days within 1 week]
  G1 --> FACT[WORK-06 real-corpus validation/publication]
  FACT --> POC[WORK-07/08 real-corpus checks]
  POC --> G2[WORK-09 G2 report and user acceptance]
  G2 --> LATER[WORK-10 through WORK-19]
```

G0-LIVE is per source and is not approved for any bank source as of 2026-10-10. G1 requires an approved source and scheduled-fetch evidence for all four banks on at least three different days within one week. Manual import does not count. G2 requires real documents, human-reviewed gold/tune/holdout, and all original thresholds. Reports or checkpoints cannot self-accept G1/G2; user acceptance is required.

WORK-16 is not a prerequisite for source retrieval: SRC-001 records the source-specific decision on acquisition, storage, and reuse before bytes are fetched. WORK-16 remains the broader production legal/privacy/retention review and gates production capabilities.

[WORK_INDEX](WORK_INDEX.json) | [TASK_INDEX](TASK_INDEX.json) | [ADR-006](../architecture/ADR/006-g0-offline-and-live-ingestion.md)
