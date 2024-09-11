from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.models import Variable
import requests
import json
from twilio.rest import Client
from airflow.utils.trigger_rule import TriggerRule
from google.cloud import bigquery
import pandas

#Get the variables from Airflow Variable
api_key = Variable.get("openweather_api_key")
account_sid = Variable.get("twilio_account_sid")
auth_token = Variable.get("twilio_auth_token")
from_phone_number = Variable.get("twilio_phone_number")
to_phone_number = Variable.get("recipient_phone_number")


def get_weather_data_and_send_sms(country, city):
    #Weather API URL for the forecast of the next day
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city},{country}&appid={api_key}&units=metric&cnt=2"

    #Make the API call
    response = requests.get(url)
    if response.status_code == 200:
        #Parse the response to get the min and max temperatures for the next day
        weather_data = response.json()
        next_day_data = weather_data['list'][1]  #Assuming the 2nd element is the next day
        min_temp = round(next_day_data['main']['temp_min'])
        max_temp = round(next_day_data['main']['temp_max'])

        #Format temperatures to display as '+number', '0', or '-number' based on value
        min_temp_formatted = f"{min_temp:+d}" if min_temp != 0 else "0"
        max_temp_formatted = f"{max_temp:+d}" if max_temp != 0 else "0"

        #Extract rain information and description if available
        rain_info = next_day_data.get('rain')
        weather_description = next_day_data['weather'][0]['description'] if 'weather' in next_day_data and next_day_data['weather'] else "No rain expected"

        #Prepare the message
        rain_message = f"Rain expected: {weather_description}" if rain_info else "No rain expected"
        message = f"Weather forecast for {city}/{country} (next day):\nMin Temperature: {min_temp_formatted}°C\nMax Temperature: {max_temp_formatted}°C\n{rain_message}"

        #Prepare the data to save
        weather_summary = {
            'city': city,
            'min_temp': min_temp,
            'max_temp': max_temp,
            'rain': bool(rain_info),  #True or False depending on the presence of rain data
            'rain_description': weather_description if rain_info else "No Rain"
        }

        weather_record = []
        weather_record.append(weather_summary)

        dataframe = pandas.DataFrame(
            weather_record,
            columns=[
                "city",
                "min_temp",
                "max_temp",
                "rain",
                "rain_description",
            ],
        )
        dataframe = dataframe.astype({
        'city': 'string',
        'min_temp': 'int64',
        'max_temp': 'int64',
        'rain': 'bool',
        'rain_description': 'string'
    })
        client = bigquery.Client()
        table_id = "data-engineering-poc-435112.weather_data.maharashtra_weather_report_composer"
        job_config = bigquery.LoadJobConfig(
            schema=[
                bigquery.SchemaField("city", "STRING"),
                bigquery.SchemaField("min_temp", "INTEGER"),
                bigquery.SchemaField("max_temp", "INTEGER"),
                bigquery.SchemaField("rain", "BOOLEAN"),
                bigquery.SchemaField("rain_description", "STRING"),
            ],
        )
        job = client.load_table_from_dataframe(
            dataframe, table_id, job_config=job_config
        )
        job.result()
        print(f"\nWeather data saved to {table_id} BigQuery table")
        #Send the message via SMS using Twilio
        client = Client(account_sid, auth_token)
        client.messages.create(body=message, from_=from_phone_number, to=to_phone_number)
    else:
        raise Exception(f"Failed to fetch weather data for {city}/{country}")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2024, 09, 11),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "weather_forecast_sms",
    default_args=default_args,
    schedule_interval="0 7 * * *",  #Run daily at 07:00 AM UTC
    catchup=False,
)

get_weather_data_pune = PythonOperator(
    task_id="get_weather_data_pune",
    python_callable=get_weather_data_and_send_sms,
    op_args=["IN", "Pune"],
    dag=dag,
)

get_weather_data_mumbai = PythonOperator(
    task_id="get_weather_data_mumbai",
    python_callable=get_weather_data_and_send_sms,
    op_args=["IN", "Mumbai"],
    dag=dag,
    trigger_rule=TriggerRule.ALL_DONE,  #This will ensure the task runs regardless of upstream task success/failure
)

get_weather_data_pune >> get_weather_data_mumbai