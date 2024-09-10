# GCP Composer Weather Forecast SMS Notifications and Store the data in Bigquery

## Note: https://medium.com/apache-airflow/%EF%B8%8Fgcp-data-engineering-project-automating-weather-forecast-sms-notifications-with-composer-airflow-a667feaee19f

## Note: https://github.com/janaom/gcp-de-project-weather-forecast-sms-with-airflow/tree/main

## We will need twilio account and openweather account for this pipeline setup

## In GCP Free trial account we have to create Cloud Composer 3 since the Cloud Composer 2 will fail to create (Error was regarding pods not created because of quota limitations in free trial account): https://stackoverflow.com/questions/78597995/google-cloud-composer-creation-failing-for-all-types-of-environment-sizes-and-ve

## We have to put our file in DAG folder also mention twilio and pandas in PyPI Packages option present in Conposer UI

