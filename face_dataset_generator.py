from google_photo_api import GooglePhotoHelper
import json
from PIL import Image
from io import BytesIO
import piexif
import requests
from requests.exceptions import ConnectionError
import os
from retrying import retry

ALBUM_NAME = 'Ada'

def generate_face_dataset_from_google_album_for_hugging_face(album_name, size):
    '''
    If you want to generate face with someone specific, do the following:
    1. make sure all the face images are generated using this automation tool
    2. in Google photo, use the search function to search for the person you want to generate face with
    3. in the search result page, create a new album using "share as album"
    4. name the album as the person's name, use the name as the parameter for this function

    How to use the file with huggingface datasets:
    ```
    from datasets import load_dataset
    from google.colab import files
    files.upload_file('uploaded_face.json')
    config.dataset_name = "json"
    dataset = load_dataset(config.dataset_name, data_files="uploaded_face.json", split='train')

    from datasets import Image as DsImage
    from PIL import Image
    from io import BytesIO
    import requests

    # you also need to pre-download the image files to your local machine, since the urls will be expired after an hour
    def pre_download(example):
        example['image'] = Image.open(BytesIO(requests.get(example["image_url"]).content))
        return example

    dataset = dataset.map(pre_download, batched=False)
    dataset = dataset.cast_column("image", DsImage())
    ```
    '''
    helper = GooglePhotoHelper()
    album_list = helper.find_albums_by_name(album_name)
    if len(album_list) != 1:
        raise Exception(f'There should be only one album named {album_name}!')
    file_name_url_list = helper.list_face_download_urls_from_album(album_list[0]['id'], size=size)
    data_json_str_list = [json.dumps({"image_url": url, "label": album_name}) for _, url in file_name_url_list]
    # write json lines to file:
    with open(album_name + '_face_dataset.json', 'w') as f:
        f.writelines(data_json_str_list)

def retry_if_connection_error(exception):
    return isinstance(exception, ConnectionError)

@retry(retry_on_exception=retry_if_connection_error, wait_fixed=500, stop_max_attempt_number=3, wrap_exception=True)
def save_image_from_url_helper(url, file_path):
    image = Image.open(BytesIO(requests.get(url).content))
    image.save(file_path)

def download_file_into_folder_from_url_list(album_name, size, dir_path):
    # create dir if not exist
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    helper = GooglePhotoHelper()
    album_list = helper.find_albums_by_name('Ada')
    if len(album_list) != 1:
        raise Exception(f'There should be only one album named {album_name}!')
    file_name_url_list = helper.list_face_download_urls_from_album(album_list[0]['id'], size=size)
    print(f'Found {len(file_name_url_list)} images in album {album_name}')
    for i, file_name_url_pair in enumerate(file_name_url_list):
        if i % 100 == 0:
            print(f'Downloading {i}th image...')
        file_name, url = file_name_url_pair
        file_name_without_suffix = file_name.split('.')[0]
        file_name = file_name_without_suffix + '.jpg'
        file_path = os.path.join(dir_path, file_name)
        image = Image.open(BytesIO(requests.get(url).content))
        image.save(file_path)


def read_exif_user_comment_from_image_file(file_path):
    image = Image.open(file_path)
    exif_dict = piexif.load(image.info['exif'])
    return exif_dict['Exif'][piexif.ExifIFD.UserComment].decode('utf-8')

def read_exif_user_comment_from_image_url(url):
    image = Image.open(BytesIO(requests.get(url).content))
    exif_dict = piexif.load(image.info['exif'])
    return exif_dict['Exif'][piexif.ExifIFD.UserComment].decode('utf-8')


if __name__ == '__main__':
    download_file_into_folder_from_url_list(ALBUM_NAME, 5000, '/Users/lingxiao/Documents/ada_face_dataset')
