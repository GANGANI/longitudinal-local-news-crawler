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
from urllib.parse import urljoin, urlparse, unquote, urlsplit
from storysniffer import StorySniffer
from urllib.parse import urlparse, urlunparse, quote, parse_qsl, urlencode

logging.basicConfig(
    level=logging.INFO,  
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("news_scraper.log"),  
        logging.StreamHandler()  
    ]
)

logging.info("Starting the script...")

sniffer = StorySniffer()

logging.info("Loading input data from output.json...")
with open("output.json", "r") as f:
    data = json.load(f)
logging.info("Loaded input data successfully.")

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
    normalized_url = urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, encoded_query, parsed.fragment))
    return normalized_url.replace("&", "&amp;")

def extract_domain(url):
    parsed_url = urlparse(unquote(url))
    domain = parsed_url.netloc.split('&')[0].split('?')[0]
    return domain[4:] if domain.startswith("www.") else domain


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

def archive(seed_urls, archive_file_name, directory, tmp_directory):
    try:
        os.makedirs(tmp_directory, exist_ok=True)

        seed_file_path = os.path.join(tmp_directory, f"{archive_file_name}.txt")
        with open(seed_file_path, "w") as f:
            for url in seed_urls:
                f.write(f"{url}\n")

        command = (
            f"docker run -v {os.path.abspath(tmp_directory)}:/crawls/ "
            f"-it webrecorder/browsertrix-crawler "
            f"crawl --urlFile /crawls/{archive_file_name}.txt --generateWACZ "
            f"--collection {archive_file_name} --timeLimit 360"
        )

        logging.info(f"Starting subprocess: {command} with live logging...")

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        for line in process.stdout:
            print(line, end="")

        for line in process.stderr:
            print(line, end="")

        process.wait()
        move_wacz(directory, archive_file_name, tmp_directory)
        delete_warc_dir(archive_file_name, tmp_directory)
    except subprocess.SubprocessError as e:
        logging.error(f"Exception during archiving: {e}")

def move_wacz(dest_dir, archive_file_name, tmp_directory):
    """
    Move the .wacz file from src_dir to dest_dir.
    """
    try:
        logging.info(f"Started moving warcz file {archive_file_name}")
        os.makedirs(dest_dir, exist_ok=True)
        wacz_file = os.path.join(tmp_directory, 'collections', archive_file_name, f"{archive_file_name}.wacz")
        dest_path = os.path.join(dest_dir, f"{archive_file_name}.wacz")
        if os.path.exists(wacz_file):
            shutil.move(wacz_file, dest_path)
            logging.info(f"Moved {wacz_file} to {dest_path}")
        else:
            logging.warning(f"WACZ file not found: {wacz_file}")
    except Exception as e:
        logging.error(f"Error moving WACZ file: {e}")


def delete_warc_dir(archive_file_name, directory):
    """
    Delete a directory and all its contents and a corresponding .txt file.
    """
    try:
        logging.info(f"Started deleting warcz directory {archive_file_name}")
        dir_path = os.path.join(directory, 'collections', archive_file_name)
        txt_file_path = os.path.join(directory, f"{archive_file_name}.txt")

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
        logging.error(f"Error during cleanup for {archive_file_name}: {e}")

def process_publication(state, publication, timestamp):

    year = timestamp.year
    month = timestamp.month
    day = timestamp.day

    website_url = publication.get("website")
    logging.info(f"Processing publication: {website_url}")

    parsed_url = urlparse(website_url)
    hn = parsed_url.hostname
    hostname = hn.replace('www.', '')
    cleaned_hostname = hostname.replace('.', '-')

    tmp_directory = "tmp"
    directory = os.path.join(f"us-local-news-data-{state}-{year}-{month}", str(day), hostname)
    formatted = timestamp.strftime('%Y%m%dT%H%M%S')
    archive_file_name = f"{cleaned_hostname}-{formatted}"

    rss_feeds = publication.get("rss", [])

    seed_urls = []
    
    for rss_feed_url in rss_feeds:
        normalized_rss_feed_url = normalize_rss_url(rss_feed_url)
        logging.info(f"Processing RSS feed: {normalized_rss_feed_url}")
        feed = feedparser.parse(normalized_rss_feed_url)
        for entry in feed.entries:
            article_url = entry.link
            if article_url and sniffer.guess(article_url):
                logging.info(f"Found article: {article_url}")
                seed_urls.append(article_url)
                if len(seed_urls) >= 5:
                    break
        if len(seed_urls) >= 5:
            break

    if len(seed_urls) < 5:
        try:
            logging.info(f"Scraping website: {website_url}")
            response = requests.get(website_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            for article_url in extract_article_urls_from_html(response.text, website_url):
                if article_url and sniffer.guess(article_url):
                    logging.info(f"Found article: {article_url}")
                    seed_urls.append(article_url)
                    if len(seed_urls) >= 5:
                        break
        except requests.RequestException as e:
            logging.error(f"Error scraping {website_url}: {e}")

    if seed_urls:
        seed_urls.append(website_url)
        archive(seed_urls, archive_file_name, directory, tmp_directory)
    else:
        logging.warning("No valid seed URLs found; skipping archiving.")

while True:
    for state, publications in data.items():
        logging.info(f"Processing state: {state}")
        
        for news_media in ['newspaper', 'tv', 'radio', 'broadcast']:
            for publication in publications.get(news_media, []):
                website_url = publication.get("website")
                logging.info(f"Evaluating publication: {website_url}")
                
                website_status_code = publication.get("website_status_code")
                if website_status_code and (200 <= website_status_code < 400):
                    start_time = time.perf_counter()  # Start timing
                    timestamp = datetime.datetime.now(datetime.timezone.utc)
                    
                    process_publication(state, publication, timestamp)
                    
                    end_time = time.perf_counter()  # End timing
                    elapsed = end_time - start_time
                    
                    logging.info(f"⏱️ Processing time for {website_url}: {elapsed:.2f} seconds")
                    print(f"Processed {website_url} in {elapsed:.2f} seconds")
                
                logging.info(f"Finished processing publication: {website_url}")
        logging.info(f"State: {state} and publications processed successfully.")