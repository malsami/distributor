"""
This module realises a complete system to process tasksets.
It does everything from creating a Qemu instance (connected to a provided bridge) with Genode,
to sending tasksets while listening for events from genode.

"""
import threading
import errno
import time
#TODO
#import session ?
#import sessions.genode ?
#import monitor ?
#import taskset ?
#import TaskSetQueue ?

class Machine(threading.Thread):
    # Starts up a Qemu instance with Genode.
    # Holds a reference to a TasksetQueue.
    # Holds a reference to a Monitor provided with the Taskset.
    # Creates a session to connect to Genode.
    # Creates a listener_thread for log data from Genode
    
    # This class is only instatiated in `_refresh_starter`.

    def __init__(self, lock, tasksets, port, session_class, bridge, m_running, kill_log):
        self._bridge = bridge
        self._tap = _create_tap_device()#TODO
        self._host = ""
        self._kill_log = kill_log
        self._port = port

		self._running = m_running #threading.Event() |used to shut instance down
        self._session_class = session_class
        self._session_died = True #state of the current session
        self._session = None
        self._session_params = None

        self._logger = logging.getLogger("Distributor({})".format(host))#TODO no host here yet

        self._taskset_list_lock = lock #threading.Lock()
        self._taskset_list = tasksets
        self._current_set = None
        self._set_running = False
        self._current_generator = None
        
        self._monitor = None

        self._listening = threading.Event()#initially false
        self._listener_thread = None
        self._started = False
        self._stopped = True
        self._continue = True

    def run(self):
        while self._running.is_set():#life loop of Machine
            if not self._session_died:
                try:
                    if self._current_set is not None:
                        if not self._started and not self._session.running():
                            # if not started -> session.start()
                            try:
                                self._session.start(self._current_set, *self._session_params)
                                self._started = True
                                self._stopped = False
                                # inform the monitor about the start.
                                if self._monitor is not None:
                                    self._monitor.__taskset_start__(self._current_set)
                                self._logger.debug("Taskset variant processing started.")
                            except TypeError as e:
                                #meaning session params for a quemu instance are not instance of dict(admctrl) or a taskset not of TaskSet
                                self._logger.debug(e)
                                #should not happen because we check the type in distributor.add_job()
                        
                        elif not self._stopped and not self._session.running():#TODO make running great again otherwise we need a timelimit
                            self._session.stop()
                            if self._monitor is not None:
                                self._monitor.__taskset_finish__(self._current_set)
                            # The _current_set is finished and the queue (`current_generator`) is notified
                            # about the processed task-set. This is important, because
                            # TaskSetQueue keeps track of currently processed task-sets.
                            self._current_generator.done(self._current_set)
                            self._logger.debug("Taskset variant is successfully processed.")
                            self._current_set = None

                        else:#still running check again in one 10th of a second TODO
                            time.sleep(0.1)

                    else:#_current_set is None
                        if self._continue:#check for soft shutdown
                            try:
                                if not self._get_taskset():
                                    #no more tasksets, go kill yourself!
                                    self._running.clear()
                            except StopIteration:
                                self._logger.debug("StopIteration: Last taskset was stolen.")
                                if self._current_set is not None:#should never be the case, but better save than sorry
                                    self._logger.debug("This is weired, a set was appointed while a StopIteration happened. The Taskset was lost.")
                        else:
                            self._running.clear()#initiating shutdown with no _current_set
                except socket.error as e:
                    self._logger.debug("run says: Host at {} died.".format(self._host))
                    #besides this we do nothing as the listener will run into the same issue

            else:
                self._host = _spawn_host()#TODO: adapt method call
                while not self._revive_session():
                    time.sleep(5)

        
        """ #   This part is just a comment because what this section does is performed by the _listener thread
            #   upon a socket error, which is triggered by killing the qemu below
        if self._current_set is not None:
                # the shutdown occured during the task-set processing. The task-set
                # is pushed back to the task-set queue.
                self._current_generator.put(self._current_set)
                self._logger.debug("Taskset variant is pushed back to queue due to" +
                                   " an external shutdown")
                # notify monitor about the unprocessed task-set
                if self._monitor is not None:
                    self._monitor.__taskset_stop__(self._current_set)
                self._current_set = None
        
        if not self._session_died:#TO DO: can _session be None here?
            self._session.close()
            self._session_died = True
        """
        
        with open(self._kill_log, "a") as log:
            log.write(self._host + "\n")
        self.logger.info("Qemu instance of {} was killed.".format(self._host))
        # remove tap device? or is it gone anyway?
        self.logger.info("Machine with host  {} is closed.".format(self._host))

    def _create_tap_device(self):
        #TODO
        pass

    def _spawn_host(self):
        #TODO
        #check if macadress currently active(host already/still up? if yes, kill it)
        #spawns a Qemu/Genode host
        #bridge comes from self
        #should return the ip address of the started host

    def _revive_session(self):
    	###Connect to existing host and starts listener
        try:
        	connection = self._session_class(self._host, self._port)
			self._logger.info("Connection to {} established.".format(self._host))
			self._session_died = False
			self._session = connection
            self._listening.set()
            self._listener_thread = threading.Thread(target = Machine._listener, args = (self,))
            return True #successful startup
        except socket.error as e:
			if e.errno == errno.ECONNREFUSED:
				#J connection refused. there might be other computers in the
				#J network. that's ok and the error is handled silently.
				self._logger.debug(e)
			else:
				#J otherwise a bigger problem occured
				self._logger.critical(e)
            self._session_died = True
            self._session = None
            self._listening.clear()
			return False#return False so we can retry

    def _listener(self):
        #Listener for the session
        try:
	        while self._listening.is_set():
	            if self._current_set is not None and self.session.run(self._current_set):#TODO check for none sinnvoll?
	            	if self._monitor is not None:
	            		self._monitor.__taskset_event__(self._current_set)
		
		except socket.error as e:
            # an error occured and is handled now
            self._logger.critical(e)

            if self._current_set is not None:
                # the error occured during the task-set processing. The task-set
                # is pushed back to the task-set queue.
                self._current_generator.put(self._current_set)#TODO delete information from this run from set.job?
                self._logger.debug("Taskset variant is pushed back to queue due to" +
                                   " a critical error")
                # notify monitor about the unprocessed task-set
                if self._monitor is not None:
                    self._monitor.__taskset_stop__(self._current_set)
                self._current_set = None
        finally:
        	self._session_died = True
        	self._listening.clear()

    def close(self):
    	self._continue = False

    def _get_taskset(self):
        if self._current_generator is None
        	with self._taskset_list_lock:
	            if not self._taskset_list:
                    return False#abort thread, nothing to process
            	else:
                    self._current_generator = self._taskset_list[0]
                    self._monitor = self._current_generator.monitor
                    self._session_params = self._current_generator.session_params
        else:
            if self._current_generator.empty():
            	with self._taskset_list_lock:
	            	if self._taskset_list:
                        if self._taskset_list.index(self._current_generator) == 0:
                            self._taskset_list.remove(self._current_generator)
                            if not self._taskset_list:
                                self._current_set = None
                                return False#abort thread, nothing to process
                        
                        self._current_generator = self._taskset_list[0]
                        self._monitor = self._current_generator.monitor
                        self._session_params = self._current_generator.session_params
                    else:
                        self._current_set = None
                        return False#abort thread, nothing to process
            
        self._current_set = self._current_generator.get()#might throw StopIteration is handled upstairs
        return True#all fine

