import datetime
from todoist import Todoist
from notion import Notion
import logging

# [ ] sincronizzare colore label/tags ?
# [ ] conversione da markdown a formato notion
# [ ] implementare task con quick add (tipo se inserisci da notion con dentro # o @ fai aggiunta rapida)
# [ ] se un task su notion ha la colonna id vuota, possiamo assumere che sia nuovo
# [ ] se rimuovo data su notion, non viene rimossa su todoist
# [ ] se spunto evento ricorrente su Notion, invece di crearmi la nuova ricorrenza, me lo spunta del tutto (non appare più su todoist)
# [ ] aggiornare data su Notion quando si inserisce/aggiorna/spunta un evento ricorrente da Notion (altrimenti rimane vuota o non aggiornata)
# [ ] eventi ricorrenti sono buggati, a volte sposta il giorno su todoist (capire perché)

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

        if self.last_sync is not None:
            self.logger.info(f"Last sync: {self.last_sync.strftime('%d/%m/%Y %H:%M:%S')}")
        else:
            self.logger.info("Last sync: never")

    
    def sync(self):
        created = 0
        updated = 0
        deleted = 0

        # Used for Notion to Todoist sync
        before_last_sync = datetime.datetime.now(tz=self.config.timezone)

        # Update projects list
        self.notion.update_projects()

        just_modified = []

        # Sync Todoist to Notion
        for task in self.todoist.sync_read_items(self.sync_token):
            task_content = task['content']

            # Check if event exists in notion
            notion_task_id = self.notion.check_task_exists(task['id'])

            # Delete tasks
            if task['is_deleted']:
                self.logger.info(f"Deleting task: {task_content}")
                if notion_task_id is not None:
                    self.notion.delete_task(notion_task_id)
                    deleted += 1
                else:
                    self.logger.info(f"Task does not exist in Notion, skipping")
            else:
                # Update task
                if notion_task_id is not None:
                    self.logger.info(f"Updating task: {task_content}")
                    self.notion.update_task(notion_task_id, task)
                    just_modified.append(task['id'])
                    updated += 1

                # Create task
                else:
                    self.logger.info(f"Creating task: {task_content}")
                    self.notion.add_task(task)
                    just_modified.append(task['id'])
                    created += 1

        success_message = f"Notion tasks sync successful: "
        if created == 0 and updated == 0 and deleted == 0:
            self.logger.info(success_message + "nothing to sync")

        else:
            if created > 0:
                success_message += f"{created} created, "
            if updated > 0:
                success_message += f"{updated} updated, "
            if deleted > 0:
                success_message += f"{deleted} deleted, "

            self.logger.info(success_message[:-2])

        
        # Sync Notion to Todoist
        created = 0
        updated = 0
        deleted = 0

        for task in self.notion.get_tasks(self.last_sync, before_last_sync):
            task_content = task['content']

            # Check if event exists in notion
            task_exists = self.todoist.check_task_exists(task['id'])

            # Delete tasks
            if task['is_deleted']:
                pass    # Notion non restituisce task cancellati
                # self.logger.info(f"Deleting task: {task_content}")
                # if todoist_task_id is not None:
                #     self.todoist.delete_task(todoist_task_id)
                #     deleted += 1
                # else:
                #     self.logger.info(f"Task does not exist in Todoist, skipping")
            else:
                if task['id'] in just_modified:
                    self.logger.info(f"Skipping task: {task_content} (just modified)")
                    continue

                # Update task
                if task_exists:
                    self.logger.info(f"Updating task: {task_content}")
                    self.todoist.update_task(task)
                    updated += 1

                # Create task
                else:
                    self.logger.info(f"Creating task: {task_content}") 
                    task_id = self.todoist.add_task(task)
                    # update the id on notion
                    self.notion.update_id_task(task['notion_id'], task_id)
                    created += 1
        

        success_message = f"Todoist tasks sync successful: "
        if created == 0 and updated == 0 and deleted == 0:
            self.logger.info(success_message + "nothing to sync")

        else:
            if created > 0:
                success_message += f"{created} created, "
            if updated > 0:
                success_message += f"{updated} updated, "
            if deleted > 0:
                success_message += f"{deleted} deleted, "

            self.logger.info(success_message[:-2])


        # Save last sync
        self.sync_token = self.todoist.sync_token
        self.last_sync = self.config.update_last_sync(self.activity, self.sync_token)
        return self.last_sync



if __name__ == '__main__':
    # set logging level to debug
    logging.basicConfig(level=logging.INFO)

    from config import Config
    config = Config()
    todoist_sync = TodoistSync(config)
    todoist_sync.sync()
