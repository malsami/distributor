
import sys
sys.path.append('../')
from distributor_service.monitor import AbstractMonitor
import logging

class DataGenerationMonitor(AbstractMonitor):
    
    def __init__(self, output_list):
        self.out = output_list # Tasksets will be appended
        
        
    def __taskset_event__(self, taskset):
        pass


    def __taskset_start__(self, taskset):
        pass


    def __taskset_finish__(self, taskset):
        self.out.append(taskset)

    def __taskset_stop__(self, taskset):
        for task in taskset:
            task['jobs'] = {}
        pass

    def __taskset_bad__(self, taskset, n):
        """After n tries the taskset could not be executedcorrectly"""
        self.out.append(taskset)



