# Longitudinal Local News Crawler

This Python-based crawler scrapes and archives local news articles from various media publications using RSS feeds and direct website scraping. It stores the collected articles in `.warc.gz` format and uploads them to the Internet Archive.

---

## 📦 Setup Instructions

1. **Clone the repository:**
   
      ```bash
      git clone https://github.com/GANGANI/longitudinal-local-news-crawler.git
      cd longitudinal-local-news-crawler
      ```

3. **Install dependencies**

      Make sure you have Python 3.8+ and pip installed.
      ```bash
      pip install -r requirements.txt
      ```
4. **Install Docker:**

     - The crawler uses Browsertrix Crawler via Docker to archive webpages.
     - Ensure Docker is installed and running on your system.
     - Run the following command
       ```bash
       docker pull webrecorder/browsertrix-crawler
       ```
       
5. **Internet Archive Upload (Optional)**
   - If Internet Archive credentials are configured and Docker is running, the `.wacz` files will be uploaded to archive.org.
   - To configure credentials:
      ```bash
      ia configure
      ```

6. **Setup Cronjos**
  - Set up a cron job to verify and delete .wacz files weekly:
    ```bash
    cronjob -e
    ```
  - Add the following line:
    ```
    * * * * * /path/to/python /path/to/verify_delete.py
    ```

## ⚙️ Usage

Run the crawler.py as follows with the required command line arguments

```bash
python crawler.py --<argument> <value>
```

### Command line arguments

# Command-Line Arguments

| Argument                 | Default Value                                             | Description                                                   |
|--------------------------|------------------------------------------------------------|---------------------------------------------------------------|
| `--input`                | `"output.json"`                                            | Path to JSON input file                                       |
| `--sleep`                | `3600`                                                     | Time between iterations (in seconds)                          |
| `--max_articles`         | `5`                                                        | Maximum number of articles to scrape per publication          |
| `--log`                  | `"news_scraper.log"`                                       | Path to log file                                              |
| `--log_level`            | `"CRITICAL"`                                               | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)         |
| `--mediatype`            | `"web"`                                                    | Media type for Internet Archive upload                        |
| `--collection`           | `"us-local-news-data"`                                     | Collection name of the Internet Archive                       |
| `--item_identifier`      | `"USLNDA"`                                                 | Prefix of the item identifier                                 |
| `--uploader`             | `"Alexander C. Nwala <alexandernwala@gmail.com>"`         | Uploader identity                                             |
| `--time_limit`           | `None`                                                     | Time limit (in seconds) for archiving subprocess              |
| `--time_per_url`         | `60`                                                       | Time limit (in seconds) for archiving one article             |
| `--collection_directory` | `"collection"`                                             | Directory to collect WARC files                               |
| `--tmp_directory`        | `"tmp"`                                                    | Directory to temporarily collect WARC files                   |
| `--delete_warc`          | `True`                                                     | Delete the WARC file after uploading to Internet Archive      |
| `--upload_warc`          | `True`                                                     | Upload the WARC file to Internet Archive                      |
| `--start`                | `0`                                                        | Start index of states to process                              |
| `--end`                  | `None`                                                     | End index (exclusive) of states to process                    |
| `--once_per_day`         | `True`                                                     | Run only once per day for all states                          |
| `--workers`              | `10`                                                       | Number of workers for crawling per run                        |
| `--delete_uploaded_warc`| `True`                                                     | Delete the .warc file after successful upload to Archive      |
| `--rolloverSize`         | `10000000000`                                              | Declare the rollover size                                     |



## 🗂️ Internet Archive Collection
```
us-local-news-data
│   ├── us-local-news-data-<state>-<year>-<month>
│   │   └── <day>
│   │       └── <hostname>
│   │               ├── <{cleaned_hostname}-{timestamp}>.warcz
```

Internet Archive Collection: https://archive.org/details/us-local-news-data

---


