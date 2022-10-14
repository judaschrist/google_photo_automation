from google.cloud import storage
import requests

def upload_url_to_google_cload(url, target_file_name, content_type, bucket_name):
    '''
    Uploads a file from a given url to a bucket
    '''
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(target_file_name)
    blob.upload_from_string(requests.get(url).content, content_type=content_type)


def read_file_from_google_cloud_to_string(file_name, bucket_name):
    '''
    Reads a file from a bucket
    '''
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    return blob.download_as_text()


def read_file_from_google_cloud_to_bytes(file_name, bucket_name):
    '''
    Reads a file from a bucket to bytes
    '''
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    return blob.download_as_bytes()


def read_file_from_gs_url_to_bytes(gs_url):
    storage_client = storage.Client()
    bucket_name = gs_url.split('/')[2]
    file_name = '/'.join(gs_url.split('/')[3:])
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    return blob.download_as_bytes()