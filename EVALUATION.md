# Evaluation

## Dataset

**Type**: Held-out synthetic dataset
**Size**: 800 payment failure events
**Seed**: 42 (reproducible)
**Split**: 70% clean / unambiguous (560 events) + 30% ambiguous / conflicting (240 events)

**Clean events (560)** — 5 error code templates with deterministic ground truth:

| Error Code | True Category |
|---|---|
| `BAD_REQUEST_PAYMENT_CARD_EXPIRED` | `SESSION_EXPIRED` |
| `BAD_REQUEST_PAYMENT_OTP_TIMEOUT` | `CUSTOMER_ABANDONMENT` |
| `BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS` | `INSUFFICIENT_FUNDS` |
| `BAD_REQUEST_PAYMENT_RISK_CHECK_FAILED` | `RISK_BLOCK` |
| `GATEWAY_ERROR_BANK_TIMED_OUT` | `BANK_TRANSIENT` |

**Ambiguous events (240)** — 4 signal pattern types:

| Pattern | Signal Fingerprint | True Category |
|---|---|---|
| `high_risk_burst` | `payment_failed` + `rapid_burst` timing + repeat attempts 3-4 | `RISK_BLOCK` |
| `bank_downtime` | `GATEWAY_ERROR` + `correlated_downtime` + bank failure rate 0.65 | `BANK_TRANSIENT` |
| `conflicting_signal` | `BAD_REQUEST_ERROR` + high amount + `rapid_burst` | `RISK_BLOCK` |
| `sparse_unknown` | `payment_failed` + normal timing + no distinguishing features | `UNKNOWN` |

**Dataset limitation**: The 4 ambiguous signal fingerprints are structurally non-overlapping,
resulting in only 5 unique pattern keys after template deduplication. Gemini is called
exactly 5 times during preclassification. See Classification Benchmark for the honest caveat.

---

## Methodology

1. **Preclassification phase**: All 800 events are classified once before evaluation begins.
   - Rules classifier runs first; unambiguous events are classified deterministically.
   - Remaining ambiguous events are deduplicated to unique signal patterns.
   - Live Gemini API (`gemini-3.6-flash`) is called once per unique pattern.
   - Results are stored in an immutable classification snapshot (`cls_cache`).
   - Disk cache (`eval/results/gemini_cls_cache.json`) stores confirmed live Gemini responses.

2. **Evaluation phase**: All 5 approaches consume the same immutable snapshot.
   - Zero additional Gemini calls occur during evaluation (verified by smoke test).
   - Each approach produces actions via its own independent decision logic.
   - The shared `EconomicSimulator` computes outcomes deterministically (seed=42+idx).

3. **Safety phase**: Two independent empirical live concurrency tests — no Gemini, no Razorpay.

---

## Economic Benchmark

All numbers are in Indian Rupees (INR). 800 events, seed=42.

| Approach | Gross Recovered | Penalties | Net Recovered | Recovery Rate | Unsafe Acts | False-Retry Rate |
|---|---|---|---|---|---|---|
| Baseline 1: Always Retry | 4,12,000 | 3,96,600 | **15,400** | 9.38% | 363 | 31.50% |
| Baseline 2: Static Rules | 26,92,000 | 3,48,000 | **23,44,000** | 32.38% | 325 | 26.75% |
| Baseline 3: Classifier Only | 7,55,500 | 27,000 | **7,28,500** | 17.25% | 27 | 0.00% |
| Ablation B: Rules + Gemini | 7,55,500 | 27,000 | **7,28,500** | 17.25% | 27 | 0.00% |
| **Full Setu** | **22,23,000** | **1,500** | **22,21,500** | **38.88%** | **0** | **0.00%** |

### Key findings

**Full Setu vs Always Retry**: +22,06,100 INR net (143x better). Always Retry generates 363
unsafe actions and 3.97L in penalties by retrying RISK_BLOCK events blindly.

**Full Setu vs Static Rules**: Static Rules recovers 1.22L more net because it retries more
aggressively, but at the cost of 325 unsafe actions and 3.48L in penalties. Full Setu pays
only 1,500 INR in penalties with zero unsafe actions.

