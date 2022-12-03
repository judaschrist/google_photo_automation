## Todos

- [X] standardize logging
- [ ] Logging is not working for the new google cloud API
- [ ] How to proccess photos that are not uploaded in time?
- [ ] what if processing time exceeds the limited timeout?
- [ ] support face detection for videos
- [ ] instruction for deployment
- [ ] script for automated deployment

## project structure

[Ref](https://cloud.google.com/functions/docs/writing/write-event-driven-functions)

## deploy

```
gcloud functions deploy google-photo-face-detection \
--gen2 \
--runtime=python38 \
--region=europe-west2 \
--source=. \
--entry-point=main \
--trigger-topic=recurring_jobs \
--memory=512MiB \
--timeout=540 \
--run-service-account="gpa-service@astute-maxim-365110.iam.gserviceaccount.com"
```

see [all CLI flags](https://cloud.google.com/sdk/gcloud/reference/functions/deploy)


## test locally

send a message
```
gcloud pubsub topics publish recurring_jobs --message="{\"dry_run\": true, \"days_past\": 3}"
```
read results in log:
```
gcloud beta functions logs read google-photo-face-detection --gen2
```

[Ref](https://cloud.google.com/functions/docs/tutorials/pubsub#triggering_the_function)
