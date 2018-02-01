"""Module for establishing connection to a target plattform

"""

from abc import ABCMeta, abstractmethod


class AbstractSession(metaclass=ABCMeta):
    """Abstract class for the low level implementation of a session.

    It is important to keep the low level implementation as simple as possible
    for debugging purposes. For examples, look at the `taskgen.sessions.*`
    implementations.

    """
    
    @staticmethod
    def is_available(host):
        """Check the availability of a destination. 

        The goal of the this method is to run a short check, if a destination is
        most likely available. This is useful for connections over network,
        where establishing connections have a long timeout and an IP range need
        to be scanned. Implementing a short ping test shortens the scan
        duration.

        :param host str: IP address formatted as string, like: "192.25.1.2"

        :return: `True`, if the destination is available, otherwise `False`
        :rtype: bool

        """
        return True
    
    @abstractmethod
    def __init__(self, host, port):
        """Called, whenever a connection to a target plattform is established.

        It is fully valid, to raise an error if the connection establishing fails.

        :param host str: IP address of target plattform formatted as string,
        like: "192.25.1.2" 
        :param port int: Port of target plattform.

        """
        pass

    @abstractmethod
    def start(self, taskset, *params):
        """Start processing a task-set
        
        :param taskset taskgen.taskset.TaskSet: Process this taskset 
        :param *params: Further optional parameters, which are passed by the `start`
        method of the distributor.

        """
        pass

    @abstractmethod
    def stop(self):
        """Stop processing current task-sets"""
        pass

    @abstractmethod
    def is_running(self, taskset):
        """Determinate if task-set is still executing

        :return: `True`, if task-set is still running, False otherwise.
        :rtype: bool
        """
        pass

    @abstractmethod
    def run(self, taskset):
        """Updates task-set with incoming event data

        During runtime a task is executed multiple times. A single execution is
        called `Job`. Whenever a jobs is starts, a new `taskgen.task.Job` object
        is added to the task. If the the jobs stops, the `Job` object is updated
        by an end-date. For a concret implementation, look at `sessions.genode`.
        
        This method is called multiple times during the task-set execution and
        updates the tasks of the task-set with data.
        
        :return: `True`, if task-set changed, `False` otherwise
        :rtype: bool
        """
        pass

    @abstractmethod
    def close(self):
        """Close connection"""
        pass
