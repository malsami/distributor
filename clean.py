from subprocess import Popen, PIPE
import sys

for i in range(1, 1 + int(sys.argv[1])):
	screens = Popen(['./grep_screen.sh', str(i)], stdout=PIPE, stderr=PIPE).communicate()[0].split()
	print(i, screens)
	for screen in screens:
		Popen(['kill', '-9', str(screen, 'utf-8')])
		#Popen(['screen', '-X','-S', str(screen,'utf-8'), 'kill'])
	Popen(['sudo', 'ip', 'link', 'delete', 'tap{}'.format(i)])

