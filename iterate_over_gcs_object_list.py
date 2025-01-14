from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.gcs import GCSListObjectsOperator
from airflow.contrib.operators.gcs_to_gcs import GoogleCloudStorageToGoogleCloudStorageOperator
from airflow.decorators import task
from airflow.models.xcom_arg import XComArg
from datetime import datetime, timedelta

source_bucket = 'dags-bucket-test'
destination_bucket = 'target-gcs-copy-bucket'

def end_fun():
    print(f"Santash and Shubham End Task")

@task
def process_objects(objects):
    processed_objects = []
    for object_name in objects:
        print(f"Santash and Shubham first {object_name}")
        processed_objects.append(object_name)
    return processed_objects

@task
def create_copy_tasks(processed_objects):
    for object_name in processed_objects:
        gcs_move = GoogleCloudStorageToGoogleCloudStorageOperator(
            task_id=f'copy_{object_name}',
            source_bucket=source_bucket,
            source_object=object_name,
            destination_bucket=destination_bucket,
            destination_object=object_name,
        )
        gcs_move.execute(context=None)
        print(f"Santash and Shubham Second {object_name}")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='gcs_object_copy_dag',
    default_args=default_args,
    schedule_interval=timedelta(days=1),
) as dag:

    list_objects = GCSListObjectsOperator(
        task_id='list_objects',
        bucket=source_bucket,
    )

    process_task = process_objects(list_objects.output)

    copy_tasks = create_copy_tasks(process_task)

    end = PythonOperator(
        task_id='end_task',
        python_callable=end_fun,
    )

    list_objects >> process_task >> copy_tasks >> end
