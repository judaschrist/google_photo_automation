## Todos

- [ ] standardize logging
- [ ] support face detection for videos

## project structure

see [this](https://cloud.google.com/functions/docs/writing/write-event-driven-functions)

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
--timeout=540
```

see [this](https://cloud.google.com/functions/docs/tutorials/pubsub)


## test locally

send a message
```
gcloud pubsub topics publish recurring_jobs --message="{\"dry_run\": true, \"days_past\": 3}"
```
read results in log:
```
gcloud beta functions logs read google-photo-face-detection --gen2
```

see [this](https://cloud.google.com/functions/docs/tutorials/pubsub#triggering_the_function)