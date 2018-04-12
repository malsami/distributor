"""
This module realises a complete system to process tasksets.
It does everything from creating a Qemu instance (connected to a provided bridge) with Genode,
to sending tasksets while listening for events from genode.

"""
import os
import threading
import errno
import time
from subprocess import * 
import subprocess as sb

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
		#self._bridge = bridge
		#self._tap = self._create_tap_device("tap"+str(id))
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

		self.script_dir = os.path.dirname(os.path.realpath(__file__))
		self.logger = logging.getLogger("Machine({})".format(self.id))
		if not len(self.logger.handlers):
			self.hdlr = logging.FileHandler('{}/log/machine.log'.format(self.script_dir))
			self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
			self.hdlr.setFormatter(self.formatter)
			
			self.logger.addHandler(self.hdlr)#TODO check if logger has no other handlers before or check for this specific handler other wise I belive that the logger keeps on living and we add filehandlers to it, so we get every output multiple times after multiple calls to Machine()
			self.logger.setLevel(logging.DEBUG)

		self._taskset_list_lock = lock #threading.Lock()
		self._taskset_list = tasksets
		self._current_set = None
		self._set_running = False
		self._current_generator = None

		self._monitor = None

		self._listening = threading.Event()#initially false
		self._listener_thread = None
		self.started = False
		self.stopped = True
		self._continue = True

		#self._pid_dict = {}
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
						self.logger.debug("id {}: started = {}, stopped = {}, finished() = {}".format(self.id, self.started, self.stopped, self._session.finished()))
						if not self.started:# and not self._session.is_running(self._current_set):
							self.logger.debug("id {}: have a set and about to start".format(self.id))
							# if not started -> session.start()
							try:
								self._session.start(self._current_set)#, *self._session_params)
								self.started = True
								self.stopped = False
								# inform the monitor about the start.
								if self._monitor is not None:
									self._monitor.__taskset_start__(self._current_set)
								self.logger.debug("id {}: Taskset variant processing started.".format(self.id))
							except TypeError as e:
								#meaning session params for a quemu instance are not instance of dict(admctrl) or a taskset not of TaskSet
								self.logger.debug("id {}: {}".format(self.id,e))
								#should not happen because we check the type in distributor.add_job()
						
						elif not self.stopped and self._session.finished():#TODO make running great again otherwise we need a timelimit
							self.logger.debug("id {}: have a finished set and about to stop".format(self.id))
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

						else:#still running check again in one 10th of a second TODO
							self.logger.debug("id {}: have a set and still running, will sleep 5s".format(self.id))
							time.sleep(5)

					else:#_current_set is None
						if self._continue:#check for soft shutdown
							self.logger.debug("id {}: getting a taskset, continue is True".format(self.id))
							try:
								if not self._get_taskset():
									self.logger.debug("id {}: no more tasksets, go kill yourself".format(self.id))
									#no more tasksets, go kill yourself!
									self.inactive.set()
							except StopIteration:
								self.logger.debug("id {}: StopIteration: Last taskset was stolen.".format(self.id))
								if self._current_set is not None:#should never be the case, but better save than sorry
									self.logger.debug("id {}: This is weired, a set was appointed while a StopIteration happened. The Taskset was lost.".format(self.id))
						else:
							self.inactive.set()#initiating shutdown with no _current_set
				except socket.error as e:
					self.logger.debug("id {}: run says: Host at {} died.".format(self.id, self._host))
					
					if self._current_set is not None:
						# the shutdown occured during the task-set processing. The task-set
						# is pushed back to the task-set queue.
						#self._current_generator.put(self._current_set)
						#self.logger.debug("id {}: Taskset variant is pushed back to queue due to an external shutdown".format(self.id))
						# notify monitor about the unprocessed task-set
						if self._monitor is not None:
							self._monitor.__taskset_stop__(self._current_set)
						#self._current_set = None
					self.started = False
					self.stopped = True
					self._session_died = True
					self._session = None
					#besides this we do nothing as the listener will run into the same issue

			else:
				while not self._spawn_host():
					pass
				while not self._revive_session():
					time.sleep(5)

		
		if self._current_set is not None:
			# the shutdown occured during the task-set processing. The task-set
			# is pushed back to the task-set queue.
			self._current_generator.put(self._current_set)
			self.logger.debug("id {}: Taskset variant is pushed back to queue due to an external shutdown".format(self.id))
			# notify monitor about the unprocessed task-set
			if self._monitor is not None:
				self._monitor.__taskset_stop__(self._current_set)

		if not self._session_died:#TO DO: can _session be None here?
			if self._session is not None:
				self._session.close()
				self._session = None
			self._session_died = True
		

		with open(self._kill_log, "a") as log:
			log.write(self._host + "\n")
		self.logger.info("id {}: Qemu instance of {} was killed.".format(self.id, self._host))
		# remove tap device? or is it gone anyway?
		self.logger.info("id {}: Machine with host  {} is closed.".format(self.id, self._host))
		

	def _spawn_host(self):
		#check if macadress currently active(host already/still up? if yes, kill it)

		#Generate random mac address
		#mac = self.randomize_mac()

		#check if host has already spawned a host that is still active. 
		#active_host = Popen(["{}/check_mac.sh".format(self.script_dir),self._qemu_mac], stdout=PIPE, stderr=PIPE).communicate()[0]

		#We may not need this as this machine should be in the kill log already. If we get that active_host is still running, we can kill it
		#if(active_host != ''):
		#	sb.call(["kill", "-9", self._pid]) #Kill if not already in kill log? 

		try:
			while self.id_pid[self.id]:
				pass
		except KeyError as e:
			#Spawn new qemu host and return the pid of the parent process, qemu_ip and mac address
			pid_and_qemuIP_mac = Popen(["{}/qemu.sh".format(self.script_dir), str(self.id)], stdout=PIPE, stderr=PIPE).communicate()[0].split()

			self.logger.debug("id {}: {}".format(self.id, pid_and_qemuIP_mac))
			self.logger.info("id {}: ___________________________________".format(self.id))
			ret_id = int(pid_and_qemuIP_mac[0])
			self.logger.debug("id {}: {}".format(self.id, ret_id))
			if self.id != ret_id:
				self.logger.debug("id {}: something went wrong while spawning a qemu: {}".format(self.id, str(pid_and_qemuIP_mac[0],'utf-8')))
				#so the qemu is killed instantly
				Popen(["{}/clean_id.sh".format(self.script_dir), str(self.id), str(pid_and_qemuIP_mac[1],'utf-8')])
				return False
			else:
				self.id_pid[self.id] = str(pid_and_qemuIP_mac[1],'utf-8')
				self._host = str(pid_and_qemuIP_mac[2],'utf-8')
				self._qemu_mac = str(pid_and_qemuIP_mac[3],'utf-8')
				return True



	def _revive_session(self):#TODO continue here!!!
		###Connect to existing host and starts listener
		try:
			connection = self._session_class(self._host, self._port)
			self.logger.info("id {}: _revive_session: Machine {} connected to {}".format(self.id, self.id, self._host))
			self._session_died = False
			self._session = connection
			self._listening.set()
			self.logger.debug("id {}:_revive_session: starting listener".format(self.id))
			self._listener_thread = threading.Thread(target = Machine._listener, args = (self,))
			self._listener_thread.start()
			return True #successful startup
		except socket.error as e:
			if e.errno == errno.ECONNREFUSED:
				#J connection refused. there might be other computers in the
				#J network. that's ok and the error is handled silently.
				self.logger.debug("id {}: {}".format(self.id,e))
			else:
				#J otherwise a bigger problem occured
				with open(self._kill_log, "a") as log:
					log.write(self._host + "\n")
				self.logger.critical("id {}: _revive_session: {}".format(self.id,e))
			self._session_died = True
			self._session = None
			#self._listening.clear()#can go because session = none clears listening in the listener
			self.logger.debug("id {}:_revive_session: reset stuff and reset session".format(self.id))
			return False#return False so we can retry

	def _listener(self):
		#Listener for the session
		self.logger.debug("id {}: listener: started".format(self.id))
		try:
			while self._listening.is_set():
				self.logger.debug("id {}: listener: is listening".format(self.id))
				time.sleep(5)
				if self._session is not None:
					if self._session.run():
						self.logger.debug("id {}: listener: have session, received a profile".format(self.id))
						if self._monitor is not None and self._current_set is not None:
							self._monitor.__taskset_event__(self._current_set)
				else:
					self._listening.clear()
					self.logger.debug("id {}: listener: no session, so shutting down ".format(self.id))

		except socket.error as e:
			# an error occured and is handled now
			self.logger.critical("id {}:listener: {}".format(self.id,e))

			if self._current_set is not None:
				# the error occured during the task-set processing. The task-set
				# is pushed back to the task-set queue.
				self._current_generator.put(self._current_set)#TODO delete information from this run from set.job?
			self.logger.debug("id {}:listener: Taskset variant is pushed back to queue due to".format(self.id) +
									" a critical error")
			# notify monitor about the unprocessed task-set
			if self._monitor is not None:
				self._monitor.__taskset_stop__(self._current_set)
			self._current_set = None
			
			self._session = None
			self._session_died = True
			self._listening.clear()

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
		self._current_set = self._current_generator.get()#might throw StopIteration is handled upstairs
		self.logger.debug("id {}: get_taskset: got set".format(self.id))
		return True#all fine
