
from google.cloud import storage
import pickle
import os
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request
import requests
import json


CLIENT_SECRET_FILE = "/Users/lingxiao/workspace/google_keys/credentials.json"
BUCKET_NAME = "test-bucket-gpa"
ADA_ALBUM_ID = "AKllbf1C1gz3LARx1H2d7xnY8Twr0ormAqs9E2QWMeBKOStro1qrXcezAxRBTTXkU-weB3N0WD7C"

class GooglePhotosApi:
    def __init__(self,
                 api_name = 'photoslibrary',
                 client_secret_file=CLIENT_SECRET_FILE,
                 api_version = 'v1',
                 scopes = ['https://www.googleapis.com/auth/photoslibrary']):
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
        self.cred_pickle_file = f'/Users/lingxiao/workspace/google_keys/token_{self.api_name}_{self.api_version}.pickle'

        self.cred = None
        self.run_local_server()

    def run_local_server(self):
        # is checking if there is already a pickle file with relevant credentials
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


    def upload_from_google_photo_to_bucket(self, year, month, day):
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
                # TODO add people filter
                # "contentFilter": {
                #     "includedContentCategories": [
                #         "PEOPLE"
                #     ]
                # }
            }
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.cred.token)
        }
        
        res = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        try:
            for i, item in enumerate(res.json()['mediaItems']):
                print(f"==== Uploading phone {i}: {item['filename']} ====")
                # print(item)
                base_url = item['baseUrl']
                if 'photo' in item['mediaMetadata']:
                    base_url += '=d'
                else:
                    base_url += '=dv'
                
                # upload_to_google_cload(base_url, f"{year}_{month}_{day}_{item['filename']}", item['mimeType'])
        except Exception as e:
            print(res.json())
            raise e
            
def upload_to_google_cload(url, target_file_name, content_type):
    storage_client = storage.Client()

    bucket = storage_client.get_bucket(BUCKET_NAME)
    blob = bucket.blob(target_file_name)
    blob.upload_from_string(requests.get(url).content, content_type=content_type) 

if __name__ == '__main__':
    # upload_to_google_cload()

    # initialize photos api and create service
    gclient = GooglePhotosApi()
    # creds = google_photos_api.run_local_server()

    gclient.upload_from_google_photo_to_bucket(2022, 10, 9)