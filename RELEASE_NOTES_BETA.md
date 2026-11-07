# 0.1.0b1 — Experimental pre-release (2026-11-07)

**Experimental / beta. Do not use for billing, financial reporting or safety-critical monitoring. No guaranteed maintenance or support.**

- Initial Home Assistant integration based on undocumented Trybatec consumer portal endpoints.
- UI authentication and index retrieval, per-physical-meter sensors and optional annual tariffs.
- Parsing guards and limited handling of token rejection.
- 19 local unit tests; **no verified real Home Assistant deployment** yet.
- No historical backfill. The service may change without notice. Index gaps and resets can lead to misleading statistics; verify the values manually before using them.
- GitHub releases tagged `0.1.0b1` must be marked as **Pre-release** to opt-in via Home Assistant Marketplace.

Feedback is welcome but no bug fix, security patch, compatibility update or response is promised. Neither Trybatec nor OpenAI maintains or endorses this independent project.
