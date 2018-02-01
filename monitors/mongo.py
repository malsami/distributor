from taskgen.monitor import AbstractMonitor
from pymongo import MongoClient

"""Monitor for mongodb


"""


class MongoMonitor(AbstractMonitor):
    """Stores task-sets and events to a MongoDB


    """
    
    def __init__(self, uri='mongodb://localhost:27017'):
        client = MongoClient(uri)
        self.database = client['tasksets']

    def __taskset_event__(self, taskset):
        pass
        
    def __taskset_start__(self, taskset):
        pass

    def __taskset_finish__(self, taskset):
        for task in taskset:
            jobs_func = lambda job : {
                'start_date' : job.start_date,
                'end_date' : job.end_date
            }
            
            # insert description & jobs of task to db
            self.database.taskset.task.insert_one({
                'description' : task,
                'jobs' : list(map(jobs_func, task.jobs))
            })
            
    def __taskset_stop__(self, taskset):
        pass
