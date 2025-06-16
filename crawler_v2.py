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
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote, urlsplit, urlunparse, quote, parse_qsl, urlencode
from storysniffer import StorySniffer
from internetarchive import upload

def setup_logger(log_file, log_level):
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def get_arguments():
    parser = argparse.ArgumentParser(description="News Archival Script")
    parser.add_argument("--input", default="output.json", help="Path to JSON input file")
    parser.add_argument("--sleep", type=int, default=3600, help="Time between iterations (in seconds)")
    parser.add_argument("--max_articles", type=int, default=5, help="Maximum number of articles to scrape per publication")
    parser.add_argument("--log", default="news_scraper.log", help="Path to log file")
    parser.add_argument("--log_level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    parser.add_argument("--upload_identifier", default="us-local-news-data-va-2025-06", help="Internet Archive identifier")
    parser.add_argument("--mediatype", default="web", help="Media type for Internet Archive upload")
    parser.add_argument("--collection", default="us-local-news-data", help="Collection name / directory prefix")
    parser.add_argument("--uploader", default="Alexander C. Nwala <alexandernwala@gmail.com>", help="Uploader identity")
    parser.add_argument("--time_limit", type=int, default=360, help="Time limit (in seconds) for archiving subprocess")
    return parser.parse_args()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36'
}


def is_valid_url(url):
    try:
        result = urlsplit(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        logging.error(f"Invalid URL: {url}")
        return False


def normalize_rss_url(url):
    parsed = urlparse(url)
    scheme = "https"
    encoded_query = urlencode(parse_qsl(parsed.query, keep_blank_values=True), doseq=True)
    return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, encoded_query, parsed.fragment)).replace("&", "&amp;")


def get_expanded_url(short_url):
    try:
        response = requests.head(short_url, allow_redirects=True, timeout=5)
        return response.url
    except requests.RequestException as e:
        logging.error(f"Error resolving URL: {short_url}: {e}")
        return short_url


def extract_article_urls_from_html(html_content, base_url):
    soup = BeautifulSoup(html_content, 'html.parser')
    resolved_base = get_expanded_url(base_url)
    return {
        urljoin(resolved_base, link['href'])
        for link in soup.find_all("a", href=True)
    }

# Update archive function to take args
def archive(seed_urls, archive_file_name, directory, args):
    try:
        os.makedirs(directory, exist_ok=True)
        seed_file_path = os.path.join(directory, f"{archive_file_name}.txt")

        with open(seed_file_path, "w") as f:
            for url in seed_urls:
                f.write(f"{url}\n")

        command = (
            f"docker run -v {os.path.abspath(directory)}:/crawls/ "
            f"-it webrecorder/browsertrix-crawler "
            f"crawl --urlFile /crawls/{archive_file_name}.txt --generateWACZ "
            f"--collection {archive_file_name} --timeLimit {args.time_limit}"
        )

        logging.info(f"Running archive subprocess: {command}")
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        for line in process.stdout:
            logging.info(line.strip())
        for line in process.stderr:
            logging.error(line.strip())

        process.wait()

    except subprocess.SubprocessError as e:
        logging.error(f"Archiving subprocess failed: {e}")


# Update upload_wacz to take args
def upload_wacz(dst_file, args):
    try:
        logging.info(f'Uploading to Internet Archive: {dst_file}')
        upload(
            args.upload_identifier,
            files=[dst_file],
            metadata={
                'collection': args.collection,
                'uploader': args.uploader,
                'mediatype': args.mediatype
            }
        )
        logging.info(f'Successfully uploaded: {args.upload_identifier}/{dst_file}')
    except Exception as e:
        logging.error(f"Error Uploading {dst_file}: {e}")


def move_wacz(dest_dir, archive_file_name):
    try:
        os.makedirs(dest_dir, exist_ok=True)
        wacz_file = os.path.join('collections', archive_file_name, f"{archive_file_name}.wacz")
        dest_path = os.path.join(dest_dir, f"{archive_file_name}.wacz")
        if os.path.exists(wacz_file):
            shutil.move(wacz_file, dest_path)
            logging.info(f"Moved WACZ to: {dest_path}")
        else:
            logging.warning(f"WACZ file not found: {wacz_file}")
    except Exception as e:
        logging.error(f"Error moving WACZ file: {e}")


def delete_warc_dir(archive_file_name, directory):
    try:
        dir_path = os.path.join(directory, 'collections', archive_file_name)
        txt_file_path = os.path.join(directory, f"{archive_file_name}.txt")

        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            logging.info(f"Deleted: {dir_path}")
        if os.path.exists(txt_file_path):
            os.remove(txt_file_path)
            logging.info(f"Deleted: {txt_file_path}")

    except Exception as e:
        logging.error(f"Cleanup failed for {archive_file_name}: {e}")


def process_publication(state, publication, timestamp, args, sniffer):
    year, month, day = timestamp.year, timestamp.month, timestamp.day
    website_url = publication.get("website")
    hostname = urlparse(website_url).hostname

    tmp_directory = "tmp"
    directory = os.path.join(f"{args.collection}-{state}-{year}-{month}", str(day), hostname)
    archive_file_name = f"{hostname}-{timestamp.strftime('%Y%m%dT%H%M%S')}"

    seed_urls = []

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
        archive(seed_urls, archive_file_name, tmp_directory, args)
        move_wacz(directory, archive_file_name)
        upload_wacz(os.path.join(directory, f"{archive_file_name}.wacz"), args)
        delete_warc_dir(archive_file_name, tmp_directory)
    else:
        logging.warning(f"No valid URLs for {website_url}")


def main():
    args = get_arguments()
    setup_logger(args.log, args.log_level)
    sniffer = StorySniffer()

    logging.info("Starting news archiving process...")

    while True:
        try:
            with open(args.input, "r") as f:
                data = json.load(f)

            for state, publications in data.items():
                logging.info(f"Processing state: {state}")
                for news_media in ['newspaper', 'tv', 'radio', 'broadcast']:
                    for publication in publications.get(news_media, []):
                        if publication.get("website_status_code") in range(200, 300):
                            timestamp = datetime.datetime.now(datetime.timezone.utc)
                            process_publication(state, publication, timestamp, args, sniffer)

        except Exception as e:
            logging.error(f"Fatal error: {e}")

        logging.info(f"Sleeping for {args.sleep} seconds before next iteration...")
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()