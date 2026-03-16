import unittest
import subprocess

from unittest.mock import patch
from log_indexing import *

class TestLogging(unittest.TestCase):
    def setUp(self):
        self.logger = Logging(log_dir="logs/test")

    @patch('logging.Logger.info')
    def test_info_log(self, mock_info):
        msg = "Test info"
        result = self.logger.info(msg)

        mock_info.assert_called_once_with(msg)
        self.assertIn("[INFO]", result)
        self.assertIn(msg, result)

    @patch('logging.Logger.warning')
    def test_warning_log(self, mock_warning):
        msg = "Test warning"
        result = self.logger.warning(msg)

        mock_warning.assert_called_once_with(msg)
        self.assertIn("[WARNING]", result)
        self.assertIn(msg, result)

    @patch('logging.Logger.error')
    def test_error_log(self, mock_error):
        msg = "Test error"
        result = self.logger.error(msg)

        mock_error.assert_called_once_with(msg)
        self.assertIn("[ERROR]", result)
        self.assertIn(msg, result)

    @patch('logging.Logger.info')
    @patch('subprocess.run')
    def test_push_logs_to_github_no_change(self, mock_log_info, mock_subprocess_run):
        # Simulate clean git status
        mock_subprocess_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=""),  # status
        ]

        result = self.logger.push_logs_to_github()
        self.assertIn("No changes", result)

    @patch('subprocess.run')
    @patch('logging.Logger.info')
    def test_push_logs_to_github_with_change(self, mock_log_info, mock_subprocess_run):
        # Simulate dirty git status and successful Git operations
        mock_subprocess_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="logs/CDCT.log\n"),  # status
            subprocess.CompletedProcess(args=[], returncode=0),  # checkout
            subprocess.CompletedProcess(args=[], returncode=0),  # add
            subprocess.CompletedProcess(args=[], returncode=0),  # commit
            subprocess.CompletedProcess(args=[], returncode=0),  # push
            subprocess.CompletedProcess(args=[], returncode=0)   # checkout back
        ]

        result = self.logger.push_logs_to_github("Test commit")
        self.assertIn("pushed to GitHub", result)

if __name__ == '__main__':
    unittest.main()