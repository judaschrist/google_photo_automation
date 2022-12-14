import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import requests
from requests.exceptions import ConnectionError
import json
from google_cloud_storage_api import GoogleStorageHelper
import google_crc32c
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound
from google_logging import structured_log, LogSeverity
from retrying import retry
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import os

CLIENT_SECRET_FILE = "secrets/google_photo_credentials.json"
CREDENTIAL_PICKLE_FILE_SECRET_SOURCE = "projects/1083696682843/secrets/google-photo-api-credential-pickle/versions/2"

def get_api_credential_from_google_secret():
    # loads of setup to do, see: https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets
    client = secretmanager.SecretManagerServiceClient()
    # remember to upload your own pickle file to google secret manager!!
    response = client.access_secret_version(request={"name": CREDENTIAL_PICKLE_FILE_SECRET_SOURCE})
    crc32c = google_crc32c.Checksum()
    crc32c.update(response.payload.data)
    if response.payload.data_crc32c != int(crc32c.hexdigest(), 16):
        raise Exception("Secret data corruption detected.")
    return response.payload.data

def retry_if_connection_error(exception):
    return isinstance(exception, ConnectionError)

@retry(retry_on_exception=retry_if_connection_error, wait_fixed=500, stop_max_attempt_number=3, wrap_exception=True)
def safe_retryable_requests(*args, **kwargs):
    return requests.request(*args, **kwargs)

@retry(retry_on_exception=retry_if_connection_error, wait_fixed=500, stop_max_attempt_number=3, wrap_exception=True)
def save_image_from_url_helper(url, file_path):
    try:
        image = Image.open(BytesIO(requests.get(url).content))
        # save original image exif data
        image.save(file_path, exif=image.info.get('exif'))
    except UnidentifiedImageError:
        print(f'UnidentifiedImageError: {url}')
        pass

