"""
One-time script: query Gemini for the 5 unique ambiguous templates and save to disk cache.
Run this once to populate eval/results/gemini_cls_cache.json.
Subsequent benchmark runs will be instant for preclassification.
"""
import sys, os, time, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

from eval.generator import generate_synthetic_dataset
from src.classifier.rules import rules_classifier
from src.classifier.llm import llm_classifier

events, _ = generate_synthetic_dataset(num_events=800, seed=42)

ambiguous_templates = {}
for ev in events:
    rule_res = rules_classifier(ev)
    if rule_res is None:
        ctx = ev.get("context", {})
        pattern_key = f"{ev['error_code']}_{ctx.get('timing_pattern')}_{ctx.get('repeat_attempt_count')}_{ctx.get('recent_bank_failure_rate')}"
        if pattern_key not in ambiguous_templates:
            ambiguous_templates[pattern_key] = ev

disk_cache_path = os.path.join("eval", "results", "gemini_cls_cache.json")
os.makedirs(os.path.join("eval", "results"), exist_ok=True)

# Load existing cache
disk_cache = {}
if os.path.exists(disk_cache_path):
    with open(disk_cache_path) as f:
        disk_cache = json.load(f)

new_patterns = {k: v for k, v in ambiguous_templates.items() if k not in disk_cache}
print(f"Found {len(ambiguous_templates)} unique patterns. {len(disk_cache)} already cached. Querying {len(new_patterns)} new...")

for i, (p_key, sample_ev) in enumerate(new_patterns.items()):
    print(f"  [{i+1}/{len(new_patterns)}] Querying pattern: {p_key}")
    time.sleep(4.0)  # Extra conservative for rate limit after recent 429s
    res = llm_classifier(sample_ev, sample_ev.get("context"))
    disk_cache[p_key] = {
        "category": res.category.value,
        "confidence": res.confidence,
        "evidence": res.evidence,
        "abstain": res.abstain,
        "source": res.source,
    }
    print(f"     -> {res.category.value} (confidence={res.confidence:.2f}, abstain={res.abstain})")
    with open(disk_cache_path, "w", encoding="utf-8") as f:
        json.dump(disk_cache, f, indent=2)

print(f"\nDisk cache now has {len(disk_cache)} patterns saved to {disk_cache_path}")
print("You can now run 'python eval/run_eval.py' without any live Gemini calls during preclassification.")
