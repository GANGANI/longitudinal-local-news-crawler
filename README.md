# Longitudinal Local News Crawler

This Python-based crawler scrapes and archives local news articles from various media publications using RSS feeds and direct website scraping. It stores the collected articles in `.wacz` format and uploads them to the Internet Archive.

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

| Argument               | Default                                                      | Description |
|------------------------|--------------------------------------------------------------|-------------|
| `--input`              | `output.json`                                                | Path to the input JSON file containing state-wise media data. |
| `--max_articles`       | `5`                                                          | Maximum number of articles to scrape per publication. |
| `--log`                | `news_scraper.log`                                           | Log file path for storing runtime logs. |
| `--log_level`          | `INFO`                                                       | Logging level: one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `--mediatype`          | `web`                                                        | Media type used for metadata during Internet Archive upload. |
| `--collection`         | `us-local-news-data`                                         | Collection name or prefix used in upload path and local directory structure. |
| `--uploader`           | `"Alexander C. Nwala <alexandernwala@gmail.com>"`            | Uploader metadata used during Internet Archive upload. |
| `--time_limit`         | `360`                                                        | Time limit (in seconds) for each archiving subprocess. |
| `--collection_directory` | `collection`                                               | Directory to save finalized `.wacz` files. |
| `--tmp_directory`      | `tmp`                                                        | Temporary working directory used during web archiving. |
| `--start`              | `0`                                                          | Start index (inclusive) for states to process from the input JSON. |
| `--end`                | `None`                                                       | End index (exclusive) for states to process. If `None`, all remaining states are processed. |
| `--timing_log`         | `timing_log.txt`                                             | File to save the processing time (in seconds) for each publication. |


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


