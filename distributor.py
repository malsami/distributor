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
    
    def __init__(self, max_machine=1, max_allowed=42, session_type="QemuSession", logging_level=logging.DEBUG, bridge='br0', port=3001):
        self.max_allowed_machines = max_allowed #this value is hardcoded and dependant on the amount of defined entrys in the dhcpd.conf it can be lower but not higher
        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        
        self.logger = logging.getLogger('Distributor')
        self.logging_level = logging_level
        if not len(self.logger.handlers):
            self.hdlr = logging.FileHandler('{}/log/distributor.log'.format(self.script_dir))
            self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            self.hdlr.setFormatter(self.formatter)
            self.logger.addHandler(self.hdlr)
            self.logger.setLevel(self.logging_level)

        self._max_machine = max_machine
        self._machines = []

        self._bridge = bridge
        self._port = port
        self._session_class = getattr(importlib.import_module("distributor_service.sessions.genode"), session_type)

        self._jobs_list_lock = threading.Lock()
        self._jobs = []
        
        self.id_to_machine={}
        self.machinestate={}
        for i in range(self.max_allowed_machines):
            index=i+1
            self.machinestate[index]=0
        
        self._cleaner = threading.Thread(target = Distributor._clean_machines, args = (self,),daemon=True)
                    
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
                    for c in range(0, self._max_machine):
                        new_id = -1
                        found = False
                        for k, v in self.machinestate.items():
                            if not found:
                                if v == 0:
                                    found = True
                                    new_id = k
                                    self.machinestate[k] = 1
                                    break
                        if new_id != -1:
                            m_running = threading.Event()
                            machine = Machine(new_id, self._jobs_list_lock, self._jobs, self._port, self._session_class, self._bridge, m_running, self.id_to_machine, self.logging_level)
                            machine.daemon = True
                            machine.start()
                            self.id_to_machine[new_id] = machine
                            self._machines.append((machine, m_running, new_id))
                    self.logger.info("started {} machines".format(len(self._machines)))
                
                else:
                    l = self._max_machine - len(self._machines)
                    if l > 0:
                        for c in range(0,l):
                            new_id = -1
                            found = False
                            for k, v in self.machinestate.items():
                                if not found:
                                    if v == 0:
                                        found = True
                                        new_id = k
                                        self.machinestate[k] = 1
                                        break
                            if new_id != -1:
                                m_running = threading.Event()
                                machine = Machine(new_id, self._jobs_list_lock, self._jobs, self._port, self._session_class, self._bridge, m_running, self.id_to_machine, self.logging_level)
                                machine.daemon = True
                                machine.start()
                                self.id_to_machine[new_id] = machine
                                self._machines.append((machine,m_running, new_id))
                        self.logger.info("started {} additional machines".format(abs(l)))
                    elif l < 0:
                        for k in range(0,abs(l)):
                            triple = self._machines.pop()
                            machine=triple[0]
                            machine.close()
                            self.machinestate[triple[2]]=0
                        self.logger.info("closed {} machines".format(abs(l)))
            else:
                self.logger.debug("no machines currently running")


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
        for m in self._machines:
            m[1].set()
        self.logger.info("\nAll machines shuting down.\n====############=====")


    def shut_down_all_machines(self):
        #soft kill, callable from outside
        self.logger.info("\n====############=====\nShutting down machines")
        for m in self._machines:
            m[0].close()
        self.logger.info("\nAll machines shuting down after processing the current set.\n====############=====")


    def _clean_machines(self):
        self.logger.info("cleaner: started, will clean up _machines list and machine states")
        cont = 2
        while True:
            time.sleep(5)
            if self.id_to_machine or cont > 0:
                if not self.id_to_machine:
                    cont -= 1
                else:
                    cont = 2
                self.logger.debug("cleaner: id_to_machine: {}".format(self.id_to_machine))
                self.logger.info("cleaner: looking for inactive machines")
                for m in self._machines:
                    if m[1].is_set():
                        self.logger.debug("cleaner: removing inactive machine with id -{}-".format(m[2]))
                        self.machinestate[m[2]]=0
                        self._machines.remove(m)
                self.logger.debug("cleaner: machinestates after cleaning: {}".format(self.machinestate))
                self.logger.debug("cleaner: _machines after cleaning: {}".format(self._machines))
                self.logger.info("cleaner: [(processing/-ed, of total)]: {}".format([(tset.already_used,tset.total_it_length) for tset in self._jobs]))



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
            # in progress?
            #if len(self.in_progress) > 0:
            #    return False
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
