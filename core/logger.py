import logging
from datetime import datetime, timedelta
import os
import glob

def setup_logger(log_dir: str = "logs", days_to_keep: int = 30) -> logging.Logger:
    """Configures daily file logging and automatically prunes old logs."""
    os.makedirs(log_dir, exist_ok=True)

    # 1. Generate a unique filename for the current run
    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"pipeline.log.{timestamp}.txt")

    # 2. Configure standard logging (force=True overrides any existing basicConfig)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
        force=True 
    )
    
    logger = logging.getLogger(__name__)

    # 3. Clean up old logs to save server space
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        # Find all log files matching the pipeline pattern
        for old_log in glob.glob(f"{log_dir}/pipeline.log.*.txt"):
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(old_log))
            if file_mod_time < cutoff_date:
                os.remove(old_log)
                logger.debug(f"Deleted old log file: {old_log}")
    except Exception as e:
        logger.warning(f"Failed to clean up old logs: {e}")

    return logger