import logging
import os
import subprocess
from datetime import datetime

class Logging:
    def __init__(
        self,
        log_dir: str = "../logs",
        log_file: str = "CDCT.log",
        level: int = logging.DEBUG if os.getenv("ENV") == "dev" else logging.INFO
    ) -> None:
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, log_file)

        logging.basicConfig(
            filename=self.log_path,
            level=level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%m-%d-%y %H:%M"
        )

        self.logger = logging.getLogger("CDCTLogger")

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", "%m-%d-%y %H:%M"
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

    def push_logs_to_github(self, commit_msg: str = None) -> str:
        if not commit_msg:
            commit_msg = f"Updating CDCT logs - {datetime.now().strftime('%H:%M %m-%d-%y')}"

        try:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))  # repo root

            # Only push if the log file changed
            status_output = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True
            )
            if "logs/CDCT.log" not in status_output.stdout:
                return "[INFO] No changes to log file to commit."

            subprocess.run(["git", "checkout", "log-archive"], check=True)
            subprocess.run(["git", "add", self.log_path], check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push", "origin", "log-archive"], check=True)
            subprocess.run(["git", "checkout", "-"], check=True)  # return to previous branch

            self.info("Pushed CDCT.log to GitHub.")
            return "[INFO] Log file committed and pushed to GitHub log-archive branch."

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git push failed: {e}")
            return f"[ERROR] Git push failed: {e}"

    def info(self, msg: str) -> str:
        self.logger.info(msg)
        now = datetime.now().strftime("%m-%d-%y %H:%M")
        return f"{now} [INFO] {msg}"

    def warning(self, msg: str) -> str:
        self.logger.warning(msg)
        now = datetime.now().strftime("%m-%d-%y %H:%M")
        return f"{now} [WARNING] {msg}"

    def error(self, msg: str) -> str:
        self.logger.error(msg)
        now = datetime.now().strftime("%m-%d-%y %H:%M")
        return f"{now} [ERROR] {msg}"


if __name__ == "__main__":
    log = Logging()

    print(log.info("Scan started."))
    print(log.warning("No DKIM record found."))
    print(log.error("Failed to connect to AbuseIPDB."))

    result = log.push_logs_to_github()
    print(result)