import unittest
from bk.logging.log_parser import LogParser

class TestLogParser(unittest.TestCase):
    
    def test_parse_logs(self):
        parser = LogParser("bk/test_logs.txt")
        entries = parser.parse_logs()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["level"], "INFO")
        self.assertEqual(entries[1]["level"], "ERROR")
        self.assertEqual(entries[2]["level"], "WARNING")

    def test_filter_by_level(self):
        parser = LogParser("bk/test_logs.txt")
        error_entries = parser.filter_by_level("ERROR")
        self.assertEqual(len(error_entries), 1)
        self.assertEqual(error_entries[0]["message"], "An error occurred")
        
if __name__ == "__main__":
    unittest.main()