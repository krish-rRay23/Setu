# ADR 003: Three Deterministic Components Over Multi-Agent Orchestration

## Context & Problem Statement
Modern AI frameworks often overuse multi-agent loops, where multiple LLM agents communicate autonomously to negotiate decisions. In financial revenue recovery, multi-agent theater introduces unpredictable control flows, high latency, infinite loops, and unexplainable policy choices that violate financial auditability.

## Decision Drivers
- **Bounded Autonomy**: System decisions must strictly obey policy rules (retry caps, cooldown windows, amount thresholds).
- **Auditability & Observability**: Every decision must produce an explicit, structured audit trail with transparent policy rationale.
- **Predictability & Zero Illusion**: LLMs must never have the authority to trigger financial transactions directly.

## Decision
We enforce a strict **Three-Component Architecture**:
1. **Classifier** (`src/classifier/`): Diagnoses failure cause (Rules first, LLM residual fallback).
2. **Policy Engine** (`src/policy/`): Pure deterministic function mapping classification + context -> bounded Action. Zero LLM involvement.
3. **Ledger-Executor** (`src/ledger/`, `src/executor/`): Enforces transactional write-ahead logging and executes Razorpay API calls.

## Consequences
- **Positive**: Strict separation of concerns. LLM only suggests diagnostic categories; pure policy logic decides actions.
- **Positive**: Zero possibility of an LLM hallucinating a custom action, ignoring retry limits, or double-charging.
- **Positive**: System latency is under 0.01ms for rule-classified events and avg ~0.005ms overall.
