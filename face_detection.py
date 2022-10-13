from photo_api import TEST_BUCKET_NAME
from google.cloud import vision_v1


def sample_async_batch_annotate_images(
    bucket_name,
    input_image_file_name_list=["gs://test-bucket-gpa/IMG_6010.JPG"],
    output_file_name="gs://test-bucket-gpa/IMG_6010",
):
    """
    Perform async batch image annotation.
    """
    client = vision_v1.ImageAnnotatorClient()

    features = [
        {"type_": vision_v1.Feature.Type.FACE_DETECTION},
    ]

    # Each requests element corresponds to a single image.  To annotate more
    # images, create a request element for each image and add it to
    # the array of requests
    # requests = [{"image": image, "features": features}]
    requests = [{"image": {"source":  {"image_uri": f"gs://{bucket_name}/{file_name}"}}, "features": features} for file_name in input_image_file_name_list]
    gcs_destination = {"uri": f"gs://{bucket_name}/{output_file_name}"}

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



if __name__ == '__main__':
    # detect_faces('/Users/lingxiao/Downloads/IMG_6010.JPG')
    sample_async_batch_annotate_images(TEST_BUCKET_NAME, ['2022_10_9_uploaded_at_20221013_145536_IMG_8461.JPG', '2022_10_9_uploaded_at_20221013_145540_IMG_8460.JPG', '2022_10_9_uploaded_at_20221013_145543_IMG_8459.JPG', '2022_10_9_uploaded_at_20221013_145547_IMG_6083.MOV', '2022_10_9_uploaded_at_20221013_145559_IMG_6082.HEIC', '2022_10_9_uploaded_at_20221013_145604_IMG_6081.HEIC', '2022_10_9_uploaded_at_20221013_145609_IMG_6080.HEIC', '2022_10_9_uploaded_at_20221013_145613_IMG_6079.HEIC', '2022_10_9_uploaded_at_20221013_145617_IMG_6078.HEIC', '2022_10_9_uploaded_at_20221013_145622_IMG_6077.HEIC', '2022_10_9_uploaded_at_20221013_145627_IMG_6076.HEIC', '2022_10_9_uploaded_at_20221013_145631_IMG_6075.MOV', '2022_10_9_uploaded_at_20221013_145640_IMG_8458.JPG', '2022_10_9_uploaded_at_20221013_145645_IMG_8457.JPG', '2022_10_9_uploaded_at_20221013_145650_IMG_8456.JPG', '2022_10_9_uploaded_at_20221013_145655_IMG_8455.JPG', '2022_10_9_uploaded_at_20221013_145659_IMG_8454.JPG', '2022_10_9_uploaded_at_20221013_145704_IMG_8453.JPG', '2022_10_9_uploaded_at_20221013_145709_IMG_8452.JPG', '2022_10_9_uploaded_at_20221013_145715_IMG_8447.JPG', '2022_10_9_uploaded_at_20221013_145720_IMG_8446.JPG'], 'output-test')