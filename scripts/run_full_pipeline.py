# scripts/run_full_pipeline.py
# Runs the full pipeline in order:
# 1. Canonical backfill (loops until converged)
# 2. Match key backfill (loops until converged)
# 3. Price history backfill
# 4. Deal delta
# 5. Scorer

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ENV = {"PYTHONUTF8": "1", "PYTHONPATH": "."}
import os
ENV.update(os.environ)

def run(script, label):
    logger.info(f"Starting {label}...")
    result = subprocess.run(
        [sys.executable, script],
        env=ENV,
        capture_output=False
    )
    if result.returncode != 0:
        logger.error(f"{label} failed with exit code {result.returncode}")
    else:
        logger.info(f"{label} complete.")

def run_until_converged(script, label, max_passes=3):
    for i in range(max_passes):
        logger.info(f"{label} — pass {i+1}/{max_passes}")
        result = subprocess.run(
            [sys.executable, script, "--only-missing"],
            env=ENV,
            capture_output=False
        )
        if result.returncode != 0:
            logger.error(f"{label} failed on pass {i+1}")
            break
    logger.info(f"{label} converged.")

def main():
    # Step 1: Canonical backfill
    run_until_converged("scripts/write_canonical_fields.py", "Canonical backfill")

    # Step 2: Match key backfill
    run_until_converged("scripts/backfill_match_key.py", "Match key backfill")

    # Step 3: Price history
    run("scripts/backfill_price_history.py", "Price history backfill")

    # Step 4: Deal delta
    run("scripts/run_deal_delta.py", "Deal delta")

    # Step 5: Scorer
    run("scripts/run_scorer.py", "Scorer")

    logger.info("Full pipeline complete.")

if __name__ == "__main__":
    main()