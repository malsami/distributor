from subprocess import Popen, PIPE
import sys

def clean_function(upToID):
	for i in range(1, 1 + upToID):
		screens = Popen(['../distributor/grep_screen.sh', str(i)], stdout=PIPE, stderr=PIPE).communicate()[0].split()
		#print(i, screens)
		for screen in screens:
			Popen(['kill', '-9', str(screen, 'utf-8')])
			#Popen(['screen', '-X','-S', str(screen,'utf-8'), 'kill'])
		Popen(['sudo', 'ip', 'link', 'delete', 'tap{}'.format(i)], stdout=PIPE, stderr=PIPE)


def clean_panda(upToID):
    for i in range(1, upToID+1):
        panda = 'panda' + str(i)
        Popen(['../distributor/poe_off.sh', panda])

if __name__ == '__main__':
	clean_function(int(sys.argv[1]))
