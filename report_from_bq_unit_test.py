import unittest
from unittest.mock import patch, MagicMock
import os
import pandas as pd
import sys
from pathlib import Path
from datetime import date, timedelta, datetime, timezone
from google.cloud import bigquery, storage, logging


# Import the functions to be tested
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[3]
sys.path.append(str(root))
from src.main.bqreport import bqreport

TEST_QUERY = "SELECT * FROM test_table"
TEST_EXCEPTION = "Test Exception"
os.environ["GCP_PROJECT"] = "test-project"

class TestCheckTime(unittest.TestCase):
    @patch('src.main.bqreport.bqreport.datetime')
    def test_check_time_before_target(self, mock_datetime):
        mock_now = datetime(2023, 10, 5, 5, 0, 0)
        mock_now = mock_now.replace(tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.timezone = timezone

        reprocess_run, query_file_path, destination_blob_name, destination_blob_name_interactionids = bqreport.check_time('2023-10-05')
        
        self.assertEqual(reprocess_run, 0)
        self.assertEqual(query_file_path, 'execute.sql')
        self.assertEqual(destination_blob_name, 's2t_bq_report_2023-10-05.csv')
        self.assertEqual(destination_blob_name_interactionids, 'failed_interaction_ids_2023-10-05.csv')

    @patch('src.main.bqreport.bqreport.datetime')
    def test_check_time_after_target(self, mock_datetime):
        mock_now = datetime(2023, 10, 6, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        reprocess_run, query_file_path, destination_blob_name, destination_blob_name_interactionids = bqreport.check_time('2023-10-06')
        
        self.assertEqual(reprocess_run, 1)
        self.assertEqual(query_file_path, 'reprocess_execute.sql')
        self.assertEqual(destination_blob_name, 'reprocess_s2t_bq_report_2023-10-06.csv')
        self.assertEqual(destination_blob_name_interactionids, 'reprocess_failed_interaction_ids_2023-10-06.csv')

    @patch('src.main.bqreport.bqreport.datetime')
    def test_check_time_at_target(self, mock_datetime):
        # Mock current time to be exactly at 11:30 AM UTC
        mock_now = datetime(2023, 10, 7, 11, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        reprocess_run, query_file_path, destination_blob_name, destination_blob_name_interactionids = bqreport.check_time('2023-10-07')
        
        self.assertEqual(reprocess_run, 1)
        self.assertEqual(query_file_path, 'reprocess_execute.sql')
        self.assertEqual(destination_blob_name, 'reprocess_s2t_bq_report_2023-10-07.csv')
        self.assertEqual(destination_blob_name_interactionids, 'reprocess_failed_interaction_ids_2023-10-07.csv')

    @patch('src.main.bqreport.bqreport.datetime')
    def test_check_time_error(self, mock_datetime):
        # Mock datetime to raise an exception
        mock_datetime.now.side_effect = Exception(TEST_EXCEPTION)
        mock_datetime.timezone = timezone  # Add this line

        result = bqreport.check_time('2023-10-08')
        self.assertIsNone(result)

class TestCreateAndUploadCSV(unittest.TestCase):

    @patch('google.cloud.storage.Client')
    def test_create_and_upload_csv(self, mock_storage_client):
        # Mock the storage client and blob
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Call the function
        bqreport.create_and_upload_csv(100, 90, 10, 10.0, 'test-bucket', 'test-blob.csv', 'test-project', '2023-10-01', '2023-10-02', 1, 2, 3, 4)

        # Assert that the blob was uploaded with the correct data
        mock_blob.upload_from_string.assert_called_once()

class TestReprocessingUpload(unittest.TestCase):

    @patch('google.cloud.storage.Client')
    def test_reprocessing_upload(self, mock_storage_client):
        # Mock the storage client and blob
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Create a mock DataFrame
        mock_df = pd.DataFrame({
            'interaction_id': [1, 2, 3],
            'message': ['error1', 'error2', 'error3']
        })

        # Call the function
        bqreport.reprocessing_upload(mock_df, 'test-reprocessing-bucket', 'test-reprocessing-blob.csv', 'test-project', '2023-10-01')

        # Assert that the blob was uploaded with the correct data
        mock_blob.upload_from_string.assert_called_once()

    @patch('google.cloud.storage.Client')
    def test_reprocessing_upload_error(self, mock_storage_client):
        # Mock the storage client to raise an exception
        mock_storage_client.side_effect = Exception(TEST_EXCEPTION)

        # Create a mock DataFrame
        mock_df = pd.DataFrame({
            'interaction_id': [1, 2, 3],
            'message': ['error1', 'error2', 'error3']
        })

        # Call the function
        bqreport.reprocessing_upload(mock_df, 'test-reprocessing-bucket', 'test-reprocessing-blob.csv', 'test-project', '2023-10-01')

        # Assert that the exception was handled
        self.assertTrue(mock_storage_client.called)

class TestBQReportWithReprocessing(unittest.TestCase):

    @patch('src.main.bqreport.bqreport.detect_env', return_value='dev')
    @patch('src.main.bqreport.bqreport.read_config_json', return_value={
        'settings': {
            'bucket_name': 'test-bucket',
            'reprocessing_bucket_name': 'test-reprocessing-bucket'
        }
    })
    @patch('src.main.bqreport.bqreport.list_logs', return_value=100)
    @patch('src.main.bqreport.bqreport.check_time', return_value=(1, 'reprocess_execute.sql', 'test.csv', 'test_ids.csv'))
    @patch('src.main.bqreport.bqreport.read_query_from_file', return_value='TEST QUERY')
    @patch('src.main.bqreport.bqreport.execute_query')
    @patch('src.main.bqreport.bqreport.execute_bigquery_count')
    @patch('src.main.bqreport.bqreport.other_error_count_query')
    @patch('google.cloud.storage.Client')
    def test_bq_report_reprocessing_complete(self, mock_storage_client, mock_other_error_query,
                                           mock_execute_bigquery_count, mock_execute_query,
                                           mock_read_query_from_file, mock_check_time,
                                           mock_list_logs, mock_read_config_json,
                                           mock_detect_env):
        # Setup mock returns
        mock_execute_query.return_value = pd.DataFrame({
            'interaction_ids': [100],
            'trs_interactions_success': [90],
            'Difference': [10],
            'request_guid': ['guid1']
        })
        mock_execute_bigquery_count.return_value = (pd.DataFrame({'interaction_id': [1], 'message': ['error']}), 1)
        mock_other_error_query.return_value = pd.DataFrame({'interaction_id': [2], 'message': ['error']})
        
        # Mock storage client setup
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob


        result = bqreport.bq_report()
        self.assertEqual(result, "BQ Report and Failure Interaction Ids Report Generated successfully")

    @patch('src.main.bqreport.bqreport.detect_env', return_value='dev')
    @patch('src.main.bqreport.bqreport.read_config_json', return_value={
        'settings': {
            'bucket_name': 'test-bucket',
            'reprocessing_bucket_name': 'test-reprocessing-bucket'
        }
    })
    @patch('src.main.bqreport.bqreport.list_logs', return_value=100)
    @patch('src.main.bqreport.bqreport.check_time', return_value=(0, 'execute.sql', 'test.csv', 'test_ids.csv'))
    @patch('src.main.bqreport.bqreport.read_query_from_file', return_value='TEST QUERY')
    @patch('src.main.bqreport.bqreport.execute_query')
    @patch('src.main.bqreport.bqreport.execute_bigquery_count')
    @patch('src.main.bqreport.bqreport.other_error_count_query')
    @patch('google.cloud.storage.Client')
    def test_bq_report_mismatch_during_reprocessing(self, mock_storage_client, mock_other_error_query,
                                                   mock_execute_bigquery_count, mock_execute_query,
                                                   mock_read_query_from_file, mock_check_time,
                                                   mock_list_logs, mock_read_config_json,
                                                   mock_detect_env):
        # Setup mock to return different number than log_num
        mock_execute_query.return_value = pd.DataFrame({
            'interaction_ids': [90],  # Different from log_num (100)
            'trs_interactions_success': [80],
            'Difference': [10],
            'request_guid': ['guid1']
        })


        result = bqreport.bq_report()
        self.assertEqual(result, "Failed generating BQ Report As Not all records processed successfully")

    @patch('src.main.bqreport.bqreport.detect_env', return_value='dev')
    @patch('src.main.bqreport.bqreport.read_config_json', return_value={
        'settings': {
            'bucket_name': 'test-bucket',
            'reprocessing_bucket_name': 'test-reprocessing-bucket'
        }
    })
    @patch('src.main.bqreport.bqreport.list_logs', return_value=100)
    @patch('src.main.bqreport.bqreport.check_time', return_value=0)
    @patch('src.main.bqreport.bqreport.read_query_from_file', return_value=TEST_QUERY)
    @patch('src.main.bqreport.bqreport.execute_query', side_effect=Exception(TEST_EXCEPTION))
    def test_bq_report_error_during_reprocessing(self, mock_execute_query, mock_read_query_from_file,
                                                mock_check_time, mock_list_logs, mock_read_config_json,
                                                mock_detect_env):

        # Call function
        result = bqreport.bq_report()

        # Assert result
        self.assertEqual(result, 'Failed BQ Report and Failure Interaction Ids Report Generation')

    @patch('src.main.bqreport.bqreport.detect_env', return_value='dev')
    @patch('src.main.bqreport.bqreport.read_config_json', return_value={
        'settings': {
            'bucket_name': 'test-bucket',
            'reprocessing_bucket_name': 'test-reprocessing-bucket'
        }
    })
    @patch('src.main.bqreport.bqreport.list_logs', return_value=100)
    @patch('src.main.bqreport.bqreport.check_time', return_value=(0, 'execute.sql', 'test.csv', 'test_ids.csv'))
    @patch('src.main.bqreport.bqreport.read_query_from_file', return_value='TEST QUERY')
    @patch('src.main.bqreport.bqreport.execute_query')
    @patch('src.main.bqreport.bqreport.execute_bigquery_count')
    @patch('src.main.bqreport.bqreport.other_error_count_query')
    @patch('google.cloud.storage.Client')
    def test_bq_report_mismatch_during_reprocessing(self, mock_storage_client, mock_other_error_query,
                                                   mock_execute_bigquery_count, mock_execute_query,
                                                   mock_read_query_from_file, mock_check_time,
                                                   mock_list_logs, mock_read_config_json,
                                                   mock_detect_env):
        # Setup mock to return different number than log_num
        mock_execute_query.return_value = pd.DataFrame({
            'interaction_ids': [90],  # Different from log_num (100)
            'trs_interactions_success': [80],
            'Difference': [10],
            'request_guid': ['guid1']
        })


        result = bqreport.bq_report()
        self.assertEqual(result, "Failed generating BQ Report As Not all records processed successfully")

class TestListLogs(unittest.TestCase):

    @patch('google.cloud.logging.Client')
    def test_list_logs(self, mock_logging_client):
        # Mock the logging client and entries
        mock_entry = MagicMock()
        mock_entry.payload = "Total records retrieved from PR2: 100"
        mock_logging_client.return_value.list_entries.return_value = [mock_entry]

        # Call the function
        result = bqreport.list_logs('test-project', '2023-10-01')

        # Assert the result
        self.assertEqual(result, 100)
    
    @patch('google.cloud.logging.Client')
    def test_list_logs_wrong_log(self, mock_logging_client):
        # Mock the logging client and entries
        mock_entry = MagicMock()
        mock_entry.payload = "Incomplete log line without colon and number"
        mock_logging_client.return_value.list_entries.return_value = [mock_entry]

        # Call the function
        result = bqreport.list_logs('test-project', '2023-10-01')

        # Assert the result
        self.assertEqual(result, 0)

class TestOtherErrorCountQuery(unittest.TestCase):

    @patch('google.cloud.bigquery.Client')
    def test_other_error_count_query_success(self, mock_bigquery_client):
        # Mock data
        project_id = 'test-project'
        today = '2023-10-01'
        formatted_guids = '"guid1","guid2"'
        
        # Create mock DataFrame
        mock_df = pd.DataFrame({
            'interaction_id': [1, 2, 3],
            'message': ['error1', 'error2', 'error3']
        })
        
        # Mock the BigQuery client and query job
        mock_query_job = MagicMock()
        mock_query_job.result.return_value.to_dataframe.return_value = mock_df
        mock_bigquery_client.return_value.query.return_value = mock_query_job

        # Call the function
        result = bqreport.other_error_count_query(project_id, today, formatted_guids)

        # Assert the results
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)
        self.assertTrue('interaction_id' in result.columns)
        self.assertTrue('message' in result.columns)
        mock_bigquery_client.assert_called_once()

    @patch('google.cloud.bigquery.Client')
    def test_other_error_count_query_no_results(self, mock_bigquery_client):
        # Mock data
        project_id = 'test-project'
        today = '2023-10-01'
        formatted_guids = '"guid1","guid2"'
        
        # Create empty mock DataFrame
        mock_df = pd.DataFrame({
            'interaction_id': [],
            'message': []
        })
        
        # Mock the BigQuery client and query job
        mock_query_job = MagicMock()
        mock_query_job.result.return_value.to_dataframe.return_value = mock_df
        mock_bigquery_client.return_value.query.return_value = mock_query_job

        # Call the function
        result = bqreport.other_error_count_query(project_id, today, formatted_guids)

        # Assert the results
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 0)
        self.assertTrue('interaction_id' in result.columns)
        self.assertTrue('message' in result.columns)
        mock_bigquery_client.assert_called_once()

    @patch('google.cloud.bigquery.Client')
    def test_other_error_count_query_error(self, mock_bigquery_client):
        # Mock data
        project_id = 'test-project'
        today = '2023-10-01'
        formatted_guids = '"guid1","guid2"'
        
        # Mock the BigQuery client to raise an exception
        mock_bigquery_client.side_effect = Exception(TEST_EXCEPTION)

        # Call the function
        result = bqreport.other_error_count_query(project_id, today, formatted_guids)

        # Assert the result
        self.assertIsNone(result)
        mock_bigquery_client.assert_called_once()

    def test_other_error_count_query_invalid_params(self):
        # Test with invalid parameters
        result = bqreport.other_error_count_query(None, None, None)
        self.assertIsNone(result)

class TestExecuteQuery(unittest.TestCase):

    @patch('google.cloud.bigquery.Client')
    def test_execute_query(self, mock_bigquery_client):
        # Mock the BigQuery client and query job
        mock_query_job = MagicMock()
        mock_query_job.result.return_value.to_dataframe.return_value = pd.DataFrame({'col1': [1, 2, 3]})
        mock_bigquery_client.return_value.query.return_value = mock_query_job

        # Call the function
        result = bqreport.execute_query('test-project', TEST_QUERY)

        # Assert the result
        self.assertIsInstance(result, pd.DataFrame)

class TestReadQueryFromFile(unittest.TestCase):

    def test_read_query_from_file(self):
        # Mock the file content
        with patch('builtins.open', unittest.mock.mock_open(read_data='SELECT * FROM test_table WHERE date = "update_process_date"')):
            result = bqreport.read_query_from_file('test.sql', '2023-10-01')

        # Assert the result
        self.assertEqual(result, 'SELECT * FROM test_table WHERE date = "2023-10-01"')

class TestDetectEnv(unittest.TestCase):

    def test_detect_env_dev(self):
        # Call the function
        result = bqreport.detect_env('db-dev-zzss-voice-surv')

        # Assert the result
        self.assertEqual(result, 'dev')

    def test_detect_env_uat(self):
        # Call the function
        result = bqreport.detect_env('db-uat-n1vi-dbmacs-voice-surv')

        # Assert the result
        self.assertEqual(result, 'uat')

    def test_detect_env_prd(self):
        # Call the function
        result = bqreport.detect_env('db-prd-7q33-dbmacs-voice-surv')

        # Assert the result
        self.assertEqual(result, 'prd')

    def test_detect_env_test(self):
        # Call the function
        result = bqreport.detect_env('unknown-project')

        # Assert the result
        self.assertEqual(result, 'test')

class TestReadConfigJson(unittest.TestCase):

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='{"settings": {"bucket_name": "test-bucket"}}')
    def test_read_config_json_dev(self, mock_file):
        # Call the function
        result = bqreport.read_config_json('dev')

        # Assert the result
        self.assertEqual(result, {"settings": {"bucket_name": "test-bucket"}})

