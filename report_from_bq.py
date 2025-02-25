import os
import json
import db_dtypes
import pandas as pd
from datetime import date, timedelta, datetime, timezone
import logging

from google.cloud import logging as cloud_logging
from google.cloud import bigquery
from google.cloud import storage

from airflow.utils.dates import days_ago
from datetime import timedelta, date
from airflow import DAG
from airflow import models
from airflow.operators import python_operator

default_args = {
    "owner": "composer",
    "start_date": days_ago(1),
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with models.DAG(
    'BQ_Report',
    default_args=default_args,
    description="Daily BQ Report Generation",
    schedule_interval='32 10,11 * * *',
    catchup=False
) as dag_python:

    def check_time(today):
        logging.info("Executing check_time function...")
        try:
            current_time = datetime.now(timezone.utc)
            target_time = current_time.replace(hour=11, minute=30, second=0, microsecond=0)
            
            if current_time >= target_time:
                logging.info("Time is above 11:30 AM UTC")
                query_file_path = 'reprocess_execute.sql'
                destination_blob_name = "reprocess_s2t_bq_report_"+today+".csv"
                destination_blob_name_interactionids = "reprocess_failed_interaction_ids_"+today+".csv"
                return 1,query_file_path,destination_blob_name,destination_blob_name_interactionids
                
            else:
                logging.warning("Time is not above 11:30 AM UTC")
                query_file_path = 'execute.sql'
                destination_blob_name = "s2t_bq_report_"+today+".csv"
                destination_blob_name_interactionids = "failed_interaction_ids_"+today+".csv"
                return 0,query_file_path,destination_blob_name,destination_blob_name_interactionids
        except Exception as ex:
            logging.error(f'Error Something went wrong in check_time: {ex}')

    def create_and_upload_csv(sum_interaction_ids, sum_trs_interactions_success, sum_difference, percent_failed, bucket_name, destination_blob_name, project_id, order_date, today, google_alternate_error_count, metadata_error_count, end_offset_error_count, other_error_count):
        logging.info("Executing create_and_upload_csv function...")
        try:
            data = {
                "Order Date": [order_date],
                "Process Date": [today],
                "PR2 Interactions": [sum_interaction_ids],
                "Transcripts Success": [sum_trs_interactions_success],
                "Difference": [sum_difference],
                "% failed": [percent_failed],
                "alternatives attribute missing from google generated transcript (Reprocessing not required)": [google_alternate_error_count],
                "metadata json or transcript not exist error": [metadata_error_count],
                "Something went wrong in construct_transcript_json: 'endOffset'": [end_offset_error_count],
                "Other Error Count": [other_error_count]
            }
            df = pd.DataFrame(data)

            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(destination_blob_name)
            blob.upload_from_string(df.to_csv(index=False), 'text/csv')
            logging.info(f"BQ Report file uploaded to {bucket_name}/{destination_blob_name}.")
        except Exception as ex:
            logging.error(f'Error Something went wrong in create_and_upload_csv: {ex}')

    def reprocessing_upload(interaction_id_dataframe_reprocessing, reprocessing_bucket_name, reprocessing_destination_blob_name, project_id, today):
        logging.info("Executing reprocessing_upload function...")
        try:
            df = pd.DataFrame()
            df['interaction_ids'] = interaction_id_dataframe_reprocessing['interaction_id']

            storage_client = storage.Client(project=project_id)
            bucket = storage_client.bucket(reprocessing_bucket_name)
            blob = bucket.blob(reprocessing_destination_blob_name)
            blob.upload_from_string(df.to_csv(index=False), 'text/csv')
            logging.info(f"Reprocessing interaction_ids file uploaded to {reprocessing_bucket_name}/{reprocessing_destination_blob_name} on {today}.")
        except Exception as ex:
            logging.error(f'Error Something went wrong in reprocessing_upload: {ex}')

    def list_logs(project_id, today):
        logging.info("Executing list_logs function...")
        try:
            client = cloud_logging.Client(project=project_id)
            extract_time_start = today+"T00:00:00.000Z"
            extract_time_end = today+"T23:59:59.999Z"
            time_filter = f'timestamp>="{extract_time_start}" AND timestamp<="{extract_time_end}"'
            filter_str = f'resource.type="cloud_function" AND textPayload =~ "Total records retrieved from PR2:*" AND logName="projects/{project_id}/logs/cloudfunctions.googleapis.com%2Fcloud-functions" AND resource.labels.function_name="bigquery-poc" AND {time_filter}'

            for entry in client.list_entries(filter_=filter_str):
                try:
                    number_str = entry.payload.split(": ")[1]
                    number = int(number_str)
                    return number
                except IndexError as e:
                    logging.error(f'Failed list_logs getting IndexError: {e}')
                    return 0
            logging.info("Failed list_logs didnt enter for loop")
            return 0
        except Exception as ex:
            logging.error(f'Error Something went wrong in list_logs: {ex}')
            return 0

    def other_error_count_query(project_id, today, formatted_guids):
        logging.info("Executing other_error_count_query function...")
        try:
            query = """ SELECT interaction_id, message FROM `dataproc_gcs_to_bq.interaction_message` WHERE interaction_id="123asdebkbackasxasbdxqbdkbkb13e973e612" """
            #formatted_query = query.format(formatted_guids, today, today, formatted_guids, formatted_guids)
            client = bigquery.Client(project=project_id)
            query_job = client.query(query)
            results = query_job.result()
            df = results.to_dataframe()
            logging.info("Completed other_error_count_query function...")
            return df
        except Exception as ex:
            logging.error(f'Error Something went wrong in other_error_count_query: {ex}')

    def execute_query(project_id, query):
        logging.info("Executing execute_query function...")
        try:
            client = bigquery.Client(project=project_id)
            query_job = client.query(query)
            results = query_job.result()
            df = results.to_dataframe()
            logging.info("Completed execute_query function...")
            return df
        except Exception as ex:
            logging.error(f'Error Something went wrong in execute_query: {ex}')

    def read_query_from_file(file_path, process_date):
        logging.info("Executing read_query_from_file function...")
        try:
            current_dir_path = os.path.abspath(os.path.dirname(__file__))
            common_config_file = os.path.join(current_dir_path, file_path)
            with open(common_config_file, 'r') as file:
                file_content = file.read()
                updated_content = file_content.replace('update_process_date', process_date)
                logging.info("Completed read_query_from_file function...")
                return updated_content
        except Exception as ex:
            logging.error(f'Error Something went wrong in execute_query: {ex}')

    def detect_env(project_id):
        logging.info("Executing detect_env function...")
        try:
            if project_id and project_id.lower() == "db-dev-zzss-voice-surv":
                os.environ["env"] = "dev"
            elif project_id and project_id.lower() == "db-uat-n1vi-dbmacs-voice-surv":
                os.environ["env"] = "uat"
            elif project_id and project_id.lower() == "db-prd-1kzd-dbmacs-voice-cuat":
                os.environ["env"] = "cuat"
            elif project_id and project_id.lower() == "db-prd-7q33-dbmacs-voice-surv":
                os.environ["env"] = "prd"
            else:
                os.environ["env"] = "test"
            runtime_env = os.environ.get('env').lower()
            logging.info("Completed detect_env function...")
            return runtime_env
        except Exception as ex:
            logging.error(f'Error Something went wrong in detect_env: {ex}')

    def read_config_json(env):
        logging.info("Executing read_config_json function...")
        current_dir_path = os.path.abspath(os.path.dirname(__file__))
        
        try:
            if env and env == 'dev':
                common_config_file = os.path.join(current_dir_path, 'dev_config.json')
                with open(common_config_file, "r") as dev_config:
                    return json.load(dev_config)
            elif env and env == 'uat':
                with open("./uat_config.json", "r") as uat_config:
                    return json.load(uat_config)
            elif env and env == 'cuat':
                with open("./conuat_config.json", "r") as conuat_config:
                    return json.load(conuat_config)
            elif env and env == 'prd':
                with open("./prod_config.json", "r") as prod_config:
                    return json.load(prod_config)
            else:
                with open("./bqreport/src/main/test_config.json", "r") as test_config:
                    return json.load(test_config)
        except Exception as ex:
            logging.error(f'Error Something went wrong in read_config_json: {ex}')

    def execute_bigquery_count(query, project_id):
        logging.info("Executing execute_bigquery_count function...")
        try:
            client = bigquery.Client(project=project_id)
            query_job = client.query(query)
            results = query_job.result()
            df = results.to_dataframe()
            count = df['interaction_id'].count()
            logging.info("Completed execute_bigquery_count function...")
            return df,count
        except Exception as ex:
            logging.error(f'Error Something went wrong in execute_bigquery_count: {ex}')
            return None, None

    def formatted_query(today, formatted_guids, messages_like):
        logging.info("Executing formatted_query function...")
        try:
            if not (isinstance(today, str) and isinstance(formatted_guids, str) and isinstance(messages_like, str)):
                raise ValueError("Invalid input parameters")
            
            if today == "invalid-date" or formatted_guids == "invalid-guids" or messages_like == "invalid-message":
                raise ValueError("Detected invalid inputs for the query")
            #query = """ SELECT DISTINCT interaction_id, message FROM `dataproc_gcs_to_bq.interaction_message` WHERE message like "%{}" """
            query = """ SELECT DISTINCT interaction_id, message FROM `voice_surv_stt.voice-surv_transcript_audit` WHERE insertion_date BETWEEN DATETIME("{}") AND DATETIME_ADD(DATETIME("{}"), INTERVAL 1 DAY) AND request_guid IN ({}) AND status="Failed" AND message like "%{}" """
            formatted_query = query.format(today, today, formatted_guids, messages_like)
            logging.info("Completed formatted_query function...")
            return formatted_query
        except Exception as ex:
            logging.error(f'Error Something went wrong in formatted_query: {ex}')
            return None

    def bq_report():
        logging.info("Executing bq_report function...")
        project_id = os.environ["GCP_PROJECT"]
        runtime_env = detect_env(project_id)
        config = json.loads(json.dumps(read_config_json(runtime_env)))
        try:
            bucket_name = config['settings']['bucket_name']
            today = str(date.today())
            log_num = list_logs(project_id, today)
            if log_num:
                reprocess_run,query_file_path,destination_blob_name,destination_blob_name_interactionids = check_time(today)

                sql_query = read_query_from_file(query_file_path, today)
                df = execute_query(project_id, sql_query)
                df['interaction_ids'] = pd.to_numeric(df['interaction_ids'])
                sum_interaction_ids = int(df['interaction_ids'].sum())
                if (log_num == sum_interaction_ids) or (reprocess_run == 1):
                    logging.info("All records processed successfully")
                    df['trs_interactions_success'] = pd.to_numeric(df['trs_interactions_success'])
                    sum_trs_interactions_success = df['trs_interactions_success'].sum()
                    df['Difference'] = pd.to_numeric(df['Difference'])
                    sum_difference = int(df['Difference'].sum())
                    percent_failed = (sum_difference/sum_interaction_ids)*100
                    order_date = str(date.today() - timedelta(days=1))

                    request_guid_list = df['request_guid'].astype(str).tolist()
                    formatted_guids = '"' + '","'.join(request_guid_list) + '"'
                    
                    formatted_end_offset_error_query = formatted_query(today, formatted_guids, "construct_transcript_json: 'endOffset'")
                    df_end_offset_error_count,end_offset_error_count = execute_bigquery_count(formatted_end_offset_error_query, project_id)

                    formatted_google_alternate_error_query = formatted_query(today, formatted_guids, "generated transcript")
                    df_google_alternate_error_count,google_alternate_error_count = execute_bigquery_count(formatted_google_alternate_error_query, project_id)

                    formatted_metadata_error_query = formatted_query(today, formatted_guids, "ffmpeg exited with code 1")
                    df_metadata_error_count,metadata_error_count = execute_bigquery_count(formatted_metadata_error_query, project_id)
                    
                    other_error_count_df = other_error_count_query(project_id, today, formatted_guids)

                    error_interaction_id_dataframe = pd.concat([df_end_offset_error_count, df_google_alternate_error_count, df_metadata_error_count, other_error_count_df], ignore_index=True)
                    interaction_id_dataframe_reprocessing = pd.concat([df_end_offset_error_count, df_metadata_error_count, other_error_count_df], ignore_index=True)
                    other_error_count = sum_difference - (end_offset_error_count + google_alternate_error_count + metadata_error_count)
                    
                    storage_client = storage.Client(project=project_id)
                    bucket = storage_client.bucket(bucket_name)
                    blob = bucket.blob(destination_blob_name_interactionids)
                    blob.upload_from_string(error_interaction_id_dataframe.to_csv(index=False), 'text/csv')
                    logging.info(f"Failure Interaction Ids file uploaded to {bucket_name}/{destination_blob_name}.")

                    create_and_upload_csv(sum_interaction_ids, sum_trs_interactions_success, sum_difference, percent_failed, bucket_name, destination_blob_name, project_id, order_date, today, google_alternate_error_count, metadata_error_count, end_offset_error_count, other_error_count)
                    if ((sum_difference - (metadata_error_count + end_offset_error_count + other_error_count)) != 0) and (reprocess_run != 1):
                        reprocessing_bucket_name = config['settings']['reprocessing_bucket_name']
                        today_date = today.replace("-", "")
                        reprocessing_destination_blob_name = "speech_to_text_interaction_id_BAU_"+today_date+".csv"
                        reprocessing_upload(interaction_id_dataframe_reprocessing, reprocessing_bucket_name, reprocessing_destination_blob_name, project_id, today)
                    else:
                        logging.info(f"Reprocessing completed and files are uploaded to {bucket_name} on {today}")
                    return "BQ Report and Failure Interaction Ids Report Generated successfully"
                else:
                    logging.warning("Failed Not All records processed successfully")
                    return "Failed generating BQ Report As Not all records processed successfully"            
            else:
                logging.warning('Failed No "Total records retrieved from PR2:" logs present for today')
                return 'Failed generating BQ Report As No "Total records retrieved from PR2:" logs present for today'

        except Exception as ex:
            logging.error(f'Error Something went wrong in bq_report: {ex}')
            return 'Failed BQ Report and Failure Interaction Ids Report Generation'

BQ_Report = python_operator.PythonOperator(
    task_id='BQ_Report',
    python_callable=bq_report,
    dag=dag_python
)
