"""Module for asyncron distribution of task-sets

This modules provides a class for the distribution of task-sets to one or
multiple target plattforms. The connection to a target plattform is handled by a
session.

"""


from abc import ABCMeta, abstractmethod
import threading
import time
import logging
import subprocess
import copy
import socket
from queue import Empty, Queue, Full
from collections.abc import Mapping
from ipaddress import ip_network, ip_address
from itertools import chain
from math import ceil
import errno

from taskgen.taskset import TaskSet #TODO pfad anpassen
from taskgen.monitor import AbstractMonitor#TODO pfad anpassen
from taskgen.session import AbstractSession#TODO pfad anpassen
from taskgen.sessions.genode import PingSession#TODO pfad anpassen


class Distributor:
    """Class for controll over host sessions and asycronous distribution of tasksets"""
    
    def __init__(self,
                 max_machine = 5):
        """Start a bridge and await tasksets.

        :param max_machine int: positive non zero number of machines the distributor is allowed hold

        """
"""DEPRECATED
        if not isinstance(port, int):
            raise TypeError("port must be int")

        if not issubclass(session_class, AbstractSession):
            raise TypeError("session_class must be a class with subtype AbstractSession")
"""
        self._max_machine = max_machine
        self._sessions = []
        self._starter = []
        self._port = port
        self._session_class = session_class
        self.logger = logging.getLogger('Distributor')
        self._close_event = threading.Event()
        self._pool = Queue()
        self._monitor = None
        self._run = False
        self._tasksets = []
        self._session_params = None
        
        self._create_bridge(self)


    def _create_bridge(self):
        #TODO: create network bridge and keep reference for cleanup
        pass

