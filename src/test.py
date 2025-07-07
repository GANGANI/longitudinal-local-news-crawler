# import internetarchive

# item = internetarchive.get_item('us-local-news-data-mn-2025-06')
# item.get_metadata(glob_pattern='22/kittsonarea-com/kittsonarea-com-20250622T200401.wacz')  # Or *.warc if not compressed


# from warcio.archiveiterator import ArchiveIterator

# with open('USLNDA-20250627/USLNDA-AK-20250627-154560.wacz', 'rb') as stream:
#     for record in ArchiveIterator(stream):
#         if record.rec_type == 'response':
#             print(record.rec_headers.get_header('WARC-Target-URI'))

# from internetarchive import get_item

# item = get_item('us-local-news-data-mn-2025-06')
# print(item.item_size)

from internetarchive import get_item
item = get_item('USLNDA-20250627')
for k,v in item.metadata.items():
    print(print(k,":",v))