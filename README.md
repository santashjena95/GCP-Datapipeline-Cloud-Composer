# GCP Composer Weather Forecast SMS Notifications and Store the data in Bigquery

## Note: https://medium.com/apache-airflow/%EF%B8%8Fgcp-data-engineering-project-automating-weather-forecast-sms-notifications-with-composer-airflow-a667feaee19f

## Note: https://github.com/janaom/gcp-de-project-weather-forecast-sms-with-airflow/tree/main

## We will need twilio account and openweather account for this pipeline setup

## In GCP Free trial account we have to create Cloud Composer 3 since the Cloud Composer 2 will fail to create (Error was regarding pods not created because of quota limitations in free trial account): https://stackoverflow.com/questions/78597995/google-cloud-composer-creation-failing-for-all-types-of-environment-sizes-and-ve

## We have to put our file in DAG folder also mention twilio, pandas and google-cloud-bigquery in PyPI Packages option present in Conposer UI

## Make sure to add "openweather_api_key", "recipient_phone_number", "twilio_account_sid", "twilio_auth_token" and "twilio_phone_number" variables in airflow url (refer the attached screenshots)

## If this is the first time you are creating composer in the gcp project, then remember to grant the Cloud Composer v2 API Service Agent Extension role to the Cloud Composer Service Agent service account

## NOTE: When we create Cloud Composer 2 it creates Kubernetes Cluster and in free trial that exceeds quota and results in Composer failure but in Cloud Composer 3 it doesn't create kubernetes cluster hence we are able to create composer 3 environment in free trial account