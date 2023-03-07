from notion_client import Client

# [ ] Salvarsi projects senza doverli recuperare ogni volta
# [ ] Fare update progetti ad ogni sync

class Notion:
    def __init__(self, config, timezone):
        self.notion = Client(auth=config['key'])
        self.project_db = config['projects_db']
        self.calendar_db = config['calendar_db']
        self.tasks_db = config['tasks_db']
        self.timezone = timezone

    
    def get_projects_names(self):
        """Get all the projects from Notion database
        
        Returns:
            dict: {project_name: project_id}
        """
        response = self.notion.databases.query(database_id=self.project_db)
        projects = {p['properties']['Nome']['title'][0]['text']['content']:p['id'] for p in response['results']}
        
        return projects
    

    def get_project_id(self, project_name):
        """Get project id from project name
        
        Args:
            project_name (str): project name
        
        Returns:
            str: project id
        """
        projects = self.get_projects_names()
        return projects.get(project_name, None)
    


    def projects_name_to_id(self, projects):
        """Convert projects names to ids
        
        Args:
            projects (list): list of project names
        
        Returns:
            list: list of project ids
        """
        projects_ids = []

        if projects is not None:
            for p in projects:
                project_id = self.get_project_id(p)
                if project_id is not None:
                    projects_ids.append({'id': project_id})
        
        return projects_ids

    
    def get_from_db(self, db_id, id):
        """Get an element from a database

        Args:
            db_id (str): database id
            id (str): element id

        Returns:
            dict: element data
        """

        response = self.notion.databases.query(
            database_id=db_id,
            filter={"property": "Id", "rich_text": {"equals": id}}
        )

        if response['results']:
            return response['results'][0]
        
        return None
        

    def add_in_db(self, db_id, data, **kwargs):
        """Add an element in a database
        
        Args:
            db_id (str): database id
            data (dict): element data
        """
        self.notion.pages.create(parent={"database_id": db_id}, properties=data, **kwargs)


    def add_calendar_event(self, data, **kwargs):
        """Add a calendar event in Notion
        
        Args:
            data (dict): event data
        """
        
        properties, content, icon = self.convert_event_to_notion(data)
        self.add_in_db(self.calendar_db, properties, children=content, icon=icon, **kwargs)


    def update_calendar_event(self, event_internal_id, data, **kwargs):
        """Edit a calendar event in Notion
        
        Args:
            event_id (str): event id
            data (dict): event data
        """
        # TODO update the content too
        # "To update page content instead of page properties, use the block object endpoints"
        # update the properties
        properties, _, icon = self.convert_event_to_notion(data)

        # update the page
        self.notion.pages.update(event_internal_id, properties=properties, icon=icon, **kwargs)
        

    def delete_calendar_event(self, event_internal_id):
        """Delete a calendar event in Notion
        
        Args:
            event_id (str): event id
        """
        
        self.notion.blocks.delete(event_internal_id)


    def convert_event_to_notion(self, event):
        """Convert an event to a Notion page

        Args:
            event (dict): event data

        Returns:
            dict: Notion page data
        """

        start = event['start'].isoformat()
        end = event['end'].isoformat()
        date = event['start'].date().isoformat()
        # duration in hours
        duration = event['end'] - event['start']
        hours = duration.seconds / 3600

        data = {
            'Id': {'rich_text': [{'text': {'content': event['id']}}]},
            'Nome': {'title': [{'text': {'content': event['subject']}}]},
            'Data': {'date': {'start': date}},
            'Intervallo': {'date': {'start': start, 'end': end, 'time_zone': self.timezone}},
            'Tags': {'multi_select': [{'name': 'Meeting'}]},
            'Ore': {'number': hours},
            'Progetto': {'relation': self.projects_name_to_id(event['project'])},
            # 'Luogo': {'rich_text': [{'text': {'content': event['location']}}]},
            # 'Organizzatore': {'rich_text': [{'text': {'content': event['organizer']}}]}
        }

        # TODO add support for links and format the body
        body = event['body']
        content = []
        if body != '':
            content = [{
                'object': 'block',
                'type': 'callout',
                'callout': {
                    'icon': {"type": "external", "external":{"url": "https://www.notion.so/icons/drafts_gray.svg?mode=dark"}},
                    "color": "gray_background",
                    "rich_text": [{"type": "text","text": {"content": event['body']}}],
                }
            }]


        icon = {
            "type": "external",
            "external":{
                "url": "https://www.notion.so/icons/calendar_gray.svg?mode=dark"
            }
        }

        return data, content, icon


    def get_calendar_events(self, start_date, end_date):
        """Get all the events in a date range
        
        Args:
            start_date (str): start date
            end_date (str): end date
        
        Returns:
            list: list of events
        """
        response = self.notion.databases.query(
            database_id=self.calendar_db,
            filter={"and": [
                {"property": "Intervallo", "date": {"on_or_after": start_date, "on_or_before": end_date}},
                {"property": "Tags", "multi_select": {"contains": "Meeting"}}
            ]},
            sorts=[{"property": "Intervallo", "direction": "ascending"}])
        return response['results']
    

    def check_event_exists(self, event_id):
        """Check if an event exists in Notion

        Args:
            event_id (str): event id

        Returns:
            str: event internal id
        """
        data = self.get_from_db(self.calendar_db, event_id)
        
        if data is not None:
            return data['id']
        
        return None
    

    def check_task_exists(self, task_id):
        """Check if a task exists in Notion

        Args:
            task_id (str): task id

        Returns:
            str: task internal id
        """
        data = self.get_from_db(self.tasks_db, task_id)
        
        if data is not None:
            return data['id']
        
        return None


    def add_task(self, data, **kwargs):
        """Add a task in Notion
        
        Args:
            data (dict): task data
        """
        properties, content, icon = self.convert_task_to_notion(data)
        self.add_in_db(self.tasks_db, properties, children=content, icon=icon, **kwargs)


    def update_task(self, task_internal_id, data, **kwargs):
        """Edit a task in Notion
        
        Args:
            task_id (str): task id
            data (dict): task data
        """
        # TODO update the content too
        properties, _, icon = self.convert_task_to_notion(data)

        # update the page
        self.notion.pages.update(task_internal_id, properties=properties, icon=icon, **kwargs)


    def complete_task(self, task_internal_id):
        """Check a task in Notion
        
        Args:
            task_id (str): task id
            checked (bool): checked or not
        """
        self.notion.pages.update(task_internal_id, properties={'Fatto': {'checkbox': True}})


    def delete_task(self, task_internal_id):
        """Delete a task in Notion
        
        Args:
            task_id (str): task id
        """
        self.notion.blocks.delete(task_internal_id)

    
    def convert_task_to_notion(self, task):
        """Convert a task to a Notion page

        Args:
            task (dict): task data

        Returns:
            dict: Notion page data
        """

        data = {
            'Id': {'rich_text': [{'text': {'content': task['id']}}]},
            'Nome': {'title': [{'text': {'content': task['content']}}]},
            'Progetto': {'relation': self.projects_name_to_id([task['project']])},
            'Fatto': {'checkbox': task['checked']},
            'Tags': {'multi_select': [{'name': t} for t in task['labels']]}
        }

        priority = task['priority']
        if priority > 1:
            priority = 5-task['priority']

            priority = str(priority)
            data.update({'Priorità': {'select': {'name': priority}}})

        date = task['due']
        if date is not None:
            date = date.isoformat()
            data.update({'Data': {'date': {'start': date}}})


        content = [{
            'object': 'block',
            'type': 'paragraph',
            'paragraph': {
                'rich_text': [
                    {'type': 'text', 'text': {'content': task['description'],}}
                ]
            }

        }]

        icon = {
            "type": "external",
            "external":{
                "url": "https://www.notion.so/icons/list_gray.svg?mode=dark"
            }
        }

        return data, content, icon