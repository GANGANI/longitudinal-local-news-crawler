# Longitudinal Local News Repo

## 3DLNews Local news media website dataset Analysis

Usable websites: 9315 + 13 + 1 + 9 = 9338

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

  
Processing time Samples
- for http://www.adn.com/: 450.15 seconds
- for http://www.alaskajournal.com/: 366.24 seconds
- for http://www.alaska-native-news.com/: 365.13 seconds
- for http://www.deltawindonline.com/: 373.37 seconds

If we take processing time as **480 seconds** per website, per day, only **180 (86400/480)** websites can process

Required parallelism = Total time / seconds per day
                     = (9,338 websites × 480 sec) / 86,400 sec
                     = 52 workers



