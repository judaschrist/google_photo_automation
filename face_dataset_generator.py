from google_photo_api import GooglePhotoHelper
import json

ALBUM_NAME = 'Ada'

def generate_face_dataset_from_google_album(album_name, size):
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
    album_list = helper.find_albums_by_name('Ada')
    if len(album_list) != 1:
        raise Exception(f'There should be only one album named {album_name}!')
    url_list = helper.list_face_download_urls_from_album(album_list[0]['id'], size=size)
    data_json_str_list = [json.dumps({"image_url": url, "label": album_name}) for url in url_list]
    # write json lines to file:
    with open(album_name + '_face_dataset.json', 'w') as f:
        f.writelines(data_json_str_list)



if __name__ == '__main__':
    generate_face_dataset_from_google_album(ALBUM_NAME, 1000)
