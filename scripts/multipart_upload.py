import os
import math
import json
import requests


BASE_URL = 'http://127.0.0.1:8000/api/v1'
API_TOKEN = ''
FILE_PATH = '/home/web/media/test/Final_Avoided_Wetland_priority_norm.tif'
# chunk_size must be greater than 5MB, for now use 100MB
CHUNK_SIZE = 100 * 1024 * 1024


def start_upload(fp):
    file_size = os.stat(fp).st_size
    payload = {
        "layer_type": 0,
        "component_type": "ncs_pathway",
        "privacy_type": "private",
        "name": os.path.basename(fp),
        "size": file_size,
        "number_of_parts": math.ceil(file_size / CHUNK_SIZE)
    }
    url = f'{BASE_URL}/layer/upload/start/'
    print(f'***REQUEST: {url}')
    print(json.dumps(payload))
    response = requests.post(url, json=payload, headers={
            "Authorization": f"Bearer {API_TOKEN}",
    })
    result = response.json()
    print(result)
    return result


def upload_part(signed_url, file_data, file_part_number):
    # TODO: use exponential backoff for retry
    # ref: https://github.com/aws-samples/amazon-s3-multipart-upload-transfer-acceleration/blob/main/frontendV2/src/utils/upload.js#L119
    res = requests.put(signed_url, data=file_data)
    return {
        'part_number': file_part_number,
        'etag': res.headers['ETag']
    }


def finish_upload(layer_uuid, upload_id, items):
    payload = {
        "multipart_upload_id": upload_id,
        "items": items
    }
    url = f'{BASE_URL}/layer/upload/{layer_uuid}/finish/'
    print(f'***REQUEST: {url}')
    print(json.dumps(payload))
    response = requests.post(url, json=payload, headers={
            "Authorization": f"Bearer {API_TOKEN}",
    })
    result = response.json()
    print(result)
    return result


def main():
    # start upload
    upload_params = start_upload(FILE_PATH)
    upload_id = upload_params['multipart_upload_id']
    layer_uuid = upload_params['uuid']
    upload_urls = upload_params['upload_urls']
    # do upload by chunks
    items = []
    idx = 0
    with open(FILE_PATH, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)  
            if not chunk:
                break
            url_item = upload_urls[idx]
            print(f"starting upload part {url_item['part_number']}")
            part_item = upload_part(url_item['url'], chunk, url_item['part_number'])
            items.append(part_item)
            print(f"finished upload part {url_item['part_number']}")
            idx += 1
    print(f'***Total upload_urls: {len(upload_urls)}')
    print(f'***Total chunks: {idx}')
    # finish upload
    finish_upload(layer_uuid, upload_id, items)

if __name__ == "__main__":
    main()

