import argparse
import json
import os
import re
import shutil
import feedparser
import requests
import subprocess
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from queue import Queue
import concurrent.futures
from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlsplit, urlunparse, parse_qsl, urlencode
from storysniffer import StorySniffer
# from internetarchive import upload
from datetime import datetime, timezone, timedelta
# from upload_validator import UploadValidator
import smtplib
from multiprocessing import Process
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# from upload_ia import IAUploader, upload_directory

# === CONFIGURATION ===
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "ga****@gmail.com"
EMAIL_PASS = ""
EMAIL_TO = "local***@gmail.com"


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

def send_email(subject, body):
    """Send an email alert."""
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
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def get_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="News Archival Script")
    parser.add_argument("--input", default="data.json", help="Path to JSON input file")
    parser.add_argument("--sleep", type=int, default=3600, help="Time between iterations (in seconds)")
    parser.add_argument("--max_articles", type=int, default=5, help="Maximum number of articles to scrape per publication")
    parser.add_argument("--log", default="/app2/news_scraper.log", help="Path to log file")
    parser.add_argument("--log_level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    parser.add_argument("--mediatype", default="web", help="Media type for Internet Archive upload")
    parser.add_argument("--collection", default="us-local-news-data", help="Collection name of the internet archive")
    parser.add_argument("--item_identifier", default="USLNDA", help="Prefix of the item identifier")
    # parser.add_argument("--uploader", default="Alexander C. Nwala <alexandernwala@gmail.com>", help="Uploader identity")
    parser.add_argument("--time_limit", type=int, help="Time limit (in seconds) for archiving subprocess")
    parser.add_argument("--time_per_url", type=int, default=120, help="Time limit (in seconds) for archiving one article")
    parser.add_argument("--collection_directory", default="/app2/ia-collection-2", help="Directory to collect warc files")
    parser.add_argument("--tmp_directory", default="/app2", help="Directory to temporarily collect warc files")
    parser.add_argument("--delete_warc",type=bool, default=True, help="Delete the warc file after uploading to internet archive")
    # parser.add_argument("--upload_warc",type=bool, default=True, help="Upload the warc file to internet archive")
    parser.add_argument("--start", type=int, default=0, help="Start index of states to process")
    parser.add_argument("--end", type=int, default=None, help="End index (exclusive) of states to process")
    parser.add_argument('--once_per_day', type=bool, default=True, help='Run only once per day for all states')
    parser.add_argument('--workers', type=int, default=3, help='Number of workers for crawling per run')
    # parser.add_argument("--upload_wacz", type=bool, default=True, help="Upload .wacz file to Internet Archive")
    # parser.add_argument("--delete_uploaded_warc", type=bool, default=False, help="Delete the .warc file after successful upload to Internet Archive")
    parser.add_argument("--rolloverSize", type=int, default=10000000000, help="Declare the rollover size")
    return parser.parse_args()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
}

# upload_queue = Queue()

# def upload_worker(worker_id: int): 
#     while True: 
#         job = upload_queue.get() 
#         if job is None: # poison pill to stop 
#             break 
#         file_path, file_name, item_identifier, args = job 
#         logging.info(f"[Worker {worker_id}] Uploading: {file_name}")
#         upload_single_file(file_path, file_name, item_identifier, args)
#         logging.info(f"[Worker {worker_id}] Successfully uploaded: {file_name}")
#         upload_queue.task_done()
#         logging.info(f"[Worker {worker_id}] Task done for: {file_name}")


def is_valid_url(url):
    """Check if URL is valid."""
    try:
        result = urlsplit(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        logging.warning(f"Invalid URL: {url}")
        return False


def normalize_rss_url(url):
    """Ensure RSS feed uses HTTPS and encode its query parameters."""
    parsed = urlparse(url)
    scheme = "https"
    encoded_query = urlencode(parse_qsl(parsed.query, keep_blank_values=True), doseq=True)
    return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, encoded_query, parsed.fragment)).replace("&", "&amp;")


