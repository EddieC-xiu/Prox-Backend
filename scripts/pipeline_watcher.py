# scripts/pipeline_watcher.py
#
# Watches the pipeline_queue table and runs the full pipeline
# whenever a new 'pending' entry appears (triggered by new flyer_deals inserts).
#
# Run this once and leave it running:
#   PYTHONPATH=. python scripts/pipeline_watcher.py

import time
import logging
import subprocess
import sys
import os
from datetime import datetime, timezone
from config.supabase import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # check every 30 seconds
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": "."}


def get_pending_jobs(client):
    res = (
        client.table("pipeline_queue")
        .select("id, triggered_at")
        .eq("status", "pending")
        .order("triggered_at")
        .limit(1)
        .execute()
    )
    return res.data or []


def mark_running(client, job_id: int):
    client.table("pipeline_queue").update({
        "status": "running"
    }).eq("id", job_id).execute()


def mark_complete(client, job_id: int):
    client.table("pipeline_queue").update({
        "status":       "complete",
        "completed_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", job_id).execute()


def mark_failed(client, job_id: int):
    client.table("pipeline_queue").update({
        "status": "failed"
    }).eq("id", job_id).execute()


def run_pipeline():
    logger.info("Running full pipeline...")
    result = subprocess.run(
        [sys.executable, "scripts/run_full_pipeline.py"],
        env=ENV
    )
    return result.returncode == 0


def main():
    client = get_supabase_client()
    logger.info(f"Pipeline watcher started — polling every {POLL_INTERVAL}s")

    while True:
        try:
            jobs = get_pending_jobs(client)
            if jobs:
                job = jobs[0]
                job_id = job["id"]
                logger.info(f"Found pending job {job_id} triggered at {job['triggered_at']}")
                mark_running(client, job_id)

                success = run_pipeline()

                if success:
                    mark_complete(client, job_id)
                    logger.info(f"Job {job_id} completed successfully")
                else:
                    mark_failed(client, job_id)
                    logger.error(f"Job {job_id} failed")
            else:
                logger.debug("No pending jobs")

        except Exception as e:
            logger.error(f"Watcher error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()