import datetime
import uuid
import requests
import logging
from simplejson.errors import JSONDecodeError

# [ ] unire parti comuni add e update


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
            # self.logger.error(f'Error: {response_data}')
            raise Exception(response_data["error"])
        
        return response_data


    def sync_read_items(self, sync_token=None):
        if sync_token == None:
            sync_token = '*'

        resource_types = '["items"]'
        data = self.request('GET', '/sync', data={'sync_token': sync_token, 'resource_types': resource_types})
        self.sync_token = data['sync_token']

        projects = self.update_projects()

        for item in data['items']:
            due_date = None
            recurrence = None

            if item['due'] is not None:
                if not item['is_deleted']:
                    due_date = datetime.datetime.strptime(item['due']['date'], '%Y-%m-%d').date()

                if item['due']['is_recurring']:
                    recurrence = item['due']['string']
                
            processed_item = {
                'id': item['id'],
                'content': item['content'],
                'description': item['description'],
                'priority': item['priority'],
                'due': due_date,
                'project': projects.get(item['project_id'], None),
                'labels': item['labels'],
                'checked': item['checked'],
                'is_deleted': item['is_deleted'],
                'recurrence': recurrence,
                # 'section': next((section['name'] for section in sections if section['id'] == item['section_id']), None),
            }

            yield processed_item
    

    def update_projects(self):
        projects = self.request('GET', '/sync', data={'resource_types': '["projects"]'})['projects']
        self.projects = {p['id']: p['name'] for p in projects}

        return self.projects
    

    def project_id_from_name(self, name):
        for p_id, p_name in self.projects.items():
            if p_name == name:
                return p_id
    

    def add_task(self, task):
        data = {
            'content': task['content'],
            'description': task['description'],
            'priority': task['priority'],
            'labels': task['labels'],
            'checked': task['checked'],
            'due': {}
        }

        if task['due'] is not None:
            data['due']['date'] = task['due'].strftime('%Y-%m-%d')

        if task['recurrence'] is not None:
            data['due']['string'] = task['recurrence']
            data['due']['is_recurring'] = True
            data['due']['lang'] = 'en'

        else:
            data['due']['is_recurring'] = False
            

        project = self.project_id_from_name(task['project'])
        if project is not None:
            data['project_id'] = project

        uuid_gen = str(uuid.uuid4())

        commands = [{
            'type': 'item_add',
            'uuid': uuid_gen,
            'temp_id': uuid_gen,
            'args': data
        }]

        response = self.request('POST', '/sync', data={'sync_token': '*', 'resource_types': [], 'commands': commands})
        status = response['sync_status'][uuid_gen]

        if str(status) != 'ok':
            raise Exception(response["error"])
        
        self.sync_token = response['sync_token']
        task_id = response['temp_id_mapping'][uuid_gen]
        return task_id
    

    def update_task(self, task):
        data = {
            'id': task['id'],
            'content': task['content'],
            'description': task['description'],
            'priority': task['priority'],
            'labels': task['labels'],
            'checked': task['checked']
        }

        if task['due'] is not None:
            data['due'] = {
                'date': task['due'].strftime('%Y-%m-%d')
            }
        else:
            data['due'] = None
            
        if task['recurrence'] is not None:
            data['due'] = {
                'string': task['recurrence'],
                'lang': 'en',
                'is_recurring': True
            }
        else:
            data['due'] = {
                'is_recurring': False
            }
            

            project = self.project_id_from_name(task['project'])
            if project is not None:
                data['project_id'] = project

        uuid_gen = str(uuid.uuid4())

        commands = [{
            'type': 'item_update',
            'uuid': uuid_gen,
            'args': data
        }]

        response = self.request('POST', '/sync', data={'sync_token': self.sync_token, 'resource_types': [], 'commands': commands})
        status = response['sync_status'][uuid_gen]

        if str(status) != 'ok':
            raise Exception(response["error"])
        
        self.sync_token = response['sync_token']
    

    def check_task_exists(self, task_id):
        if task_id is None:
            return False
        
        try:
            self.request('GET', '/items/get', data={'item_id': task_id})
            return True
        
        except Exception as e:
            if e.args[0] == 'Item not found':
                return False
            
            else:
                raise e

        