def get_expanded_url(short_url):
    """Follow redirects to expand short URLs."""
    try:
        response = requests.head(short_url, allow_redirects=True, timeout=5)
        return response.url
    except requests.RequestException as e:
        logging.error(f"Error resolving URL: {short_url}: {e}")
        return short_url


def extract_article_urls_from_html(html_content, base_url):
    """Extract article URLs from HTML using BeautifulSoup."""
    soup = BeautifulSoup(html_content, 'html.parser')
    resolved_base = get_expanded_url(base_url)
    return {
        urljoin(resolved_base, link['href'])
        for link in soup.find_all("a", href=True)
    }


def rename_warc_filename(directory, archive_file_name):
    # Match pattern and replace the last underscore + number with 4-digit zero-padded version
    logging.info(f"started renaming {archive_file_name}...")
    match = re.match(r"^(.*_)(\d+)(\.warc\.gz)$", archive_file_name)
    if match:
        logging.info(f"Renaming matched for {archive_file_name}...")
        base, num, ext = match.groups()
        new_file_name = f"{base}{int(num):04}{ext}"

        source_dir = os.path.join(directory, archive_file_name)
        new_src_dir = os.path.join(directory, new_file_name)
        os.rename(source_dir, new_src_dir)
        logging.info(f"File: {archive_file_name}, renamed to: {new_file_name}")
        return new_file_name
    logging.warning(f"Renaming didn't match for {archive_file_name}...")
    return archive_file_name


# def upload_single_file(file_path, file_name, item_identifier, args):

#     if not args.upload_warc:
#         return

#     try:
#         logging.info(f'Uploading to Internet Archive: {item_identifier}/{file_name}')
#         upload(
#             item_identifier,
#             files={file_name: file_path},
#             metadata={
#                 'collection': args.collection,
#                 'uploader': args.uploader,
#                 'mediatype': args.mediatype
#             },
#             queue_derive=False,
#             retries=10,         
#             retries_sleep=60,   
#             verbose=True
#         )
#         logging.info(f'Successfully uploaded: {item_identifier}/{file_name}')

#         if args.delete_uploaded_warc:
#             if os.path.exists(file_path):
#                 os.remove(file_path)
#                 logging.info(f"Deleted uploaded file: {file_path}")
#             else:
#                 logging.info(f"Could not find file to delete after upload: {file_path}")

#     except Exception as e:
#         logging.error(f"Error uploading {file_name}: {e}")
#         subject = f"Upload Failed: {item_identifier}/{file_name}"
#         body = f"Failed to upload WARC file {file_name} to Internet Archive.\nException: {e}"
#         send_email(subject, body)

def create_directories(args, item_identifier):
    tmp_directory = os.path.abspath(args.tmp_directory)
    collection_directory = os.path.join(os.path.abspath(args.collection_directory), item_identifier)

    os.makedirs(tmp_directory, exist_ok=True)
    os.makedirs(collection_directory, exist_ok=True)

    logging.info(f"Created Directories:\n - TMP: {tmp_directory}\n - Collection: {collection_directory}")
    return collection_directory, tmp_directory


def write_seed_urls(seed_urls, tmp_directory, archive_file_name):
    logging.info(f"Start writing seed URLs")
    seed_file_path = os.path.join(tmp_directory, f"{archive_file_name}.txt")
    
    # Filter only valid HTTP/HTTPS URLs
    filtered_urls = [url for url in seed_urls if is_valid_url(url)]
    logging.info(f"Writing {len(filtered_urls)} valid URLs to: {seed_file_path}")

    with open(seed_file_path, "w") as f:
        for url in filtered_urls:
            f.write(f"{url}\n")
    
    logging.info(f"Seed file written with {len(filtered_urls)} URLs")
    return seed_file_path


