# Day 7.3 — Evaluation Results

**Scope: synthetic evaluation only; not real-world accuracy.**

| Metric | Investigator | Baseline |
|---|---:|---:|
| Cases processed | 15 | 15 |
| Model calls | 0 | 12 |
| Expected cause labels matched | 2/15 | 2/9 scored cases |
| Exact cause-set matches | 0/15 | Not measured |
| Abstention matches | 12/15 | Not consistently measured |
| Real cases | 0 | 0 |
| Accuracy by confidence band | Unavailable | Unavailable |
| Median checks to correct top cause | Unavailable — no ground-truth check sequence | Unavailable — no ground-truth check sequence |

## Limitations

- All 15 evaluation cases are synthetic.
- Investigator and baseline use different cause-label matching rules; their scores are not directly comparable.
- Baseline cause scoring excludes cases without expected cause labels.
- Exact next-check matching is literal string comparison, not semantic grading.
- Evidence passages are fixed test fixtures, not live retrieval results.

Baseline run status: `completed`.
