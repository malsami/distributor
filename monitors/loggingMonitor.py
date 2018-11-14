
import sys
sys.path.append('../')
from distributor_service.monitor import AbstractMonitor
import logging

class LoggingMonitor(AbstractMonitor):
    
    def __init__(self):
        self.logger = logging.getLogger('OutputMonitorLogger')
        self.hdlr = logging.FileHandler('../distributor_service/log/monitor.log')
        self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        self.hdlr.setFormatter(self.formatter)
        self.logger.addHandler(self.hdlr)
        self.logger.setLevel(logging.DEBUG)
        
    def __taskset_event__(self, taskset):
        pass

    def __taskset_start__(self, taskset):
        pass

    def __taskset_finish__(self, taskset):
        for task in taskset:
            self.logger.info("task: {}".format(task.id))
            self.logger.info(task)

    def __taskset_stop__(self, taskset):
        for task in taskset:
            task['jobs'] = {}
        pass

    def __taskset_bad__(self, taskset, n):
        """After n tries the taskset could not be executedcorrectly"""
        self.logger.info('BAD: after {} tries, the following taskset could not be processed:\n{}'.format(n, str(taskset)))
        pass