def submit_crawl(archive_file_name, seed_file_path, args, retries=4):
    logging.info(f"Crawling with browsertrix for: {archive_file_name}")

    cmd = [
        "crawl",
        "--urlFile", str(seed_file_path),
        "--collection", archive_file_name,
        "--combineWARC",
        "--workers", str(args.workers),
        "--behaviorTimeout", "90",
        "--rolloverSize", str(args.rolloverSize),
        "--diskUtilization", "95",
        "--pageLoadTimeout", "90",
        "--netIdleWait", "2",
        "--logLevel", "error",
        "--headless", 
        "--scopeType", "page",
        "--blockads",
        "--timeLimit", "7200"
    ]

    attempt = 0
    while attempt <= retries:

        proc = subprocess.run(cmd)
        code = proc.returncode

        # --- success & expected stops ---
        if code == 0:
            logging.info(f"Crawling completed successfully with the cmd: {cmd}")
            return
        elif code == 14:
            logging.info("Crawling stopped due to WARC size limit reached.")
            return
        elif code == 15:
            logging.info(f"Crawling stopped due to time limit.")
            return
        elif code == 11:
            logging.info("Crawling stopped gracefully by SIGINT.")
            return
        elif code == 13:
            logging.info("Crawling stopped forcefully by SIGTERM or repeated SIGINT.")
            return

        # --- retryable errors ---
        elif code in [1, 9, 10, 21]:
            error_map = {
                1: "Generic error (check logs)",
                9: "Crawl failed unexpectedly",
                10: "Browser crashed",
                21: "Proxy error"
            }
            logging.warning(f"[WARNING] {error_map[code]} (exit {code}). Attempt {attempt+1}/{retries}.")
            if attempt < retries:
                time.sleep(5)
                attempt += 1
                continue
            else:
                subject = f"Crawl Failed: {archive_file_name} ({error_map[code]})"
                body = (
                    f"The Browsertrix crawl for '{archive_file_name}' failed repeatedly.\n\n"
                    f"Exit Code: {code}\n"
                    f"Seed File: {seed_file_path}\n"
                    f"Command Run: {' '.join(cmd)}\n\n"
                    f"Please check logs for more details."
                )
                send_email(subject, body)
                raise subprocess.CalledProcessError(code, cmd)

        # --- fatal errors ---
        elif code in [3, 12, 16, 17]:
            fatal_map = {
                3: "Out of disk space",
                12: "Too many failed pages (failed limit reached)",
                16: "Disk utilization limit reached",
                17: "Fatal non-retryable error"
            }
            logging.error(f"[ERROR] {fatal_map[code]} (exit {code}).")
            subject = f"Crawl Failed: {archive_file_name} ({fatal_map[code]})"
            body = (
                f"The Browsertrix crawl for '{archive_file_name}' failed with a fatal error.\n\n"
                f"Exit Code: {code}\n"
                f"Reason: {fatal_map[code]}\n"
                f"Seed File: {seed_file_path}\n"
                f"Command Run: {' '.join(cmd)}\n\n"
                f"Please check logs and fix the issue before retrying."
            )
            send_email(subject, body)
            raise subprocess.CalledProcessError(code, cmd)

        # --- unknown codes ---
        else:
            logging.error(f"[ERROR] Crawling failed with unexpected exit code {code}.")
            subject = f"Crawl Failed: {archive_file_name} (Exit Code {code})"
            body = (
                f"The Browsertrix crawl for '{archive_file_name}' failed with an unknown exit code.\n\n"
                f"Exit Code: {code}\n"
                f"Seed File: {seed_file_path}\n"
                f"Command Run: {' '.join(cmd)}\n\n"
                f"Please check logs for more details."
            )
            send_email(subject, body)
            raise subprocess.CalledProcessError(code, cmd)

