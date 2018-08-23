"""Module for asyncron distribution of task-sets

This modules provides a class for the distribution of task-sets to one or
multiple target plattforms. The connection to a target plattform is handled by a
session.

"""
import threading
import time
import logging
import errno
import importlib
import copy
from queue import Empty, Queue, Full
from subprocess import Popen, PIPE

import os
import sys
sys.path.append('../')
from distributor_service.monitor import AbstractMonitor
from distributor_service.session import AbstractSession
from distributor_service.machine import Machine
from taskgen.taskset import TaskSet


class Distributor:
    """Class for controll over host sessions and asycronous distribution of tasksets"""

    def __init__(self, max_machine=1, max_allowed=42, session_type="QemuSession", logging_level=logging.DEBUG, bridge='br0', port=3001, startup_delay=20, set_tries=1, timeout=40):
        self.max_allowed_machines = max_allowed #this value is hardcoded and dependant on the amount of defined entrys in the dhcpd.conf it can be lower but not higher
        self.logger = logging.getLogger('Distributor')
        self.logging_level = logging_level
        if not len(self.logger.handlers):
            self.hdlr = logging.FileHandler('../distributor_service/log/distributor.log')
            self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            self.hdlr.setFormatter(self.formatter)
            self.logger.addHandler(self.hdlr)
            self.logger.setLevel(self.logging_level)

        self._max_machine = max_machine
        self._machines = []

        self._bridge = bridge
        self._port = port
        self._set_tries = set_tries
        self.timeout = timeout
        self._session_class = getattr(importlib.import_module("distributor_service.sessions.genode"), session_type)

        self._jobs_list_lock = threading.Lock()
        self._jobs = []
        
        self.id_to_machine={}
        self.machinestate={}
        
        self._cleaner = threading.Thread(target = Distributor._clean_machines, args = (self,),daemon=True)
        self.delay = startup_delay
        self.logger.info('\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n')
        self.logger.info("=====================================================")
        self.logger.info("Distributor started")
        self.logger.info("=====================================================")
        
        self._cleaner.start()
        

    def get_distributor_state(self):    
        #function to check if the distributor is already working
        #under the assumption that the distributor is working as soon as there are tasksets to work on
        ret = False
        with self._jobs_list_lock:
            if self._jobs:
                ret = True 
            elif self.id_to_machine:
                ret = True
        return ret


    def get_max_machine_value(self):
        """Returns the current max_machine value."""
        return self._max_machine 


    def set_max_machine_value(self, new_value):
        """Changes the _max_machine value. 
        :param new_value int: positive non zero value
        :raises ValueError: new_value is not a natural number
        """
        if(isinstance(new_value, int) and 0 < new_value):
            if new_value > self.max_allowed_machines:
                self.logger.debug("the new value in set_max_machine_value was {}, thus bigger than the max_allowed_machines of {} the _max_machine value was set to the max_allowed_machines value".format(new_value,self.max_allowed_machines))
                self._max_machine = self.max_allowed_machines
            else:
                self.logger.info("Adjusted the max_machine value from {} to {}".format(self._max_machine, new_value))
                self._max_machine = new_value
            self._refresh_machines()
        else:
            raise ValueError("The new max_machine value is not an integer greater than zero.")

    def _refresh_machines(self):
        #Adjusts the amount of running starter threads to the current max_machine value.
        #first checking if 
        working = False
        with self._jobs_list_lock:
            if self._jobs:
                working = True
                
            if working:
                if not self._machines:
                    for c in range(self._max_machine):
                        self.spawn_machine()
                    self.logger.info("started {} machines".format(len(self._machines)))
                else:
                    l = self._max_machine - len(self._machines)
                    if l > 0:
                        for c in range(l):
                            self.spawn_machine()
                        self.logger.info("started {} additional machines".format(abs(l)))
                    elif l < 0:
                        for k in range(abs(l)):
                            machine,event,machine_id = self._machines[-(k+1)]#.pop()
                            #machine=triple[0]
                            machine.close()
                            self.machinestate[machine_id] = 0 #triple[2]]=0
                        self.logger.info("closed {} machines".format(abs(l)))
            else:
                self.logger.debug("no machines currently running")

    def spawn_machine(self):
        new_id = self.get_new_id()
        self.logger.debug('new_id: {}'.format(new_id))
        if new_id != -1:
            inactive = threading.Event()
            machine = Machine(new_id, self._jobs_list_lock, self._jobs, self._port, self._session_class, inactive, self.id_to_machine, self.logging_level, self.delay, self._set_tries, self.timeout)
            machine.daemon = True
            machine.start()
            self.machinestate[new_id] = 1
            self.id_to_machine[new_id] = machine
            self._machines.append((machine,inactive, new_id))


    def get_new_id(self):
        for new_id in range(1, self._max_machine+1):
            try:
                self.id_to_machine[new_id]
            except KeyError as ke:
                return new_id
        return -1
        

    def add_job(self, taskset, monitor = None, offset = 0, *session_params):
        #   Adds a taskset to the queue and calls _refresh_machines()
        #   :param taskset taskgen.taskset.TaskSet: a taskset for the distribution
        #   :param monitor distributor_service.monitor.AbstractMonitor: a monitor to handle the resulting data
        #   :param offset  number of tasksets that should be discarded from the head of the generator
        #   :param session_params: optional parameters which are passed to the
        #   `start` method of the actual session. Pay attention: Theses parameters
        #   must be implemented by the session class. A good example is the
        #   `taskgen.sessions.genode.GenodeSession`, which implements a parameter
        #   for optional admission control configuration.  
        
        if taskset is None or not isinstance(taskset, TaskSet):
            raise TypeError("taskset must be of type TaskSet.")

        if monitor is not None:
            if not isinstance(monitor, AbstractMonitor):
                raise TypeError("monitor must be of type AbstractMonitor")

        # wrap tasksets into an threadsafe iterator
        generator = taskset.variants()
        try:
            for i in range(offset):
                discard = generator.__next__()
            with self._jobs_list_lock:
                self._jobs.append(_Job(generator, monitor, offset, len(list(taskset.variants())), session_params))#TODO will ich hier immer variants aufrufen?
            self.logger.info("a new job was added, offset was {}".format(offset))
            self._refresh_machines()
        except StopIteration:
            self.logger.error("offset was bigger than taskset size, no job was added")
            

    def kill_all_machines(self):
        #hard kill, callable from outside
        self.logger.info("\n====############=====\nKilling machines")
        for machine, event, machine_id in self._machines:
            event.set()
        self.logger.info("\nAll machines shuting down.\n====############=====")


    def shut_down_all_machines(self):
        #soft kill, callable from outside
        self.logger.info("\n====############=====\nShutting down machines")
        for machine, event, machine_id in self._machines:
            machine.close()
        self.logger.info("\nAll machines shuting down after processing the current set.\n====############=====")


    def _clean_machines(self):
        # cleans up _machines list and machine states and logs values
        stopping_log_in = 2
        sleeptime = 5 if self.logging_level == logging.DEBUG else 10
        while True:
            if self.id_to_machine or stopping_log_in > 0:
                stopping_log_in = 2 if self.id_to_machine else stopping_log_in - 1
                # self.logger.debug("looking for inactive machines")
                for machine, event, machine_id in self._machines:
                    if event.is_set():
                        try:
                            self.id_to_machine[machine_id]
                        except KeyError as ke:
                            self.logger.debug("cleaner: removing inactive machine with id -{}-".format(machine_id))
                            self._machines.remove((machine,event, machine_id))
                            try:
                                del self.machinestate[machine_id]
                            except:
                                pass
                self.logger.info('#######################################################')
                self.logger.info("machinestates (1:running/0:shutting down): {}".format(self.machinestate))
                self.logger.info("id_to_machine: {}".format([(k,'Machine_UP') for k,v in self.id_to_machine.items()]))
                self.logger.debug("_machines after cleaning: {}".format([machine_id for _,_,machine_id in self._machines]))
                self.logger.info("[(processing/-ed, of total)]: {}".format([(tset.already_used,tset.total_it_length) for tset in self._jobs]))
                self.logger.info('#######################################################')
                time.sleep(sleeptime)
            