class TestExecuteBigQueryCount(unittest.TestCase):

    @patch('google.cloud.bigquery.Client')
    def test_execute_bigquery_count(self, mock_bigquery_client):
        # Mock the BigQuery client and query job
        mock_query_job = MagicMock()
        mock_query_job.result.return_value.to_dataframe.return_value = pd.DataFrame({'interaction_id': [1, 2, 3]})
        mock_bigquery_client.return_value.query.return_value = mock_query_job

        # Call the function
        result_df, result_count = bqreport.execute_bigquery_count(TEST_QUERY, 'test-project')

        # Assert the result
        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertEqual(result_count, 3)

class TestFormattedQuery(unittest.TestCase):

    def test_formatted_query(self):
        # Call the function
        result = bqreport.formatted_query('2023-10-01', '"guid1","guid2"', 'test-message')

        # Assert the result
        expected_query = """ SELECT DISTINCT interaction_id, message FROM `voice_surv_stt.voice-surv_transcript_audit` WHERE insertion_date BETWEEN DATETIME("2023-10-01") AND DATETIME_ADD(DATETIME("2023-10-01"), INTERVAL 1 DAY) AND request_guid IN ("guid1","guid2") AND status="Failed" AND message like "%test-message" """
        self.assertEqual(result, expected_query)

