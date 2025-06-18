import os
import datetime
import internetarchive
import argparse
import logging
from internetarchive import upload

# --- Configuration ---
DAYS_BACK = 7
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Upload Function ---
def upload_wacz(directory, archive_file_name, item_identifier, upload_dest_file, args):
    try:
        src_file = os.path.join(directory, f"{archive_file_name}.wacz")
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
        logging.error(f"Error uploading {item_identifier}/{upload_dest_file}: {e}")

# --- Helper Functions ---
def get_wacz_files_from_local(base_dir):
    wacz_files = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith('.wacz'):
                relative_path = os.path.relpath(os.path.join(root, f), base_dir)
                wacz_files.append(relative_path.replace("\\", "/"))
    return set(wacz_files)

def get_wacz_files_from_ia(identifier, target_day):
    item = internetarchive.get_item(identifier)
    return set(
        f['name']
        for f in item.files
        if f['name'].startswith(f'{target_day}/') and f['name'].endswith('.wacz')
    )

def process_item_for_state(state, year, month, day, args):
    item_identifier = f"{args.collection}-{state}-{year}-{month}"
    local_base_dir = os.path.join(args.collection_directory, item_identifier, day)

    if not os.path.isdir(local_base_dir):
        logging.warning(f"No local directory found for {local_base_dir}. Skipping.")
        return

    logging.info(f"Checking {item_identifier} for day {day}...")

    local_files = get_wacz_files_from_local(local_base_dir)
    remote_files = get_wacz_files_from_ia(item_identifier, day)

    only_local = local_files - remote_files
    only_remote = remote_files - local_files

    if only_local:
        logging.info("Found missing uploads. Uploading...")
        for f in sorted(only_local):
            cleaned_hostname = f.split('/')[0]
            archive_file_name = os.path.splitext(os.path.basename(f))[0]
            upload_wacz(
                os.path.join(local_base_dir, cleaned_hostname),
                archive_file_name,
                item_identifier,
                f,
                args
            )
    else:
        logging.info("✅ All local files exist on the Internet Archive.")

    if only_remote:
        logging.info("These files exist remotely but not locally:")
        for f in sorted(only_remote):
            logging.info(f"  {f}")

# --- Main Logic ---
def main(args):
    today = datetime.datetime.utcnow().date()
    target_date = today - datetime.timedelta(days=DAYS_BACK)

    year = target_date.year
    month = str(target_date.month).zfill(2)
    day = str(target_date.day)

    logging.info(f"Running verification for {year}-{month}-{day}")

    # Discover states by scanning directory names
    for entry in os.listdir(args.collection_directory):
        if not entry.startswith(args.collection + "-"):
            continue

        # Match pattern like warcz-ca-2025-06
        parts = entry.split('-')
        if len(parts) < 4:
            continue

        state = parts[1].lower()

        try:
            process_item_for_state(state, year, month, day, args)
        except Exception as e:
            logging.error(f"Error processing state {state}: {e}")

# --- CLI ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True)
    parser.add_argument("--collection_directory", required=True)
    parser.add_argument("--uploader", required=True)
    parser.add_argument("--mediatype", default="web", help="Default: web")

    args = parser.parse_args()
    main(args)
