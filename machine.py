"""
TODO
Put module description

"""
import os
import sys
sys.path.append('../')
import threading
import errno
import time
from subprocess import Popen, PIPE

from distributor_service.sessions.genode import * 

class Machine(threading.Thread):
	# Starts up a Qemu instance with Genode.
	# Holds a reference to a TasksetQueue.
	# Holds a reference to a Monitor provided with the Taskset.
	# Creates a session to connect to Genode.
	# Creates a listener_thread for log data from Genode

	# This class is only instatiated in `_refresh_starter`.

	def __init__(self, machine_id, lock, tasksets, port, session_class, inactive, id_to_machine, logging_level, delay, set_tries, timeout):
		super(Machine, self).__init__()
		# setting up logger
		self.logging_level = logging_level
		self.logger = logging.getLogger("Machine({})".format(machine_id))
		if not len(self.logger.handlers):
			self.hdlr = logging.FileHandler('../distributor_service/log/machine{}.log'.format(machine_id))
			self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
			self.hdlr.setFormatter(self.formatter)
			
			self.logger.addHandler(self.hdlr)
			self.logger.setLevel(self.logging_level)
		# setting up variables
		self.machine_id = machine_id
		self.host = ""
		self._port = port
		self.startup_delay = delay
		
		self.inactive = inactive #threading.Event() |used to shut instance down
		self._continue = True

		self._session_class = session_class
		self._session = self._session_class(self.machine_id, self._port, self.logging_level, self.startup_delay, timeout)
		self._session_params = None
		
		self._job_list_lock = lock #threading.Lock()
		self._job_list = tasksets
		self._current_set = None
		self._current_set_tries = 1
		self._max_set_tries = set_tries
		self._current_generator = None

		self._monitor = None

		self.started = False
		self.finished = False
		
		self.id_to_machine=id_to_machine
		self.logger.info('\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n')
		self.logger.info("=====================================================")
		self.logger.info("id {}: NEW MACHINE INIT done".format(self.machine_id))
		self.logger.info("=====================================================")


	def _taskset_start(self):
		self.logger.debug("id {}: have a set and about to start".format(self.machine_id))
		self._session.connect()
		self._session.start(self._current_set)#, *self._session_params)#this needs to be added if session_params should be used again
		self.started = True
		# inform the monitor about the start.
		if self._monitor is not None:
			self._monitor.__taskset_start__(self._current_set)
		self.logger.info("id {}: Taskset variant processing started.".format(self.machine_id))
	

	def _taskset_stop(self):
		self.logger.debug("id {}: have a finished set and about to stop".format(self.machine_id))
		self._session.stop()
		self.started = False
		if self._monitor is not None:
			self._monitor.__taskset_finish__(self._current_set)
		# The _current_set is finished and the queue (`current_generator`) is notified
		# about the processed task-set. This is important, because
		# TaskSetQueue keeps track of currently processed task-sets.
		self._current_generator.done(self._current_set)
		self.logger.info("id {}: Taskset variant was successfully processed.".format(self.machine_id))
		self._current_set = None
		self._session.close()
		self._session.removeSet()


	def _check_tries(self):
		if self._current_set_tries >= self._max_set_tries:
			if self._monitor is not None:
				self._monitor.__taskset_bad__(self._current_set, self._current_set_tries)
			self.logger.debug("id {}: Taskset variant is logged as BAD after {} tries".format(self.machine_id, self._current_set_tries))
			self._current_set_tries = 1
			self._current_set = None
		else:
			self._current_set_tries += 1
			for task in self._current_set:
				task.jobs = []
			self.logger.info("id {}: Taskset variant is tried for {}. time".format(self.machine_id, self._current_set_tries))


	def _active(self):
		if self._session.run():
			self.logger.debug("id {}: received a profile".format(self.machine_id))
			if self._monitor is not None and self._current_set is not None:
				self._monitor.__taskset_event__(self._current_set)
		else:
			self.logger.debug("id {}:run() have a set, {}s since last profile, will sleep 2s".format(self.machine_id, self._session.t))
			time.sleep(2)
		

	def _work(self):
		self.finished = self._session.finished()
		self.logger.debug("id {}: started = {}, finished() = {}".format(self.machine_id, self.started, self.finished))
		if not self.started:# if not started we want to call session.start()
			self._taskset_start()
		elif self.finished:
			self._taskset_stop()
		else:#the taskset is not finished
			self._active()
			

	def _get_set(self):
		if self._continue:#check for soft shutdown
			self.logger.debug("id {}: _get_set: continue is True".format(self.machine_id))
			self.logger.info("id {}: getting a taskset...".format(self.machine_id))
			try:
				if not self._get_taskset():
					self.logger.info("id {}: no more tasksets, shutting down".format(self.machine_id))
					self.inactive.set()
			except StopIteration:
				self.logger.debug("id {}: StopIteration: Last taskset was stolen.".format(self.machine_id))
		else:
			self.logger.debug("id {}:_get_set: continue is False".format(self.machine_id))
			self.logger.info("id {}: shutting down".format(self.machine_id))
			self.inactive.set()#initiating shutdown with no _current_set


	def run(self):
		while not self.inactive.is_set():#life loop of Machine
			if self.host:
				try:
					if self._current_set is None:
						self._get_set()
					else:
						self._work()
				except HOST_killed as hk:
					self.logger.info("id {}: Host instance of {} was killed.\n{}".format(self.machine_id, self.host, hk))
					self.host = ''
					self._check_tries()
					self._session.close()
					self.started = False

			else:
				if self._current_set is None:
					self._get_set()
				if not self.inactive.is_set() and self._current_set is not None:
					self.host = self._session.start_host(self.inactive, self._continue)

		# end of while ###### machine is shutting down, some cleanup takes place #######
		if self._current_set is not None:
			# the shutdown occured during the task-set processing. The task-set
			# pushed back to the task-set queue.
			for task in self._current_set:
				task.jobs = []
			self._current_generator.put(self._current_set)
			with self._job_list_lock:
				if self._current_generator not in self._job_list:
					self._job_list.insert(0, self._current_generator)
			self.logger.debug("id {}: Taskset variant is pushed back to queue due to an external shutdown".format(self.machine_id))
			
		# self._session.close()
		self._session_class.clean_host(self.logger, self.machine_id)
		del self.id_to_machine[self.machine_id]
		self.logger.info("id {}: Machine with host  {} is closed.".format(self.machine_id, self.host))
	
  
	def close(self):
		self._continue = False

	def _get_taskset(self):
		if self._current_generator is not None and  self._current_generator.empty():
			self.logger.debug("id {}:get_taskset: My generator is empty, will remove from list".format(self.machine_id))
			with self._job_list_lock:	
				try:
					self._job_list.remove(self._current_generator)
					self.logger.debug("id {}:get_taskset: empty generator was still in taskset_list, removed it".format(self.machine_id))
				except ValueError as e:
					self.logger.debug("id {}: get_taskset: empty generator was not in _job_list anymore, probably was removed by other machine".format(self.machine_id))	
				finally:
					self._current_generator  = None

		if self._current_generator is None:
			self.logger.debug("id {}:get_taskset: I hold no generator, will try to fetch one".format(self.machine_id))
			with self._job_list_lock:
				if not self._job_list:
					self.logger.debug("id {}:get_taskset: we are out of jobs".format(self.machine_id))
					return False#abort thread, nothing to process
				else:
					self.logger.debug("id {}:get_taskset: getting new generator and monitor and stuff".format(self.machine_id))
					self._current_generator = self._job_list[0]
					self._monitor = self._current_generator.monitor
					self._session_params = self._current_generator.session_params

		self.logger.debug("id {}: get_taskset: generator is fine, getting new taskset".format(self.machine_id))    
		self._current_set = self._current_generator.get()#might throw StopIteration but is handled upstairs
		self.logger.debug("id {}: get_taskset: got set".format(self.machine_id))
		return True#all fine