class TestBQReport(unittest.TestCase):

    @patch('src.main.bqreport.bqreport.detect_env', return_value='dev')
    @patch('src.main.bqreport.bqreport.read_config_json', return_value={
        'settings': {
            'bucket_name': 'test-bucket',
            'reprocessing_bucket_name': 'test-reprocessing-bucket'
        }
    })
    @patch('src.main.bqreport.bqreport.list_logs', return_value=100)
    @patch('src.main.bqreport.bqreport.read_query_from_file', return_value=TEST_QUERY)
    @patch('src.main.bqreport.bqreport.execute_query', return_value=pd.DataFrame({'interaction_ids': [100], 'trs_interactions_success': [90], 'Difference': [10], 'request_guid': ['guid1']}))
    @patch('src.main.bqreport.bqreport.execute_bigquery_count', return_value=(pd.DataFrame({'interaction_id': [1, 2, 3]}), 3))
    @patch('google.cloud.storage.Client')
    @patch('google.cloud.logging.Client')
    def test_bq_report_success(self, mock_storage_client, mock_logging_client, mock_execute_bigquery_count, mock_execute_query, mock_read_query_from_file, mock_list_logs, mock_read_config_json, mock_detect_env):
        # Mock the storage client and blob
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        mock_entry = MagicMock()
        mock_entry.payload = "Total records retrieved from PR2: 100"
        mock_logging_client.return_value.list_entries.return_value = [mock_entry]

        # Call the function
        result = bqreport.bq_report()

        # Assert the result
        self.assertEqual(result, "BQ Report and Failure Interaction Ids Report Generated successfully")