def move_warc(directory, archive_file_name, tmp_directory):
    """Move generated WARC.GZ files to final collection directory."""
    try:
        logging.info(f"Started moving WARC.GZ files for {archive_file_name}")
        os.makedirs(directory, exist_ok=True)
        source_dir = os.path.join(tmp_directory, 'collections', archive_file_name)
        if not os.path.exists(source_dir):
            logging.info(f"Source directory not found: {source_dir}")
            return

        for file_name in os.listdir(source_dir):
            if file_name.endswith(".warc.gz"):
                src_file = os.path.join(source_dir, file_name)
                shutil.move(src_file, directory)
                logging.info(f"Moved: {file_name} to {directory}")
    except Exception as e:
        logging.error(f"Error moving WARC.GZ files for {archive_file_name}: {e}")
        subject = f"Move Failed: {archive_file_name}"
        body = f"Failed to move WARC.GZ files to collection directory.\nException: {e}"
        send_email(subject, body)

# def launch_upload_thread(directory, archive_file_name, item_identifier, args):
#     warc_files = [
#             file_name for file_name in os.listdir(directory)
#             if file_name.endswith(".warc.gz")
#         ]

#     for file_name in warc_files:
#         file_name = rename_warc_filename(directory, file_name)
#         file_path = os.path.join(directory, file_name)    
#         logging.info(f"Queueing upload job for: {file_path}")
#         upload_queue.put((file_path, file_name, item_identifier, args))


def delete_warc_dir(archive_file_name, tmp_directory, args):
    """Delete temporary WARC.GZ directory, seed file, if enabled."""
    if not args.delete_warc:
        return

    try:
        dir_path = os.path.join(tmp_directory, 'collections', archive_file_name)
        txt_file_path = os.path.join(tmp_directory, f"{archive_file_name}.txt")

        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            logging.info(f"Deleted directory: {dir_path}")
        else:
            logging.info(f"Directory not found: {dir_path}")

        if os.path.exists(txt_file_path):
            os.remove(txt_file_path)
            logging.info(f"Deleted file: {txt_file_path}")
        else:
            logging.info(f"File not found: {txt_file_path}")

    except Exception as e:
        logging.error(f"Cleanup failed for {archive_file_name}: {e}")
        subject = f"Cleanup Failed: {archive_file_name}"
        body = f"Failed to delete temporary WARC directory or seed file.\nException: {e}"
        send_email(subject, body)


def seconds_until_next_utc_midnight():
    now = datetime.now(timezone.utc)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (next_midnight - now).total_seconds()


