# Conjecture Prover — Analyzer-Utilization Experiment (Stage 1)

- Source: `results.jsonl` (17 recorded run(s))
- LangSmith project: `conjecture_experiment` (token usage)

## Per-run table

| run_id | problem | condition | status | exit | dur_s | round | total | proved | unproved | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| with_analyzer__fateH_94 | fateH_94 | with_analyzer | timeout | -9 | 5400.0 | — | — | — | — | killed after 90 min wall-clock timeout; no summary.json produced |
| with_analyzer__fateH_94 | fateH_94 | with_analyzer | timeout | -9 | 5400.0 | — | — | — | — | killed after 90 min wall-clock timeout; no summary.json produced |
| with_analyzer__fateX_94 | fateX_94 | with_analyzer | timeout | -9 | 5400.3 | — | — | — | — | killed after 90 min wall-clock timeout; no summary.json produced |
| with_analyzer__putnam_a6_1972 | putnam_a6_1972 | with_analyzer | failed | 1 | 3961.4 | — | — | — | — | no summary.json produced |
| wo_analyzer__fateH_94 | fateH_94 | wo_analyzer | failed | 1 | 1877.7 | — | — | — | — | no summary.json produced |
| wo_analyzer__fateX_94 | fateX_94 | wo_analyzer | timeout | -9 | 5400.0 | — | — | — | — | killed after 90 min wall-clock timeout; no summary.json produced |
| wo_analyzer__putnam_a6_1972 | putnam_a6_1972 | wo_analyzer | failed | 1 | 4269.1 | — | — | — | — | no summary.json produced |
| optional_analyzer__fateH_94 | fateH_94 | optional_analyzer | timeout | -9 | 5400.0 | — | — | — | — | killed after 90 min wall-clock timeout; no summary.json produced |
| optional_analyzer__fateX_94 | fateX_94 | optional_analyzer | failed | 1 | 4130.1 | — | — | — | — | no summary.json produced |
| optional_analyzer__putnam_a6_1972 | putnam_a6_1972 | optional_analyzer | failed | 1 | 8.8 | — | — | — | — | no summary.json produced |
| with_analyzer__fateX_94 | fateX_94 | with_analyzer | timeout | -9 | 5400.4 | — | — | — | — | killed after 90 min wall-clock timeout; no summary.json produced |
| wo_analyzer__fateX_94 | fateX_94 | wo_analyzer | completed | 0 | 4679.1 | 8 | 12 | 11 | 1 |  |
| optional_analyzer__fateX_94 | fateX_94 | optional_analyzer | completed | 0 | 4824.7 | 8 | 18 | 16 | 2 |  |
| with_analyzer__fateX_94 | fateX_94 | with_analyzer | failed | 1 | 1730.6 | 0 | — | — | — |  |
| with_analyzer__fateX_94 | fateX_94 | with_analyzer | completed | 0 | 3768.3 | 8 | 7 | 6 | 1 |  |
| wo_analyzer__fateX_94 | fateX_94 | wo_analyzer | completed | 0 | 2639.9 | 8 | 5 | 4 | 1 |  |
| optional_analyzer__fateX_94 | fateX_94 | optional_analyzer | completed | 0 | 3735.1 | 8 | 6 | 5 | 1 |  |

## Status rollup

| status | count |
|---|---|
| failed | 6 |
| timeout | 6 |
| completed | 5 |

## Comparison by condition

| condition | runs | proved mean/med | unproved mean/med | round mean/med | dur_s mean/med |
|---|---|---|---|---|---|
| optional_analyzer | 2 | 10.5/10.5 | 1.5/1.5 | 8.0/8.0 | 4279.9/4279.9 |
| with_analyzer | 1 | 6.0/6.0 | 1.0/1.0 | 8.0/8.0 | 3768.3/3768.3 |
| wo_analyzer | 2 | 7.5/7.5 | 1.0/1.0 | 8.0/8.0 | 3659.5/3659.5 |

## Comparison by problem

| problem | runs | proved mean/med | unproved mean/med | round mean/med | dur_s mean/med |
|---|---|---|---|---|---|
| fateX_94 | 5 | 8.4/6.0 | 1.2/1.0 | 8.0/8.0 | 3929.42/3768.3 |

## Unsolved nodes (union across runs, per condition)

- **optional_analyzer**: Problem94.ideal_finitelyGenerated, Problem94.orbit_zeroSet_structured, Problem94.orbitZeroSet_finite_or_arithProgression
- **with_analyzer**: Problem94.zeroSet_infinite_contains_ap
- **wo_analyzer**: Problem94.zeroSetAt_finset_dichotomy, Problem94.zeroSet_isFiniteUnionOfAPs

> Token usage is not captured here — filter the LangSmith project by the `condition`/`problem` metadata tags.
