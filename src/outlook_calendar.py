import datetime
import math
import pywintypes
from outlook import Outlook

# [ ] get the link for joining a meeting
# [ ] eventi ricorrenti sono buggati quando vanno aggiornati o cancellati (se cambio orario non lo trova più...)
# [ ] finire log da get_reccurrent_occurences in poi


class OutlookCalendar(Outlook):
    """Outlook calendar client class"""

    def __init__(self):
        """Initialize the Outlook calendar client"""

        super().__init__()
        self.logger.info("Initializing Outlook calendar client")
        self.deleted_recurrences = []


    def iterate_events(self, from_date=None, to_date=None, last_modified=None, threaded=False):
        """Iterate through the events in the calendar
        Call pythoncom.CoInitialize() before using this function in a thread and pythoncom.CoUninitialize() after using it.

        Args:
            from_date (datetime): Only return events after this date
            to_date (datetime): Only return events before this date
            last_modified (datetime): Only return events modified after this date
            threaded (bool): Whether to use a threaded MAPI client

        Yields:
            dict: Event
        """
        
        for event in self.iterate_folder(9, from_date, to_date, last_modified, threaded=threaded):
            self.logger.info(f"Event: {event.Subject} - start: {event.Start} - last modified: {event.LastModificationTime}")

            if event.IsRecurring:
                self.logger.debug("Recurring event, iterating through occurrences")
                for occurrence, recurrence_number in self.get_reccurrent_occurences(event, from_date, to_date, last_modified):
                    yield self.appointment_to_dict(occurrence, recurrence_number)

            else:
                event_dict = self.appointment_to_dict(event)
                yield event_dict


    def iterate_deleted_events(self, last_modified=None, threaded=False):
        """Iterate through the deleted events in the calendar
        Call pythoncom.CoInitialize() before using this function in a thread and pythoncom.CoUninitialize() after using it.

        Args:
            last_modified (datetime): Only return events modified after this date
            threaded (bool): Whether to use a threaded MAPI client

        Yields:
            dict: Deleted event
        """

        for event in self.iterate_folder(3, last_modified=last_modified, message_class="IPM.Appointment", threaded=threaded):
            self.logger.info(f"Deleted event: {event.Subject} - start: {event.Start} - last modified: {event.LastModificationTime}")

            if event.IsRecurring:
                self.logger.debug("Recurring deleted event, iterating through occurrences")
                for occurrence, recurrence_number in self.get_reccurrent_occurences(event, last_modified=last_modified):
                    yield self.appointment_to_dict(occurrence, recurrence_number)

            yield self.appointment_to_dict(event)

        for occurrence, recurrence_number, recurrence_date in self.deleted_recurrences:
            self.logger.info(f"Deleted recurrent event: {occurrence.Subject} - start: {recurrence_date} - recurrence number: {recurrence_number}")
            yield self.appointment_to_dict(occurrence, recurrence_number, recurrence_date)



    def get_reccurrent_occurences(self, appointment, from_date=None, to_date=None, last_modified=None):
        """Get the occurrences of a recurring appointment

        Args:
            appointment (win32com.client.Dispatch): Appointment object
            from_date (datetime): Only return events after this date
            to_date (datetime): Only return events before this date
            last_modified (datetime): Only return events modified after this date

        Yields:
            tuple: Occurrence, recurrence number
        """

        recurrence_pattern = appointment.GetRecurrencePattern()
        recurrence_type = recurrence_pattern.RecurrenceType

        start_date = appointment.Start
        end_date = recurrence_pattern.PatternEndDate
        self.logger.debug(f"Recurrence start date: {start_date} - end date: {end_date}")

        recurrence_map = {
            0: 1,   # Daily
            1: 7,   # Weekly
            2: 30,  # Monthly
            3: 365  # Yearly
        }
        delta_days = recurrence_map.get(recurrence_type, None)
        self.logger.debug(f"Recurrence type: {recurrence_type} - delta days: {delta_days}")

        if delta_days is None:
            raise Exception("Unknown recurrence type: " + recurrence_type)

        # These are the exceptions to the recurrence pattern
        exceptions = list(recurrence_pattern.Exceptions)

        # sort the exceptions by date
        exceptions.sort(key=lambda x: x.OriginalDate)

        if from_date is None or from_date < start_date:
            from_date = start_date

        if to_date is None or to_date > end_date:
            to_date = end_date

        # remove the exceptions that are before the from_date
        exceptions = [e for e in exceptions if e.OriginalDate >= from_date]

        # Get the first occurrence starting from the from_date
        recurrence_number = math.ceil((from_date - start_date).days / delta_days)
        recurrence_date = start_date + datetime.timedelta(days=recurrence_number * delta_days)

        while recurrence_date.date() <= to_date.date():
            # Check if the occurrence is an exception
            next_exception = exceptions[0] if len(exceptions) > 0 else None
            if next_exception is not None and next_exception.OriginalDate.date() == recurrence_date.date():
                if next_exception.Deleted:
                    occurrence = None

                else:
                    occurrence = next_exception.AppointmentItem
                    
                exceptions.pop(0)

            else:
                try:
                    occurrence = recurrence_pattern.GetOccurrence(recurrence_date)
                
                except pywintypes.com_error:
                    self.logger.warning("No occurrence found for " + appointment.Subject + " on " + recurrence_date.strftime("%d/%m/%Y"))
                    occurrence = None


            if occurrence is not None:
                occurrence_last_modified = occurrence.LastModificationTime

                if last_modified is None or occurrence_last_modified >= last_modified:
                    yield occurrence, recurrence_number

            else:
                # If the occurrence is deleted, save it to the deleted_recurrences list
                self.deleted_recurrences.append((appointment, recurrence_number, recurrence_date))

            recurrence_number += 1
            recurrence_date += datetime.timedelta(days=delta_days)


    def appointment_to_dict(self, appointment, recurrence_num=None, recurrence_date=None):
        """Convert an appointment object to a dict

        Args:
            appointment (win32com.client.Dispatch): Appointment object
            recurrence_num (int): Recurrence number
            recurrence_date (datetime): Recurrence date

        Returns:
            dict: Event data
        """

        identifier = appointment.GlobalAppointmentID
        if recurrence_num is not None:
            identifier += f"_{recurrence_num}"

        if recurrence_date is None:
            appointment_start = appointment.Start
            appointment_end = appointment.End

        else:
            appointment_start = recurrence_date
            appointment_end = recurrence_date + (appointment.End - appointment.Start)
            

        event_dict = {
            "id": identifier,
            "subject": appointment.Subject,
            "start": appointment_start,
            "end": appointment_end,
            "location": appointment.Location,
            "project": appointment.Categories,
            "organizer": appointment.Organizer,
            "last_modified": appointment.LastModificationTime,
        }
        
        self.logger.debug(f"Event dict: {event_dict}")

        event_dict.update({"body": appointment.Body})
        return event_dict