def process_publication(publication, sniffer, args):
    """Process a single publication by gathering articles and archiving them."""
    website_url = publication.get("website")
    seed_urls = []

    # First try to get articles from RSS feeds
    for rss_feed_url in publication.get("rss", []):
        feed = feedparser.parse(normalize_rss_url(rss_feed_url))
        for entry in feed.entries:
            article_url = entry.link
            if article_url and sniffer.guess(article_url):
                seed_urls.append(article_url)
                if len(seed_urls) >= args.max_articles:
                    break
        if len(seed_urls) >= args.max_articles:
            break

    # If not enough from RSS, fallback to scraping the website
    if len(seed_urls) < args.max_articles:
        try:
            response = requests.get(website_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            for article_url in extract_article_urls_from_html(response.text, website_url):
                if article_url and sniffer.guess(article_url):
                    seed_urls.append(article_url)
                    if len(seed_urls) >= args.max_articles:
                        break
        except requests.RequestException as e:
            logging.debug(f"Failed to scrape {website_url}: {e}")

    if seed_urls:
        seed_urls.append(website_url)
        return seed_urls
        
    else:
        logging.debug(f"No valid URLs for {website_url}")


# def archive(seed_urls, archive_file_name, item_identifier, uploader, args):
def archive(seed_urls, archive_file_name, item_identifier, args):

    """Run Browsertrix Crawler as a Kubernetes Job to archive seed URLs."""
    logging.info(f"--- Starting archive job for: {archive_file_name} ---")
    
    try:
        # 1. Create directories
        collection_dir, tmp_dir = create_directories(args, item_identifier)
        
        # 2. Write seed URLs
        seed_file_path = write_seed_urls(seed_urls, tmp_dir, archive_file_name)
        
        # 3. Run Browsertrix crawl
        submit_crawl(archive_file_name, seed_file_path, args)
        
        # 4. Move WARC files to collection directory
        move_warc(collection_dir, archive_file_name, tmp_dir)
        
        # # 5. Queue files for upload
        # upload_directory(collection_dir, item_identifier, args, uploader)
        
        # 6. Clean up temporary WARC directory & seed file
        delete_warc_dir(archive_file_name, tmp_dir, args)

        logging.info(f"--- Archive job completed for: {archive_file_name} ---\n")
    except subprocess.CalledProcessError as e:
        logging.error(f"[ERROR] Subprocess failed: {e}")
        return 0, 0

# def start_validator_in_background():
#     validator = UploadValidator()
#     process = Process(target=validator.run_once)
#     process.start()
#     logging.info(f"[Main] UploadValidator running in background (PID={process.pid})")

def main():
    args = get_arguments()

    # Setup logger
    setup_logger(args)
    cleanup_old_logs(args.log, days=2)

    sniffer = StorySniffer()
    last_run_date = None

    # uploader = IAUploader(max_workers=5)
    # uploader.start_workers()

    while True:
        try:
            current_date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

            # start_validator_in_background()

            if args.once_per_day and current_date_str == last_run_date:
                sleep_secs = seconds_until_next_utc_midnight()
                logging.info(f"Already ran today. Sleeping until next UTC midnight ({sleep_secs:.0f} sec)...")
                time.sleep(sleep_secs)
                continue

            with open(args.input, "r") as f:
                data = json.load(f)

            states = list(data.keys())
            start = args.start
            end = args.end if args.end is not None else len(states)
            logging.info(f"Start is: {start}, end is: {end}")
            selected_states = states[start:end]
            logging.info(f"Selected states {len(selected_states)} are: {selected_states}")

            timestamp = datetime.now(timezone.utc)
            item_identifier = f"{args.item_identifier}-{timestamp.strftime('%Y%m%d')}"

            for state in selected_states:
                logging.info(f"Processing state: {state}")

                seed_urls = []
                timestamp_state = datetime.now(timezone.utc)
                if timestamp.strftime('%Y%m%d') != timestamp_state.strftime('%Y%m%d'):
                    break

                archive_file_name = f"{args.item_identifier}-{state}-{timestamp.strftime('%Y%m%d')}-{timestamp.strftime('%H%M%S')}"

                publications = data[state]

                all_publications = []
                for news_media in ['newspaper', 'tv', 'radio', 'broadcast']:
                    all_publications.extend([
                        pub for pub in publications.get(news_media, [])
                        if pub.get("website_status_code") in range(200, 400)
                    ])

                # Run them all in parallel with one global tqdm bar
                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    futures = [executor.submit(process_publication, pub, sniffer, args) for pub in all_publications]

                    for future in tqdm(concurrent.futures.as_completed(futures),
                                    total=len(futures),
                                    desc="Processing all publications"):
                        try:
                            publication_urls = future.result()
                            if publication_urls:
                                seed_urls.extend(publication_urls)
                        except Exception as e:
                            logging.error(f"Error processing publication in parallel: {e}")

                if seed_urls:
                    # archive(seed_urls, archive_file_name, item_identifier, uploader, args)
                    archive(seed_urls, archive_file_name, item_identifier, args)

                else:
                    logging.error(f"No seed URLs collected for state: {state}. Skipping archive.")

            last_run_date = current_date_str

        except Exception as e:
            logging.error(f"Fatal error: {e}")
            subject = "News Archival Script Fatal Error"
            body = f"The main archival script crashed.\nException: {e}"
            send_email(subject, body)
if __name__ == "__main__":
    main()