"""DEPRECATED        
        # build pool of IP destination addresses
        if isinstance(destinations, str):
            self._append_pool(destinations)
        elif isinstance(destinations, list):
            for destination in destinations:
                self._append_pool(destination)
        else:
            raise TypeError("destinations must be [str] or str.")

        # initialize pinging and connecting of destinations
        for c in range(0, starter_threads):
            starter = threading.Thread(target=Distributor._starter, args=(self,))
            starter.start()
            self._starter.append(starter)
"""
"""DEPRECATED
            
    def _append_pool(self, destination):
        #Adds a range of ip addresses to the pool
        # try to parse as single ip address
        try:
            ip = ip_address(destination)
            self._pool.put(str(ip))
            return
        except ValueError:
            pass
        # parse as ip range or raise error
        for ip in ip_network(destination).hosts():
            self._pool.put(str(ip))
"""

    def get_max_machine_value(self):
        """Returns the current max_machine value."""
        return self._max_machine
    

    def set_max_machine_value(self, new_value):
        """Changes the _max_machine value.
        :param new_value int: positive non zero value
        :raises ValueError: new_value is not a natural number
        """
        if isinstance(new_value, int) and 0 < new_value:
            #TODO maybe add upper bound for not crashing the system with large numbers
            self._max_machine = new_value
            #TODO: add notification to adjust running sessions if running
        else:
            raise ValueError("The new max_machine value is not an integer greater zero.")

    def _refresh_starter(self):
        #Adjusts the amount of running starter threads to the current max_machine value.
        if not self._starter:
            for c in range(0, self._max_machine):
                starter = threading.Thread(target=Distributor._starter, args=(self,))
                starter.start()
                self._starter.append(starter)
        else:
            l = self._max_machine - len(self._starter)
            if l > 0:
                for c in range(0,l):
                starter = threading.Thread(target=Distributor._starter, args=(self,))
                starter.start()
                self._starter.append(starter)
            elif l < 0:
                #TODO stop l threads (gently)



    @staticmethod
    def _starter(self):
        """Starts up a Qemu instance with Genode and a session to connect to Genode.
        
        A thread _`WrapperSession` is started for establishing a connection. 
        The actual connection is handled by a session.
        
        This method is only called by a seperated thread. These are started in
        `_refresh_starter`.

        """

        # continue checking destination in the pool until distributor is closed.
        while not self._close_event.is_set():
            try:
                host = self._pool.get(True, 2)
                if self._session_class.is_available(host):
                    self.logger.info("Found {}".format(host))
                    # initalize session
                    session = _WrapperSession(host,
                                              self._port,
                                              self._close_event,
                                              self._session_class,
                                              self._pool,
                                              self._sessions)
                    session.monitor = self.monitor
                    # start session
                    if self._run:
                        session.start(self._tasksets, *self._session_params)
                    session.thread_start()
                    self._sessions.append(session)
                else:
                    self._pool.put(host)
            except Empty:
                pass

            
    @property
    def monitor(self):
        """Getter method for the currently used monitor.
        
        :return: returns the currenctly monitor. If no monitor is set, `None` is
        the return value.

        :rtype: taskgen.monitor.AbstractMonitor or None

        """
        return self._monitor

    
    @monitor.setter
    def monitor(self, monitor):
        """Setter method for a monitor.
        
        :param monitor taskgen.monitor.AbstractMethod: Set `monitor` as handler
        for incoming events.

        """
        if monitor is not None:
            if not isinstance(monitor, AbstractMonitor):
                raise TypeError("monitor must be of type AbstractMonitor")
        self._monitor = monitor
        for session in self._sessions:
            session.monitor = monitor

            
    def start(self, taskset, *session_params, wait=True):
        ####TODO: this should trigger spawning of _start threads

        """Starts the distribution of task-sets

        :param taskset taskgen.taskset.TaskSet: a taskset for the distribution

        :param session_params: optional parameters which are passed to the
        `start` method of the actual session. Pay attention: Theses parameters
        must be implemented by the session class. A good example is the
        `taskgen.sessions.genode.GenodeSession`, which implements a parameter
        for optional admission control configuration.  

        :param wait bool: `False` if the method should not wait until all
        sessions started and the method returns immediately. 

        """
        if taskset is None or not isinstance(taskset, TaskSet):
            raise TypeError("taskset must be TaskSet.")

        # wrap tasksets into an threadsafe iterator
        self._tasksets = _TaskSetQueue(taskset.variants())
        self._session_params = session_params
        self._run = True
        for session in self._sessions:
            session.start(self._tasksets, *session_params)
        if wait: self.wait_finished()

        
    def stop(self, wait=True):
        """Stops the distribution of task-sets

        :param wait bool: `False` if the method should not wait until all
        sessions stopped and the method returns immediately.

        """
        self.logger.info("Stop processing taskset")
        self._run = False
        for session in self._sessions:
            session.stop()
        if wait: self.wait_stopped()

        
    def close(self, wait=True):
        """Closes all connections to distributors.

        After closing this distributor the usage is exhausted. Do not call any
        methods after.  

        :param wait bool: `False` if the method should not wait until all
        sessions are closed and the method returns immediately.

        """
        self._close_event.set()
        self.logger.info("Closing connections...")
        if wait: self.wait_closed()

        
    def wait_closed(self):
        """Waits until all connections to target plattforms are closed."""        
        self.logger.info("Waiting until ping threads are stopped")
        for starter in self._starter:
            starter.join()

        # TODO: when closing, it might happen that a starter thread still opens a connection.
        # the log message then might be disturbing.
        self.logger.info("Waiting until sessions are closed")
        for session in self._sessions:
            session.join()
        
    def wait_stopped(self):
        """Waits until all sessions stopped processing task-sets."""        
        self.logger.info("Waiting until session processings are stopped")
        for session in self._sessions:
            session.wait_stopped()

    def wait_finished(self):
        """Waits until all sessions finished processing task-sets."""
        while not self._close_event.is_set():
            if self._tasksets.empty():
                break
            time.sleep(1)

            
class _TaskSetQueue():
    """Takes an iterator/generator and makes it thread-safe by
    serializing call to the `next` method of given iterator/generator.
    """
    def __init__(self, iterator):
        self.it = iterator
        self.lock = threading.Lock()
        self.queue = Queue(maxsize=1000)
        self.in_progress = []
        self.processed = 0
        self.logger = logging.getLogger("Distributor")
        
    def get(self):
        # return a regular taskset
        with self.lock:
            taskset = None
            if not self.queue.empty():
                try:
                    taskset = self.queue.get_nowait()
                except Queue.Empty:
                    # ups, another distributor just stole our taskset
                    pass

            # take a new one from the iterator
            if taskset is None:
                taskset = self.it.__next__()

            # keep track of current processed tasksets
            self.in_progress.append(taskset)
            return taskset
            
    def empty(self):
        with self.lock:
            # in progress?
            if len(self.in_progress) > 0:
                return False
            # in queue?
            if not self.queue.empty():
                return False
            # in iterator?
            try:
                self.queue.put(self.it.__next__())
                return False
            except StopIteration:
                return True

    def done(self, taskset):
        """Call this method, if a task-set is finally processed.

        This mechanism keeps references of currenctly processed task-sets.

        """
        with self.lock:
            self.in_progress.remove(taskset)
            self.processed += 1
            self.logger.info("{} taskset variant(s) processed".format(self.processed))
        
    def put(self, taskset):
        """Call this method, if a task-set processing is canceled.

        This mechanism keeps references of currenctly processed task-sets.

        """
        with self.lock:
            try:
                self.in_progress.remove(taskset)
                self.queue.put_nowait(taskset)
            except Full:
                # We don't care about the missed taskset. Actually, there is a bigger
                # problem:
                self.logger.critical("The Push-Back Queue of tasksets is full. This is a"
                    + "indicator, that the underlying session is buggy"
                    + " and is always canceling currently processed tasksets.")

            

