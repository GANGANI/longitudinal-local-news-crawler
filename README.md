# Longituinal Local News Repo

## Preprocess local news media website dataset

| Status Code | Meaning                   | Explanation                                                                                        | Number of Links |
|-------------|---------------------------|----------------------------------------------------------------------------------------------------|-----------------|
| 200         | OK                        | Request succeeded; server returned the expected content.                                          | 9,144           |
| 202         | Accepted                  | Request accepted for processing but not yet completed.                                            | 51              |
| 301         | Moved Permanently         | Resource permanently moved to a new URL.                                                          | 1               |
| 307         | Temporary Redirect        | Resource temporarily at a different URL; use same method at new location.                        | 9               |
| 400         | Bad Request               | Server couldn’t understand the request due to invalid syntax.                                     | 5               |
| 401         | Unauthorized              | Authentication is required.                                                                       | 5               |
| 402         | Payment Required          | Reserved for future use (e.g., paywalls).                                                         | 1               |
| 403         | Forbidden                 | Server understood the request but refuses to authorize it (e.g., blocked non-browser).           | 1,593           |
| 404         | Not Found                 | Requested resource doesn’t exist on the server.                                                   | 619             |
| 405         | Method Not Allowed        | The used method (e.g., `HEAD`) is not allowed at this URL.                                       | 701             |
| 406         | Not Acceptable            | Server can’t produce response matching the request’s `Accept` headers.                           | 223             |
| 408         | Request Timeout           | Server timed out waiting for the full request.                                                    | 2               |
| 409         | Conflict                  | Request conflicts with current server state.                                                      | 7               |
| 410         | Gone                      | Resource was intentionally removed and is no longer available.                                    | 16              |
| 412         | Precondition Failed       | A condition given in request headers was not met.                                                 | 1               |
| 418         | I’m a teapot 🫖           | Joke status code from RFC 2324; sometimes used to block bots.                                     | 1               |
| 429         | Too Many Requests         | Client sent too many requests in a given time; rate limiting.                                     | 136             |
| 500         | Internal Server Error     | Generic server-side error occurred while processing a valid request.                              | 27              |
| 501         | Not Implemented           | Server doesn’t support functionality required to fulfill the request.                             | 1               |
| 503         | Service Unavailable       | Server is temporarily unable to handle the request (e.g., overloaded, down for maintenance).      | 19              |
| 504         | Gateway Timeout           | Server acting as a gateway didn’t receive a timely response from upstream.                        | 1               |
| 520         | Unknown Error             | Cloudflare error: origin server returned an unexpected response.                                  | 6               |
| 521         | Web Server Down           | Cloudflare couldn’t reach the origin server.                                                      | 1               |
| 523         | Origin Unreachable        | Cloudflare could not reach the origin server (DNS failure, etc.).                                | 1               |
| 526         | Invalid SSL Certificate   | Cloudflare couldn’t validate SSL certificate on origin server.                                    | 11              |
| 530         | Origin Error              | Cloudflare-specific error indicating origin is returning errors.                                  | 3               |
| 999         | Bot Block                 | Non‑standard code used by sites (e.g., LinkedIn) to block bots or headless requests.              | 1               |
