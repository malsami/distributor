from taskgen.monitor import AbstractMonitor


class StdOutMonitor(AbstractMonitor):

    def __init__(self):
        pass
        
    def __taskset_event__(self, taskset):
        pass

    def __taskset_start__(self, taskset):
        pass

    def __taskset_finish__(self, taskset):
        for task in taskset:
            print("task: {}".format(task.id))
            for job in task.jobs:
                print("{} {}".format(job.start_date, job.end_date))

    def __taskset_stop__(self, taskset):
        pass




