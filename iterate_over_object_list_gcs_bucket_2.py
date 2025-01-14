from airflow import DAG
from airflow.contrib.operators.gcs_list_operator import GoogleCloudStorageListOperator
from airflow.contrib.operators.gcs_download_operator import GoogleCloudStorageDownloadOperator
from airflow.contrib.operators.gcs_to_gcs import GoogleCloudStorageToGoogleCloudStorageOperator
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta

source_bucket = 'dags-bucket-test'
destination_bucket = 'target-gcs-copy-bucket'

def generate_download_and_copy_tasks(**kwargs):
    ti = kwargs['ti']
    dag = kwargs['dag']
    objects = ti.xcom_pull(task_ids='list_objects')
    print(f"Santash and Shubham first {objects}")
    for object_name in objects:
        print(f"Santash and Shubham Second {object_name}")
        gcs_move = GoogleCloudStorageToGoogleCloudStorageOperator(
            task_id=f'copy_{object_name}',
            source_bucket=source_bucket,
            source_object=object_name,
            destination_bucket=destination_bucket,
            destination_object=object_name,
        )
        gcs_move.execute(context=None)
        download_task = GoogleCloudStorageDownloadOperator(
            task_id=f'download_{object_name}',
            bucket=source_bucket,
            object_name=object_name,
            filename=f'/tmp/{object_name}',
        )
        download_task.execute(context=None)


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    dag_id='gcs_object_copy_dag',
    default_args=default_args,
    schedule_interval=timedelta(days=1),
)
        
list_objects_task = GoogleCloudStorageListOperator(
    task_id='list_objects',
    bucket=source_bucket,
    dag=dag,
)


generate_tasks = PythonOperator(
    task_id='generate_tasks',
    python_callable=generate_download_and_copy_tasks,
    op_kwargs={'dag': dag},
    dag=dag,
)

list_objects_task >> generate_tasks
