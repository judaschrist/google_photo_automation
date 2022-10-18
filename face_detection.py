from distutils.log import error
from typing import List

from scipy.misc import face
from google_photo_api import GooglePhotoHelper
from google.cloud import vision_v1
import google_cloud_storage_api as cloud_api
import json
from PIL import Image
from io import BytesIO
import piexif

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
    print("Waiting for operation to complete...")
    response = operation.result(300)

    # The output is written to GCS with the provided output_uri as prefix
    gcs_output_uri = response.output_config.gcs_destination.uri
    output_put_filename = f"{output_file_prefix}output-1-to-{batch_size}.json"

    print("Output written to GCS with file name: {}".format(output_put_filename))
    return output_put_filename


def upload_face_detection_result(detect_result_file_name, bucket_name, dry_run=False):
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
            # get image creation time
            exif_dict = piexif.load(image.info['exif'])
            if exif_dict and piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
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
                    if exif_dict:
                        exif_dict['Exif'][piexif.ExifIFD.UserComment] = json.dumps(face).encode('utf-8')
                    exif_bytes = piexif.dump(exif_dict)
                    # get bytes from the cropped image
                    face_crop_bytes = BytesIO()
                    face_crop.save(face_crop_bytes, format='JPEG', exif=exif_bytes)
                    # save the cropped image to album
                    print('\t\tUploading face {} of {}'.format(i, ori_file_name))
                    helper.upload_image_to_photo_album(face_crop_bytes.getvalue(), f"{FACE_IMAGE_FILE_PREFIX}{image_creation_time}_{i}_{ori_file_name}", album_id)
                else:
                    print(face['boundingPoly']['vertices'])



def main():
    helper = GooglePhotoHelper()
    file_name_list = helper.upload_from_google_photo_to_bucket(2022, 10, 16, TEST_BUCKET_NAME, dry_run=False)
    detection_result_file = async_batch_annotate_images(TEST_BUCKET_NAME, file_name_list, '2022_10_16_', vision_v1.Feature.Type.FACE_DETECTION)
    upload_face_detection_result(detection_result_file, TEST_BUCKET_NAME)

if __name__ == '__main__':
    main()
    # upload_face_detection_result('2022_10_08_output-1-to-27.json', TEST_BUCKET_NAME, dry_run=False)                   
    
    # open image and read exif
    image = Image.open('/Users/lingxiao/Downloads/auto_detected_face_image_UNKONWN_TIME_0_IMG_6185.JPG')
    exif_dict = piexif.load(image.info['exif'])
    print(exif_dict['Exif'][piexif.ExifIFD.UserComment].decode('utf-8'))