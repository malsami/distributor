
import sys
sys.path.append('../')
from distributor.monitor import AbstractMonitor
import logging

class ValueTestingMonitor(AbstractMonitor):
    
    def __init__(self, output_list):
        self.out = output_list
        # listelements have the following format
        # (tasksetTries, {id : (Task, [Job]) })    tasksetTries=0 if successful; Job=(startTime, exitTime, eventType)

        
    def __taskset_event__(self, taskset):
        pass


    def __taskset_start__(self, taskset):
        pass


    def __taskset_finish__(self, taskset):
        ret_dict = {}
        for task in taskset:
            j = []
            for number, job in task['jobs'].items():
                j.append((job[0], job[1], job[2]))
            ret_dict[str(task.id)] = (task,j)
        self.out.append((0,ret_dict))

    def __taskset_stop__(self, taskset):
        for task in taskset:
            task['jobs'] = {}
        pass

    def __taskset_bad__(self, taskset, n):
        """After n tries the taskset could not be executedcorrectly"""
        ret_dict = {}
        for task in taskset:
            j = []
            for number, job in task['jobs'].items():
                j.append((job[0], job[1], job[2]))
            ret_dict[str(task.id)] = (task,j)
        self.out.append((n,ret_dict))



