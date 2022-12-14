from typing import List

from google_photo_api import GooglePhotoHelper
from google.cloud import vision_v1
from google_cloud_storage_api import GoogleStorageHelper
import json
from PIL import Image
from io import BytesIO
import piexif
import functions_framework
from datetime import datetime, timedelta
import base64
from cloudevents.http.event import CloudEvent
from google_logging import structured_log

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
    return: the output file name
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
    structured_log("Waiting for operation to complete...")
    response = operation.result(300)

    # The output is written to GCS with the provided output_uri as prefix
    output_put_filename = f"{output_file_prefix}output-1-to-{batch_size}.json"

    structured_log("Output written to GCS with file name: {}".format(output_put_filename))
    return output_put_filename


def upload_face_detection_result(photo_api_helper, detect_result_file_name, file_name_dict, bucket_name, dry_run=False):
    storage_helper = GoogleStorageHelper(bucket_name)
    album_id = photo_api_helper.upsert_album(FACE_ALBUM_NAME)
    face_detection_result_json = json.loads(storage_helper.read_file_from_google_cloud_to_string(detect_result_file_name))
    for detection_res in face_detection_result_json['responses']:
        file_url = detection_res['context']['uri']
        ori_file_name = file_url.split('/')[-1]
        if 'error' in detection_res:
            continue
        if 'faceAnnotations' in detection_res:
            structured_log('======== Found {} faces in {}'.format(len(detection_res['faceAnnotations']), ori_file_name))
            image = Image.open(BytesIO(file_name_dict[ori_file_name]))
            # get image creation time
            try:
                exif_dict = piexif.load(image.info['exif'])
            except KeyError:
                # some images does not have proper exif data altogether
                exif_dict = {"0th": {}, "Exif": {}}
            if piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
                image_creation_time = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal][:10].decode('utf-8')
            else:
                image_creation_time = 'UNKONWN_TIME'
            for i, face in enumerate(detection_res['faceAnnotations']):
                if not dry_run:
                    # crop the faces from the image
                    face_crop = image.crop((
                        face['boundingPoly']['vertices'][0]['x'] if 'x' in face['boundingPoly']['vertices'][0] else 0,
                        face['boundingPoly']['vertices'][0]['y'] if 'y' in face['boundingPoly']['vertices'][0] else 0,
                        face['boundingPoly']['vertices'][2]['x'] if 'x' in face['boundingPoly']['vertices'][2] else image.width,
                        face['boundingPoly']['vertices'][2]['y'] if 'y' in face['boundingPoly']['vertices'][2] else image.height,
                    ))
                    # add face detection meta data to exif
                    exif_dict = {"0th": {}, "Exif": {}}
                    exif_dict['Exif'][piexif.ExifIFD.UserComment] = json.dumps(face).encode('utf-8')
                    exif_bytes = piexif.dump(exif_dict)
                    # get bytes from the cropped image
                    face_crop_bytes = BytesIO()
                    face_crop.save(face_crop_bytes, format='JPEG', exif=exif_bytes)
                    # save the cropped image to album
                    structured_log('Uploading face {} of {}'.format(i, ori_file_name))
                    # get file name witout extension
                    file_name_without_ext = ori_file_name.split('.')[0]
                    photo_api_helper.upload_image_to_photo_album(face_crop_bytes.getvalue(), f"{FACE_IMAGE_FILE_PREFIX}{image_creation_time}_{i}_{file_name_without_ext}.jpeg", album_id)
                else:
                    structured_log(face['boundingPoly']['vertices'])


def face_image_generation_for_google_photo(year, month, day, dry_run=False):
    '''
    Generate face images for google photo for a given date.
    face images will be saved to a google photo album named 'auto_detected_face_images'
    args:
        year: 4 digits integer
        month: 2 digits integer
        day: 2 digits integer
    '''
    structured_log('======= processing image from {}-{}-{} ========'.format(year, month, day))
    if dry_run:
        structured_log('=== dry run mode ===')
    helper = GooglePhotoHelper()
    file_name_dict = helper.upload_from_google_photo_to_bucket(year, month, day, TEST_BUCKET_NAME, dry_run=dry_run, upload_photo=True, upload_video=False, exclude_file_prefix=FACE_IMAGE_FILE_PREFIX)
    if not file_name_dict:
        structured_log('No image found for {}-{}-{}'.format(year, month, day))
        return
    detection_result_file = async_batch_annotate_images(TEST_BUCKET_NAME, file_name_dict.keys(), f'{year}_{month}_{day}_', vision_v1.Feature.Type.FACE_DETECTION)
    upload_face_detection_result(helper, detection_result_file, file_name_dict, TEST_BUCKET_NAME)


# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def main(cloud_event: CloudEvent):
    structured_log("=================== PROCESS START FOR" + base64.b64decode(cloud_event.data["message"]["data"]).decode() + '=====================')
    msg_json = json.loads(base64.b64decode(cloud_event.data["message"]["data"]).decode())
    days_past = msg_json['days_past']
    dry_run = msg_json['dry_run']
    target_day = datetime.now() - timedelta(days=days_past)
    year = target_day.year
    month = target_day.month
    day = target_day.day
    face_image_generation_for_google_photo(year, month, day, dry_run=dry_run)
    structured_log("=================== PROCESS END FOR" + base64.b64decode(cloud_event.data["message"]["data"]).decode() + '=====================')


def batch_process_photo(year, month, day):
    # batch process photo
    cur_date = datetime(year, month, day)
    while cur_date < datetime(2022, 10, 10):
        face_image_generation_for_google_photo(cur_date.year, cur_date.month, cur_date.day)
        cur_date += timedelta(days=1)

def test_main():
    msg = {
        "message": {
            "data": base64.b64encode(json.dumps({
                                "dry_run": True,
                                "days_past": 3
                            }).encode('utf-8'))
        }
    }
    cloud_event = CloudEvent({
        "type": "test",
        "source": "local_test",
    }, msg)
    main(cloud_event)

# run this locally as an integrated test
if __name__ == '__main__':
    pass
    # test_main()
    # face_image_generation_for_google_photo(2022, 10, 29, dry_run=False)
    # helper = GooglePhotoHelper()
    # upload_face_detection_result(helper, '2021_12_5_output-1-to-7.json', TEST_BUCKET_NAME)
    # batch_process_photo(2022, 10, 29)