class GooglePhotoHelper:
    '''
    Helper class to manage medias files in Google Photo
    '''

    def __init__(self,
                 api_name = 'photoslibrary',
                 api_version = 'v1',
                 # change scopes according the use case
                 # see https://developers.google.com/photos/library/guides/authorization
                 scopes = [
                    'https://www.googleapis.com/auth/photoslibrary.appendonly',
                    'https://www.googleapis.com/auth/photoslibrary.readonly',
                ]):
        '''
        Args:
            api_version: string, the version of the service
            api_name: string, name of the api e.g."docs","photoslibrary",...
            api_version: version of the api
        '''

        self.api_name = api_name
        self.api_version = api_version
        self.scopes = scopes
        self.cred_pickle_file = f'token_{self.api_name}_{self.api_version}.pickle'

        self.cred = None
        self.run_local_server()

    def run_local_server(self):
        # checking if there is already a pickle file with relevant credentials
        try:
            self.cred = pickle.loads(get_api_credential_from_google_secret())
        except NotFound:
            self.cred = None
            structured_log("!!! Make sure this is run locally first to create the pickle file, then upload it as a secret !!!", severity=LogSeverity.WARNING)
            structured_log('************ upload the generated pickle file to your google secret and update the secret source id in CREDENTIAL_PICKLE_FILE_SECRET_SOURCE ************', severity=LogSeverity.WARNING)

        # if there is no pickle file with stored credentials, create one using google_auth_oauthlib.flow
        if not self.cred or not self.cred.valid:
            if self.cred and self.cred.expired and self.cred.refresh_token:
                structured_log("=== Refreshing token ===")
                self.cred.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, self.scopes)
                self.cred = flow.run_local_server()

            with open(self.cred_pickle_file, 'wb') as token:
                pickle.dump(self.cred, token)
        
        return self.cred

    def upload_from_google_photo_to_bucket(self, year, month, day, bucket_name, upload_photo=True, upload_video=False, dry_run=False, exclude_file_prefix=None):
        '''
        Uploads all photos from a given day to a bucket
        Args:
            year: int, year of the day
            month: int, month of the day
            day: int, date of the day
            bucket_name: string, name of the bucket
            dry_run: boolean, if True, only prints the files that would be uploaded without actually uploading them
            exclude_file_prefix: string, if not None, files with this prefix will not be uploaded
        returns:
            A dictionary with file names as keys and file content as values
        '''
        media_type_list = []
        if upload_photo:
            media_type_list.append('PHOTO')
        if upload_video:
            media_type_list.append('VIDEO')
        url = 'https://photoslibrary.googleapis.com/v1/mediaItems:search'
        payload = {
            "filters": {
                "dateFilter": {
                    "dates": [
                        {
                        "day": day,
                        "month": month,
                        "year": year
                        }
                        
                    ]
                },
                "mediaTypeFilter": {
                    "mediaTypes": media_type_list
                }
                # TODO people filter does not work very well
                # "contentFilter": {
                #     "includedContentCategories": [
                #         "PEOPLE"
                #     ]
                # }
            },
            #TODO: add pagination according to https://developers.google.com/photos/library/guides/list#pagination
            "pageSize": 100
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.cred.token)
        }
        
        res = safe_retryable_requests("POST", url, data=json.dumps(payload), headers=headers)
        if 'mediaItems' not in res.json():
            structured_log("No media items found")
            return []
        file_name_dict = {}
        storage_api = GoogleStorageHelper(bucket_name)
        for i, item in enumerate(res.json()['mediaItems']):
            if exclude_file_prefix is not None and item['filename'].startswith(exclude_file_prefix):
                continue
            base_url = item['baseUrl']
            if 'photo' in item['mediaMetadata']:
                base_url += '=d'
            else:
                base_url += '=dv'
            structured_log(f"==== Uploading photo {i}: {item['filename']} ====")
            if not dry_run:
                # preserving the original file name when uploading.
                target_file_name = item['filename']
                file_content = requests.get(base_url).content
                storage_api.upload_string_content_to_google_cloud(file_content, target_file_name, item['mimeType'])
                file_name_dict[target_file_name] = file_content
        return file_name_dict

    def upload_image_to_photo_album(self, image_bytes, file_name, album_id):
        '''
        Uploads an image to a photo album
        Args:
            image_bytes: bytes, image data to be uploaded
            album_id: string, id of the album to which the image will be uploaded
        '''
        url = 'https://photoslibrary.googleapis.com/v1/uploads'
        headers = {
            'content-type': 'application/octet-stream',
            'Authorization': 'Bearer {}'.format(self.cred.token)
        }
        res = safe_retryable_requests("POST", url, data=image_bytes, headers=headers)
        # get the upload token as a string
        upload_token = res.content.decode('utf-8')
        url = 'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate'
        payload = {
            "albumId": album_id,
            "newMediaItems": [
                {
                    "description": "Uploaded from Ada",
                    "simpleMediaItem": {
                        "fileName": file_name,
                        "uploadToken": upload_token
                    }
                }
            ]
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.cred.token)
        }
        safe_retryable_requests("POST", url, data=json.dumps(payload), headers=headers)

    def create_new_album(self, album_name):
        '''
        Creates a new album
        Args:
            album_name: string, name of the album
        '''
        url = 'https://photoslibrary.googleapis.com/v1/albums'
        payload = {
            "album": {
                "title": album_name
            }
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.cred.token)
        }
        res = safe_retryable_requests("POST", url, data=json.dumps(payload), headers=headers)
        return res.json()['id']
    
    def find_albums_by_name(self, album_name):
        '''
        Finds all albums with a given name
        Args:
            album_name: string, name of the album
        '''
        url = 'https://photoslibrary.googleapis.com/v1/albums'
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.cred.token)
        }
        res = safe_retryable_requests("GET", url, headers=headers)
        albums = res.json()['albums']
        return [album for album in albums if album['title'] == album_name]

    def upsert_album(self, album_name):
        '''
        Creates a new album if it does not exist, otherwise returns the existing album
        Args:
            album_name: string, name of the album
        '''
        albums = self.find_albums_by_name(album_name)
        if len(albums) == 0:
            album_id = self.create_new_album(album_name)
        elif len(albums) == 1:
            album_id = albums[0]['id']
        else:
            raise Exception('More than one album found, please delete all albums with the name of {}'.format(album_name))
        return album_id

    def list_face_download_urls_from_album(self, album_id, size=100, download=False, download_dir=None):
        '''
        Lists all the base urls of the face images in an album
        Args:
            album_id: string, id of the album
            download: boolean, whether to download the images
            download_dir: string, directory to download the images, must be specified if download is True
        returns:
            list of tuples (file_name, download_url)
        '''
        if download and download_dir is None:
            raise Exception('download_dir must be specified if download is True')
        url = 'https://photoslibrary.googleapis.com/v1/mediaItems:search'
        payload = {
            "albumId": album_id,
            "pageSize": 100
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.cred.token)
        }
        next_page_token = None
        file_url_list = []
        if download and not os.path.exists(download_dir):
            os.makedirs(download_dir)
        while True:
            if next_page_token is not None:
                payload['pageToken'] = next_page_token
            res = safe_retryable_requests("POST", url, data=json.dumps(payload), headers=headers)
            for item in res.json()['mediaItems']:
                if item['filename'].startswith('auto_detected_face_image_'):
                    file_name = item['filename'].split('.')[0] + '.jpg'
                    file_path = os.path.join(download_dir, file_name)
                    image_url = item['baseUrl'] + '=d'
                    if download:
                        save_image_from_url_helper(image_url, file_path)
                    file_url_list.append((item['filename'], image_url))
                    if len(file_url_list) % 100 == 0:
                        print('processing {} images'.format(len(file_url_list)))
                    if len(file_url_list) == size:
                        break
            next_page_token = res.json().get('nextPageToken')
            if next_page_token is None or len(file_url_list) == size:
                break
        return file_url_list

if __name__ == '__main__':
    pass
    # print(get_api_credential_from_google_secret())



            