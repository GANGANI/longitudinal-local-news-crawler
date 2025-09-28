#!/usr/bin/env python3
"""
Threaded Internet Archive uploader with retries, MD5 verification, logging and email alerts.

Key features:
 - ThreadPoolExecutor for concurrency (network-bound)
 - Exponential backoff + jitter for retries on 429/5xx/connection errors
 - Larger IO buffer for MD5 computation and streaming (4 MiB)
 - Optional staging to local ephemeral disk to avoid slow shared FS
 - MD5 verification by fetching IA metadata after upload
 - Rotating logs + failure email notifications
"""

import os
import re
import time
import json
import math
import random
import argparse
import shutil
import hashlib
import logging
import smtplib
import traceback
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from logging.handlers import TimedRotatingFileHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# internetarchive library
from internetarchive import upload, get_item, configure  # make sure package installed

# ================= Configuration (edit / override with CLI args) =================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "gangani95ariyarathne@gmail.com"
EMAIL_PASS = "hwms isib tnxz gdon"
EMAIL_TO = "localnewscrawler@gmail.com"

# IO buffer for hashing/streaming (4 MiB recommended)
IO_BUFFER = 4 * 1024 * 1024

# ================= Logging =================
def setup_logger(args):
    log_dir = os.path.dirname(args.log) or "."
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, args.log_level.upper(), logging.DEBUG))

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)

    file_handler = TimedRotatingFileHandler(args.log, when="D", interval=1, backupCount=7, utc=True)
    file_handler.setLevel(getattr(logging, args.log_level.upper(), logging.DEBUG))
    file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logging.info(f"Logging initialized. Writing logs to {args.log}")

def cleanup_old_logs(log_path, days=7):
    log_dir = os.path.dirname(log_path) or "."
    now = time.time()
    cutoff = now - (days * 86400)
    base = os.path.basename(log_path)
    for fname in os.listdir(log_dir):
        if fname.startswith(base):
            fpath = os.path.join(log_dir, fname)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    logging.info(f"Deleted old log file: {fpath}")
            except Exception:
                logging.exception("Error cleaning logs")

# ================= Utilities =================
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        logging.info(f"[Email] Sent: {subject}")
    except Exception as e:
        logging.error(f"[Email] Failed to send email: {e}")

