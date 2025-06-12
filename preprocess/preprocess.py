import json
import gzip
import requests
from tqdm import tqdm
import logging
from collections import defaultdict

# === Logging Setup ===
logging.basicConfig(
    filename='failed_websites.log',
    filemode='w',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# === Website status check function ===
def check_website_status(url):
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code
    except requests.RequestException as e:
        logging.warning(f"Failed to reach {url} - {str(e)}")
        return None

# === Load Gzipped JSON ===
input_file = 'output.json.gz'
with gzip.open(input_file, 'rt', encoding='utf-8') as f:
    data = json.load(f)

# === Initialize counters and progress ===
status_counter = defaultdict(int)

total_outlets = sum(
    len(outlets)
    for state in data.values()
    for outlets in state.values()
)

# === Process Each Website ===
with tqdm(total=total_outlets, desc="Checking websites", unit="site") as pbar:
    for state, media_types in data.items():
        for media_type, outlets in media_types.items():
            for outlet in outlets:
                website = outlet.get('website')
                if website:
                    status_code = check_website_status(website)
                else:
                    status_code = None
                outlet['website_status_code'] = status_code
                status_counter[status_code] += 1
                pbar.update(1)

# === Save Updated Data ===
output_file = 'updated_media_data.json.gz'
with gzip.open(output_file, 'wt', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

# === Print Summary ===
print("\n📊 Summary of Website Response Codes:")
for code, count in sorted(status_counter.items(), key=lambda x: (x[0] is None, x[0])):
    label = "None (Failed)" if code is None else str(code)
    print(f"{label}: {count} websites")

print(f"\n✅ Updated data saved to: {output_file}")
print("⚠️  Failed URLs logged to: failed_websites.log")
