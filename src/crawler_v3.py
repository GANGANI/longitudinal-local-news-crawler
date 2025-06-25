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
    """Configure logging to output to both file and console."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def get_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="News Archival Script")
    parser.add_argument("--input", default="output.json", help="Path to JSON input file")
    parser.add_argument("--sleep", type=int, default=3600, help="Time between iterations (in seconds)")
    parser.add_argument("--max_articles", type=int, default=5, help="Maximum number of articles to scrape per publication")
    parser.add_argument("--log", default="news_scraper.log", help="Path to log file")
    parser.add_argument("--log_level", default="CRITICAL", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    parser.add_argument("--mediatype", default="web", help="Media type for Internet Archive upload")
    parser.add_argument("--collection", default="USLNDA", help="Collection name / directory prefix")
    parser.add_argument("--uploader", default="Alexander C. Nwala <alexandernwala@gmail.com>", help="Uploader identity")
    parser.add_argument("--time_limit", type=int, default=360, help="Time limit (in seconds) for archiving subprocess")
    parser.add_argument("--collection_directory", default="collection", help="Directory to collect warcz files")
    parser.add_argument("--tmp_directory", default="tmp", help="Directory to temporarily collect warcz files")
    parser.add_argument("--delete_warc",type=bool, default=False, help="Delete the warc file after uploading to internet archive")
    parser.add_argument("--upload_warc",type=bool, default=False, help="Upload the warc file to internet archive")
    parser.add_argument("--start", type=int, default=0, help="Start index of states to process")
    parser.add_argument("--end", type=int, default=None, help="End index (exclusive) of states to process")
    
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


def move_wacz(directory, archive_file_name, tmp_directory):
    """Move generated WACZ file to final collection directory."""
    try:
        logging.info(f"Started moving warcz file {archive_file_name}")
        os.makedirs(directory, exist_ok=True)
        wacz_file = os.path.join(tmp_directory, 'collections', archive_file_name, f"{archive_file_name}.warc.gz")
        if os.path.exists(wacz_file):
            shutil.move(wacz_file, directory)
            logging.info(f"Moved WACZ to: {directory}")
        else:
            logging.warning(f"WACZ file not found: {wacz_file}")
    except Exception as e:
        logging.error(f"Error moving WACZ file: {e}")


def upload_wacz(directory, archive_file_name, item_identifier, args):
    """Upload WACZ file to Internet Archive if enabled."""
    if not args.upload_warc:
        return

    try:
        src_file = os.path.join(directory, f"{archive_file_name}.warc.gz")
        upload_dest_file = f"./{archive_file_name}.warc.gz"
        logging.info(f'Uploading to Internet Archive: {item_identifier}/{upload_dest_file}')
        upload(
            item_identifier,
            files={upload_dest_file: src_file},
            metadata={
                'collection': args.collection,
                'uploader': args.uploader,
                'mediatype': args.mediatype
            }
        )
        logging.info(f'Successfully uploaded: {item_identifier}/{upload_dest_file}')
    except Exception as e:
        logging.error(f"Error Uploading {item_identifier}/{upload_dest_file}: {e}")


def delete_warc_dir(archive_file_name, tmp_directory, args):
    """Delete temporary WARC file and its directory if enabled."""
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


def archive(seed_urls, archive_file_name, item_identifier, args):
    """Run Browsertrix Crawler inside Docker to archive seed URLs."""
    try:
        directory = os.path.join(args.collection_directory, item_identifier)
        tmp_directory = args.tmp_directory
        os.makedirs(tmp_directory, exist_ok=True)
        seed_file_path = os.path.join(tmp_directory, f"{archive_file_name}.txt")

        with open(seed_file_path, "w") as f:
            for url in seed_urls:
                f.write(f"{url}\n")

        command = (
            f"docker run -v {os.path.abspath(tmp_directory)}:/crawls/ "
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
        move_wacz(directory, archive_file_name, tmp_directory)
        upload_wacz(directory, archive_file_name, item_identifier, args)
        delete_warc_dir(archive_file_name, tmp_directory, args)
    except subprocess.SubprocessError as e:
        logging.error(f"Archiving subprocess failed: {e}")


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


def main():
    args = get_arguments()
    setup_logger(args.log, args.log_level)
    sniffer = StorySniffer()

    logging.info("Starting news archiving process...")

    while True:
        try:
            with open(args.input, "r") as f:
                data = json.load(f)

            states = list(data.keys())
            start = args.start
            end = args.end if args.end is not None else len(states)
            selected_states = states[start:end]

            for state in selected_states:
                logging.info(f"Processing state: {state}")

                seed_urls = []
                timestamp = datetime.datetime.now(datetime.timezone.utc)
                item_identifier = f"{args.collection}-{timestamp.strftime('%Y%m')}"
                archive_file_name = f"{args.collection}-{state}-{timestamp.strftime('%Y%m')}-{timestamp.strftime('%H%M%S')}"


                publications = data[state]
                for news_media in ['newspaper', 'tv', 'radio', 'broadcast']:
                    for publication in publications.get(news_media, []):
                        if publication.get("website_status_code") in range(200, 400):                            
                            publication_urls = process_publication(publication, sniffer, args)
                            seed_urls.extend(publication_urls)
                archive(seed_urls, archive_file_name, item_identifier, args)

        except Exception as e:
            logging.error(f"Fatal error: {e}")

        logging.info(f"Sleeping for {args.sleep} seconds before next iteration...")
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()