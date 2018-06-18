"""
This module realises a complete system to process tasksets.
It does everything from creating a Qemu instance (connected to a provided bridge) with Genode,
to sending tasksets while listening for events from genode.

"""
import os
import threading
import errno
import time
from subprocess import Popen, PIPE

from sessions.genode import * 

class Machine(threading.Thread):
	# Starts up a Qemu instance with Genode.
	# Holds a reference to a TasksetQueue.
	# Holds a reference to a Monitor provided with the Taskset.
	# Creates a session to connect to Genode.
	# Creates a listener_thread for log data from Genode

	# This class is only instatiated in `_refresh_starter`.

	def __init__(self, machine_id, lock, tasksets, port, session_class, bridge, m_running, id_to_machine):
		super(Machine, self).__init__()
		self.machine_id = machine_id
		self._host = ""
		#self._kill_log = kill_log
		self._port = port
		#self._qemu_mac = "" #Mac address of qemu instance that it spawns
		self.start_up_delay = 30

		self.inactive = m_running #threading.Event() |used to shut instance down
		self._session_class = session_class
		self._session_died = True #state of the current session
		self._session = None
		self._session_params = None
		#self._session_lock = threading.Lock()

		self.script_dir = os.path.dirname(os.path.realpath(__file__))
		self.logger = logging.getLogger("Machine({})".format(self.machine_id))
		if not len(self.logger.handlers):
			self.hdlr = logging.FileHandler('{}/log/machine{}.log'.format(self.script_dir, self.machine_id))
			self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
			self.hdlr.setFormatter(self.formatter)
			
			self.logger.addHandler(self.hdlr)
			self.logger.setLevel(logging.DEBUG)

		self._taskset_list_lock = lock #threading.Lock()
		self._taskset_list = tasksets
		self._current_set = None
		self._set_running = False
		self._current_generator = None

		self._monitor = None

		self.started = False
		self.stopped = True
		self.finished = False
		self._continue = True
		self.t = 0

		self._pid = "" 
		self.id_to_machine=id_to_machine
		self.logger.info("=====================================================")
		self.logger.info("id {}: NEW MACHINE INIT done".format(self.machine_id))
		self.logger.info("=====================================================")


	def run(self):
		while not self.inactive.is_set():#life loop of Machine
			if not self._session_died:
				try:
					if self._current_set is not None:
						self.finished = self._session.finished()
						self.logger.debug("id {}: started = {}, stopped = {}, finished() = {}".format(self.machine_id, self.started, self.stopped, self.finished))
						if not self.started:# if not started we want to call session.start()
							self.logger.info("id {}: have a set and about to start".format(self.machine_id))
							try:
								self._session.start(self._current_set)#, *self._session_params)#this needs to be added if session_params should be used again
								self.started = True
								self.stopped = False
								# inform the monitor about the start.
								if self._monitor is not None:
									self._monitor.__taskset_start__(self._current_set)
								self.logger.info("id {}: Taskset variant processing started.".format(self.machine_id))
							except TypeError as e:#TODO thought this only catches the type error, but also takes other errors...
								#meaning session params for a quemu instance are not instance of dict(admctrl) or a taskset not of TaskSet
								self.logger.critical("id {}:error while start: {}".format(self.machine_id, e))
								#should not happen because we check the type in distributor.add_job()
						
						elif not self.stopped and self.finished:
							self.logger.info("id {}: have a finished set and about to stop".format(self.machine_id))
							self._session.stop()
							self.started = False
							self.stopped = True
							if self._monitor is not None:
								self._monitor.__taskset_finish__(self._current_set)
							# The _current_set is finished and the queue (`current_generator`) is notified
							# about the processed task-set. This is important, because
							# TaskSetQueue keeps track of currently processed task-sets.
							self._current_generator.done(self._current_set)
							self.logger.debug("id {}: Taskset variant is successfully processed.".format(self.machine_id))
							self._current_set = None
							self._session.removeSet()
							#time.sleep(10)
						else:#the taskset is not finished
							if self.t > 40:
								# self.logger.critical("id {}:run() no communication for 40s, will check with clear.".format(self.machine_id))
								# self._session.clear()
								# self.logger.critical("id {}:run() but clear worked...".format(self.machine_id))
								self.logger.critical("id {}:run() nothing from the qemu for {}s...".format(self.machine_id, self.t))
								self.t = 0
								kill_qemu(self.logger, self.machine_id)
								self.logger.info("id {}: Qemu instance of {} was killed.".format(self.machine_id, self._host))
								for task in self._current_set:
									task.jobs = []
								self._current_generator.put(self._current_set)
								self._current_set = None
								self.logger.debug("id {}: Taskset variant is reset and put back".format(self.machine_id))
								self._session.close()
								self.started = False
								self.stopped = True
								self._session_died = True
								self._session = None
								
							else:	
								self.logger.debug("id {}:run() have a set, running {}s, will sleep 2s".format(self.machine_id, self.t))
								if self._session is not None:
									if self._session.run():
										self.t = 0
										self.logger.info("id {}:run() have session, received a profile".format(self.machine_id))
										if self._monitor is not None and self._current_set is not None:
											self._monitor.__taskset_event__(self._current_set)
								time.sleep(2)
								self.t+=2


					else:#_current_set is None
						if self._continue:#check for soft shutdown
							self.logger.info("id {}: getting a taskset, continue is True".format(self.machine_id))
							try:
								if not self._get_taskset():
									self.logger.info("id {}: no more tasksets, go kill yourself".format(self.machine_id))
									#no more tasksets, go kill yourself!
									self.inactive.set()
							except StopIteration:
								self.logger.debug("id {}: StopIteration: Last taskset was stolen.".format(self.machine_id))
								if self._current_set is not None:#should never be the case, but better save than sorry
									self.logger.critical("id {}: This is weired, a set was appointed while a StopIteration happened. The Taskset was lost.".format(self.machine_id))
						else:
							self.logger.info("id {}: shutting down, continue is False".format(self.machine_id))
							self.inactive.set()#initiating shutdown with no _current_set
				except (socket.error,socket.timeout) as e:
					self.logger.debug("id {}: run(): Host at {} died with:".format(self.machine_id, self._host,e))
					if self._current_set is not None:
						# the shutdown occured during the task-set processing. The task-set
						# is reset by clearing the jobs attribute of each task.
						for task in self._current_set:
							task.jobs = []
						self._current_generator.put(self._current_set)
						self._current_set = None
						self.logger.debug("id {}: Taskset variant is reset and dput back".format(self.machine_id))
						# notify monitor about the unprocessed task-set
						# if self._monitor is not None:
						# 	self._monitor.__taskset_stop__(self._current_set)#TODO monitor should maybe also provide a method for an abort due to an error
					self.started = False
					self.stopped = True
					self._session_died = True
					self._session = None
					
			else:
				while not self._spawn_host():
					time.sleep(2)
					if self.inactive.is_set():
						break
					if not self._continue:
						self.inactive.set()
						break
				while not self.inactive.is_set() and self._host and not self._revive_session():
					time.sleep(5)
					if self.inactive.is_set():
						break
					if not self._continue:
						self.inactive.set()
						break

		#Now outside of while loop; happens if self.inactive.is_set()
		if self._current_set is not None:
			# the shutdown occured during the task-set processing. The task-set
			# is reset and pushed back to the task-set queue.
			for task in self._current_set:
				task.jobs = []
			self._current_generator.put(self._current_set)
			self.logger.debug("id {}: Taskset variant is pushed back to queue due to an external shutdown".format(self.machine_id))
			# notify monitor about the unprocessed task-set
			if self._monitor is not None:
				self._monitor.__taskset_stop__(self._current_set)#TODO same as in line 142

		if not self._session_died:
			if self._session is not None:
				self._session.close()
				self._session = None
			self._session_died = True
		
		self._clean_id()
		# with open(self._kill_log, "a") as log:
		# 	log.write(self._host + "\n")
		self.logger.info("id {}: Qemu instance of {} was killed.".format(self.machine_id, self._host))
		del self.id_to_machine[self.machine_id]
		self.logger.info("id {}: Machine with host  {} is closed.".format(self.machine_id, self._host))
		

	def _spawn_host(self):
		#grep_result = ["init"]
		#while grep_result:
		#	Popen(['screen', '-wipe'], stdout=PIPE, stderr=PIPE)
		#	grep_result = Popen(['{}/grep_screen.sh'.format(self.script_dir), str(self.machine_id)], stdout=PIPE, stderr=PIPE).communicate()[0].split()
		#	self.logger.debug("id {}: spawn_host(): grep_result is {}".format(self.machine_id, grep_result))
		self._clean_id()
		time.sleep(2)
		#Spawn new qemu host and return the id if the machine was reachable, otherwise -1
		ret_id = int(Popen(["{}/qemu.sh".format(self.script_dir), str(self.machine_id), str(self.start_up_delay)], stdout=PIPE, stderr=PIPE).communicate()[0])
		self.logger.debug("id {}:spawn_host(): {}".format(self.machine_id, ret_id))
		self.logger.debug("id {}:spawn_host(): ___________________________________".format(self.machine_id))
		#self.logger.debug("id {}: {}".format(self.machine_id, ret_id))
		if self.machine_id != ret_id:
			self.logger.info("id {}:spawn_host(): something went wrong while spawning a qemu: {}".format(self.machine_id, ret_id))
			#so the qemu is killed instantly
			kill_qemu(self.logger, self.machine_id)
			# self._clean_id()
			return False
		else:
			self.logger.info("id {}:spawn_host(): successfully spawned qemu {}".format(self.machine_id, ret_id))
			self._host = '10.200.45.{}'.format(self.machine_id)
			return True

	
	def _clean_id(self):
		pids = Popen(['{}/grep_screen.sh'.format(self.script_dir), str(self.machine_id)], stdout=PIPE, stderr=PIPE).communicate()[0].split()
		c = 0
		for p in pids:
			Popen(['screen', '-X','-S', str(p,'utf-8'), 'kill'])
			c+=1
		Popen(['sudo', 'ip', 'link', 'delete', 'tap{}'.format(self.machine_id)], stdout=PIPE, stderr=PIPE)
		Popen(['screen', '-wipe'], stdout=PIPE, stderr=PIPE)
		self.logger.debug("id {}: clean_id: removed {} screen(s)".format(self.machine_id,c))
	

	def _revive_session(self):
		###Connect to existing host
		try:
			connection = self._session_class(self._host, self._port)
			self.logger.info("id {}: _revive_session: Machine {} connected to {}".format(self.machine_id, self.machine_id, self._host))
			self._session_died = False
			self._session = connection
			return True #successful startup
		except socket.error as e:
			if e.errno == errno.ECONNREFUSED:
				#connection refused. there might be other computers in the
				#network. that's ok and the error is handled silently.
				self.logger.debug("id {}: {}".format(self.machine_id,e))
			else:
				#otherwise a bigger problem occured
				kill_qemu(self.logger, self.machine_id)
				self._host = ''
				self.logger.critical("id {}: qemu was killed in _revive_session, error: {}".format(self.machine_id,e))
			self._session_died = True
			self._session = None
			self.logger.debug("id {}:_revive_session: connection was not possible".format(self.machine_id))
			return False#return False so we can retry

	
	def close(self):
		self._continue = False

	def _get_taskset(self):
		if self._current_generator is None:
			self.logger.debug("id {}:get_taskset: I hold no generator, will try to fetch one".format(self.machine_id))
			with self._taskset_list_lock:
				if not self._taskset_list:
					self.logger.debug("id {}:get_taskset: we are out of tasksets".format(self.machine_id))
					return False#abort thread, nothing to process
				else:
					self.logger.debug("id {}:get_taskset: getting new generator and monitor and stuff".format(self.machine_id))
					self._current_generator = self._taskset_list[0]
					self._monitor = self._current_generator.monitor
					self._session_params = self._current_generator.session_params
		else:
			if self._current_generator.empty():
				self.logger.debug("id {}:get_taskset: My generator is empty, trying to get a new one...".format(self.machine_id))
				with self._taskset_list_lock:
					if self._taskset_list:
						try:
							if self._taskset_list.index(self._current_generator) == 0:
								self._taskset_list.remove(self._current_generator)
								self.logger.debug("id {}:get_taskset: empty generator was still in taskset_list, did remove it".format(self.machine_id))
								if not self._taskset_list:
									self.logger.debug("id {}:get_taskset: but now taskset_list is empty so we abort".format(self.machine_id))
									self._current_set = None
									return False#abort thread, nothing to process
							self.logger.debug("id {}:get_taskset: getting new generator...".format(self.machine_id))
							self._current_generator = self._taskset_list[0]
							self._monitor = self._current_generator.monitor
							self._session_params = self._current_generator.session_params
						except ValueError as e:
							self.logger.error("id {}: get_taskset: _current_generator was not in _taskset_list anymore, probably was removed by other machine".format(self.machine_id))
							self._current_generator = self._taskset_list[0]
							self._monitor = self._current_generator.monitor
							self._session_params = self._current_generator.session_params
					else:
						self.logger.debug("id {}:get_taskset: taskset_list is empty, we abort".format(self.machine_id))
						self._current_set = None
						return False#abort thread, nothing to process

		self.logger.debug("id {}: get_taskset: generator is fine, getting new taskset".format(self.machine_id))    
		self._current_set = self._current_generator.get()#might throw StopIteration but is handled upstairs
		self.logger.debug("id {}: get_taskset: got set".format(self.machine_id))
		return True#all fine
