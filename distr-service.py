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
		self.distributor = Distributor()#TODO use this? https://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object


	def run(self):
		n = 0
		while not self.got_sigterm():
			self.logger.info("I'm working...")
			#TODO or should the distributor be created in run()
		self.logger.info("I stopped")

if __name__ == '__main__':
	import sys

	if len(sys.argv) != 2:
		sys.exit('Syntax: %s COMMAND' % sys.argv[0])

	cmd = sys.argv[1].lower()
	service = DistributorService('distr_service', pid_dir='/tmp')

	if cmd == 'service_start':
		service.start()
		with open('/home/hamsch/operating-system/client-tools/service/try1.log', 'w') as f:#only for testing something
				f.write("still here {}\n".format(0))
		print("i got told to start")

	elif cmd == 'service_stop':
		#TODO: close distributor first
		service.stop()

	elif cmd == 'service_status':
		if service.is_running():
			print("Service is running.")
		else:
			print("Service is not running.")

	elif cmd == 'add_job':
		#TODO check for number of arguments ( taskset, monitor, *session_params)
		#TODO call add_job(taskset, monitor, *session_params) on the distributor

	elif cmd == 'check_state':
		#TODO call get_distributor_state() on distributor
		#	print message accordingly

	elif cmd == 'get_max_machine_value':
		#TODO call get_max_machine_value() on distributor

	elif cmd == 'change_max_machine_value':
		#TODO call set_max_machine_value(new_value) on distributor


	elif cmd == 'help':
		#TODO print commands and what they are for

	#TODO discard this after debugging
	elif cmd == 'custom':
		log = service.logger.handlers
		for h in log:
			print(h.format())

	else:
		sys.exit('Unknown command "%s".' % cmd)