class TestCreateAndUploadCSVErrorHandling(unittest.TestCase):

    @patch('google.cloud.storage.Client')
    def test_create_and_upload_csv_error(self, mock_storage_client):
        # Mock the storage client to raise an exception
        mock_storage_client.side_effect = Exception(TEST_EXCEPTION)

        # Call the function
        bqreport.create_and_upload_csv(100, 90, 10, 10.0, 'test-bucket', 'test-blob.csv', 'test-project', '2023-10-01', '2023-10-02', 1, 2, 3, 4)

        # Assert that the exception was handled
        self.assertTrue(mock_storage_client.called)

class TestListLogsErrorHandling(unittest.TestCase):

    @patch('google.cloud.logging.Client')
    def test_list_logs_error(self, mock_logging_client):
        # Mock the logging client to raise an exception
        mock_logging_client.side_effect = Exception(TEST_EXCEPTION)

        # Call the function
        result = bqreport.list_logs('test-project', '2023-10-01')

        # Assert the result
        self.assertEqual(result, 0)

class TestExecuteQueryErrorHandling(unittest.TestCase):

    @patch('google.cloud.bigquery.Client')
    def test_execute_query_error(self, mock_bigquery_client):
        # Mock the BigQuery client to raise an exception
        mock_bigquery_client.side_effect = Exception(TEST_EXCEPTION)

        # Call the function
        result = bqreport.execute_query('test-project', TEST_QUERY)

        # Assert the result
        self.assertIsNone(result)

