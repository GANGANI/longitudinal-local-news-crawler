import os
import re
import time
import json
import subprocess
import smtplib
import hashlib
import logging
import argparse
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logging.handlers import TimedRotatingFileHandler
from multiprocessing import Pool, cpu_count
from math import ceil

# ================= Configuration =================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "gangani95ariyarathne@gmail.com"
EMAIL_PASS = "hwms isib tnxz gdon"
EMAIL_TO = "localnewscrawler@gmail.com"

# ================= Logging =================
def setup_logger(args):
    log_dir = os.path.dirname(args.log)
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, args.log_level.upper(), logging.DEBUG))

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)

    file_handler = TimedRotatingFileHandler(args.log, when="D", interval=1, backupCount=2, utc=True)
    file_handler.setLevel(getattr(logging, args.log_level.upper(), logging.DEBUG))
    file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(f"Logging initialized. Writing logs to {args.log}")


# ================= Utility Functions =================
def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        logging.info(f"[Email] Sent: {subject}")
    except Exception as e:
        logging.error(f"[Email] Failed to send email: {e}")


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


def get_yesterday_directory(prefix="USLNDA"):
    yesterday_utc = datetime.now(timezone.utc) - timedelta(days=1)
    return f"{prefix}-{yesterday_utc.strftime('%Y%m%d')}"


def upload_chunk(args_tuple):
    """Worker function to upload a chunk of WARC files in parallel."""
    item_identifier, files, metadata_args = args_tuple
    start = time.time()
    try:
        cmd = [
            "ia", "upload", item_identifier,
            *files,
            "--no-derive",
            *metadata_args
        ]
        logging.info(f"[Worker] Starting upload of {len(files)} files: {files}")
        subprocess.run(cmd, check=True)
        duration = time.time() - start
        logging.info(f"[Worker] Uploaded {len(files)} files in {duration/60:.1f} min")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"[Worker] Upload failed for chunk {files}: {e}")
        send_email("Upload Failed", f"Chunk upload failed. Error: {e}")
        return False


# ================= Upload Logic =================
def run_parallel_upload(args):
    item_identifier = get_yesterday_directory()
    collection_dir = os.path.join(args.collection_directory, item_identifier)
    logging.info(f"[Scheduler] Starting upload for {collection_dir}")

    if not os.path.exists(collection_dir):
        logging.error(f"[Scheduler] Directory not found: {collection_dir}")
        send_email("Upload Error", f"Directory not found: {collection_dir}")
        return

    warc_files = [rename_warc_filename(collection_dir, f) for f in os.listdir(collection_dir) if f.endswith(".warc.gz")]

    if not warc_files:
        logging.warning("[Scheduler] No WARC files found to upload.")
        return

    # Build metadata params for ia CLI
    metadata_args = [
        f"--metadata=collection:{args.collection}",
        f"--metadata=uploader:{args.uploader}",
        f"--metadata=mediatype:{args.mediatype}"
    ]

    file_paths = [os.path.join(collection_dir, f) for f in warc_files]
    logging.info(f"[Upload-Start] Uploading {len(file_paths)} WARC files to {item_identifier}")

    # Split into chunks
    chunk_size = max(1, ceil(len(file_paths) / args.max_workers))
    chunks = [file_paths[i:i + chunk_size] for i in range(0, len(file_paths), chunk_size)]

    start = time.time()
    with Pool(processes=args.max_workers) as pool:
        pool.map(upload_chunk, [(item_identifier, chunk, metadata_args) for chunk in chunks])

    duration = time.time() - start
    logging.info(f"[Upload-Done] Uploaded {len(file_paths)} files in total in {duration/60:.1f} min")

    if args.delete_uploaded_warc:
        for f in file_paths:
            os.remove(f)
            logging.info(f"[Cleanup] Deleted {f}")


# ================= Main =================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Internet Archive parallel uploader.")
    parser.add_argument("--collection", default="us-local-news-data", help="Collection name")
    parser.add_argument("--collection_directory", default="/app1/ia-collection", help="Directory with WARC files")
    parser.add_argument("--uploader", default="Alexander C. Nwala <alexandernwala@gmail.com>", help="Uploader identity")
    parser.add_argument("--mediatype", default="web", help="Media type for Internet Archive")
    parser.add_argument("--delete_uploaded_warc", type=bool, default=False, help="Delete WARC after upload")
    parser.add_argument("--log", default="/app1/news_scraper.log", help="Path to log file")
    parser.add_argument("--log_level", default="INFO", help="Logging level")
    parser.add_argument("--max_workers", type=int, default=min(cpu_count(), 5), help="Number of parallel upload workers")
    args = parser.parse_args()

    setup_logger(args)
    logging.info("[Main] Starting parallel uploader for yesterday's directory...")
    run_parallel_upload(args)
