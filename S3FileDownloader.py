"""
S3FileDownloader.py
-------------------
Download files from an S3 prefix with size filtering and parallel concurrency.

Usage:
    python S3FileDownloader.py <s3_uri> <local_folder> <min_mb> <max_mb> <concurrency>

Example:
    python S3FileDownloader.py s3://my-bucket/data/2024/ ./downloads 100 500 4

Arguments:
    s3_uri        S3 URI in format s3://bucket/prefix
    local_folder  Local directory to save downloaded files
    min_mb        Minimum file size in MB (exclusive, i.e. size > min_mb)
    max_mb        Maximum file size in MB (inclusive, i.e. size <= max_mb)
    concurrency   Max number of parallel download threads

AWS credentials are read from ~/.aws/credentials.
"""

import argparse
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from tqdm import tqdm

MB = 1024 * 1024


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse s3://bucket/prefix into (bucket, prefix)."""
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URI (must start with s3://): {s3_uri}")
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    if not bucket:
        raise ValueError(f"Could not extract bucket from URI: {s3_uri}")
    return bucket, prefix


def list_filtered_objects(
    s3_client, bucket: str, prefix: str, min_bytes: int, max_bytes: int
) -> list[dict]:
    """
    Return all S3 objects under prefix where min_bytes < size <= max_bytes.
    Handles S3 pagination automatically.
    """
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    matched = []
    total_listed = 0

    print(f"\n🔍 Scanning s3://{bucket}/{prefix} ...")
    for page in pages:
        for obj in page.get("Contents", []):
            total_listed += 1
            size = obj["Size"]
            if min_bytes < size <= max_bytes:
                matched.append({"Key": obj["Key"], "Size": size})

    print(f"   Listed {total_listed} objects, {len(matched)} match the size filter.\n")
    return matched


def download_one(
    s3_client,
    bucket: str,
    s3_key: str,
    local_path: Path,
    file_size: int,
    failed_list: list,
    lock: threading.Lock,
) -> None:
    """
    Download a single S3 object to local_path.
    Uses a .downloading temp file during transfer; renames on success.
    """
    tmp_path = local_path.with_suffix(local_path.suffix + ".downloading")
    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with (
            tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=local_path.name,
                leave=False,
                dynamic_ncols=True,
            ) as pbar,
            open(tmp_path, "wb") as f,
        ):
            s3_client.download_fileobj(
                bucket,
                s3_key,
                f,
                Callback=lambda bytes_transferred: pbar.update(bytes_transferred),
            )

        tmp_path.rename(local_path)

    except (BotoCoreError, ClientError, OSError) as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        with lock:
            failed_list.append((s3_key, str(exc)))


def run_downloads(
    s3_client,
    bucket: str,
    objects: list[dict],
    local_folder: Path,
    prefix: str,
    concurrency: int,
) -> list[tuple[str, str]]:
    """
    Download all objects in parallel; return list of (s3_key, error) for failures.
    """
    failed: list[tuple[str, str]] = []
    lock = threading.Lock()

    overall = tqdm(
        total=len(objects),
        desc="Overall progress",
        unit="file",
        dynamic_ncols=True,
    )

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {}
        for obj in objects:
            s3_key = obj["Key"]
            # Strip the prefix so directory structure is relative to local_folder
            relative_key = s3_key[len(prefix):].lstrip("/")
            local_path = local_folder / relative_key

            future = executor.submit(
                download_one,
                s3_client,
                bucket,
                s3_key,
                local_path,
                obj["Size"],
                failed,
                lock,
            )
            futures[future] = s3_key

        for future in as_completed(futures):
            overall.update(1)
            # Exceptions are caught inside download_one; nothing to re-raise here.

    overall.close()
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download S3 objects by prefix with size filtering and concurrency."
    )
    parser.add_argument("s3_uri", help="S3 URI, e.g. s3://bucket/prefix/")
    parser.add_argument("local_folder", help="Local directory to store downloaded files")
    parser.add_argument(
        "min_mb",
        type=float,
        help="Min file size in MB (exclusive). Files must be > min_mb.",
    )
    parser.add_argument(
        "max_mb",
        type=float,
        help="Max file size in MB (inclusive). Files must be <= max_mb.",
    )
    parser.add_argument(
        "concurrency",
        type=int,
        help="Max number of parallel download threads.",
    )
    args = parser.parse_args()

    if args.min_mb < 0 or args.max_mb < 0:
        parser.error("min_mb and max_mb must be non-negative.")
    if args.min_mb >= args.max_mb:
        parser.error("min_mb must be strictly less than max_mb.")
    if args.concurrency < 1:
        parser.error("concurrency must be at least 1.")

    try:
        bucket, prefix = parse_s3_uri(args.s3_uri)
    except ValueError as exc:
        parser.error(str(exc))

    local_folder = Path(args.local_folder)
    local_folder.mkdir(parents=True, exist_ok=True)

    min_bytes = int(args.min_mb * MB)
    max_bytes = int(args.max_mb * MB)

    print(f"S3 URI       : {args.s3_uri}")
    print(f"Local folder : {local_folder.resolve()}")
    print(f"Size filter  : > {args.min_mb} MB  and  <= {args.max_mb} MB")
    print(f"Concurrency  : {args.concurrency} threads")

    try:
        s3_client = boto3.client("s3")
    except Exception as exc:
        print(f"[ERROR] Failed to create S3 client: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        objects = list_filtered_objects(s3_client, bucket, prefix, min_bytes, max_bytes)
    except (BotoCoreError, ClientError) as exc:
        print(f"[ERROR] Failed to list S3 objects: {exc}", file=sys.stderr)
        sys.exit(1)

    if not objects:
        print("No objects match the filter. Nothing to download.")
        sys.exit(0)

    total_size_mb = sum(o["Size"] for o in objects) / MB
    print(f"Downloading {len(objects)} file(s), total ~{total_size_mb:.1f} MB ...\n")

    failed = run_downloads(
        s3_client, bucket, objects, local_folder, prefix, args.concurrency
    )

    print("\n" + "=" * 60)
    if failed:
        print(f"[DONE] {len(objects) - len(failed)}/{len(objects)} succeeded.")
        print(f"\n[FAILED] {len(failed)} file(s) failed to download:\n")
        for s3_key, reason in failed:
            print(f"  ✗ s3://{bucket}/{s3_key}")
            print(f"    Reason: {reason}")
    else:
        print(f"[DONE] All {len(objects)} file(s) downloaded successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