class TestReadQueryFromFileErrorHandling(unittest.TestCase):

    def test_read_query_from_file_error(self):
        # Mock the file to raise an exception
        with patch('builtins.open', side_effect=Exception(TEST_EXCEPTION)):
            result = bqreport.read_query_from_file('test.sql', '2023-10-01')

        # Assert the result
        self.assertIsNone(result)

class TestDetectEnvErrorHandling(unittest.TestCase):

    def test_detect_env_error(self):
        # Call the function with an invalid project ID
        result = bqreport.detect_env('invalid-project')

        # Assert the result
        self.assertEqual(result, 'test')

class TestReadConfigJsonErrorHandling(unittest.TestCase):

    @patch('builtins.open', side_effect=Exception(TEST_EXCEPTION))
    def test_read_config_json_error(self, mock_file):
        # Call the function
        result = bqreport.read_config_json('dev')

        # Assert the result
        self.assertIsNone(result)

class TestExecuteBigQueryCountErrorHandling(unittest.TestCase):

    @patch('google.cloud.bigquery.Client')
    def test_execute_bigquery_count_error(self, mock_bigquery_client):
        # Mock the BigQuery client to raise an exception
        mock_bigquery_client.side_effect = Exception(TEST_EXCEPTION)

        # Call the function
        result_df, result_count = bqreport.execute_bigquery_count(TEST_QUERY, 'test-project')

        # Assert the result
        self.assertIsNone(result_df)
        self.assertIsNone(result_count)

