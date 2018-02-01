"""Module for monitoring task-set events

Keep in mind, that the methods are called by another threads than the main
thread. Due to this fact, you have to take care of multi threading by using
locks, semaphores, usw.

"""

from abc import ABCMeta, abstractmethod


class AbstractMonitor(metaclass=ABCMeta):
    """Abstract monitor class."""

    @abstractmethod
    def __taskset_event__(self, taskset, event):
        """Called, whenever a job of the taskset is updated."""
        pass

    @abstractmethod
    def __taskset_start__(self, taskset):
        """A task-set processing started"""
        pass

    @abstractmethod
    def __taskset_finish__(self, taskset):
        """A task-set processing is finished."""
        pass

    @abstractmethod
    def __taskset_stop__(self, taskset):
        """A task-set processing is canceled due to an error or is stopped regularly."""
        pass

