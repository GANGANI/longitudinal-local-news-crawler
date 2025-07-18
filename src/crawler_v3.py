import argparse
import logging
import json
import os
import shutil
import feedparser
import datetime
import requests
import subprocess
import time
import internetarchive
import concurrent.futures
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote, urlsplit, urlunparse, quote, parse_qsl, urlencode
from storysniffer import StorySniffer
from internetarchive import upload
from threading import Thread

def setup_logger(log_file, log_level):
    """Configure logging to output to both file and console."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

# Global upload thread pool
UPLOAD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=5)


def get_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="News Archival Script")
    parser.add_argument("--input", default="output.json", help="Path to JSON input file")
    parser.add_argument("--sleep", type=int, default=3600, help="Time between iterations (in seconds)")
    parser.add_argument("--max_articles", type=int, default=5, help="Maximum number of articles to scrape per publication")
    parser.add_argument("--log", default="news_scraper.log", help="Path to log file")
    parser.add_argument("--log_level", default="CRITICAL", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    parser.add_argument("--mediatype", default="web", help="Media type for Internet Archive upload")
    parser.add_argument("--collection", default="us-local-news-data", help="Collection name of the internet archive")
    parser.add_argument("--item_identifier", default="USLNDA", help="Prefix of the item identifier")
    parser.add_argument("--uploader", default="Alexander C. Nwala <alexandernwala@gmail.com>", help="Uploader identity")
    parser.add_argument("--time_limit", type=int, help="Time limit (in seconds) for archiving subprocess")
    parser.add_argument("--time_per_url", type=int, default=60, help="Time limit (in seconds) for archiving one article")
    parser.add_argument("--collection_directory", default="collection", help="Directory to collect warc files")
    parser.add_argument("--tmp_directory", default="tmp", help="Directory to temporarily collect warc files")
    parser.add_argument("--delete_warc",type=bool, default=True, help="Delete the warc file after uploading to internet archive")
    parser.add_argument("--upload_warc",type=bool, default=True, help="Upload the warc file to internet archive")
    parser.add_argument("--start", type=int, default=0, help="Start index of states to process")
    parser.add_argument("--end", type=int, default=None, help="End index (exclusive) of states to process")
    parser.add_argument('--once_per_day', type=bool, default=True, help='Run only once per day for all states')
    parser.add_argument('--workers', type=int, default=10, help='Number of workers for crawling per run')
    parser.add_argument("--delete_uploaded_warc", type=bool, default=True, help="Delete the .warc file after successful upload to Internet Archive")
    parser.add_argument("--rolloverSize", type=int, default=10000000000, help="Declare the rollover size")
    return parser.parse_args()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
}


def is_valid_url(url):
    """Check if URL is valid."""
    try:
        result = urlsplit(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        logging.error(f"Invalid URL: {url}")
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


def move_warc(directory, archive_file_name, tmp_directory):
    """Move generated WARC.GZ files to final collection directory."""
    try:
        logging.info(f"Started moving WARC.GZ files for {archive_file_name}")
        os.makedirs(directory, exist_ok=True)
        source_dir = os.path.join(tmp_directory, 'collections', archive_file_name)
        if not os.path.exists(source_dir):
            logging.warning(f"Source directory not found: {source_dir}")
            return

        for file_name in os.listdir(source_dir):
            if file_name.endswith(".warc.gz"):
                src_file = os.path.join(source_dir, file_name)
                shutil.move(src_file, directory)
                logging.info(f"Moved: {file_name} to {directory}")
    except Exception as e:
        logging.error(f"Error moving WARC.GZ files for {archive_file_name}: {e}")


# def upload_warc(directory, archive_file_name, item_identifier, args):
#     """Upload all WARC.GZ files to Internet Archive if enabled."""
#     if not args.upload_warc:
#         return

#     try:
#         for file_name in os.listdir(directory):
#             if file_name.endswith(".warc.gz"):
#                 src_file = os.path.join(directory, file_name)
#                 logging.info(f'Uploading to Internet Archive: {item_identifier}/{file_name}')
#                 upload(
#                     item_identifier,
#                     files={file_name: src_file},
#                     metadata={
#                         'collection': args.collection,
#                         'uploader': args.uploader,
#                         'mediatype': args.mediatype
#                     },
#                     queue_derive=False,
#                     verbose=True
#                 )
#                 logging.info(f'Successfully uploaded: {item_identifier}/{file_name}')

#                 if args.delete_uploaded_warc:
#                     if os.path.exists(src_file):
#                         os.remove(src_file)
#                         logging.info(f"Deleted uploaded file: {src_file}")
#                     else:
#                         logging.warning(f"Could not find file to delete after upload: {src_file}")

#     except Exception as e:
#         logging.error(f"Error uploading WARC.GZ files for {archive_file_name}: {e}")

import concurrent.futures

def upload_warc(directory, archive_file_name, item_identifier, args):
    """Upload all WARC.GZ files in parallel to Internet Archive if enabled."""
    if not args.upload_warc:
        return

    def upload_single_file(file_path, file_name):
        try:
            logging.info(f'Uploading to Internet Archive: {item_identifier}/{file_name}')
            upload(
                item_identifier,
                files={file_name: file_path},
                metadata={
                    'collection': args.collection,
                    'uploader': args.uploader,
                    'mediatype': args.mediatype
                },
                queue_derive=False,
                verbose=True
            )
            logging.info(f'Successfully uploaded: {item_identifier}/{file_name}')

            if args.delete_uploaded_warc:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Deleted uploaded file: {file_path}")
                else:
                    logging.warning(f"Could not find file to delete after upload: {file_path}")

        except Exception as e:
            logging.error(f"Error uploading {file_name}: {e}")

    try:
        warc_files = [
            file_name for file_name in os.listdir(directory)
            if file_name.endswith(".warc.gz")
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for file_name in warc_files:
                file_path = os.path.join(directory, file_name)
                futures.append(executor.submit(upload_single_file, file_path, file_name))

            # Optionally: Wait for all uploads to finish before returning
            concurrent.futures.wait(futures)

    except Exception as e:
        logging.error(f"Error scheduling WARC.GZ uploads for {archive_file_name}: {e}")


def upload_wacz(directory, archive_file_name, item_identifier, args):
    """Schedule upload of WACZ file to Internet Archive in background."""

    if not args.upload_wacz:
        return

    def _upload_task():
        try:
            src_file = os.path.join(directory, f"{archive_file_name}.wacz")
            upload_dest_file = f"{archive_file_name}.wacz"
            logging.info(f'Uploading to Internet Archive: {item_identifier}/{upload_dest_file}')
            r = upload(
                item_identifier,
                files={upload_dest_file: src_file},
                metadata={
                    'collection': args.collection,
                    'uploader': args.uploader,
                    'mediatype': args.mediatype
                },
                queue_derive=False,
                verbose=True
            )
            logging.info(f'Successfully uploaded: {item_identifier}/{upload_dest_file}')

            if args.delete_uploaded_wacz:
                if os.path.exists(src_file):
                    os.remove(src_file)
                    logging.info(f"Deleted uploaded .wacz file: {src_file}")
                else:
                    logging.warning(f"Could not find .wacz file to delete after upload: {src_file}")
        except Exception as e:
            logging.error(f"Error uploading {archive_file_name}: {e}")

    # Submit to global background thread pool
    UPLOAD_EXECUTOR.submit(_upload_task)



def delete_warc_dir(archive_file_name, tmp_directory, args):
    """Delete temporary WARC.GZ directory and its related files if enabled."""
    if not args.delete_warc:
        return
    
    try:
        dir_path = os.path.join(tmp_directory, 'collections', archive_file_name)
        txt_file_path = os.path.join(tmp_directory, f"{archive_file_name}.txt")

        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            logging.info(f"Deleted directory: {dir_path}")
        else:
            logging.warning(f"Directory not found: {dir_path}")

        if os.path.exists(txt_file_path):
            os.remove(txt_file_path)
            logging.info(f"Deleted file: {txt_file_path}")
        else:
            logging.warning(f"File not found: {txt_file_path}")

    except Exception as e:
        logging.error(f"Cleanup failed for {archive_file_name}: {e}")


def archive(seed_urls, archive_file_name, item_identifier, num_seed_urls, args, background_uploads):
    """Run Browsertrix Crawler inside Docker to archive seed URLs."""
    try:
        directory = os.path.join(args.collection_directory, item_identifier)
        tmp_directory = args.tmp_directory
        os.makedirs(tmp_directory, exist_ok=True)
        os.makedirs(directory, exist_ok=True)
        seed_file_path = os.path.join(tmp_directory, f"{archive_file_name}.txt")

        with open(seed_file_path, "w") as f:
            for url in seed_urls:
                f.write(f"{url}\n")

        if args.time_limit:
            timelimit = args.time_limit
        else:
            timelimit = (args.time_per_url * num_seed_urls) / (args.workers)
        
        logging.info(f"Timelimit for: {archive_file_name} is {timelimit}")

        command = (
            f"docker run --rm -v {os.path.abspath(tmp_directory)}:/crawls/ "
            f"-it webrecorder/browsertrix-crawler "
            f"crawl --urlFile /crawls/{archive_file_name}.txt"
            f" --collection {archive_file_name} --timeLimit {timelimit} --combineWARC --workers {args.workers} --rolloverSize {args.rolloverSize}"
        )

        logging.info(f"Running archive subprocess: {command}")

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        for line in process.stdout:
            logging.info(line.strip())
        for line in process.stderr:
            logging.error(line.strip())

        process.wait()

        move_warc(directory, archive_file_name, tmp_directory)

        # Launch upload in background
        upload_thread = Thread(target=upload_warc, args=(directory, archive_file_name, item_identifier, args))
        upload_thread.start()
        background_uploads.append(upload_thread)

        delete_warc_dir(archive_file_name, tmp_directory, args)

        # Clean up any stopped containers left over
        cleanup_cmd = "docker container prune -f"
        try:
            subprocess.run(cleanup_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.info("Cleaned up stopped Docker containers.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to prune Docker containers: {e}")

    except subprocess.SubprocessError as e:
        logging.error(f"Archiving subprocess failed: {e}")
        return 0, 0


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
                logging.info(f"RSS article found: {article_url}")
                if len(seed_urls) >= args.max_articles:
                    break
                time.sleep(5)
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
                    logging.info(f"Scraped article: {article_url}")
                    if len(seed_urls) >= args.max_articles:
                        break
                    time.sleep(5)
        except requests.RequestException as e:
            logging.error(f"Failed to scrape {website_url}: {e}")

    if seed_urls:
        seed_urls.append(website_url)
        return seed_urls
        
    else:
        logging.warning(f"No valid URLs for {website_url}")


def seconds_until_next_utc_midnight():
    now = datetime.datetime.utcnow()
    next_midnight = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (next_midnight - now).total_seconds()


def main():
    args = get_arguments()
    setup_logger(args.log, args.log_level)
    sniffer = StorySniffer()

    logging.info("Starting news archiving process...")

    timing_log_file = "timing_log.txt"
    last_run_date = None

    while True:
        background_uploads = []
        try:

            current_date_str = datetime.datetime.utcnow().strftime('%Y-%m-%d')

            if args.once_per_day and current_date_str == last_run_date:
                # Already ran today; sleep until next midnight UTC
                sleep_secs = seconds_until_next_utc_midnight()
                logging.info(f"Already ran today. Sleeping until next UTC midnight ({sleep_secs:.0f} sec)...")
                time.sleep(sleep_secs)
                continue

            with open(args.input, "r") as f:
                data = json.load(f)

            states = list(data.keys())
            start = args.start
            end = args.end if args.end is not None else len(states)
            selected_states = states[start:end]

            timestamp = datetime.datetime.now(datetime.timezone.utc)
            item_identifier = f"{args.item_identifier}-{timestamp.strftime('%Y%m%d')}"

            for state in selected_states:
                logging.info(f"Processing state: {state}")

                seed_urls = []
                timestamp_state = datetime.datetime.now(datetime.timezone.utc)
                if timestamp.strftime('%Y%m%d') != timestamp_state.strftime('%Y%m%d'):
                    break

                archive_file_name = f"{args.item_identifier}-{state}-{timestamp.strftime('%Y%m%d')}-{timestamp.strftime('%H%M%S')}"

                publications = data[state]

                seed_start_time = time.time()

                for news_media in ['newspaper', 'tv', 'radio', 'broadcast']:
                    publications_list = [
                        pub for pub in publications.get(news_media, [])
                        if pub.get("website_status_code") in range(200, 400)
                    ]

                    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                        futures = [executor.submit(process_publication, pub, sniffer, args) for pub in publications_list]
                        for future in concurrent.futures.as_completed(futures):
                            try:
                                publication_urls = future.result()
                                if publication_urls:
                                    seed_urls.extend(publication_urls)
                            except Exception as e:
                                logging.error(f"Error processing publication in parallel: {e}")

                seed_end_time = time.time()
                seed_duration = seed_end_time - seed_start_time

                if seed_urls:
                    archive(seed_urls, archive_file_name, item_identifier, len(seed_urls), args, background_uploads)
                else:
                    logging.warning(f"No seed URLs collected for state: {state}. Skipping archive.")

                # Log the timings to a file
                with open(timing_log_file, "a") as logf:
                        logf.write(f"{state}: Seeds: {len(seed_urls)}, Seed collection: {seed_duration:.2f}\n")

            # Wait for all uploads to finish before sleeping
            for t in background_uploads:
                logging.info("Waiting for background upload to finish...")
                t.join()
                logging.info("Upload completed.")

            s = internetarchive.get_session()
            s.submit_tasks(item_identifier, cmd='derive.php')

            last_run_date = current_date_str

            if args.once_per_day:
                sleep_secs = seconds_until_next_utc_midnight()
                logging.info(f"Daily run completed. Sleeping until next UTC midnight ({sleep_secs:.0f} sec)...")
                time.sleep(sleep_secs)

        except Exception as e:
            logging.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()