class TestFormattedQueryErrorHandling(unittest.TestCase):

    def test_formatted_query_error(self):
        # Call the function with invalid parameters
        result = bqreport.formatted_query('invalid-date', 'invalid-guids', 'invalid-message')

        # Assert the result
        self.assertIsNone(result)

class TestBQReportErrorHandling(unittest.TestCase):
    @patch('src.main.bqreport.bqreport.detect_env', return_value='dev')
    @patch('src.main.bqreport.bqreport.read_config_json', return_value={
        'settings': {
            'bucket_name': 'test-bucket',
            'reprocessing_bucket_name': 'test-reprocessing-bucket'
        }
    })
    @patch('src.main.bqreport.bqreport.list_logs', return_value=100)
    @patch('src.main.bqreport.bqreport.check_time', return_value=(0, 'execute.sql', 'test.csv', 'test_ids.csv'))
    @patch('src.main.bqreport.bqreport.read_query_from_file', return_value='TEST QUERY')
    @patch('src.main.bqreport.bqreport.execute_query')
    def test_bq_report_mismatch_logs(self, mock_execute_query, mock_read_query_from_file,
                                    mock_check_time, mock_list_logs, mock_read_config_json,
                                    mock_detect_env):
        # Setup mock to return different number than log_num
        mock_execute_query.return_value = pd.DataFrame({
            'interaction_ids': [90],  # Different from log_num (100)
            'trs_interactions_success': [80],
            'Difference': [10],
            'request_guid': ['guid1']
        })

        result = bqreport.bq_report()
        self.assertEqual(result, "Failed generating BQ Report As Not all records processed successfully")
