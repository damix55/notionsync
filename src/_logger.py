import logging
import os
from datetime import datetime
from _utils import text_format

# [ ] fix log output to file: se metto level stdout a info, debug su file sfasa

# Formatter for standard output
class StdoutFormatter(logging.Formatter):
    """Custom formatter for standard output with colors and custom format"""

    format_string = f"%(asctime)s.%(msecs)03d | %(name)s | {text_format('%(levelname)s', 'bold')} | %(message)s (%(filename)s:%(lineno)d)"

    # set colors for levels of log
    FORMATS = {
        logging.DEBUG: text_format(format_string, 'purple'),
        logging.INFO: text_format(format_string, 'cyan'),
        logging.WARNING: text_format(format_string, 'yellow'),
        logging.ERROR: text_format(format_string, 'red'),
        logging.CRITICAL: text_format(format_string, 'red')
    }

    def format(self, record):
        # truncate name and levelname
        record.name = record.name[:11].ljust(11)
        record.levelname = record.levelname[:6].ljust(6)

        log_fmt = self.FORMATS.get(record.levelno)
        date_fmt = "%H:%M:%S"
        formatter = logging.Formatter(log_fmt, date_fmt)
        return formatter.format(record)


def logger_setup(path, stdout_level='debug', keep_for_days=None):
    """Setup the logger to print to stdout and to a file

    Args:
        path (str): path to the log folder. If the folder doesn't exist, it will be created.
        stdout_level (str, optional): level of log to print to stdout, defaults to 'debug'.
        keep_for_days (int, optional): number of days to keep log files. Defaults to None.
    """

    # tries to create the logs folder if it doesn't exist
    if not os.path.exists(path):
        os.makedirs(path)

    # create log file name
    filename = f'{datetime.now().isoformat()[:10]}.log'
    file_path = os.path.join(path, filename)

    if keep_for_days is not None:
        # delete files older than "keep_for_days" days
        delete_older_files(path, keep_for_days)

    # create logger
    logger = logging.getLogger('root')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    # log to stdout handler
    stdout_handler  = logging.StreamHandler()
    stdout_handler.setFormatter(StdoutFormatter())

    levels = { 
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    
    stdout_handler.setLevel(levels[stdout_level.lower()])

    # log to file handler
    fh_formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s (%(filename)s:%(lineno)d)")
    file_handler = logging.getLogger('root')
    file_handler = logging.FileHandler(file_path, encoding='utf-8')
    file_handler.setFormatter(fh_formatter)

    # add handlers to logger
    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)


def delete_older_files(path, days):
    """Delete logs older than "days" days

    Args:
        path (str): path to the log folder
        days (int): number of days to keep log files
    """

    today = datetime.today()

    for root, _, files in os.walk(path,topdown=False): 
        for name in files:
            # this is the last modified time
            t = os.stat(os.path.join(root, name))[8] 
            filetime = datetime.fromtimestamp(t) - today

            # checking if file is more than n days old 
            if filetime.days <= -days:
                os.remove(os.path.join(root, name))