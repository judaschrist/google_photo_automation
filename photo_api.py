
from google.cloud import storage
import datetime
import pickle
import os
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
import requests
import json


CLIENT_SECRET_FILE = "secrets/google_photo_credentials.json"
ADA_ALBUM_ID = "AKllbf1C1gz3LARx1H2d7xnY8Twr0ormAqs9E2QWMeBKOStro1qrXcezAxRBTTXkU-weB3N0WD7C"

class GooglePhotoHelper:
    '''
    Helper class to manage medias files in Google Photo
    '''

    def __init__(self,
                 api_name = 'photoslibrary',
                 client_secret_file=CLIENT_SECRET_FILE,
                 api_version = 'v1',
                 # change scopes according the use case
                 # see https://developers.google.com/photos/library/guides/authorization
                 scopes = [
                    'https://www.googleapis.com/auth/photoslibrary.appendonly',
                    'https://www.googleapis.com/auth/photoslibrary.readonly',
                ]):
        '''
        Args:
            client_secret_file: string, location where the requested credentials are saved
            api_version: string, the version of the service
            api_name: string, name of the api e.g."docs","photoslibrary",...
            api_version: version of the api
        '''

        self.api_name = api_name
        self.client_secret_file = client_secret_file
        self.api_version = api_version
        self.scopes = scopes
        self.cred_pickle_file = f'token_{self.api_name}_{self.api_version}.pickle'

        self.cred = None
        self.run_local_server()

    def run_local_server(self):
        # checking if there is already a pickle file with relevant credentials
        if os.path.exists(self.cred_pickle_file):
            with open(self.cred_pickle_file, 'rb') as token:
                self.cred = pickle.load(token)

        # if there is no pickle file with stored credentials, create one using google_auth_oauthlib.flow
        if not self.cred or not self.cred.valid:
            if self.cred and self.cred.expired and self.cred.refresh_token:
                self.cred.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, self.scopes)
                self.cred = flow.run_local_server()

            with open(self.cred_pickle_file, 'wb') as token:
                pickle.dump(self.cred, token)
        
        return self.cred

    def upload_from_google_photo_to_bucket(self, year, month, day, bucket_name, dry_run=False):
        '''
        Uploads all photos from a given day to a bucket
        Args:
            year: int, year of the day
            month: int, month of the day
            day: int, date of the day
            bucket_name: string, name of the bucket
            dry_run: boolean, if True, only prints the files that would be uploaded without actually uploading them
        returns:
            A list of the file names that were uploaded
        '''
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
        
        res = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        try:
            if 'mediaItems' not in res.json():
                print("No media items found")
                return []
            file_name_list = []
            for i, item in enumerate(res.json()['mediaItems']):
                print(f"==== Uploading phone {i}: {item['filename']} ====")
                base_url = item['baseUrl']
                if 'photo' in item['mediaMetadata']:
                    base_url += '=d'
                else:
                    base_url += '=dv'
                if not dry_run:
                    # preserving the original file name when uploading.
                    target_file_name = item['filename']
                    upload_url_to_google_cload(base_url, target_file_name, item['mimeType'], bucket_name)
                    file_name_list.append(target_file_name)
            return file_name_list
        except Exception as e:
            print(res.json())
            raise e

def get_current_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
def upload_url_to_google_cload(url, target_file_name, content_type, bucket_name):
    '''
    Uploads a file from a given url to a bucket
    '''
    storage_client = storage.Client()

    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(target_file_name)
    blob.upload_from_string(requests.get(url).content, content_type=content_type)