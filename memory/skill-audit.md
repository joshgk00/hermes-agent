# Skill Audit Log

## 2026-05-09 Nightly Maintenance
- prompt-optimization-analyzer (~1,650 tokens): Critical conflict with platform policy because it requires visible `<thinking>` tags. Rewrite to "Reason internally; final answer only" and remove XML wrappers. Saves ~30-60 tokens per run and avoids policy conflicts.
- decision-moment-cards (~1,050 tokens): Matrix registry/troubleshooting details dominate routine card creation. Move implementation internals to a reference file and keep the main skill to card format + fallback commands. Saves ~300-450 tokens; trigger reliability unchanged.
- nightly-maintenance-routine (~850 tokens): Git push fallback and quiet-delivery guidance are useful but partly repeated in Workflow/Pitfalls/Delivery. Merge repeated quiet-mode bullets. Saves ~40-70 tokens.

## 2026-05-10 Nightly Maintenance
- prompt-optimization-analyzer (~1,400 tokens): Prior visible-`<thinking>` issue appears fixed. Remaining waste is verbose framework tables plus two examples that overlap with the output schema. Condense tables and keep one before/after example. Saves ~180-260 tokens; clarity unchanged.
- decision-moment-cards (~1,050 tokens): Still mixes card-authoring instructions with Matrix gateway implementation/troubleshooting. Move registry design and troubleshooting to `references/matrix-decision-reactions.md`; keep main skill to trigger, card fields, cron precedence, and fallback commands. Saves ~350-550 tokens.
- nightly-maintenance-routine (~850 tokens): Repeats delivery silence in Workflow, Pitfalls, and Delivery behavior. Replace with one precedence rule under Delivery. Saves ~40-70 tokens.

## 2026-05-11 Nightly Maintenance
- prompt-optimization-analyzer (~1,450 tokens): The analyzer is cleaner after the `<thinking>` fix, but still carries four tables plus two examples. Merge severity tables into compact checklists and keep one example. Saves ~200-300 tokens; trigger reliability unchanged.
- decision-moment-cards (~1,650 tokens): Cron and Matrix troubleshooting content now outweighs the card-authoring core. Move troubleshooting and registry design into a linked reference, keep the main skill to card schema, precedence, and fallback commands. Saves ~500-700 tokens; reduces duplicate-send risk.
- nightly-maintenance-routine (~1,000 tokens): Delivery silence and git push cautions repeat across Workflow, Pitfalls, and Delivery. Keep one Delivery precedence rule and one Git fallback rule. Saves ~70-110 tokens.
