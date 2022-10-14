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
    file_name_list = helper.upload_from_google_photo_to_bucket(2022, 10, 11, TEST_BUCKET_NAME, dry_run=False)
    async_batch_annotate_images(TEST_BUCKET_NAME, file_name_list, 'test_', vision_v1.Feature.Type.FACE_DETECTION)


if __name__ == '__main__':
    #read json from string:
    face_detection_result_json = json.loads(cloud_api.read_file_from_google_cloud_to_string('test_output-1-to-14.json', TEST_BUCKET_NAME))
    for detection_res in face_detection_result_json['responses']:
        file_url = detection_res['context']['uri']
        #open image from bytes
        image = Image.open(BytesIO(cloud_api.read_file_from_gs_url_to_bytes(file_url)))
        image.show()
        if 'error' in detection_res:
            continue
        if 'faceAnnotations' in detection_res:
            for faces in detection_res['faceAnnotations']:
                image.crop((faces['boundingPoly']['vertices'][0]['x'], 
                            faces['boundingPoly']['vertices'][0]['y'], faces['boundingPoly']['vertices'][2]['x'], faces['boundingPoly']['vertices'][2]['y'])).show()
            
