import datetime
import requests
import logging
from simplejson.errors import JSONDecodeError

class Todoist:
    def __init__(self, config):
        self.config = config
        self.key = config['key']
        self.logger = logging.getLogger(__name__)
        self.endpoint = 'https://api.todoist.com/sync/v9'
        self.sync_token = None
    

    def request(self, method, endpoint, data=None):
        url = self.endpoint + endpoint
        self.logger.debug(f'Request: {method} {url} {data}')
        headers = {'Authorization': f'Bearer {self.key}', 'Content-Type': 'application/json'}
        if method == 'GET':
            response = requests.request(method, url, headers=headers, params=data)
        else:
            response = requests.request(method, url, headers=headers, json=data)

        try:
            response_data = response.json()
        except JSONDecodeError as e:
            self.logger.error(f'Error: {response.content}')
            raise e

        if response.status_code < 200 or response.status_code > 299:
            self.logger.error(f'Error: {response_data}')
            raise Exception(f'Error: {response_data["error"]}')
        
        return response_data
    

    def sync_read(self, sync_token=None):
        if sync_token == None:
            sync_token = '*'

        resource_types = '["labels", "projects", "items", "sections"]'
        data = self.request('GET', '/sync', data={'sync_token': sync_token, 'resource_types': resource_types})
        self.sync_token = data['sync_token']
        return data


    def sync_read_items_all(self, sync_token=None, last_sync=None):
        # [ ] Add support for sections ?
        # [ ] Manage recurring tasks: since the id is the same, instead of checking if the task, edit to the next date

        projects = self.get_projects()

        for item in self.sync_read_items_completed(last_sync):
            processed_item = {
                'id': item['id'],
                'content': item['content'],
                'checked': True
            }

            yield processed_item


        for item in self.sync_read(sync_token)['items']:
            due_date = None
            is_recurring = False
            if not item['is_deleted'] and item['due'] is not None:
                due_date = datetime.datetime.strptime(item['due']['date'], '%Y-%m-%d').date()
                is_recurring = item['due']['is_recurring']
                
            processed_item = {
                'id': item['id'],
                'content': item['content'],
                'description': item['description'],
                'priority': item['priority'],
                'due': due_date,
                'project': next((project['name'] for project in projects if project['id'] == item['project_id']), None),
                # 'section': next((section['name'] for section in sections if section['id'] == item['section_id']), None),
                'labels': item['labels'],
                'checked': item['checked'],
                'is_deleted': item['is_deleted'],
                'is_recurring': is_recurring,
            }

            yield processed_item


        self.last_sync = datetime.datetime.now(tz=datetime.timezone.utc)


    def sync_read_items_completed(self, last_sync=None):
        data = {} 
        if last_sync is not None:
            # Set last sync time in UTC
            since = last_sync.astimezone(datetime.timezone.utc)
            data['since'] = since.isoformat().split('.')[0]

        data = self.request('GET', '/completed/get_all', data=data)['items']

        return data
    
    def get_projects(self):
        return self.request('GET', '/sync', data={'resource_types': '["projects"]'})['projects']