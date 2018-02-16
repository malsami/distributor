from service import Service, find_syslog
import logging
from logging.handlers import SysLogHandler
import time
class DistributorService(Service):
	def __init__(self, *args, **kwargs):
		super(DistributorService, self).__init__(*args,**kwargs)
		#TODO understand logger and use correct loghandlers
		self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
		self.logger.setLevel(logging.INFO)


	def run(self):
		n = 0
		while not self.got_sigterm():
			self.logger.info("I'm working...")
			"""
			TODO
			here we want to create the distributor instance
			"""

if __name__ == '__main__':
	import sys

	if len(sys.argv) != 2:
		sys.exit('Syntax: %s COMMAND' % sys.argv[0])

	cmd = sys.argv[1].lower()
	service = DistributorService('distr_service', pid_dir='/tmp')

	if cmd == 'start':
		service.start()
		with open('/home/hamsch/operating-system/client-tools/service/try1.log', 'w') as f:#only for testing something
				f.write("still here {}\n".format(0))
		print("i got told to start")

	elif cmd == 'stop':
		service.stop()

	elif cmd == 'custom':
		log = service.logger.handlers
		for h in log:
			print(h.format())

	elif cmd == 'status':
		if service.is_running():
			print("Service is running.")
		else:
			print("Service is not running.")
	else:
		sys.exit('Unknown command "%s".' % cmd)