def compute_md5(path, bufsize=IO_BUFFER):
    """Compute md5 digest using large buffer to reduce syscall overhead."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            h.update(chunk)
    return h.hexdigest()

def rename_warc_filename(directory, archive_file_name):
    match = re.match(r"^(.*_)(\d+)(\.warc\.gz)$", archive_file_name)
    if match:
        base, num, ext = match.groups()
        new_file_name = f"{base}{int(num):04}{ext}"
        old_path = os.path.join(directory, archive_file_name)
        new_path = os.path.join(directory, new_file_name)
        if old_path != new_path:
            os.rename(old_path, new_path)
            logging.info(f"[Rename] {archive_file_name} -> {new_file_name}")
        return new_file_name
    return archive_file_name

def get_ia_metadata(item_id):
    """Fetch metadata from Internet Archive using ia CLI if available via internetarchive lib fallback."""
    # Try internetarchive.get_item().item_metadata() if available
    try:
        item = get_item(item_id)
        meta = item.item_metadata()
        if isinstance(meta, dict):
            return meta
    except Exception as e:
        logging.debug(f"[Validator] internetarchive get_item meta failed: {e}")
    # fallback to empty dict
    return {}

# ================= Upload helpers (threaded) =================
def is_retryable_exception(exc):
    """Heuristic: network errors, HTTP 5xx, HTTP 429; treat others as non-retryable."""
    # internetarchive library wraps exceptions; inspect string for common markers
    txt = repr(exc).lower()
    if "429" in txt or "too many requests" in txt:
        return True
    if "5" in txt[:3] and "http" in txt:
        return True
    network_markers = ["connectionreset", "connection aborted", "timed out", "timeout", "name or service not known",
                       "temporarily unavailable", "remote end closed", "503", "502", "504"]
    if any(m in txt for m in network_markers):
        return True
    return False

def upload_with_retry(item_identifier, file_path, file_name, metadata,
                      max_retries=6, base_sleep=2.0, local_stage_path=None, delete_after=False):
    """
    Upload a single file with exponential backoff + jitter and MD5 verification.
    Returns True when upload is verified successful.
    """
    # Optionally stage file to local path (fast ephemeral disk)
    staged_path = file_path
    if local_stage_path:
        os.makedirs(local_stage_path, exist_ok=True)
        staged_path = os.path.join(local_stage_path, os.path.basename(file_path))
        if not os.path.exists(staged_path):
            logging.info(f"[Stage] copying {file_path} -> {staged_path}")
            shutil.copy2(file_path, staged_path)
        else:
            logging.info(f"[Stage] already staged: {staged_path}")

    local_md5 = compute_md5(staged_path)
    logging.info(f"[MD5] {file_name} md5={local_md5}")

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            logging.info(f"[Upload-Start] {file_name} -> {item_identifier} (attempt {attempt})")
            # Use internetarchive.upload with path (streams file); set retries=0 to rely on our policy
            # Using files dict ensures filename in IA points to desired name
            upload(item_identifier,
                   files={file_name: staged_path},
                   metadata=metadata,
                   queue_derive=False,
                   retries=0,
                   verbose=True)
            # After upload, fetch IA metadata and compare MD5
            time.sleep(1.0)  # small pause allow IA to register file
            meta = get_ia_metadata(item_identifier)
            if meta and 'files' in meta:
                # find the file entry
                ia_files = {f['name']: f.get('md5') for f in meta['files'] if 'name' in f}
                ia_md5 = ia_files.get(file_name)
                if ia_md5:
                    if ia_md5 == local_md5:
                        logging.info(f"[Upload-Verified] {file_name} md5 matches ({local_md5})")
                        if delete_after:
                            try:
                                os.remove(file_path)
                                logging.info(f"[Cleanup] Deleted original file {file_path}")
                                if staged_path != file_path and os.path.exists(staged_path):
                                    os.remove(staged_path)
                                    logging.info(f"[Cleanup] Deleted staged file {staged_path}")
                            except Exception:
                                logging.exception("Error deleting files")
                        return True
                    else:
                        # MD5 mismatch: treat as retryable
                        logging.warning(f"[MD5-MISMATCH] local {local_md5} != ia {ia_md5} for {file_name}")
                        raise RuntimeError(f"MD5 mismatch (local {local_md5} != ia {ia_md5})")
                else:
                    logging.warning(f"[IA-META] {file_name} not listed in IA metadata yet")
                    # treat as retryable; continue to retry
            else:
                logging.warning(f"[IA-META] no metadata or files for {item_identifier}")
                # treat as retryable
            # If we reach here, something wasn't verified — raise to go into backoff
            raise RuntimeError("Upload not verified yet")
        except Exception as e:
            logging.warning(f"[Upload-Error] {file_name} attempt {attempt} error: {e}")
            # send email only for final failure, not every transient exception
            retryable = is_retryable_exception(e)
            # compute sleep with exponential backoff + jitter
            sleep = base_sleep * (2 ** (attempt - 1))
            sleep = min(sleep, 300)  # cap
            jitter = random.uniform(0, sleep * 0.25)
            sleep += jitter
            logging.info(f"[Backoff] sleeping {sleep:.1f}s before next attempt (retryable={retryable})")
            time.sleep(sleep)
            # continue loop for retryable or non-retryable (we still attempt up to max_retries)
    # exhausted retries -> final failure
    body = f"Failed to upload after {max_retries} attempts: {item_identifier}/{file_name}\n\nTrace:\n{traceback.format_exc()}"
    logging.error(body)
    send_email(f"Upload Failed: {item_identifier}/{file_name}", body)
    return False

# ================= Main scheduler & threading =================
def get_yesterday_directory(prefix="USLNDA"):
    yesterday_utc = datetime.now(timezone.utc) - timedelta(days=1)
    return f"{prefix}-{yesterday_utc.strftime('%Y%m%d')}"

def run_daily_upload(args):
    # Configure internetarchive (if credentials set via env or args)
    # e.g. configure(access_key=..., secret_key=...) if you want explicit AWS-style creds
    logging.info("[Scheduler] Starting upload run")

    item_identifier = get_yesterday_directory()
    collection_dir = os.path.join(args.collection_directory, item_identifier)
    logging.info(f"[Scheduler] Target collection_dir = {collection_dir}")

    if not os.path.exists(collection_dir):
        logging.error(f"[Scheduler] Directory not found: {collection_dir}")
        send_email("Upload Error", f"Directory not found: {collection_dir}")
        return

    # gather IA metadata for comparison
    ia_meta = get_ia_metadata(item_identifier)
    ia_files_md5 = {}
    if ia_meta and 'files' in ia_meta:
        ia_files_md5 = {f['name']: f.get('md5') for f in ia_meta['files'] if f.get('name', '').endswith('.warc.gz')}

    warc_files = sorted([f for f in os.listdir(collection_dir) if f.endswith(".warc.gz")])
    if not warc_files:
        logging.warning("[Scheduler] No WARC files found to upload.")
        return

    # Prepare jobs: rename if needed, stage path, and determine which ones need upload
    jobs = []
    seen = set()
    for fname in warc_files:
        if fname in seen:
            continue
        new_fname = rename_warc_filename(collection_dir, fname)
        local_file_path = os.path.join(collection_dir, new_fname)

        # if IA has no files at all, upload all
        if not ia_files_md5:
            logging.info(f"[Scheduler] IA has no files; queuing {new_fname}")
            jobs.append((local_file_path, new_fname, item_identifier))
        elif new_fname not in ia_files_md5:
            logging.info(f"[Scheduler] New file (not in IA): queuing {new_fname}")
            jobs.append((local_file_path, new_fname, item_identifier))
        else:
            local_md5 = compute_md5(local_file_path)
            if local_md5 != ia_files_md5.get(new_fname):
                logging.info(f"[Scheduler] MD5 mismatch for {new_fname}; queuing reupload")
                jobs.append((local_file_path, new_fname, item_identifier))
            else:
                logging.info(f"[Scheduler] Skipping {new_fname} (already uploaded, md5 matches)")
        seen.add(fname)

    if not jobs:
        logging.info("[Scheduler] Nothing to upload.")
        return

    # Threaded uploads
    metadata_payload = {
        'collection': args.collection,
        'uploader': args.uploader,
        'mediatype': args.mediatype
    }

    max_workers = max(1, args.max_workers)
    logging.info(f"[Scheduler] Starting ThreadPoolExecutor with max_workers={max_workers}")

    # local staging dir (optional)
    local_stage_path = None
    if args.stage_to_local:
        local_stage_path = args.local_stage_path or "/tmp/ia_staging"
        os.makedirs(local_stage_path, exist_ok=True)

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_job = {
            ex.submit(upload_with_retry, item_id, path, fname, metadata_payload,
                      args.max_retries, args.backoff_base, local_stage_path, args.delete_uploaded_warc):
            (path, fname, item_id)
            for (path, fname, item_id) in jobs
        }

        for fut in as_completed(future_to_job):
            path, fname, item_id = future_to_job[fut]
            try:
                ok = fut.result()
                if ok:
                    logging.info(f"[Worker] Success: {fname}")
                    success_count += 1
                else:
                    logging.error(f"[Worker] Failed: {fname}")
                    fail_count += 1
            except Exception as e:
                logging.exception(f"[Worker] Exception for {fname}: {e}")
                send_email(f"Upload Exception: {fname}", f"Exception:\n{traceback.format_exc()}")
                fail_count += 1

    logging.info(f"[Scheduler] Upload run finished: {success_count} success, {fail_count} failed")
    if fail_count:
        send_email("Upload run finished with failures", f"{success_count} succeeded, {fail_count} failed for {item_identifier}")

# ================= CLI =================
def parse_args():
    p = argparse.ArgumentParser(description="Daily Internet Archive uploader (threaded).")
    p.add_argument("--collection", default="us-local-news-data", help="Collection name of the internet archive")
    p.add_argument("--collection_directory", default="/app1/ia-collection", help="Directory containing dated collection folders")
    p.add_argument("--uploader", default="Alexander C. Nwala <alexandernwala@gmail.com>", help="Uploader identity")
    p.add_argument("--mediatype", default="web", help="Media type for Internet Archive upload")
    p.add_argument("--delete_uploaded_warc", action="store_true", help="Delete the .warc file after successful upload")
    p.add_argument("--max_workers", type=int, default=4, help="Number of parallel worker threads per pod")
    p.add_argument("--log", default="/app1/news_scraper.log", help="Path to log file")
    p.add_argument("--log_level", default="INFO", help="Logging level")
    p.add_argument("--max_retries", type=int, default=6, help="Max retries per file")
    p.add_argument("--backoff_base", type=float, default=2.0, help="Base sleep in seconds for exponential backoff")
    p.add_argument("--stage_to_local", action="store_true", help="Copy files to local SSD before uploading (faster reads)")
    p.add_argument("--local_stage_path", default="/tmp/ia_staging", help="Local staging directory path")
    p.add_argument("--upload_warc", action="store_true", help="Enable uploading of warc files (default false if not provided)")
    p.add_argument("--prefix", default="USLNDA", help="Prefix for dated folder name (YESTERDAY prefix-YYYYMMDD)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    setup_logger(args)
    cleanup_old_logs(args.log, days=7)

    logging.info("[Main] Starting uploader")
    # If user didn't set upload_warc flag, treat as enabled if they explicitly set it. (Matches CLI pattern)
    if not args.upload_warc and not args.stage_to_local:
        # If user didn't pass upload_warc, but in original you had default True; here we require flag
        # For convenience, enable uploading unless explicit reason to disable; adjust as desired.
        args.upload_warc = True

    try:
        # Run upload for yesterday directory (prefix handled in get_yesterday_directory)
        run_daily_upload(args)
    except Exception as e:
        logging.exception("Fatal error in main:")
        send_email("Uploader Fatal Error", f"Exception:\n{traceback.format_exc()}")
        raise
