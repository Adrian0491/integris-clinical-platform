import re
import datetime

from datetime import datetime

class LogParser:
    def __init__(self, log_file):
        self.log_file = log_file

    def parse_logs(self):
        log_entries = []
        with open(self.log_file, 'r') as file:
            for line in file:
                log_entry = self.parse_log_line(line)
                if log_entry:
                    log_entries.append(log_entry)
        return log_entries

    def parse_log_line(self, line):
        # Example log format: "2024-06-01 12:00:00 INFO User logged in"
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)'
        match = re.match(pattern, line)
        if match:
            timestamp_str, level, message = match.groups()
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            return {
                'timestamp': timestamp,
                'level': level,
                'message': message
            }                
        today_date = datetime.now()
        if today_date.strftime(format('%Y-%m-%d')) >= timestamp.strftime(format('%Y-%m-%d')):
            print('Log file is too old to be used!  Please provide a log file with a timestamp of today or later.')
            return {
                'timestamp': timestamp,
                'level': level,
                'message': message
            }
        else:
            print('Log file is valid and can be used.')
            return {
                'timestamp': timestamp,
                'level': level,
                'message': message
            }
            
if __name__ == "__main__":
    log_parser = LogParser('example.log')
    log_entries = log_parser.parse_logs()
    for entry in log_entries:
        print(entry)