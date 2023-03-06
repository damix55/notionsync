import argparse
import logging
import os
import sys
import datetime
import time
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QSystemTrayIcon,
    QMenu,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget
)
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtGui import QIcon
from outlook_calendar_sync import CalendarSyncer
from _utils import get_file_path, load_timezone, load_config
from _logger import logger_setup

# [ ] stop the process after n errors ?
# [ ] manual start doesnt work
# [ ] update the tarkbar tooltip with the last sync date
# [ ] gestione errori
# IDEE:
# - Perché non utilizzare direttamente il db Worklog invece di Calendario?
# - A questo punto:
#   - Nuova colonna "Tipo: Meeting oppure Tag: Meeting/Evento
#   - Contenuto filtrato della roba di Teams/Google Meet così ci sono le note di chi organizza il Meeting
#   - Ore: span di tempo tra inizio e fine evento
#   - Rimane in Worklog, ci posso prendere appunti sopra


class SyncerGUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.config = load_config()

        self.logger = logging.getLogger(__name__)
        logger_setup(f'{get_file_path()[0]}/logs', keep_for_days=self.config['logs']['keep_for_days'], stdout_level='INFO')
        
        # Set up the main window
        self.setWindowTitle("NotionSync 0.0.1")
        self.setFixedSize(400, 100)

        # Get the path to the file
        self.file_path = get_file_path()[0] 

        # Set up the system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.setIcon(QIcon("assets/icon.png"))
        self.tray_icon.setToolTip("Calendar status: OK\nLast sync: " + str(datetime.date.today()))
        self.tray_icon.setVisible(True)

        # Create a context menu for the system tray icon
        self.tray_menu = QMenu()
        self.tray_menu.addAction("Open", self.show)
        self.tray_menu.addAction("Logs", self.open_logs)
        self.tray_menu.addAction("Quit", QApplication.quit)
        self.tray_icon.setContextMenu(self.tray_menu)

        # Initialize the objects
        calendar = CalendarSyncer(self.config, threaded=True)

        # Create the widgets
        self.calendar_gui_syncer = SyncerElement(calendar, 'Calendar')
        # self.mail_gui_syncer = SyncerElement(calendar, 'Mail')

        # Create the main layout
        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.calendar_gui_syncer)
        # self.main_layout.addLayout(self.mail_gui_syncer)

        # Create the main widget
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)

        # Set the main widget as the central widget of the window
        self.setCentralWidget(self.main_widget)

        # Hide the main window on startup
        self.hide()


    def open_logs(self):
        """Open the current log file in the default text editor"""
        # Get the path to the log file
        log_file = f"{self.file_path}/logs/{datetime.date.today():%Y-%m-%d}.log"

        # Open the log file in the default text editor
        os.startfile(log_file)



    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()


    def closeEvent(self, event):
        event.ignore()
        self.hide()


