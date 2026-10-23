# Stage 4 triage evaluation

`triage_stage4_cases.json` and `triage_stage4_discovery.json` are diagnostic corpora assembled while auditing the existing pipeline. They overlap in purpose with development tests and must not be described as blind holdouts. The latter includes issue-shaped cases inspired by the Stage 2 and Stage 3 review, plus the existing FastAPI issue regressions remain in `tests/`.

`triage_stage4_final_holdout.json` is a separate 12-case manually labeled evaluation corpus spanning paraphrases, issue types, misleading labels, contradictory reports, incomplete evidence, priority scopes, and index states. It was evaluated before and after small follow-up fixes prompted by existing regression tests; those fixes were not selected to pass individual cases in this corpus. Its output has now been inspected, so it is not a blind holdout for future work. Cases use synthetic repository names and report text; they are not a representative random sample of GitHub issues.

Run an evaluation corpus with:

```sh
python scripts/evaluate_triage_stage4.py --cases evaluation/triage_stage4_final_holdout.json
```

The extraction score uses exact signal-presence sets and micro precision/recall. Category and priority scores are exact agreement against manual labels. Recommendation overlap is only an exploratory token proxy and is not a validated usefulness metric. Root grounding checks flag explicit definitive causal claims without evidence and quoted source paths that are not in the evidence list; these checks do not understand every form of overclaim. The corpus runner does not create or pass fake source chunks: index status alone is not treated as repository evidence. Actual repository scoping is covered by the database-backed test that places a matching chunk in a different repository and verifies it is not cited.

Because the final corpus has only 12 hand-authored cases, the scores are diagnostic, not proof of generalization. Its labels and the rule-based checks also need review by maintainers before being treated as ground truth.
