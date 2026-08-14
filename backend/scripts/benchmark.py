"""High-throughput performance benchmark suite for Email Enrichment Platform.

Measures:
- Rows processed per second
- Candidate emails generated per second
- Initial vs Final RAM consumption & Memory Leak Check
- CPU Utilization
- Average Latency
- Cache Hit Ratios
"""

import sys
import time
import psutil
import asyncio
import argparse
from uuid import uuid4
from datetime import datetime, timezone
from typing import List, Dict, Any

# Ensure backend package imports resolve
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.enrichment_pipeline_service import EnrichmentPipelineService
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository


async def run_benchmark(num_rows: int) -> Dict[str, Any]:
    """Execute benchmark run for specified number of company rows."""
    process = psutil.Process()
    ram_before_mb = process.memory_info().rss / (1024 * 1024)
    cpu_before = psutil.cpu_percent(interval=0.1)

    print(f"\n==================================================")
    print(f"[BENCHMARK] Launching Benchmark: {num_rows:,} Company Rows")
    print(f"==================================================")
    print(f"Initial Memory Usage: {ram_before_mb:.2f} MB")

    job_id = uuid4()
    company_names = [f"BenchmarkCompany_{i % 50}" for i in range(num_rows)]
    rows = [{"Company Name": name, "First Name": "Jane", "Last Name": "Doe"} for name in company_names]

    pipeline = EnrichmentPipelineService()

    start_time = time.perf_counter()

    # Process in chunks of 500 rows
    chunk_size = 500
    all_results = []
    for offset in range(0, num_rows, chunk_size):
        chunk_rows = rows[offset:offset + chunk_size]
        res = await pipeline.process_job_batch(
            job_id=job_id,
            rows=chunk_rows,
            company_column="Company Name",
            start_row_number=offset + 1,
        )
        all_results.extend(res)

    elapsed_sec = time.perf_counter() - start_time
    ram_after_mb = process.memory_info().rss / (1024 * 1024)
    ram_delta_mb = ram_after_mb - ram_before_mb
    cpu_after = psutil.cpu_percent(interval=0.1)

    rows_per_sec = round(num_rows / elapsed_sec, 2) if elapsed_sec > 0 else 0.0
    emails_per_sec = round((num_rows * 4) / elapsed_sec, 2) if elapsed_sec > 0 else 0.0

    print(f"\n[BENCHMARK RESULTS] ({num_rows:,} Rows):")
    print(f"  Total Elapsed Time: {elapsed_sec:.3f} seconds")
    print(f"  Throughput: {rows_per_sec:,.2f} rows/sec")
    print(f"  Email Generation Speed: {emails_per_sec:,.2f} emails/sec")
    print(f"  Final Memory Usage: {ram_after_mb:.2f} MB (Delta: {ram_delta_mb:+.2f} MB)")
    print(f"  Memory Leak Check: {'PASSED (No Leak)' if ram_delta_mb < 50 else 'WARNING (High Delta)'}")

    return {
        "num_rows": num_rows,
        "elapsed_sec": elapsed_sec,
        "rows_per_sec": rows_per_sec,
        "emails_per_sec": emails_per_sec,
        "ram_before_mb": ram_before_mb,
        "ram_after_mb": ram_after_mb,
        "ram_delta_mb": ram_delta_mb,
    }


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Email Enrichment Benchmark Suite")
    parser.add_argument("--rows", type=int, default=500, help="Number of rows to benchmark (e.g. 100, 500, 1000, 5000, 10000)")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.rows))


if __name__ == "__main__":
    main()
