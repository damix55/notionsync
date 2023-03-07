from todoist import Todoist
from notion import Notion
import logging

class TodoistSync:
    def __init__(self, config):
        self.config = config
        self.config_data = self.config.config

        # Setup the logger for logger to stdout and to file
        self.logger = logging.getLogger(__name__)
        
        self.activity = 'todoist'
        self.last_sync, self.sync_token = self.config.load_last_sync(self.activity, sync_token=True)

        self.todoist = Todoist(self.config_data['todoist'])
        self.notion = Notion(self.config_data['notion'], self.config.timezone_str)
        self.status = 'not started'
        self.exception = None

        if self.last_sync is not None:
            self.logger.info(f"Last sync: {self.last_sync.strftime('%d/%m/%Y %H:%M:%S')}")
        else:
            self.logger.info("Last sync: never")

    
    def sync(self):
        created = 0
        updated = 0
        completed = 0
        deleted = 0

        try:
            for task in self.todoist.sync_read_items_all(self.sync_token, self.last_sync):
                task_content = task['content']

                # Check if event exists in notion
                notion_task_id = self.notion.check_task_exists(task['id'])

                # Complete tasks
                if task['checked']:
                    self.logger.info(f"Task completed: {task_content}")
                    if notion_task_id is not None:
                        self.notion.complete_task(notion_task_id)
                        completed += 1
                    else:
                        self.logger.info(f"Task does not exist in Notion, skipping")

                    continue

                # Delete tasks
                if task['is_deleted']:
                    self.logger.info(f"Deleting task: {task_content}")
                    if notion_task_id is not None:
                        self.notion.delete_task(notion_task_id)
                        deleted += 1
                    else:
                        self.logger.info(f"Task does not exist in Notion, skipping")
                    
                    continue

                # Update or create task
                if notion_task_id is not None:
                    self.logger.info(f"Updating task: {task_content}")
                    self.notion.update_task(notion_task_id, task)
                    updated += 1

                else:
                    self.logger.info(f"Creating task: {task_content}")
                    self.notion.add_task(task)
                    created += 1



            success_message = f"Calendar sync successful: "
            if created == 0 and updated == 0 and deleted == 0 and completed == 0:
                self.logger.info(success_message + "nothing to sync")

            else:
                if created > 0:
                    success_message += f"{created} created, "
                if updated > 0:
                    success_message += f"{updated} updated, "
                if completed > 0:
                    success_message += f"{completed} completed, "
                if deleted > 0:
                    success_message += f"{deleted} deleted, "

                self.logger.info(success_message[:-2])

            # Save last sync
            self.last_sync = self.config.update_last_sync(self.activity, self.todoist.sync_token)
            self.exception = None
            self.status = 'success'
            return self.last_sync

        except Exception as e:
            # print the stack trace
            self.logger.exception("Todoist sync failed")
            self.logger.error(e)
            self.exception = e 
            self.status = 'failed'



if __name__ == '__main__':
    # set logging level to debug
    logging.basicConfig(level=logging.DEBUG)

    from config import Config
    config = Config()
    todoist_sync = TodoistSync(config)
    todoist_sync.sync()
