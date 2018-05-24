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

	def __init__(self, id, lock, tasksets, port, session_class, bridge, m_running, kill_log, id_pid):
		super(Machine, self).__init__()
		self.id = id
		self._host = ""
		self._kill_log = kill_log
		self._port = port
		self._qemu_mac = "" #Mac address of qemu instance that it spawns

		self.inactive = m_running #threading.Event() |used to shut instance down
		self._session_class = session_class
		self._session_died = True #state of the current session
		self._session = None
		self._session_params = None
		self._session_lock = threading.Lock()

		self.script_dir = os.path.dirname(os.path.realpath(__file__))
		self.logger = logging.getLogger("Machine({})".format(self.id))
		if not len(self.logger.handlers):
			self.hdlr = logging.FileHandler('{}/log/machine{}.log'.format(self.script_dir, self.id))
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
		self.id_pid=id_pid
		self.logger.info("=====================================================")
		self.logger.info("id {}: NEW MACHINE INIT done".format(self.id))
		self.logger.info("=====================================================")


	def run(self):
		while not self.inactive.is_set():#life loop of Machine
			if not self._session_died:
				try:
					if self._current_set is not None:
						self.finished = self._session.finished()
						self.logger.debug("id {}: started = {}, stopped = {}, finished() = {}".format(self.id, self.started, self.stopped, self.finished))
						if not self.started:# if not started we want to call session.start()
							self.logger.info("id {}: have a set and about to start".format(self.id))
							try:
								self._session.start(self._current_set)#, *self._session_params)#this needs to be added if session_params should be used again
								self.started = True
								self.stopped = False
								# inform the monitor about the start.
								if self._monitor is not None:
									self._monitor.__taskset_start__(self._current_set)
								self.logger.info("id {}: Taskset variant processing started.".format(self.id))
							except TypeError as e:#TODO thought this only catches the type error, but also takes other errors...
								#meaning session params for a quemu instance are not instance of dict(admctrl) or a taskset not of TaskSet
								self.logger.critical("id {}:error while start: {}".format(self.id,e))
								#should not happen because we check the type in distributor.add_job()
						
						elif not self.stopped and self.finished:
							self.logger.info("id {}: have a finished set and about to stop".format(self.id))
							self._session.stop()
							self.started = False
							self.stopped = True
							if self._monitor is not None:
								self._monitor.__taskset_finish__(self._current_set)
							# The _current_set is finished and the queue (`current_generator`) is notified
							# about the processed task-set. This is important, because
							# TaskSetQueue keeps track of currently processed task-sets.
							self._current_generator.done(self._current_set)
							self.logger.debug("id {}: Taskset variant is successfully processed.".format(self.id))
							self._current_set = None
							self._session.removeSet()
							#time.sleep(10)
						else:#the taskset is not finished
							if self.t > 40:
								# self.logger.critical("id {}:run() no communication for 40s, will check with clear.".format(self.id))
								# self._session.clear()
								# self.logger.critical("id {}:run() but clear worked...".format(self.id))
								self.logger.critical("id {}:run() nothing from the qemu for {}s...".format(self.id, self.t))
								self.t = 0
								self._session._kill_qemu()
								self.logger.info("id {}: Qemu instance of {} was killed.".format(self.id, self._host))
								for task in self._current_set:
									task.jobs = []
								self._current_generator.put(self._current_set)
								self._current_set = None
								self.logger.debug("id {}: Taskset variant is reset and put back".format(self.id))
								self._session.close()
								self.started = False
								self.stopped = True
								self._session_died = True
								self._session = None
								
							else:	
								self.logger.debug("id {}:run() have a set and still running, will sleep 2s".format(self.id))
								#self.logger.debug("id {}: listener: is listening".format(self.id))
								if self._session is not None:
									if self._session.run():
										self.t = 0
										self.logger.info("id {}:run() listener: have session, received a profile".format(self.id))
										if self._monitor is not None and self._current_set is not None:
											self._monitor.__taskset_event__(self._current_set)
								time.sleep(2)
								self.t+=2


					else:#_current_set is None
						if self._continue:#check for soft shutdown
							self.logger.info("id {}: getting a taskset, continue is True".format(self.id))
							try:
								if not self._get_taskset():
									self.logger.info("id {}: no more tasksets, go kill yourself".format(self.id))
									#no more tasksets, go kill yourself!
									self.inactive.set()
							except StopIteration:
								self.logger.debug("id {}: StopIteration: Last taskset was stolen.".format(self.id))
								if self._current_set is not None:#should never be the case, but better save than sorry
									self.logger.critical("id {}: This is weired, a set was appointed while a StopIteration happened. The Taskset was lost.".format(self.id))
						else:
							self.logger.info("id {}: shutting down, continue is False".format(self.id))
							self.inactive.set()#initiating shutdown with no _current_set
				except (socket.error,socket.timeout) as e:
					self.logger.debug("id {}: run(): Host at {} died with:".format(self.id, self._host,e))
					if self._current_set is not None:
						# the shutdown occured during the task-set processing. The task-set
						# is reset by clearing the jobs attribute of each task.
						for task in self._current_set:
							task.jobs = []
						self._current_generator.put(self._current_set)
						self._current_set = None
						self.logger.debug("id {}: Taskset variant is reset and dput back".format(self.id))
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
				while not self._revive_session():
					time.sleep(5)

		
		if self._current_set is not None:
			# the shutdown occured during the task-set processing. The task-set
			# is reset and pushed back to the task-set queue.
			for task in self._current_set:
				task.jobs = []
			self._current_generator.put(self._current_set)
			self.logger.debug("id {}: Taskset variant is pushed back to queue due to an external shutdown".format(self.id))
			# notify monitor about the unprocessed task-set
			if self._monitor is not None:
				self._monitor.__taskset_stop__(self._current_set)#TODO same as in line 142

		if not self._session_died:
			if self._session is not None:
				self._session.close()
				self._session = None
			self._session_died = True
		

		with open(self._kill_log, "a") as log:
			log.write(self._host + "\n")
		self.logger.info("id {}: Qemu instance of {} was killed.".format(self.id, self._host))
		self.logger.info("id {}: Machine with host  {} is closed.".format(self.id, self._host))
		

	def _spawn_host(self):
		try:
			while self.id_pid[self.id]:
				pass
		except KeyError as e:
			#Spawn new qemu host and return the id and qemu_ip if the machine was reachable
			id_and_qemuIP = Popen(["{}/qemu.sh".format(self.script_dir), str(self.id)], stdout=PIPE, stderr=PIPE).communicate()[0].split()
			self.logger.debug("id {}:spawn_host(): {}".format(self.id, id_and_qemuIP))
			self.logger.debug("id {}:spawn_host(): ___________________________________".format(self.id))
			ret_id = int(id_and_qemuIP[0])
			self.logger.debug("id {}: {}".format(self.id, ret_id))
			if self.id != ret_id:
				self.logger.info("id {}:spawn_host(): something went wrong while spawning a qemu: {}".format(self.id, str(id_and_qemuIP[0],'utf-8')))
				#so the qemu is killed instantly
				self._clean_id()
				return False
			else:
				self.logger.info("id {}:spawn_host(): successfully spawned qemu {}".format(self.id, self.id))
				self.id_pid[self.id] = str(id_and_qemuIP[0],'utf-8')
				self._host = str(id_and_qemuIP[1],'utf-8')
				return True

	def _clean_id(self):
		pids = Popen(['{}/grep_screen.sh'.format(self.script_dir), str(self.id)], stdout=PIPE, stderr=PIPE).communicate()[0].split()
		c = 0
		for p in pids:
			Popen(['screen', '-X','-S', str(p,'utf-8'), 'kill'])
			Popen(['sudo', 'ip', 'link', 'delete', 'tap{}'.format(self.id)])
			c+=1
		self.logger.debug("id {}: clean_id: removed {} screen(s)".format(self.id,c))

	def _revive_session(self):
		###Connect to existing host
		try:
			connection = self._session_class(self._host, self._port)
			self.logger.info("id {}: _revive_session: Machine {} connected to {}".format(self.id, self.id, self._host))
			self._session_died = False
			self._session = connection
			return True #successful startup
		except socket.error as e:
			if e.errno == errno.ECONNREFUSED:
				#connection refused. there might be other computers in the
				#network. that's ok and the error is handled silently.
				self.logger.debug("id {}: {}".format(self.id,e))
			else:
				#otherwise a bigger problem occured
				with open(self._kill_log, "a") as log:
					log.write(self._host + "\n")
				self.logger.critical("id {}: _revive_session: {}".format(self.id,e))
			self._session_died = True
			self._session = None
			self.logger.debug("id {}:_revive_session: connection was not possible".format(self.id))
			return False#return False so we can retry

	
	def close(self):
		self._continue = False

	def _get_taskset(self):
		if self._current_generator is None:
			self.logger.debug("id {}:get_taskset: I hold no generator, will try to fetch one".format(self.id))
			with self._taskset_list_lock:
				if not self._taskset_list:
					self.logger.debug("id {}:get_taskset: we are out of tasksets".format(self.id))
					return False#abort thread, nothing to process
				else:
					self.logger.debug("id {}:get_taskset: getting new generator and monitor and stuff".format(self.id))
					self._current_generator = self._taskset_list[0]
					self._monitor = self._current_generator.monitor
					self._session_params = self._current_generator.session_params
		else:
			if self._current_generator.empty():
				self.logger.debug("id {}:get_taskset: My generator is empty, trying to get a new one...".format(self.id))
				with self._taskset_list_lock:
					if self._taskset_list:
						try:
							if self._taskset_list.index(self._current_generator) == 0:
								self._taskset_list.remove(self._current_generator)
								self.logger.debug("id {}:get_taskset: empty generator was still in taskset_list, did remove it".format(self.id))
								if not self._taskset_list:
									self.logger.debug("id {}:get_taskset: but now taskset_list is empty so we abort".format(self.id))
									self._current_set = None
									return False#abort thread, nothing to process
							self.logger.debug("id {}:get_taskset: getting new generator...".format(self.id))
							self._current_generator = self._taskset_list[0]
							self._monitor = self._current_generator.monitor
							self._session_params = self._current_generator.session_params
						except ValueError as e:
							self.logger.error("id {}: get_taskset: _current_generator was not in _taskset_list anymore, probably was removed by other machine".format(self.id))
							self._current_generator = self._taskset_list[0]
							self._monitor = self._current_generator.monitor
							self._session_params = self._current_generator.session_params
					else:
						self.logger.debug("id {}:get_taskset: taskset_list is empty, we abort".format(self.id))
						self._current_set = None
						return False#abort thread, nothing to process

		self.logger.debug("id {}: get_taskset: generator is fine, getting new taskset".format(self.id))    
		self._current_set = self._current_generator.get()#might throw StopIteration but is handled upstairs
		self.logger.debug("id {}: get_taskset: got set".format(self.id))
		return True#all fine
