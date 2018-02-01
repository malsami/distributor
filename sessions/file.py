import logging
import time
from taskgen.taskset import TaskSet
from taskgen.distributor import AbstractSession

from pprint import pprint

COUNTER = 0
COLORS_FG = [
    '\033[31m', # red
    '\033[32m', # green
    '\033[33m', # orange
    '\033[34m', # blue
    '\033[35m', # purple
    '\033[36m', # cyan
    '\033[37m', # lightgrey
    '\033[90m', # darkgrey
    '\033[91m', # lightred
    '\033[92m', # lightgreen
    '\033[93m', # yellow
    '\033[94m', # lightblue
    '\033[95m', # pink
    '\033[96m' #lightcyan
]
COLOR_RESET = '\033[0m'

class FileSession(AbstractSession):
    
    def __init__(self, host, port):
        self.logger = logging.getLogger("StdIOSession")
        self.logger.debug("stub created")

        # select color
        global COUNTER
        self.index = COUNTER % len(COLORS_FG)
        COUNTER = COUNTER + 1
        
    def start(self, taskset, optimization):
        self.logger.debug("start of taskset")
        self._timestamp = time.clock()
        self._print(taskset.description())
        self._write(taskset.description())

    def stop(self):
        self.logger.debug("stop of taskset")

    def event(self):
        running = time.clock() - self._timestamp
        return {
            'running' : running < 0.1 # 1 seconds
        }

    def close(self):
        self.logger.debug("connection closed")

    def _write(self, obj):
        with open("taskset.xml", "w") as f: 
            f.write(obj)
        
    def _print(self,  obj):
        print(COLORS_FG[self.index])
        print("taskset size: {} bytes".format(len(obj.encode("utf8"))))
        print(obj)
        print(COLOR_RESET)


        
