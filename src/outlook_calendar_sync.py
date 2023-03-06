from outlook_calendar import OutlookCalendar
from notion import Notion
import logging
import pythoncom

# [ ] Log migliori
# [ ] Trovare come fare update senza cancellare e ricreare
# [ ] Mettere i link cliccabili sul body?
# [ ] Contenuto filtrato della roba di Teams/Google Meet così ci sono le note di chi organizza il Meeting
# [ ] Icona calendario

class CalendarSyncer:
    """Calendar sync class to sync events from Outlook to Notion

    Attributes:
        config (dict): Config
        logger (self.logger.Logger): Logger
        outlook (OutlookCalendar): Outlook calendar client
        notion (Notion): Notion client
        activity (str): Activity name
        last_sync (datetime): Last sync datetime
    """

    def __init__(self, config, threaded=False):
        self.config = config
        self.config_data = self.config.config
        self.threaded = threaded

        # Setup the logger for logger to stdout and to file
        self.logger = logging.getLogger(__name__)

        self.outlook_calendar = OutlookCalendar()
        self.notion = Notion(self.config_data['notion'], self.config.timezone_str)

        self.activity = 'calendar'
        self.last_sync = self.config.load_last_sync(self.activity)
        self.status = 'not started'
        self.exception = None

        if self.last_sync is not None:
            self.logger.info(f"Last sync: {self.last_sync.strftime('%d/%m/%Y %H:%M:%S')}")
        else:
            self.logger.info("Last sync: never")


    def sync(self, from_date=None, to_date=None):
        """Sync calendar events from Outlook to Notion

        Args:
            from_date (datetime): Only return events from this date
            to_date (datetime): Only return events to this date
        """

        created = 0
        updated = 0
        deleted = 0

        if self.threaded:
            pythoncom.CoInitialize()

        try:
            # Iterate through all new and modified events
            for event in self.outlook_calendar.iterate_events(from_date, to_date, self.last_sync, self.threaded):
                if event['subject'] in self.config_data['calendar']['ignore']:
                    self.logger.info(f"Skipping event: {event['subject']}")
                    continue

                self.logger.info(f"Syncing event: {event['subject']} ({event['start'].strftime('%d/%m/%Y')}")

                # Check if event exists in notion
                notion_event_id = self.notion.check_event_exists(event['id'])

                if notion_event_id is not None:
                    self.logger.info("Event already exists in Notion, updating it")
                    self.notion.update_calendar_event(notion_event_id, event)
                    updated += 1

                else:
                    self.logger.info("Event does not exist in Notion, creating it")
                    self.notion.add_calendar_event(event)
                    created += 1

            # Iterate through all deleted events from last sync
            for event in self.outlook_calendar.iterate_deleted_events(self.last_sync, self.threaded):
                if event['subject'] in self.config_data['calendar']['ignore']:
                    self.logger.info(f"Skipping event: {event['subject']}")
                    continue

                self.logger.info(f"Deleting event: {event['subject']}")

                # Check if event exists in notion
                notion_event_id = self.notion.check_event_exists(event['id'])

                if notion_event_id is not None:
                    self.logger.info("Event exists in Notion, deleting it")
                    self.notion.delete_calendar_event(notion_event_id)
                    deleted += 1

                else:
                    self.logger.info("Event does not exist in Notion, skipping")

            
            success_message = f"Calendar sync successful: "
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
            self.last_sync = self.config.update_last_sync(self.activity)
            self.exception = None
            self.status = 'success'
            return self.last_sync
        
        
        except Exception as e:
            # print the stack trace
            self.logger.exception("Calendar sync failed")
            self.logger.error(e)


            self.exception = e 
            self.status = 'failed'

        finally:
            if self.threaded:
                pythoncom.CoUninitialize()