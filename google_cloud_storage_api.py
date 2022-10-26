from google.cloud import storage
from google.api_core.exceptions import BadRequest
import requests
from retrying import retry

def retry_if_bad_request(exception):
    return isinstance(exception, BadRequest)


class GoogleStorageHelper:

    @retry(retry_on_exception=retry_if_bad_request, wait_fixed=500, stop_max_attempt_number=3, wrap_exception=True)
    def __init__(self, bucket_name) -> None:
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        pass

    @retry(retry_on_exception=retry_if_bad_request, wait_fixed=500, stop_max_attempt_number=3, wrap_exception=True)
    def upload_url_to_google_cloud(self, url, target_file_name, content_type):
        '''
        Uploads a file from a given url to a bucket
        '''
        blob = self.bucket.blob(target_file_name)
        blob.upload_from_string(requests.get(url).content, content_type=content_type)
    

    def read_file_from_google_cloud_to_string(self, file_name):
        '''
        Reads a file from a bucket
        '''
        blob = self.bucket.blob(file_name)
        return blob.download_as_text()
    

    def read_file_from_google_cloud_to_bytes(self, file_name):
        '''
        Reads a file from a bucket to bytes
        '''
        blob = self.bucket.blob(file_name)
        return blob.download_as_bytes()
    