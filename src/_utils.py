from datetime import datetime
import os
import sys
import pytz
import toml
import json
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


def text_format(text, style, additional_style=None):
    """Format text. Support different styles: purple, cyan, darkcyan, blue, green, yellow, red, bold, underline.

    Args:
        text (str): text to format
        style (str): style to apply to the text
        additional_style (str, optional): additional style to apply to the text. Defaults to None.

    Returns:
        str: formatted text
    """

    styles = {
        'purple': '\033[95m',
        'cyan': '\033[96m',
        'darkcyan': '\033[36m',
        'blue': '\033[94m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'bold': '\033[1m',
        'underline': '\033[4m'
    }

    if additional_style is not None:
        text = text_format(text, additional_style)

    return styles[style] + text + '\033[0m'


def fprint(text, style, additional_style=None, *args, **kwargs):
    """Funzione per stampare testo formattato. Wrapper di text_format. """
    print(text_format(text, style, additional_style), *args, **kwargs)


def get_file_path():
    """Get file path.
    
    Returns:
        str: file path, where the script is located if it's a script, otherwise the path of the exe
        str: base path, where the exe is extracted if it's an exe, otherwise the same as file_path
    """

    # Get file directory
    if getattr(sys, 'frozen', False):   # if it's an exe
        file_path = os.path.dirname(sys.executable)
        base_path = sys._MEIPASS    # temporary folder where the exe is extracted
    else:
        file_path = os.path.dirname(os.path.realpath(__file__))
        base_path = file_path
    
    return file_path, base_path


@lru_cache(maxsize=None)
def load_config(base_path=None):
    """Load config file.

    Args:
        base_path (str, optional): base path. Defaults to None.

    Returns:
        dict: config file
    """

    if base_path is None:
        base_path = get_file_path()[1]
    
    # Load config file
    config_file = f'{base_path}/data/config.toml'
    
    logger.info(f'Loading config file from {config_file}')
    return toml.load(config_file)


def load_timezone():
    """Load timezone from config file.

    Returns:
        pytz.timezone: timezone
    """

    return pytz.timezone(load_config()['misc']['timezone'])


def load_last_sync(activity):
    """Load last sync from config file.

    Returns:
        datetime.datetime: last sync
    """

    path = f'{get_file_path()[1]}/data/last_sync.json'

    # check if the file exists
    if not os.path.isfile(path):
        return None
    
    # load last sync
    with open(path, 'r') as f:
        last_sync = json.load(f)[activity]

    # convert to datetime
    last_sync = datetime.strptime(last_sync, '%Y-%m-%d %H:%M:%S.%f')

    # add timezone
    last_sync = load_timezone().localize(last_sync)
    return last_sync


def update_last_sync(activity):
    """Update last sync in config file.

    Returns:
        datetime.datetime: last sync
    """

    path = f'{get_file_path()[0]}/data/last_sync.json'
    last_sync = datetime.now(load_timezone())
    data = {activity: last_sync.strftime('%Y-%m-%d %H:%M:%S.%f')}
    
    
    # update the json file
    if os.path.isfile(path):
        with open(path, 'r') as f:
            last_sync_file = json.load(f)
        last_sync_file.update(data)
        
        with open(path, 'w') as f:
            json.dump(last_sync_file, f)

    else:
        with open(path, 'w') as f:
            json.dump(data, f)


    return last_sync