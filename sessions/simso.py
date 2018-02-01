import logging
import sys

from taskgen.taskset import TaskSet
from taskgen.task import Job
from taskgen.session import AbstractSession
from simso.core import Model
from simso.configuration import Configuration



class SimSoSession(AbstractSession):
    
    def __init__(self, host, port):
        self.logger = logging.getLogger("SimSoSession")

        # choose a configuration
        self.configuration = Configuration()
        # set processsors
        self.configuration.add_processor(name="CPU 1", identifier=1)

        
    def start(self, taskset, scheduler_class = "simso.schedulers.RM"):
        # add tasks to simso
        for task in taskset:
            self.configuration.add_task(
                name = 'task_'+str(task['id']),
                identifier = task['id'],
                period = task['period'],
                activation_date = 0,
                wcet = 3, # !
                deadline = 20
            )

        self.configuration.scheduler_info.clas = scheduler_class
        self.configuration.check_all()
        self.model = Model(self.configuration)

    def is_available(host):
        return True
    
    def is_running(self, taskset):
        # this method is called after the first `run`. So we are already done.
        return False 
        
    def stop(self):
        pass

    def run(self, taskset):
        # run the model
        self.model.run_model()

        # update taskset
        for task in self.model.results.tasks:
            _task = self._get_task_by_id(taskset, task.identifier)
            for job in task.jobs:
                _job = Job()
                _job.start_date = job.activation_date
                _job.end_date = job.end_date
                _task.jobs.append(_job)

                
    def close(self):
        pass
    
    def _get_task_by_id(self, taskset, task_id):
        # the taskset is a list, we have to loop over all items...
        for task in taskset:
            if task.id == task_id:
                return task
        return None