class SyncerElement(QHBoxLayout):
    def __init__(self, handler, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

        self.label = QLabel(name)
        self.label.setStyleSheet("font-weight: bold;")
        self.ok_label = QLabel("OK")
        self.ok_label.setStyleSheet("color: green; font-weight: bold;")
        self.sync_label = QLabel()

        self.handler = handler
        
        last_sync = self.handler.last_sync
        if last_sync is None:
            self.sync_label.setText("Last sync: never")

        else:
            self.update_sync_time(last_sync)

        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(QIcon("assets/refresh.png"))
        self.refresh_button.setFixedSize(32, 32)
        self.refresh_button.clicked.connect(self.manual_sync)

        self.pause_button = QPushButton()
        self.pause_button.setIcon(QIcon("assets/pause.png"))
        self.pause_button.setFixedSize(32, 32)
        self.pause_button.clicked.connect(self.toggle_pause)

        self.is_paused = False
        self.is_running = False

        self.addWidget(self.label)
        self.addWidget(self.ok_label)
        self.addWidget(self.sync_label)
        self.addWidget(self.refresh_button)
        self.addWidget(self.pause_button)

        self.sync_thread = QThread()
        self.sync_worker = SyncScheduler(self.handler, 1)
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_thread.started.connect(self.sync_worker.start_sync)
        self.sync_worker.last_sync.connect(self.update_sync_time)

        # disable the buttons if the sync process is running
        self.sync_worker.is_running.connect(self.pause_button.setDisabled)
        self.sync_worker.is_running.connect(self.refresh_button.setDisabled)
        self.sync_worker.is_running.connect(self.update_status_running)

        if not self.is_paused:
            self.start_sync_thread()

    
    def start_sync_thread(self):
        """
        Start the sync thread.
        """
        self.sync_thread.wait()
        self.sync_thread.start()


    def quit_sync_thread(self):
        """
        Quit the sync thread.
        """
        self.sync_worker.pause_sync()
        self.sync_thread.quit()


    def manual_sync(self):
        """
        Manually sync with the button.
        """

        if not self.is_running:
            self.logger.info("Manual sync")
            self.quit_sync_thread()
            self.start_sync_thread()


    def pause_process(self):
        """
        Pause the sync process.
        """
        self.is_paused = True
        self.pause_button.setIcon(QIcon("assets/play.png"))
        self.update_status("Paused")
        self.quit_sync_thread()


    def start_process(self):
        """
        Start the sync process.
        """
        self.is_paused = False
        self.pause_button.setIcon(QIcon("assets/pause.png"))
        self.update_status("OK")
        self.start_sync_thread()


    def toggle_pause(self):
        """
        Toggle the pause status of the sync process.
        """
        if self.is_paused:
            self.start_process()

        else:
            self.pause_process()


    def update_sync_time(self, time):
        """
        Update the last sync time.

        Args:
            time (datetime): Time of the last sync
        """
        
        today = datetime.date.today()

        if time.date() == today:
            date = "today"

        elif time.date() == today - datetime.timedelta(days=1):
            date = "yesterday"

        else:
            date = time.strftime("%d/%m/%Y")

        self.sync_label.setText(f"Last sync: {date}, {time.strftime('%H:%M:%S')}")


    def update_status_running(self, is_running):
        """
        Update the status of the syncer element to "Syncing...".
        """
        self.is_running = is_running
    
        if is_running:
            self.update_status("Syncing...")
        
        else:
            if self.is_paused:
                self.update_status("Paused")
            
            else:
                self.update_status("OK")
            

    def update_status(self, status):
        """
        Update the status of the syncer element.

        Args:
            status (str): Status to update to
        """

        color_map = {
            "OK": "green",
            "Error": "red",
            "Paused": "orange",
            "Syncing...": "gray"
        }

        self.ok_label.setText(status)
        self.ok_label.setStyleSheet(f"color: {color_map[status]}; font-weight: bold;")


class SyncScheduler(QObject):
    last_sync = pyqtSignal(datetime.datetime)
    is_running = pyqtSignal(bool)

    def __init__(self, handler, minutes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.handler = handler
        self.minutes = minutes
        self.pause = False
        self.is_running.emit(False)


    def sync(self):
        self.is_running.emit(True)
        # Sync from yesterday
        # TODO make it configurable
        from_date = datetime.datetime.now(load_timezone()) - datetime.timedelta(days=1)
        last_sync = self.handler.sync(from_date=from_date)
        self.last_sync.emit(last_sync)
        self.is_running.emit(False)


    def start_sync(self):
        self.pause = False
        refresh_time = 1

        while not self.pause:
            self.sync()

            sleep_time = self.minutes * 60

            # Check every second if the pause button has been pressed
            while sleep_time > 0:
                if self.pause:
                    break

                time.sleep(refresh_time)
                sleep_time -= refresh_time

    
    def pause_sync(self):
        self.pause = True
            

if __name__ == '__main__':
    # Create an argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-from", choices=["gui", "taskbar"], default="gui")

    # Parse the arguments
    args = parser.parse_args()

    # Start the application
    app = QApplication(sys.argv)
    myapp = SyncerGUI()

    # Determine whether to start from GUI or taskbar
    if args.start_from == "gui":
        myapp.show()
    elif args.start_from == "taskbar":
        myapp.tray_icon.show()

    sys.exit(app.exec_())