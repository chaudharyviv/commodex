# COMMODEX Prompt Registry

All agent prompts are versioned here.

## Naming Convention
{agent_name}_v{major}.{minor}.txt

Examples:
  analyst_v1.0.txt
  signal_v1.0.txt
  risk_v1.0.txt

## Versioning Rules
- Minor bump (1.0 → 1.1): wording changes, clarifications
- Major bump (1.0 → 2.0): structural changes to output schema

## Tracking
Every signal in signals_log records the prompt_version used.
This ensures paper trading evaluation is meaningful —
you know exactly which prompt generated which signals.

## Current Active Versions
analyst_agent:  pending (Phase 3)
signal_agent:   pending (Phase 3)
risk_agent:     pending (Phase 3)