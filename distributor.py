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
from multiprocessing import Queue as queue 
#from queue import Empty, Queue, Full
#from collections.abc import Mapping
from ipaddress import ip_network, ip_address
from itertools import chain
from math import ceil
import errno

from taskgen import * #TaskSet.TaskSet #TODO pfad anpassen
#from taskgen.monitor import AbstractMonitor#TODO pfad anpassen
#from taskgen.session import AbstractSession#TODO pfad anpassen
#from taskgen.sessions.genode import PingSession#TODO pfad anpassen
from machine import Machine
from bridge import *
from subprocess import *

class Distributor():
    """Class for controll over host sessions and asycronous distribution of tasksets"""
    
    def __init__(self, max_machine = 1):
        self._kill_log = '/tmp/taskgen_qemusession_ip_kill.log'
        #self._machine_killer = threading.Thread(target = Distributor._kill_log_killer, args = (self,))
        
        self._machine_killer=threading.Thread(target=Distributor._kill_log_killer, args=(self,))
        
        self._max_machine = max_machine
        self._machines = []


        self._port = 3001
        self._session_class = QemuSession
        self.logger = logging.getLogger('Distributor')


        self._taskset_list_lock = threading.Lock()
        self._tasksets = []
        #self._bridge = _create_bridge()
        #self._bridge = _create_bridge()
        
        self._bridge = _create_bridge()
        self._cleaner = None


    def _create_bridge(self):
        #This bridge is configured in the interfaces 
        br = bridge.Bridge("br0")

    def _kill_log_killer(self):
            #TODO function to target a thread to which will monitor the kill log and kill qemus as soon as ip shows up
        kill_pid = ''
         
        while True: 
            kill_ip = Popen(["./kill_logger.sh", self._kill_log], stdout=PIPE, stderr=PIPE).communicate()[0]

            if(kill_ip != ''):
                kill_pid = self._machines._pid_dict[kill_ip] #Retrieve pid 
                sb.call(["kill", "-9", kill_pid]) #Kill the pid

            #Continue searching



    def get_distributor_state(self):    
        #function to check if the distributor is already working
        #under the assumption that the distributor is working as soon as there are tasksets to work on

        ret = False
        
        with self._taskset_list_lock:
            
            if self._tasksets:
                
                ret = True 
       
        return ret

    def get_max_machine_value(self):
        """Returns the current max_machine value."""
        return self._max_Machine 



    def set_max_machine_value(self, new_value):
        """Changes the _max_machine value. 
        :param new_value int: positive non zero value
        :raises ValueError: new_value is not a natural number
        """
        
        #TODO maybe add upper bound for not crashing the system with large numbers
        if(isinstance(new_value, int) and 0 < new_value):
            self._max_machine = new_value
            self._refresh_machines()
        
        else:
            raise ValueError("The new max_machine value is not an integer greater than zero.")

    def _refresh_machines(self):
        #Adjusts the amount of running starter threads to the current max_machine value.
        #first checking if 
        working = False
        with self._taskset_list_lock:
            if self._tasksets:
                working = True
            
            if working:
                if not self._machines:
                    for c in range(0, self._max_machine):
                        m_running = threading.Event().set() #initially set to True so variable is speaking
                        machine = Machine(self._taskset_list_lock, self._tasksets, self._port, self._session_class, self._bridge, m_running, self._kill_log)
                        machine.start()
                        self._machines.append((machine, m_running))
                self._cleaner = threading.Thread(target = Distributor._clean_machines, args = (self,))#cleans machines from _machines which terminated
                self.logger.debug("started {} machines".format(len(self._machines)))
            
            else:
                l = self._max_machine - len(self._machines)
                if l > 0:
                    for c in range(0,l):
                        m_running = threading.Event().set() #initially set to True
                        machine = Machine(self._taskset_list_lock, self._tasksets, self._port, self._session_class, self._bridge, m_running, self._kill_log)
                        machine.start()
                        self._starter.append((machine,m_running))
                    self.logger.debug("started {} more machines".format(abs(l)))
                elif l < 0:
                    for k in range(0,abs(l)):
                        machine = self._machines.pop()[0]
                        machine.close()
                    self.logger.debug("closed {} machines".format(abs(l)))

    def add_job(self, taskset, monitor = None, *session_params):
        #   Adds a taskset to the queue and calls _refresh_machines()
        #   :param taskset taskgen.taskset.TaskSet: a taskset for the distribution
            #   :param monitor distributor_service.monitor.AbstractMonitor: a monitor to handle the resulting data
        #   :param session_params: optional parameters which are passed to the
        #   `start` method of the actual session. Pay attention: Theses parameters
        #   must be implemented by the session class. A good example is the
        #   `taskgen.sessions.genode.GenodeSession`, which implements a parameter
        #   for optional admission control configuration.  
        
        if taskset is None or not isinstance(taskset, TaskSet):
            raise TypeError("taskset must be TaskSet.")

        if monitor is not None:
            if not isinstance(monitor, AbstractMonitor):
                raise TypeError("monitor must be of type AbstractMonitor")

        # wrap tasksets into an threadsafe iterator
        with self._taskset_list_lock:
            self._tasksets.append(_TaskSetQueue(taskset.variants(), monitor, session_params))#TODO will ich hier immer variants aufrufen?
        self._refresh_machines()

    def kill_all(self):
        #hard kill, callable from outside
        self.logger.info("Killing machines...")
        for m in self._machines:
            m[1].clear()
        self.logger.info("All machines shuting down.")
        self._machines = []

    def _clean_machines(self):
        #cleans up machines which are not running
        dead = []
        while self._machines:
            for m in self._machines:
                if not m[1].is_set():
                    dead.append(m)
            for d in dead:
                self._machines.remove(d)
            dead = []

class _TaskSetQueue():
    """Takes an iterator/generator and makes it thread-safe by
    serializing call to the `next` method of given iterator/generator.
    """
    def __init__(self, iterator, monitor, *session_params):
        self.it = iterator
        self.lock = threading.Lock()
        self.queue = Queue(maxsize=1000)
        self.in_progress = []
        self.processed = 0
        self.logger = logging.getLogger("Distributor")
        self.monitor = monitor
        self.session_params = session_params

        
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