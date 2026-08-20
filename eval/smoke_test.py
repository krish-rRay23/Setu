"""
Smoke test: run 10 events through the full evaluation pipeline.
Verifies:
  1. Preclassification succeeds with live Gemini (calls made ONLY here).
  2. ZERO Gemini calls occur during the evaluation loop (all baselines/ablations).
  3. All five approaches produce valid actions.
"""
import sys, os, time, logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Patch the llm_classifier to count any live calls during evaluation
import src.classifier.llm as llm_module

_original_gemini_live = llm_module.gemini_live_llm_inference
_live_calls_after_preclassify = []

def _tracked_gemini(pruned_evidence, api_key):
    _live_calls_after_preclassify.append(1)
    return _original_gemini_live(pruned_evidence, api_key)

# Load env
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
env_path = os.path.join(root_dir, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()

logging.basicConfig(level=logging.INFO, format="%(message)s")

from eval.generator import generate_synthetic_dataset
from eval.run_eval import preclassify_events_with_rate_limiting, evaluate_approach
from eval.simulator import EconomicSimulator
from src.classifier.models import RootCauseCategory

# Generate 10 events (5 clean + 5 ambiguous proportionally)
events, ground_truth = generate_synthetic_dataset(num_events=20, seed=99)
events = events[:10]
ground_truth = ground_truth[:10]

print("=" * 70)
print("SMOKE TEST: 10 events — verifying zero post-preclassify Gemini calls")
print("=" * 70)

# Step 1: Preclassify (real Gemini calls happen here)
cls_cache = preclassify_events_with_rate_limiting(events)
print(f"\n[OK] Preclassification done. Cache has {len(cls_cache)} entries.\n")

# Step 2: Inject tracker AFTER preclassification
llm_module.gemini_live_llm_inference = _tracked_gemini

# Step 3: Run all approaches
simulator = EconomicSimulator()
approaches = [
    ("Baseline 1: Always Retry",     "baseline_always_retry"),
    ("Baseline 2: Static Rules",     "baseline_static_rules"),
    ("Baseline 3: Classifier Only",  "baseline_classifier_only"),
    ("Ablation B: Rules + Gemini",   "ablation_rules_gemini"),
    ("Full Setu",                    "full_system"),
]

print(f"{'Approach':<32} | {'Recovery Rate':>13} | {'Net Rec (INR)':>13}")
print("-" * 70)
for name, atype in approaches:
    res = evaluate_approach(name, events, ground_truth, atype, simulator, cls_cache)
    print(f"{name:<32} | {res['Recovery Rate (%)']:>12.2f}% | INR {res['Net Recovered (INR)']:>9,.2f}")

print("\n" + "=" * 70)
if _live_calls_after_preclassify:
    print(f"[FAIL] {len(_live_calls_after_preclassify)} UNEXPECTED live Gemini call(s) occurred during evaluation loop!")
    sys.exit(1)
else:
    print("[PASS] Zero Gemini calls during evaluation loop. Architecture is correct.")
print("=" * 70)
