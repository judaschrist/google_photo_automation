from distutils.log import error
from typing import List

from scipy.misc import face
from google_photo_api import GooglePhotoHelper
from google.cloud import vision_v1
import google_cloud_storage_api as cloud_api
import json
from PIL import Image
from io import BytesIO

TEST_BUCKET_NAME = "test-bucket-gpa"
FACE_IMAGE_FILE_PREFIX = 'auto_detected_face_image_'
FACE_ALBUM_NAME = 'auto_detected_face_images'

def async_batch_annotate_images(
    bucket_name: str,
    input_image_file_name_list: List[str],
    output_file_prefix: str,
    annotation_type: vision_v1.Feature.Type,
):
    """
    Perform async batch image annotation.
    """
    client = vision_v1.ImageAnnotatorClient()

    features = [
        {"type_": annotation_type},
    ]

    # Each requests element corresponds to a single image.  To annotate more
    # images, create a request element for each image and add it to
    # the array of requests
    # requests = [{"image": image, "features": features}]
    requests = [{"image": {"source":  {"image_uri": f"gs://{bucket_name}/{file_name}"}}, "features": features} for file_name in input_image_file_name_list]
    gcs_destination = {"uri": f"gs://{bucket_name}/{output_file_prefix}"}

    # The max number of responses to output in each JSON file
    batch_size = len(input_image_file_name_list)
    output_config = {"gcs_destination": gcs_destination,
                     "batch_size": batch_size}

    operation = client.async_batch_annotate_images(requests=requests, output_config=output_config)

    # TODO deal with timeout cases
    print("Waiting for operation to complete...")
    response = operation.result(300)

    # The output is written to GCS with the provided output_uri as prefix
    gcs_output_uri = response.output_config.gcs_destination.uri
    print("Output written to GCS with prefix: {}".format(gcs_output_uri))


def main():
    helper = GooglePhotoHelper()
    file_name_list = helper.upload_from_google_photo_to_bucket(2022, 10, 8, TEST_BUCKET_NAME, dry_run=False)
    async_batch_annotate_images(TEST_BUCKET_NAME, file_name_list, '2022_10_08_', vision_v1.Feature.Type.FACE_DETECTION)

def upload_face_detection_result(detect_result_file_name, bucket_name):
    # TODO: add date to the detected face image file name
    # TODO: think about how to save other face informations like face landmarks
    helper = GooglePhotoHelper()
    album_id = helper.upsert_album(FACE_ALBUM_NAME)
    face_detection_result_json = json.loads(cloud_api.read_file_from_google_cloud_to_string(detect_result_file_name, bucket_name))
    for detection_res in face_detection_result_json['responses']:
        file_url = detection_res['context']['uri']
        ori_file_name = file_url.split('/')[-1]
        if 'error' in detection_res:
            continue
        if 'faceAnnotations' in detection_res:
            print('======== Found {} faces in {}'.format(len(detection_res['faceAnnotations']), ori_file_name))
            image = Image.open(BytesIO(cloud_api.read_file_from_gs_url_to_bytes(file_url)))
            for i, face in enumerate(detection_res['faceAnnotations']):
                print('\t\tUploading face {} of {}'.format(i, ori_file_name))
                # crop the faces from the image
                face_crop = image.crop((
                    face['boundingPoly']['vertices'][0]['x'], 
                    face['boundingPoly']['vertices'][0]['y'],
                    face['boundingPoly']['vertices'][2]['x'],
                    face['boundingPoly']['vertices'][2]['y']
                ))
                # get bytes from the cropped image
                face_crop_bytes = BytesIO()
                face_crop.save(face_crop_bytes, format='JPEG')
                # save the cropped image to album
                helper.upload_image_to_photo_album(face_crop_bytes.getvalue(), f"{FACE_IMAGE_FILE_PREFIX}{i}_{ori_file_name}", album_id)


if __name__ == '__main__':
    # main()
    upload_face_detection_result('2022_10_08_output-1-to-27.json', TEST_BUCKET_NAME)                      
