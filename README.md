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



---

## 3DLNews Local news media website dataset Analysis

**Total Usable Websites**:  
9315 (200) + 13 (202) + 1 (301) + 9 (307) = **9338 websites**

---

### HTTP Status Summary

| Status Code     | Meaning                   | Explanation                                                                                       | Number of Links |
|------------------|---------------------------|---------------------------------------------------------------------------------------------------|-----------------|
| 200              | OK                        | Request succeeded; server returned the expected content.                                          | 9315            |
| 202              | Accepted                  | Request accepted for processing but not yet completed.                                            | 13              |
| 301              | Moved Permanently         | Resource permanently moved to a new URL.                                                          | 1               |
| 307              | Temporary Redirect        | Resource temporarily at a different URL; use same method at new location.                         | 9               |
| 400              | Bad Request               | Server couldn’t understand the request due to invalid syntax.                                     | 4               |
| 401              | Unauthorized              | Authentication is required.                                                                       | 5               |
| 403              | Forbidden                 | Server understood request but refuses to authorize it. Often due to bot blocking.                 | 1378            |
| 404              | Not Found                 | Requested resource does not exist on the server.                                                  | 632             |
| 405              | Method Not Allowed        | Request method not supported for the resource.                                                    | 614             |
| 406              | Not Acceptable            | Server can’t return a response matching the request's headers.                                    | 223             |
| 408              | Request Timeout           | Server timed out waiting for the client’s request.                                                | 2               |
| 409              | Conflict                  | Request conflicts with the current state of the server.                                           | 6               |
| 410              | Gone                      | Resource is no longer available and was intentionally removed.                                    | 15              |
| 412              | Precondition Failed       | Server does not meet one of the request’s preconditions.                                          | 1               |
| 418              | I'm a teapot              | Joke status code from RFC 2324; sometimes used to block bots.                                     | 1               |
| 429              | Too Many Requests         | Client sent too many requests; rate limiting.                                                     | 346             |
| 500              | Internal Server Error     | Server encountered an unexpected condition.                                                       | 24              |
| 501              | Not Implemented           | Server does not support the requested functionality.                                              | 1               |
| 503              | Service Unavailable       | Server is temporarily unavailable (overloaded or down for maintenance).                           | 17              |
| 504              | Gateway Timeout           | Server acting as a gateway did not receive a timely response.                                     | 1               |
| 520              | Unknown Error             | Cloudflare: Origin server returned an unexpected response.                                        | 6               |
| 521              | Web Server Down           | Cloudflare: Origin server is down or refusing connections.                                        | 1               |
| 523              | Origin Unreachable        | Cloudflare: Cannot reach origin server (DNS or network error).                                    | 1               |
| 526              | Invalid SSL Certificate   | Cloudflare: Origin server has an invalid SSL certificate.                                         | 11              |
| 530              | Origin Error              | Cloudflare-specific error indicating origin returned an error.                                    | 3               |
| 999              | Bot Block                 | Non-standard code used (e.g., by LinkedIn) to block bots or non-browser requests.                 | 1               |
| None (Failed)    | Request Failed            | Request couldn’t be completed (e.g., network error, timeout, DNS failure).                        | 1449            |

### Status by U.S. State

| State | Good (2xx/3xx) | Bad/None |
|-------|----------|----------|
| AK    | 82       | 46       |
| AL    | 193      | 71       |
| AR    | 145      | 79       |
| AZ    | 165      | 89       |
| CA    | 657      | 347      |
| CO    | 211      | 116      |
| CT    | 152      | 118      |
| DC    | 52       | 20       |
| DE    | 32       | 20       |
| FL    | 405      | 201      |
| GA    | 280      | 111      |
| HI    | 43       | 31       |
| IA    | 209      | 86       |
| ID    | 78       | 31       |
| IL    | 401      | 219      |
| IN    | 213      | 128      |
| KS    | 143      | 64       |
| KY    | 180      | 54       |
| LA    | 141      | 67       |
| MA    | 376      | 142      |
| MD    | 106      | 46       |
| ME    | 70       | 71       |
| MI    | 333      | 102      |
| MN    | 259      | 197      |
| MO    | 252      | 147      |
| MS    | 107      | 79       |
| MT    | 105      | 32       |
| NC    | 249      | 133      |
| ND    | 69       | 33       |
| NE    | 129      | 69       |
| NH    | 67       | 47       |
| NJ    | 152      | 148      |
| NM    | 76       | 38       |
| NV    | 91       | 36       |
| NY    | 373      | 196      |
| OH    | 392      | 145      |
| OK    | 152      | 48       |
| OR    | 159      | 63       |
| PA    | 277      | 118      |
| RI    | 43       | 37       |
| SC    | 101      | 72       |
| SD    | 59       | 45       |
| TN    | 204      | 97       |
| TX    | 631      | 286      |
| UT    | 57       | 42       |
| VA    | 156      | 81       |
| VT    | 38       | 17       |
| WA    | 145      | 123      |
| WI    | 192      | 104      |
| WV    | 82       | 17       |
| WY    | 54       | 33       |
| **TOTAL** | **9338** | **4742** |

Summary
- **Max number of websites per website: 657 (CA)**
- **Min number of websites per website: 32 (DE)**

  
## Processing time 

- **Estimated time per website**: approximately 480 seconds
- **Sequentially** = 9338 websites * 480 sec = 4,481,600 sec = 52 days (To run all websites, it will take 52 days)
- **Required parallelism** = Total time / seconds per day
                           = (9,338 websites * 480 sec) / 86,400 sec
                           = 52 workers
                           
  - Within 1 day, only 180 websites (86400/480)
  - To parallelize, 52 tasks should run in parallel (9339/180)
  
  
  **High-Level Strategy**
  - Split the 9338 websites into batches (180 per job)
  - Multiple HPC jobs in parallel (52 jobs)

## Storage requirements

- I have collected wacz files for AK state for june 13, 14, 15, 16 (But from 16th, it has been stopped due to lack of space)
- Eventhough above analysis shows, AK state has 82 working websites, I only got results from61 websites.
- The maximum file size is 5GB(us-local-news-data-AK-2025-6/14/kyuk.org/kyuk-org-20250614T161710.wacz)
- The minimum file size is 4MB(us-local-news-data-AK-2025-6/15/650keni.iheart.com/650keni-iheart-com-20250615T142607.wacz)
- On average 200MB per file(770 items, totalling 146.8 GB)

## Estimated Bandwidth Usage

1. Website Crawling
- Average crawl size per site: ~50 MB 
- Per day: 9338 × 50 MB avg = ~466 GB/day (just for crawling)

2. WACZ Uploading
A single .wacz file can be:
- Small: ~5 MB
- Large: 100–300 MB (pages with media)
- Estimate: average 50 MB per WACZ
- 9338 × 50 MB = ~466 GB/day upload bandwidth

3. Total
- Crawling	~466 GB (download)
- Uploading	~466 GB (upload)
- Total	~900–1000 GB/day

So it seems we require ~1 TB of bandwidth daily

## Tasks for Cron Jobs
- First store WACZ locally, then batch-upload periodically using a cron job (every hour)
- Daily, check if batch jobs are still running or have failed. If it fails, send an email
- Verify uploads and delete warcz files weekly
- Generate a report monthly/weekly summarizing archived, failed, skipped, per state
- Notify if the errors exceed a threshold.

## Questions
- Executing docker in HPC


