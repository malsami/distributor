print('this is deprecated...')
'''
#!/usr/bin/env python3.5
from service import Service, find_syslog
import logging
from logging.handlers import SysLogHandler
import time
from distributor import Distributor
import traceback
import os

"""class DistributorService(Service):
	def __init__(self, *args, **kwargs):
		super(DistributorService, self).__init__(*args,**kwargs)
		#TODO understand logger and use correct loghandlers
		self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
		self.logger.setLevel(logging.INFO)
"""		
class MyService(Service):
	def __init__(self, *args, **kwargs):
		super(MyService, self).__init__(*args,**kwargs)
		#TODO understand logger and use correct loghandlers
		self.logger.addHandler(logging.FileHandler("./log/service.log"))
		self.logger.setLevel(logging.INFO)
		self.script_dir = os.path.dirname(os.path.realpath(__file__))
		#self.distributor = None
		try:
			#if self.distributor is None:
			self.distributor = Distributor()
			with open('{}/log/service_run_test_file.log'.format(self.script_dir), 'a') as f:#only for testing something
				f.write("up in init and can run  {} machines\n".format(self.distributor.get_max_machine_value()))
		except Exception as e:
			self.logger.error(traceback.format_exc())
		self.logger.info("finished init at {}".format(self.script_dir))


	def run(self):
		n = 0
		
		while not self.got_sigterm():
			with open('{}/log/service_run_test_file.log'.format(self.script_dir), 'a') as f:#only for testing something
				f.write("up and can run  {} machines\n".format(self.distributor.get_max_machine_value()))
			self.logger.info("I'm working...")
			n+=1
			self.distributor.set_max_machine_value(n)
			time.sleep(1)
			
		self.logger.info("I stopped")

if __name__ == '__main__':
	import sys

	if len(sys.argv) != 2:
		sys.exit('Syntax: %s COMMAND' % sys.argv[0])

	cmd = sys.argv[1].lower()
	#service = DistributorService('distr_service', pid_dir='/tmp')
	service = MyService('distr_service', pid_dir='/tmp')
	

	if cmd == 'service_start':
		service.start()
		
		print("i got told to start")

	elif cmd == 'service_stop':
		#distributor is cleaned up by garbage collector after the service stops
		#but we check if it is running
		#if service.distributor.get_distributor_state():
			#if so we stop it
		#	service.distributor.kill_all()
		service.stop()

	elif cmd == 'service_status':
		if service.is_running():
			print("Service is running.")
		else:
			print("Service is not running.")

	elif cmd == 'help':
		h = 'The distr-service.py is accessible through the following commands:\n'
		h+= '"distr-service.py service_start"		is starting the service in the background\n'
		h+= '"distr-service.py service_stop"		is stopping the background service\n'
		h+= '"distr-service.py service_status"	is outputting whether there is an active background service\n'
		h+= '"distr-service.py add_job"			expects a Taskset, as defined in the taskgen Module,\n 	a monitor, implementing the AbstractMonitor and\n optional session parameters can also be provided.\n'
		h+= '"distr-service.py get_max_machine_value" 	returns the current number of machines the distributor can start up\n'
		h+= '"distr-service.py change_max_machine_value"	expects a positive integer to set the max machine value to\n'
		h+= '"distr-service.py help"				prints this help message.\n'
		
		print(h)
	
	#TODO discard this after debugging
	elif cmd == 'custom':
		
		log = service.logger.handlers
		for h in log:
			print(h.format())

	else:
		sys.exit('Unknown command "%s".\n Try "distr-service.py help" to view available commands.' % cmd)


	"""
	elif cmd == 'add_job':
		#takes an optional session_params argument
		if(len(sys.argv) < 4):
			print("Incorrect number of arguments")
			
		else: 
			taskset = sys.argv[2]
			monitor = sys.argv[3]
			if (len(sys.argv) == 5):
				session_params = sys.argv[4]
				service.distributor.add_job(taskset, monitor, session_params)
			else:
				service.distributor.add_job(taskset, monitor)

	elif cmd == 'check_state':
		if service.distributor.get_distributor_state():
			print("The Distributor is busy")
		else:
			print("The Distributor is idle")

	elif cmd == 'get_max_machine_value':
		print("max machine value: ", service.distributor.get_max_machine_value())

	elif cmd == 'change_max_machine_value':

		max_val = sys.argv[2] #second argument
		service.distributor.set_max_machine_value(max_val)
		print("new max machine value: ", service.distributor.get_max_machine_value())
	"""
'''
