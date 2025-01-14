import pendulum

from airflow.models import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import BranchPythonOperator

with DAG("loop_example") as dag:

    first = DummyOperator(task_id="first")
    last = DummyOperator(task_id="last")

    options = ["branch_a", "branch_b", "branch_c", "branch_d"]
    for option in options:
        t = DummyOperator(task_id=option)
        first >> t >> last