class _WrapperSession(threading.Thread):
    """This class handles every connection to a target plattform asynchronously.

    For each destination, which passes the availablity, a session is created and
    maintained with help of this class. Due to the fact that multiple session
    might exist and the main program should not be blocked, every new session is
    initalized in its own thread.

    To keep all session states independent from each other, a state machine is
    implemented in the `run` method.

    Keep in mind, the usage of this class is not intended outside of this
    module.

    Tasks of thes calls: 
    * Keep each session asyncron 
    * Handle raising errors. The whole processing of variants should not stop
      due to a single error of a session.

    """
    def __init__ (self, host, port, close, session_class, pool, sessions):
        """Initialize the _WrapperSession

        :param host str: ip address of target-plattform

        :param port int: port of target-plattform

        :param close threading.Event: Event object to notify the `_WrapperSession`
        to close. This object is shared between all `_WrapperSession` objects.

        :param session_class AbstractSession: Session class, which should be wrapped.

        :param pool list: list object for all unavailable hosts. If this session
        is terminated, the host string will be pushed to this list.

        :param sessions list:list object for all active sessions. If this
        session is terminated, it will be removed from this list.

        """

        super().__init__()
        self._host = host
        self._port = port
        self._pool = pool
        self._sessions = sessions
        self._tasksets = None
        self.monitor = None
        self._close = close
        self._session_class = session_class
        self._logger = logging.getLogger("Distributor({})".format(host))
        self._session_params = ()
        # current processed task-set
        self._taskset = None
        # current state of processing
        self._running = False
        self._restart_lock = threading.Lock()
        # trigger for starting/stopping 
        self._run = False
        # trigger for restarting
        self._restart = False

    def thread_start(self):
        """due to an otherwise usage of the `start` method, the method of the
        underlying `Thread` class needs to be renamed.
        """
        threading.Thread.start(self)

    def wait_stopped(self):
        """Waits until processing of the current task-set stopped"""
        while self._running and self._run and not self._close.is_set():
            time.sleep(0.5)

    def start(self, tasksets, *session_params):
        """start processing a new list of task-sets
        
        :param tasksets _TaskSetQueue: The TaskSet-Queue which holds the actual
        generator function for task-sets.  

        :param *session_params: Any further parameters are passed to the `start`
        method of the wrapped session.

        """

        # it is important to set all parameter at once, otherwise the session
        # might start sending a new task-set with wrong session_params. Due to
        # that fact, there is a lock for protecting.
        with self._restart_lock:
            self._tasksets = tasksets
            self._session_params = session_params

            # triggering a restart is done by enabling `_restart` and `_run`.
            self._restart = True
            self._run = True

    def stop(self):
        self._run = False

            
    def _internal_start(self, session):
        """Called, whenever a new task-set should be processed.
        
        :param session session.AbstractSession: Wrapped session object
        
        """
        try:
            # lets fetch the task-set queue and optional session parameters
            with self._restart_lock:
                tasksets = self._tasksets
                params = self._session_params

            # try to get a new task-set from queue, other `StopIteration` is raised.
            self._taskset = tasksets.get()

            # handle of task-set to session and start processing
            session.start(self._taskset, *params)

            # inform the monitor about the start.
            if self.monitor is not None:
                self.monitor.__taskset_start__(self._taskset)
                
            self._logger.debug("Taskset variant processing started.")

            # update internal state.
            self._restart = False
            self._running = True
        except StopIteration:
            # the task-set queue is empty.
            self._logger.debug("All taskset variants are processed")

            # update internal state
            self._running = False
            self._restart = False
            self._taskset = None


    def _internal_stop(self, session):
        """Called, whenever the distributor is stopping.
        
        :param session: Wrapped session object 

        """

        # stop session
        session.stop()

        
        if self._taskset is not None :
            # a task-set is in process. So inform the monitor about the stop
            if self.monitor is not None:
                self.monitor.__taskset_stop__(self._taskset)

            # the task-set is pushed back to the task-set queue. So another session
            # can pull it and process it.
            self._tasksets.put(self._taskset)
            self._taskset = None
        # update internal state
        self._running = False

        
    def _internal_update_handling(self, session):
        """Called multiple times during task-set processing
        
        This method handles incoming events, notifies the monitor about the
        progress and finally checks the processing status of the task-set. If
        the task-set is finished (processing is done), `False` will be returned
        and this method will not be called anymore.

        :param session: Wrapped session object 

        :return: `True` if the task-set is not finished and this method should
        be called again, otherwise `False` 

        :rtype: bool

        """

        # Finally incoming events are not directly handled here, but the
        # session.run() takes care it. If the session updated the task-set during
        # calling, the monitor is notified about the change.
        taskset_changed = session.run(self._taskset)
        if taskset_changed:
            if self.monitor is not None:
                self.monitor.__taskset_event__(self._taskset)

        # check if the task-set is finished or is still running
        target_running = session.is_running(self._taskset)
        if not target_running:
            if self.monitor is not None:
                self.monitor.__taskset_finish__(self._taskset)

            # The task-set is finished and the queue (`_tasksets`) is notified
            # about the processed task-set. This is important, because
            # `tasksets` keeps track of currently processed task-sets.
            self._tasksets.done(self._taskset) 
            self._logger.debug("Taskset variant is successfully processed")
        
        return target_running

    
    def run(self):
        """if the thread starts, this method will be called once.

        The main-loop for fetching and distributing task-sets is implemented here.
        

        A simplification of the implementation looks like that:

        while True:
            _internal_start()

            processing=True
            while processing:
                processing = _internal_update_handling()

            _internal_stop()

        """

        # at first, a connection to the target-plattform (_host, _port) is established.
        try:
            session = self._session_class(self._host, self._port)
            self._logger.info("Connection established.")
        except socket.error as e:
            if e.errno == errno.ECONNREFUSED:
                # connection refused. there might be other computers in the
                # network. that's ok and the error is handled silently.
                self._logger.debug(e)
            else:
                # otherwise a bigger problem occured
                self._logger.critical(e)
                self._pool.put(self._host)

            # in any case, the thread will stop and the session is unusable.
            return

        # The connection is established and the loop for fetching and
        # distributing a task-set starts
        try:

            # this will continue until the user or distributor sets the close-flag.
            while not self._close.is_set():

                # if the session is running and should stop
                if not self._run and self._running:
                    # stop it.
                    self._internal_stop(session, taskset)

                # if the session should restart or is still running
                if self._restart or self._running:
                    # try to start
                    self._internal_start(session)

                    # well, the session is running a task-set is delivered and
                    # events are incoming. Let's handle them. Events are handled
                    # as long as there is no closed-flag set and no restart
                    # requested.
                    while (not self._close.is_set() and not self._restart and
                           self._run and self._running):

                        # continue handling events until the session notifies
                        # about a stop.
                        if not self._internal_update_handling(session):
                            break

                elif not self._running:
                    # idle state
                    time.sleep(0.1)
                else:
                    self._logger.critical("Reached some unknown state")
                    time.sleep(0.1)

            # the session is closing and the target-plattform is stopped.
            self._internal_stop(session)
        except socket.error as e:
            # an error occured and is handled now
            self._logger.critical(e)

            if self._taskset is not None:
                # the error occured during the task-set processing. The task-set
                # is pushed back to the task-set queue.
                self._tasksets.put(self._taskset)
                self._logger.debug("Taskset variant is pushed back to queue due to" +
                                   " a critical error")
                # notify monitor about the unprocessed task-set
                if self.monitor is not None:
                    self.monitor.__taskset_stop__(self._taskset)

            # push host back in pool (only, if there was an error). A closing
            # event does not trigger the push back to the host pool.
            self._sessions.remove(self)
            self._pool.put(self._host)

            # if this was the last processing session, you will get notified
            # about missing sessions.
            if not self._tasksets.empty() and len(self._sessions) == 0:
                self._logger.warning("No session is left for processing further" +
                                      " taskset variants. Waiting for new sessions.")
        finally:
            session.close()

