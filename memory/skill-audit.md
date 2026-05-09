# Skill Audit Log

## 2026-05-09 Nightly Maintenance
- prompt-optimization-analyzer (~1,650 tokens): Critical conflict with platform policy because it requires visible `<thinking>` tags. Rewrite to "Reason internally; final answer only" and remove XML wrappers. Saves ~30-60 tokens per run and avoids policy conflicts.
- decision-moment-cards (~1,050 tokens): Matrix registry/troubleshooting details dominate routine card creation. Move implementation internals to a reference file and keep the main skill to card format + fallback commands. Saves ~300-450 tokens; trigger reliability unchanged.
- nightly-maintenance-routine (~850 tokens): Git push fallback and quiet-delivery guidance are useful but partly repeated in Workflow/Pitfalls/Delivery. Merge repeated quiet-mode bullets. Saves ~40-70 tokens.
