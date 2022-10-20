## deploy

```
gcloud functions deploy python-pubsub-function \
--gen2 \
--runtime=python310 \
--region=REGION \
--source=. \
--entry-point=subscribe \
--trigger-topic=YOUR_TOPIC_NAME
```

see [this](https://cloud.google.com/functions/docs/tutorials/pubsub)