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
from multiprocessing import Process, Queue
from internetarchive import upload
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logging.handlers import TimedRotatingFileHandler

# ================= Configuration =================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "gangani95ariyarathne@gmail.com"
EMAIL_PASS = "hwms isib tnxz gdon"
EMAIL_TO = "localnewscrawler@gmail.com"

# ================= Logging =================
def setup_logger(args):
    """Setup logging with rotation and cleanup of old logs."""
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


def cleanup_old_logs(log_path, days=2):
    """Delete log files older than N days."""
    log_dir = os.path.dirname(log_path)
    now = time.time()
    cutoff = now - (days * 86400)

    for fname in os.listdir(log_dir):
        if fname.startswith(os.path.basename(log_path)):
            fpath = os.path.join(log_dir, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                logging.info(f"Deleted old log file: {fpath}")

# ================= Utility Functions =================
def send_email(subject, body):
    """Send email notification for errors."""
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


def get_ia_metadata(item_id):
    """Fetch metadata from Internet Archive using ia CLI."""
    try:
        result = subprocess.run(
            ['ia-collection/ia', 'metadata', item_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.info(f"[Validator] Error fetching metadata for {item_id}: {e.stderr}")
        return None


def rename_warc_filename(directory, archive_file_name):
    """
    Match pattern 'name_<number>.warc.gz' and rename to zero-padded 4-digit number.
    Example: 'news_1.warc.gz' -> 'news_0001.warc.gz'
    """
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

# ================= Upload Worker =================
def worker_loop(upload_queue, args):
    while True:
        job = upload_queue.get()
        if job is None:
            break
        file_path, file_name, item_identifier = job
        try:
            if not args.upload_warc:
                logging.info(f"[Skip] {file_name} (upload_warc disabled)")
                continue

            logging.info(f"[Upload-Start][PID {os.getpid()}] {file_name} -> {item_identifier}")
            start = time.time()
            upload(
                item_identifier,
                files={file_name: file_path},
                metadata={
                    'collection': args.collection,
                    'uploader': args.uploader,
                    'mediatype': args.mediatype
                },
                queue_derive=False,
                retries=10,
                retries_sleep=60,
                verbose=True
            )
            duration = time.time() - start
            logging.info(f"[Upload-Speed] {file_name} took {duration/60:.1f} min")
            logging.info(f"[Upload-Done][PID {os.getpid()}] {file_name}")

            if args.delete_uploaded_warc and os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"[Cleanup] Deleted {file_path}")

        except Exception as e:
            subject = f"Upload Failed: {item_identifier}/{file_name}"
            body = f"Failed to upload {file_name}.\nException: {e}"
            logging.error(f"[Error] {body}")
            send_email(subject, body)

class IAUploader:
    def __init__(self, max_workers=3):
        self.upload_queue = Queue()
        self.max_workers = max_workers
        self.workers = []

    def start_workers(self, args):
        for i in range(self.max_workers):
            p = Process(target=worker_loop, args=(self.upload_queue, args))
            p.daemon = True
            p.start()
            self.workers.append(p)
            logging.info(f"[Worker] Started worker process {p.pid}")

    def queue_file(self, file_path, file_name, item_identifier):
        self.upload_queue.put((file_path, file_name, item_identifier))

    def stop_workers(self):
        for _ in self.workers:
            self.upload_queue.put(None)
        for p in self.workers:
            p.join()
        logging.info("[Worker] All workers stopped")

# ================= Daily Scheduler =================
def get_yesterday_directory(prefix="USLNDA"):
    yesterday_utc = datetime.now(timezone.utc) - timedelta(days=1)
    return f"{prefix}-{yesterday_utc.strftime('%Y%m%d')}"


def get_ia_metadata(item_id):
    """Fetch metadata from Internet Archive using ia CLI."""
    try:
        result = subprocess.run(
            ['ia', 'metadata', item_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.info(f"[Validator] Item {item_id} not found or error fetching metadata: {e.stderr.strip()}")
        return {}
    except json.JSONDecodeError:
        logging.warning("[Validator] Failed to parse metadata JSON.")
        return {}

    
def compute_md5(file_path):
    """Compute MD5 hash of a local file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def run_daily_upload(args):
    uploader = IAUploader(max_workers=args.max_workers)
    uploader.start_workers(args)

    # ✅ Use yesterday’s folder
    item_identifier = get_yesterday_directory()
    collection_dir = os.path.join(args.collection_directory, item_identifier)
    logging.info(f"[Scheduler] Starting upload for {collection_dir}")

    if not os.path.exists(collection_dir):
        logging.error(f"[Scheduler] Directory not found: {collection_dir}")
        send_email("Upload Error", f"Directory not found: {collection_dir}")
        uploader.stop_workers()
        return
    
    metadata = get_ia_metadata(item_identifier)
    ia_files_md5 = {}
    if metadata and 'files' in metadata:
        ia_files_md5 = {f['name']: f['md5'] for f in metadata['files'] if f['name'].endswith('.warc.gz')}

    seen_files = set()
    warc_files = [f for f in os.listdir(collection_dir) if f.endswith(".warc.gz")]

    if not warc_files:
        logging.warning("[Scheduler] No WARC files found to upload.")
    else:
        for file_name in warc_files:
            if file_name not in seen_files:
                file_name = rename_warc_filename(collection_dir, file_name)
                local_file_path = os.path.join(collection_dir, file_name)

                # ✅ If IA has no record -> upload all files
                if not ia_files_md5:
                    uploader.queue_file(local_file_path, file_name, item_identifier)
                    logging.info(f"[Scheduler] Queued new file: {file_name}")

                # ✅ If file not in IA at all -> upload
                elif file_name not in ia_files_md5:
                    uploader.queue_file(local_file_path, file_name, item_identifier)
                    logging.info(f"[Scheduler] Queued new file: {file_name}")

                # ✅ If file exists but MD5 differs -> re-upload
                else:
                    local_md5 = compute_md5(local_file_path)
                    if local_md5 != ia_files_md5[file_name]:
                        uploader.queue_file(local_file_path, file_name, item_identifier)
                        logging.info(f"[Scheduler] MD5 mismatch, re-queued: {file_name}")
                    else:
                        logging.info(f"[Scheduler] Skipped {file_name} (already uploaded & MD5 match)")

                seen_files.add(file_name)

    logging.info("[Scheduler] Waiting for all uploads to finish...")
    uploader.stop_workers()
    logging.info("[Scheduler] Upload complete.")

# ================= Main =================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Internet Archive uploader.")
    parser.add_argument("--collection", default="us-local-news-data", help="Collection name of the internet archive")
    parser.add_argument("--collection_directory", default="/app1/ia-collection", help="Directory to collect warc files")
    parser.add_argument("--uploader", default="Alexander C. Nwala <alexandernwala@gmail.com>", help="Uploader identity")
    parser.add_argument("--mediatype", default="web", help="Media type for Internet Archive upload")
    parser.add_argument("--upload_wacz", type=bool, default=True, help="Upload .wacz file to Internet Archive")
    parser.add_argument("--delete_uploaded_warc", type=bool, default=False, help="Delete the .warc file after upload")
    parser.add_argument("--max_workers", type=int, default=3, help="Number of parallel workers")
    parser.add_argument("--log", default="/app1/news_scraper.log", help="Path to log file")
    parser.add_argument("--log_level", default="INFO", help="Logging level")
    parser.add_argument("--upload_warc", type=bool, default=True, help="Upload the warc file to internet archive")
    args = parser.parse_args()

    setup_logger(args)
    cleanup_old_logs(args.log, days=2)

    logging.info("[Main] Starting uploader for yesterday's directory...")
    run_daily_upload(args)
