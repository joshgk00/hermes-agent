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

## 2026-05-13 Nightly Maintenance
- prompt-optimization-analyzer (~1,250 tokens): Framework tables still take more space than the fixes they describe. Collapse severity/waste/anti-pattern tables into one checklist and keep one realistic before/after example. Saves ~180-260 tokens; clarity unchanged.
- decision-moment-cards (~1,900 tokens): Main skill now includes implementation design, troubleshooting, direct Matrix send fallback, and registration internals. Move those to `references/direct-matrix-card-registration.md` and keep the main skill to card schema, cron precedence, reactions, and fallbacks. Saves ~650-900 tokens; lowers duplicate-delivery risk.
- nightly-maintenance-routine (~1,100 tokens): Quiet delivery, memory failure handling, and git push fallback repeat across Workflow/Pitfalls/Delivery. Merge into one delivery rule and one git fallback rule. Saves ~90-140 tokens.

## 2026-05-14 Nightly Maintenance
- prompt-optimization-analyzer (~1,300 tokens): Still uses four diagnostic tables plus an example that repeats the output schema. Merge severity/waste/anti-pattern checks into one compact checklist and keep one before/after example. Saves ~200-300 tokens; trigger reliability unchanged.
- decision-moment-cards (~1,950 tokens): Troubleshooting, gateway registry design, and direct-send fallback dominate routine card creation. Move those details to references and keep the main skill to card fields, cron precedence, reactions, and fallback commands. Saves ~700-950 tokens; lowers duplicate-delivery risk.
- nightly-maintenance-routine (~1,150 tokens): Git fallback, quiet delivery, and memory failure handling repeat across Workflow/Pitfalls/Verification. Keep single rules in Workflow and shorten Pitfalls to exceptions only. Saves ~100-150 tokens.

## 2026-05-15 Nightly Maintenance
- prompt-optimization-analyzer (~1,300 tokens): Still carries multiple framework tables and two examples. Collapse trigger/token/anti-pattern checks into one checklist and keep one before/after example. Saves ~200-300 tokens; clarity unchanged.
- decision-moment-cards (~2,200 tokens): Direct Matrix send/register fallback and troubleshooting now dominate the main skill. Move rollout/troubleshooting internals into references and keep the main skill to card schema, cron precedence, reactions, and fallbacks. Saves ~800-1,100 tokens; lowers duplicate-delivery risk.
- nightly-maintenance-routine (~1,200 tokens): Quiet delivery, memory failure handling, and git fallback are repeated in Workflow, Pitfalls, and Delivery. Keep one rule per behavior and leave Pitfalls for exceptions. Saves ~100-160 tokens.

## 2026-05-16 Nightly Maintenance
- prompt-optimization-analyzer (~1,300 tokens): Same open issue as 2026-05-15: framework tables and two examples repeat the output schema. Collapse checks into one checklist and keep one before/after example. Saves ~200-300 tokens.
- decision-moment-cards (~2,300 tokens): Main skill still mixes card authoring with Matrix registry, troubleshooting, and direct-send fallback. Move implementation internals to references; keep schema, cron precedence, reactions, and fallbacks. Saves ~850-1,150 tokens.
- nightly-maintenance-routine (~1,250 tokens): Workflow/Pitfalls/Delivery still repeat quiet delivery, memory failure, and git fallback. Keep one rule per behavior and shorten Pitfalls to true exceptions. Saves ~100-170 tokens.

## 2026-05-17 Nightly Maintenance
- prompt-optimization-analyzer (~1,300 tokens): Open issue unchanged: four analysis tables plus examples duplicate the output schema. Replace the tables with one severity checklist and one before/after example. Saves ~200-300 tokens.
- decision-moment-cards (~2,450 tokens): Cron delivery, Matrix registry design, troubleshooting, and manual registration dominate the main skill. Move these internals to references; keep only card schema, precedence, reactions, and fallbacks. Saves ~900-1,200 tokens.
- nightly-maintenance-routine (~1,250 tokens): The workflow repeats quiet delivery, memory failure handling, and git fallback guidance across sections. Keep one authoritative rule for each and shorten Pitfalls. Saves ~100-170 tokens.
