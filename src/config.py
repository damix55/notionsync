from datetime import datetime
import json
import os
import sys
import pytz
import toml

class Config:
    def __init__(self):
        # Get file directory
        if getattr(sys, 'frozen', False):   # if it's an exe
            self.src_folder = os.path.dirname(sys.executable)
        else:
            self.src_folder = os.path.dirname(os.path.realpath(__file__))

        # get directories
        self.base_folder = os.path.dirname(self.src_folder)
        self.data_folder = os.path.join(self.base_folder, 'data')
        self.assets_folder = os.path.join(self.base_folder, 'assets')
        self.logs_folder = os.path.join(self.base_folder, 'logs')

        # set file paths
        self.config_file = os.path.join(self.data_folder, 'config.toml')
        self.last_sync_file = os.path.join(self.data_folder, 'last_sync.json')

        # Load config file
        self.config = toml.load(self.config_file)

        # Load timezone
        self.timezone_str = self.config['misc']['timezone']
        self.timezone = pytz.timezone(self.timezone_str)


    def load_last_sync(self, activity):
        """Load last sync from config file.

        Returns:
            datetime.datetime: last sync
        """

        # check if the file exists
        if not os.path.isfile(self.last_sync_file):
            return None
        
        # load last sync
        with open(self.last_sync_file, 'r') as f:
            last_sync = json.load(f)[activity]

        # convert to datetime
        last_sync = datetime.strptime(last_sync, '%Y-%m-%d %H:%M:%S.%f')

        # add timezone
        last_sync = self.timezone.localize(last_sync)
        return last_sync
    

    def update_last_sync(self, activity):
        """Update last sync in config file.

        Returns:
            datetime.datetime: last sync
        """

        last_sync = datetime.now(self.timezone)
        data = {activity: last_sync.strftime('%Y-%m-%d %H:%M:%S.%f')}
        
        # update the json file
        if os.path.isfile(self.last_sync_file):
            with open(self.last_sync_file, 'r') as f:
                last_sync_file = json.load(f)
            last_sync_file.update(data)
            data = last_sync_file

        with open(self.last_sync_file, 'w') as f:
            json.dump(data, f)

        return last_sync