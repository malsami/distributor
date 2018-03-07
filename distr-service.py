from service import Service, find_syslog
import logging
from logging.handlers import SysLogHandler
import time
from distributor import Distributor

class DistributorService(Service):
	def __init__(self, *args, **kwargs):
		super(DistributorService, self).__init__(*args,**kwargs)
		#TODO understand logger and use correct loghandlers
		self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
		self.logger.setLevel(logging.INFO)
		self.distributor = Distributor()


	def run(self):
		n = 0
		while not self.got_sigterm():
			self.logger.info("I'm working...")
			
		self.logger.info("I stopped")

if __name__ == '__main__':
	import sys

	if len(sys.argv) != 2:
		sys.exit('Syntax: %s COMMAND' % sys.argv[0])

	cmd = sys.argv[1].lower()
	#max_val = sys.argv[2] #This may be null
	service = DistributorService('distr_service', pid_dir='/tmp')

	if cmd == 'service_start':
		service.start()
		#with open('/home/hamsch/operating-system/client-tools/service/try1.log', 'w') as f:#only for testing something
		#		f.write("still here {}\n".format(0))
		print("i got told to start")

	elif cmd == 'service_stop':
		#distributor is cleaned up by garbage collector after the service stops
		#but we check if it is running
		if service.distributor.get_distributor_state():
			#if so we stop it
			service.distributor.kill_all()
		service.stop()

	elif cmd == 'service_status':
		if service.is_running():
			print("Service is running.")
		else:
			print("Service is not running.")

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

	elif cmd == 'help':
		#TODO print commands and what they are for
		h = "The distr-service.py is accessible through the following commands:\n"
		h+= "\"distr-service.py service_start\"		is starting the service in the background\n"
		h+= "\"distr-service.py service_stop\"		is stopping the background service\n"
		h+= "\"distr-service.py service_status\"	is outputting whether there is an active background service\n"
		h+= "\"distr-service.py add_job\"			expects a Taskset, as defined in the taskgen Module,"
		#TODO add more
		print(h)
	
	#TODO discard this after debugging
	elif cmd == 'custom':
		
		log = service.logger.handlers
		for h in log:
			print(h.format())

	else:
		sys.exit('Unknown command "%s".\n Try "distr-service.py help" to view available commands.' % cmd)


