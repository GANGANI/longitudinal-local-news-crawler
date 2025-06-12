# Longituinal Local News Repo

## Preprocess local news media website dataset

Usable websites: 9139 + 34 + 1 = 9174

| Status Code     | Meaning                   | Explanation                                                                                        | Number of Links |
|------------------|---------------------------|----------------------------------------------------------------------------------------------------|-----------------|
| 200              | OK                        | Request succeeded; server returned the expected content.                                           | 9139            |
| 202              | Accepted                  | Request accepted for processing but not yet completed.                                             | 34              |
| 301              | Moved Permanently         | Resource permanently moved to a new URL.                                                           | 1               |
| 307              | Temporary Redirect        | Resource temporarily moved to a new URL; use same method at new location.                          | 9               |
| 400              | Bad Request               | Server couldn't understand the request due to invalid syntax.                                      | 5               |
| 401              | Unauthorized              | Authentication is required to access the resource.                                                 | 5               |
| 403              | Forbidden                 | Server understood the request but refuses to authorize it (e.g., bot block, restricted access).    | 1378            |
| 404              | Not Found                 | Requested resource doesn't exist on the server.                                                    | 590             |
| 405              | Method Not Allowed        | The method used (e.g., HEAD) is not supported for this resource.                                   | 670             |
| 406              | Not Acceptable            | Resource not capable of generating content acceptable according to request headers.                | 223             |
| 408              | Request Timeout           | Server timed out waiting for the request.                                                          | 2               |
| 409              | Conflict                  | Request conflicts with the current state of the resource.                                          | 6               |
| 410              | Gone                      | Resource was intentionally removed and is no longer available.                                     | 15              |
| 412              | Precondition Failed       | Preconditions given in headers failed when evaluated on the server.                                | 1               |
| 418              | I'm a teapot 🫖            | Joke response code indicating the server refuses to brew coffee in a teapot.                       | 1               |
| 429              | Too Many Requests         | Client has sent too many requests in a given amount of time.                                       | 351             |
| 500              | Internal Server Error     | Generic server error when the server fails to fulfill a valid request.                             | 86              |
| 501              | Not Implemented           | Server doesn't support functionality to fulfill the request.                                       | 1               |
| 503              | Service Unavailable       | Server is currently unavailable (overloaded or down).                                              | 17              |
| 504              | Gateway Timeout           | Server acting as a gateway didn’t get a response in time.                                          | 1               |
| 520              | Unknown Error             | Cloudflare: origin server returned an unexpected/unknown response.                                 | 6               |
| 521              | Web Server Down           | Cloudflare couldn't reach the origin server.                                                       | 1               |
| 526              | Invalid SSL Certificate   | SSL certificate at origin server is invalid.                                                       | 11              |
| 530              | Origin Error              | Cloudflare-specific error indicating the origin server returned an error.                          | 3               |
| 999              | Bot Block (Non-standard)  | Used by some websites (e.g., LinkedIn) to block non-browser traffic.                               | 1               |
| None (Failed)    | Request Failed            | The request could not be completed (e.g., timeout, DNS issue, connection error).                   | 1523            |

