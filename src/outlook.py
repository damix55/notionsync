import win32com.client
import pythoncom
import logging

class Outlook:
    """Outlook client class"""

    def __init__(self):
        """Initialize the Outlook client"""

        self.logger = logging.getLogger(__name__)
        self.outlook = win32com.client.Dispatch("Outlook.Application")
        self.outlook_id = pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch, self.outlook)
        self.mapi = self.outlook.GetNamespace("MAPI")


    def mapi_threaded(self):
        """Get MAPI client for threaded use. This is necessary because the MAPI client cannot be used in multiple threads.

        Returns:
            win32com.client.Dispatch: MAPI client
        """

        self.logger.info("Getting MAPI client for threaded use")
        self.outlook = win32com.client.Dispatch("Outlook.Application")
        self.outlook_id = pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch, self.outlook)
        self.outlook = win32com.client.Dispatch(pythoncom.CoGetInterfaceAndReleaseStream(self.outlook_id, pythoncom.IID_IDispatch))
        self.mapi = self.outlook.GetNamespace("MAPI")
        return self.mapi
    

    def iterate_folder(self, folder, from_date=None, to_date=None, last_modified=None, message_class=None, threaded=False):
        """Iterate through the items in the selected folder
        Call pythoncom.CoInitialize() before using this function in a thread and pythoncom.CoUninitialize() after using it.

        Args:
            from_date (datetime): Only return items after this date
            to_date (datetime): Only return items before this date
            last_modified (datetime): Only return items modified after this date
            message_class (str): Only return items with this message class
            threaded (bool): Whether to use a threaded MAPI client

        Yields:
            win32com.client.Dispatch: Item
        """

        # Get the default folder: http://msdn.microsoft.com/en-us/library/office/ff869301(v=office.15).aspx
        if threaded:
            mapi = self.mapi_threaded()
        else:
            mapi = self.mapi

        folder_mapping = {
            3: "Deleted Items",
            9: "Calendar"
        }

        if folder in folder_mapping:
            self.logger.info(f'Iterating through "{folder_mapping[folder]}"')
        else:
            self.logger.info(f"Iterating through folder {folder}")

        folder = mapi.GetDefaultFolder(folder).Items
        folder.IncludeRecurrences = True

        restrictions = []

        date_format = "%d/%m/%Y %I:%M %p"

        if from_date is not None:
            restrictions.append("[Start] >= '" + from_date.strftime(date_format) + "'")

        if to_date is not None:
            restrictions.append("[End] <= '" + to_date.strftime(date_format) + "'")

        if last_modified is not None:
            restrictions.append("[LastModificationTime] > '" + last_modified.strftime(date_format) + "'")

        if message_class is not None:
            restrictions.append("[MessageClass] = '" + message_class + "'")

        if len(restrictions) > 0:
            restrictions = " AND ".join(restrictions)
            self.logger.debug(f"Restricting folder to {restrictions}")
            folder = folder.Restrict(restrictions)

        for item in folder:
            yield item