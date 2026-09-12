"""Daily DAG: pull → validate → transform → refresh."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator

ROOT = Path(__file__).resolve().parents[2]
PYTHON = f"cd {ROOT} && PYTHONPATH={ROOT} python"

default_args = {
    "owner": "flowscope",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="flowscope_daily",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["flowscope", "etf", "flows"],
) as dag:
    pull_issuer = BashOperator(
        task_id="pull_issuer",
        bash_command=f"{PYTHON} -m ingestion.fetch_issuer_files",
    )
    pull_prices = BashOperator(
        task_id="pull_prices",
        bash_command=f"{PYTHON} -m ingestion.fetch_prices",
    )
    pull_macro = BashOperator(
        task_id="pull_macro",
        bash_command=f"{PYTHON} -m ingestion.fetch_macro",
    )
    validate = BashOperator(
        task_id="validate_silver",
        bash_command=f"{PYTHON} -m quality.run_expectations",
    )
    transform = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {ROOT}/dbt && dbt run --profiles-dir .",
    )

    [pull_issuer, pull_prices, pull_macro] >> transform >> validate