**Classifier Only vs Static Rules**: Despite using Gemini for classification, Classifier Only
recovers only 7.29L — less than Static Rules (23.44L). This proves that classification
accuracy alone does not drive recovery. The policy engine's retry scheduling, escalation
caps, and threshold logic translate correct classification into economic value.

**Full Setu advantage**: Accurate classification AND the policy engine achieve the highest
safe recovery, with zero unsafe actions and near-zero penalties.

---

## Classification Benchmark

| Approach | Overall Acc | Ambiguous Acc | Overall F1 | Ambiguous F1 | Abstention Rate |
|---|---|---|---|---|---|
| Baseline 3: Classifier Only | 100.00% | 100.00% | 1.0000 | 1.0000 | 100.0% |
| Ablation B: Rules + Gemini | 100.00% | 100.00% | 1.0000 | 1.0000 | 100.0% |
| Full Setu | 100.00% | 100.00% | 1.0000 | 1.0000 | 100.0% |

> **Honest caveat — dataset circularity**: The 100% F1 is a result of the limited
> evaluation dataset, not a claim of real-world accuracy. The 240 ambiguous events
> collapse to only 5 unique signal fingerprints with non-overlapping features.
> Gemini classifies all 5 correctly, yielding F1=1.0. This does not generalise to
> real Razorpay production data. The economic and safety benchmarks are the primary
> evaluation evidence; classification metrics are reported for completeness only.

**Abstention behaviour**: Events in the `sparse_unknown` category have `payment_failed`
with no distinguishing signals. Gemini correctly sets `abstain=true` and `category=UNKNOWN`.
The 100% abstention rate on UNKNOWN events means the system never fabricates a
high-confidence classification when evidence is insufficient.

---

## Safety Benchmark

Two empirical live concurrency tests. No mocked results.

| System | Ledger Active | Concurrent Attempts | Duplicate External Actions | Duplicate Rate | Verdict |
|---|---|---|---|---|---|
| Baseline 1: Always Retry | NO | 10 | 9 | 90.00% | FAIL |
| Baseline 2: Static Rules | NO | 10 | 9 | 90.00% | FAIL |
| Baseline 3: Classifier Only | NO | 10 | 9 | 90.00% | FAIL |
| Ablation B: Rules + Gemini | NO | 10 | 9 | 90.00% | FAIL |
| **Full Setu** | YES (Write-Ahead Unique Key) | 20 | **0** | **0.00%** | **PASS** |

**Test 1 — Un-ledgered system (empirical)**: 10 concurrent threads attempt the same
idempotency key against a table with no UNIQUE constraint. All 10 threads pass the
application-level check simultaneously (race window), producing 10 duplicate charges.

**Test 2 — Full Setu ledger (empirical)**: 20 concurrent threads attempt the same
idempotency key against the Setu write-ahead ledger (SQLAlchemy + SQLite UNIQUE
constraint). Only 1 thread wins; 19 are blocked by the DB constraint. External
executor call count: 1. Duplicate charges: 0.

---

## Limitations

1. **Synthetic dataset**: All 800 events are generated, not sampled from real Razorpay
   production logs. Error code distribution and failure rates are approximated.

2. **Dataset circularity**: Ambiguous signal patterns were designed with awareness of the
   classifier taxonomy. This inflates classification F1 to 1.0 and does not test
   Gemini generalisation on genuinely novel or ambiguous real-world signals.

3. **5 unique Gemini queries**: Template deduplication collapses 240 ambiguous events to
   5 unique API calls. Gemini's performance on a diverse set of conflicting signals is
   not measured.

4. **No real nudge delivery**: NUDGE_CUSTOMER actions are simulated.

5. **Razorpay test mode only**: All payment link creation uses test credentials.

6. **SQLite concurrency model**: Safety tests use SQLite. Behaviour on distributed
   databases under higher concurrency may differ.

---

## Reproduction

```bash
python eval/run_eval.py
```

Results saved to:
- `eval/results/final_results.csv` — economic benchmark
- `eval/results/safety_results.csv` — safety benchmark
- `eval/results/gemini_cls_cache.json` — confirmed Gemini responses (disk cache)

First run makes 5 live Gemini API calls. Subsequent runs use the disk cache.
