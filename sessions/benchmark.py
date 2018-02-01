import logging
import time
from taskgen.taskset import TaskSet
from taskgen.distributor import AbstractSession


class Session(AbstractSession):
    
    def __init__(self, host, port):
        pass
        
    def start(self, taskset, optimization):
        taskset.description()
        taskset.binaries()
        
    def stop(self):
        pass

    def event(self):
        return None

    def close(self):
        pass



        