class _Job():
    """Takes an iterator/generator and makes it thread-safe by
    serializing call to the `next` method of given iterator/generator.
    """
    def __init__(self, iterator, monitor, start_from, it_length, *session_params):
        self.it = iterator #the tasksets
        self.total_it_length = it_length
        self.already_used = start_from
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
                taskset = self.queue.get_nowait()
                
            # take a new one from the iterator
            if taskset is None:
                taskset = copy.deepcopy(self.it.__next__())

            # keep track of current processed tasksets
            self.in_progress.append(taskset)
            self.already_used +=1
            return taskset
            
    def empty(self):
        with self.lock:
            # in queue?
            if not self.queue.empty():
                return False
            # in iterator?
            try:
                self.queue.put(copy.deepcopy(self.it.__next__()))
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
            self.logger.info("####### {} taskset variant(s) processed #######".format(self.processed))
        
    def put(self, taskset):
        """Call this method, if a task-set processing is canceled.

        This mechanism keeps references of currenctly processed task-sets.

        """
        with self.lock:
            try:
                self.in_progress.remove(taskset)
                for task in taskset:
                    task.jobs = []
                self.queue.put_nowait(taskset)
                self.already_used -= 1
            except Full:
                # We don't care about the missed taskset. Actually, there is a bigger
                # problem:
                self.logger.critical("The Push-Back Queue of tasksets is full. This is a"
                    + "indicator, that the underlying session is buggy"
                    + " and is always canceling currently processed tasksets.")
