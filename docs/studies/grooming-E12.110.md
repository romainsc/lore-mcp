# Grooming E12.110 — Evaluation dominated by single source

## Investigation (2026-10-04)

Three balancing strategies compared:

| Strategy | Big (100) | Med (15) | Med (12) | Small (5) | Small (3) | Total |
|----------|-----------|----------|----------|-----------|-----------|-------|
| **Current** (shuffle) | ~37 | ~6 | ~4 | ~2 | ~1 | 50 |
| **Ceil cap** (N/sources) | 10 | 10 | 10 | 5 | 3 | 38 |
| **Round-robin** | 15 | 15 | 12 | 5 | 3 | 50 |

- Ceil cap: under-produces (38 < 50), wastes
  large source capacity
- Proportional: preserves the bias (74% from big)
- **Round-robin**: fairest distribution, uses all
  available questions, fills to target from
  large sources

## Fix

Replace shuffle+truncate with round-robin
sampling in `generate_questions_from_sources`:

```python
by_source = defaultdict(list)
for q in questions:
    by_source[q["source_file"]].append(q)

for qs in by_source.values():
    random.shuffle(qs)

balanced = []
iterators = {k: iter(v) for k, v in by_source.items()}
while len(balanced) < num_questions and iterators:
    exhausted = []
    for key, it in iterators.items():
        if len(balanced) >= num_questions:
            break
        try:
            balanced.append(next(it))
        except StopIteration:
            exhausted.append(key)
    for key in exhausted:
        del iterators[key]

return balanced
```

## DoD

- No source contributes all its questions before
  others are sampled
- source_diversity improves (>0.1 for multi-source
  corpora)
- Single-source corpus unaffected
- Test: 3 sources with unequal question counts →
  verify balanced distribution
- CI green
