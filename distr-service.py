from service import Service, find_syslog
import logging
from logging.handlers import SysLogHandler
import time
class MyService(Service):
	def __init__(self, *args, **kwargs):
		super(MyService, self).__init__(*args,**kwargs)
		self.logger.addHandler(SysLogHandler(address=find_syslog(), facility=SysLogHandler.LOG_DAEMON))
		self.logger.setLevel(logging.INFO)


	def run(self):
		n = 0
		while not self.got_sigterm():
			self.logger.info("I'm working...")
			n = n +1
			time.sleep(5)
			with open('/home/hamsch/operating-system/client-tools/service/try1.log', 'w') as f:
				f.write("still here {}\n".format(n))

if __name__ == '__main__':
	import sys

	if len(sys.argv) != 2:
		sys.exit('Syntax: %s COMMAND' % sys.argv[0])

	cmd = sys.argv[1].lower()
	service = MyService('my_service', pid_dir='/tmp')

	if cmd == 'start':
		service.start()
		with open('/home/hamsch/operating-system/client-tools/service/try1.log', 'w') as f:
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
