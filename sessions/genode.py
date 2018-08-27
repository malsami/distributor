import socket
import struct
import re
import os
import logging
import xmltodict
import dicttoxml
import time
import xml.dom.minidom # for xml parsing in the logfiles
from subprocess import Popen, PIPE
import sys
sys.path.append('../') # so we can find taskgen
from distributor_service.session import AbstractSession
from taskgen.taskset import TaskSet
from taskgen.task import Job



# capsulation avoids attribute pollution
class MagicNumber:
    # Packet contains task descriptions as XML. uint32_t after tag indicates size in
    # bytes.
    SEND_DESCS = 0xDE5

    # Clear and stop all tasks currently managed on the server.
    CLEAR = 0xDE6

    # Multiple binaries are to be sent. uint32_t after tag indicates number of
    # binaries. Each binary packet contains another leading uint32_t indicating
    # binary size.
    SEND_BINARIES = 0xDE5F11E
    
    # Binary received, send next one.
    GO_SEND = 0x90

    # Start queued tasks.
    START = 0x514DE5

    # Stop all tasks.
    STOP = 0x514DE6

    #Initiate task scheduling optimization.
    OPTIMIZE = 0x6F7074


def kill_qemu(logger, machine_id):
    logger.info("session {}:_kill_qemu(): Try to kill Qemu instance of 10.200.45.{}.".format(machine_id, machine_id))
    #Popen(['screen', '-X', '-S', 'qemu'+str(machine_id), 'kill'], stdout = PIPE, stderr = PIPE)
    #Popen(['sudo', 'ip', 'link', 'delete', 'tap{}'.format(machine_id)], stdout=PIPE, stderr=PIPE)
    pids = Popen(['../distributor_service/grep_screen.sh', str(machine_id)], stdout=PIPE, stderr=PIPE).communicate()[0].split()
    c = 0
    for p in pids:
        pid = str(p,'utf-8')
        Popen(['kill', '-9', pid], stdout=PIPE, stderr=PIPE)
        c+=1
    Popen(['sudo', 'ip', 'link', 'delete', 'tap{}'.format(machine_id)], stdout=PIPE, stderr=PIPE)
    Popen(['screen', '-wipe'], stdout=PIPE, stderr=PIPE)
    logger.debug("id {}: clean_id: removed {} screen(s)".format(machine_id,c))

    
# This class is a pretty simple implementation for the communication with a
# genode::Taskloader instance. There are no error handling mechanism and all
# errors are passed on to the caller. Furthmore, the communication is not
# asyncron, which means that every call is blocking.
class GenodeSession(AbstractSession):

    def __init__(self, session_id, port, logging_level, startup_delay, timeout):
        self.done = [False] # used in finished
        self.startup_delay = startup_delay # used in spawn_host
        self.t = 0 # used in run of inhereting classes
        self.timeout = timeout
        self.session_id = session_id
        self.logger = logging.getLogger("GenodeSession({})".format(self.get_host()))
        if not len(self.logger.handlers):
            self.hdlr = logging.FileHandler('../distributor_service/log/session{}.log'.format(self.session_id))
            self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            self.hdlr.setFormatter(self.formatter)
            self.logger.addHandler(self.hdlr)
            self.logger.setLevel(logging_level)
        self.tset = None
        self.admctrl = None
        self._socket = None
        self.port = port
        self.sent_bin = set()
        self.logger.info('\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n')
        self.logger.info("=====================================================")
        self.logger.info('Created new session')
        self.logger.info("=====================================================")
        

    def start(self, taskset, admctrl=None):
        self.logger.info("=====================================================")
        self.logger.info("session {}: NEW taskset".format(self.session_id))
        self.logger.debug("=====================================================")
        self._clear()
        self.done = [False for task in taskset]
        self.tset = taskset
        self.admctrl = admctrl
        self._optimize()
        self._send_descs()
        self.logger.debug("=====================================================")
        self.logger.debug("session {}: taskset DESCS_SENT".format(self.session_id))
        self.logger.debug("=====================================================")
        self._send_bins()
        self.logger.debug("=====================================================")
        self.logger.debug("session {}: taskset BINS_SENT".format(self.session_id))
        self.logger.debug("=====================================================")
        self._send_start()
        self.logger.debug("=====================================================")
        self.logger.info("session {}: taskset STARTED".format(self.session_id))
        self.logger.info("=====================================================")


    def stop(self):
        self._stop()


    def connect(self):
        self._socket = socket.create_connection((self.get_host(), self.port))
        self.logger.info('session {}: connected to {}'.format(self.session_id, self.get_host()))


    def close(self):
        try:
            self._clear()
        except:
            pass
        self._close()
        self.logger.info('session {}: closed connection to {}'.format(self.session_id, self.get_host()))


    def removeSet(self):
        self.tset = None
        

    def finished(self):
        return all(self.done)
        
    
    def run(self):
        # wait for a new event
        self.logger.debug("session {}:run(): called run".format(self.session_id))
        try:
            timeout = self._socket.gettimeout()
            self._socket.settimeout(0.1) # Non blocking
            data = self._socket.recv(4)
            self.logger.debug("session {}:run(): data_dump from read_size: {}".format(self.session_id, data))
            size = int.from_bytes(data, 'little')
        except socket.error as e:
            self.logger.debug('session {}:run(): error while receiving: {}'.format(self.session_id, e))
            self.logger.debug('session {}:run(): nothing to receive'.format(self.session_id))
            return False
        finally:
            self._socket.settimeout(timeout)

        # receive event
        try:
            self.logger.debug('host {}:run(): Receiveing new event of {} bytes.'.format(self.session_id, size))
            data = b''
            while len(data) < size:
                data += self._socket.recv(size-len(data))
        except:
            return False

        self.logger.debug("session {}:run(): data_dump: {}".format(self.session_id, data))
        # parse xml
        try:
            ascii = data.decode("ascii").replace('\x00', '')
            #ascii should now be just a string
            #to make sure no corrupted xml files still get parsed correctly, we fix it if it is broken
            temp = ascii.split("</profile>")
            ascii = temp[0]+'</profile>'
            #now we can be certain the parser will not have issues
            profile = xmltodict.parse(ascii)
            self.logger.info('session {}:run(): new Profile translates to: \n{}\n'.format(self.session_id, xml.dom.minidom.parseString(ascii).toprettyxml()))
        except:
            self.logger.error('session {}:run(): XML event data not parseable.'.format(self.session_id))
            return False

        # parse profile
        try:
            events = profile['profile']['events']['event']#returns a list of dict with each dict holding the information of an event
            self.logger.debug("session {}:run(): profile_dump: {}".format(self.session_id, profile))
            # it is possible, that only a single event is in events, which is
            # not be formated in a list. But we exspect a list.
            if not isinstance(events, list):
                events = [events]

            # iterate over all events
            for event in events:

                _task_id = int(event['@task-id'])
                _type = event['@type']
                _timestamp = int(event['@time-stamp'])

                # find task
                task = self._get_task_by_id(_task_id)
                
                # update job of task
                self.logger.debug("session {}:run(): task_id: {} |received event of type {} with timestamp {}".format(self.session_id, _task_id, _type, _timestamp))
                if _type == "START":
                    # add a new job and set its start date.
                    if not task.jobs or task.jobs[-1].start_date is not None:
                        task.jobs.append(Job())
                    task.jobs[-1].start_date = _timestamp
                elif _type == "EXIT":
                    # take last job of the list and set its end date.
                    task.jobs[-1].end_date = _timestamp
                    task.jobs[-1].exit_value = _type
                elif _type == "EXIT_CRITICAL":
                    # take last job of the list and set its end date.
                    task.jobs[-1].end_date = _timestamp
                    task.jobs[-1].exit_value = _type
                elif _type == 'EXIT_PERIOD':
                    #it was not possible to 
                    task.jobs[-1].end_date = _timestamp
                    task.jobs[-1].exit_value = _type
                elif _type == "EXIT_EXTERNAL":
                    # take last job of the list and set its end date.
                    task.jobs[-1].end_date = _timestamp
                    task.jobs[-1].exit_value = _type
                elif _type == "EXIT_ERROR":
                    # take last job of the list and set its end date.
                    task.jobs[-1].end_date = _timestamp
                    task.jobs[-1].exit_value = _type
                elif _type == "JOBS_DONE":
                    self.done[_task_id] = True
                    if not task.jobs or not((len(task.jobs)==task["numberofjobs"]) and task.jobs[-1].end_date is not None):
                    	self.logger.critical("session {}:run(): JOBS_DONE from Genode is received but jobs is not number of jobs long yet.".format(self.session_id))
                elif _type == "NOT_SCHEDULED":
                	#kommt wenn die periode kommen würde, aber optimizer oder rta start verhindern
                    # create new job in list and set its end date.
                    if not task.jobs or task.jobs[-1].start_date is not None:
                        task.jobs.append(Job())
                    task.jobs[-1].end_date = _timestamp
                    task.jobs[-1].exit_value = _type
                elif _type == "OUT_OF_QUOTA":
                    # take last job of the list and set its end date.
                    task.jobs[-1].end_date = _timestamp
                    task.jobs[-1].exit_value = _type
                else:
                    self.logger.critical("session {}:run(): Unknown event type {}".format(self.session_id,_type))

        except (ValueError,TypeError) as e:
            self.logger.critical("session {}:run(): 'profile'-node of event has unknown structure"+
                                 " and can not be parsed. TaskSet stopped.\nError: {}".format(self.session_id, e ))
            return False

        return True # task-set got new information
    

    def _get_task_by_id(self, task_id):
        # the taskset is a list, we have to loop over all items...
        for task in self.tset:
            if task.id == task_id:
                return task
        return None


    def _optimize(self):
        if self.admctrl is None:
            self.logger.debug("session {}:_optimize(): admctrl is None".format(self.session_id))
            return

        # convert admctrl dict to xml.
        # genode can't handle `<?xml version="1.0" encoding="utf-8"?>` at
        # the documents beginning. `full_document=False` removes it.
        xml = xmltodict.unparse(self.admctrl, pretty=True, full_document=False).encode('ascii')
        
        self.logger.debug('session {}:_optimize(): Send optimiziaton goal.'.format(self.session_id))
        meta = struct.pack('II', MagicNumber.OPTIMIZE, len(xml))
        self._send(len(meta),meta)
        self._send(len(xml),xml)


    def _send(self,size, data):
        self.logger.debug('session {}:_send():  have {} to send.'.format(self.session_id, size))
        sent = 0
        while sent < size:
            amount = min(size-sent,4096)
            sent += self._socket.send(data[sent:sent+amount])
            #self.logger.debug('host {}:_send(): {}/{}.'.format(self.host,sent,size))
        self.logger.debug('session {}:_send(): {} sent successful.'.format(self.session_id, sent))
        
    
    def _close(self):
        self.done = [False]
        self.tset = None
        self.admctrl=None
        if self._socket is not None:
            self._socket.close()

        
    def _stop(self):
        meta = struct.pack('I', MagicNumber.STOP)
        self.logger.debug('session {}:_stop(): Stop tasks on server.'.format(self.session_id))
        self._send(len(meta),meta)
        

    def _clear(self):
        self.done = [False]
        self.tset = None
        self.admctrl = None
        self.logger.debug('session {}:_clear(): Clear tasks on server.'.format(self.session_id))
        meta = struct.pack('I', MagicNumber.CLEAR)
        self._send(len(meta),meta)
        time.sleep(2)
        
            
    def _send_descs(self):
        list_item_to_name = lambda x : "periodictask"
        description = dicttoxml.dicttoxml(self.tset.description(), attr_type=False, root=False, item_func=list_item_to_name)
        self.logger.info('session {}:_send_descs(): Description about to send: \n{}\n '.format(self.session_id, xml.dom.minidom.parseString(description).toprettyxml()))
        
        
        self.logger.debug("session {}:_send_descs(): Sending taskset description.".format(self.session_id))
        meta = struct.pack('II', MagicNumber.SEND_DESCS, len(description))
        self._send(len(meta),meta)
        self._send(len(description),description)

    
    def _send_bins(self):
        names = self.tset.binaries()
        self.logger.debug('session {}:_send_bins(): sent_bin is \n{}\n and names is\n {}.'.format(self.session_id, self.sent_bin, names))
        binaries = []

        #binaries = names
        for name in names:
            if name not in self.sent_bin:
                binaries.append(name)
                self.sent_bin.add(name)
        
        self.logger.debug('session {}:_send_bins(): Sending {} binary file(s).'.format(self.session_id, len(binaries)))
        self.logger.debug('session {}:_send_bins(): have to send {} of {}.'.format(self.session_id, len(binaries), len(names)))
        
        meta = struct.pack('II', MagicNumber.SEND_BINARIES, len(binaries))
        self._send(len(meta),meta)

        for name in binaries:
            # Wait for 'go' message.
            msg = int.from_bytes(self._socket.recv(4), 'little')
            if msg != MagicNumber.GO_SEND:
                self.logger.critical('session {}:_send_bins(): Invalid answer received, aborting: {}'.format(self.session_id, msg))
                break

            path = "../taskgen/bin/{}".format(name)
            file = open(path, 'rb').read()
            size = os.stat(path).st_size
            self.logger.debug('session {}:_send_bins(): Sending {} of size {}.'.format(self.session_id, name, size))
            meta = struct.pack('15scI', name.encode('ascii'), b'\0', size)
            self._send(len(meta),meta)
            self._send(len(file),file)
            self.logger.debug('session {}: {} sent.'.format(self.session_id, name))
            

    def _send_start(self):
        self.logger.debug('session {}:_start():  Starting tasks on server.'.format(self.session_id))
        meta = struct.pack('I', MagicNumber.START)
        self._send(len(meta),meta)
        


class PingSession(GenodeSession):
    PING_TIMEOUT=4
    def __init__(self, session_id, port, logging_level, startup_delay, timeout):
        GenodeSession.__init__(self, session_id, port, logging_level, startup_delay, timeout)
    # overwrite the availiblity check and replace it with a ping.
    def is_available(host):
        received_packages = re.compile(r"(\d) received")
        ping_out = os.popen("ping -q -W {} -c2 {}".format(PingSession.PING_TIMEOUT, host),"r")
        while True:
            line = ping_out.readline()
            if not line:
                break
            n_received = re.findall(received_packages,line)
            if n_received:
                return int(n_received[0]) > 0

        
class HOST_killed(Exception):
    pass


class QemuSession(PingSession):
    PingSession.PING_TIMEOUT=1 # speed up, localhost is fast

    
    def __init__(self, session_id, port, logging_level, startup_delay, timeout):
        PingSession.__init__(self, session_id, port, logging_level, startup_delay, timeout)
        

    def get_host(self):
        return '10.200.45.{}'.format(self.session_id)

    
    def start(self, taskset, admctrl=None):
        try:
            PingSession.start(self, taskset, admctrl)
            self.t = 0
        except socket.timeout as e:
            self.logger.error("session {}: an error occured during start: {}".format(self.session_id, e))
            kill_qemu(self.logger, self.session_id)
            raise HOST_killed('QEMU_{} was killed'.format(self.session_id))


    def stop(self):
        try:
            PingSession.stop(self)
        except socket.timeout as e:
            self.logger.error("session {}: an error occured during stop: {}".format(self.session_id, e))
            kill_qemu(self.logger, self.session_id)
            raise HOST_killed('QEMU_{} was killed'.format(self.session_id))


    def connect(self):
        try:
            PingSession.connect(self)
        except Exception as e:
            self.logger.error("session {}: an error occured during connect(): {}".format(self.session_id, e))
            kill_qemu(self.logger, self.session_id)
            raise HOST_killed('QEMU_{} was killed'.format(self.session_id))


    def close(self):
        try:
            PingSession.close(self)
        except socket.timeout as e:
            self.logger.error("session {}: an error occured during close: {}".format(self.session_id, e))
            kill_qemu(self.logger, self.session_id)
            raise HOST_killed('QEMU_{} was killed'.format(self.session_id))


    def run(self):
        try:
            if PingSession.run(self):
                self.t = 0
                return True
            elif self.t > self.timeout:
                self.logger.error("session {}: genode is not responding for over {}s, killing it".format(self.session_id, self.timeout))
                raise HOST_killed('QEMU_{} was killed'.format(self.session_id))
            else:
                self.t += 2
                return False
        except:
            self.logger.error("session {}: an error occured during run".format(self.session_id))
            kill_qemu(self.logger, self.session_id)
            raise HOST_killed('QEMU_{} was killed'.format(self.session_id))


    def clear(self):
        try:
            PingSession._clear(self)
        except socket.timeout as e:
            self.logger.error("session {}: an error occured during clear: {}".format(self.session_id, e))
            kill_qemu(self.logger, self.session_id)
            raise HOST_killed('QEMU_{} was killed'.format(self.session_id))


    def start_host(self, inactive, _continue):
        kill_qemu(self.logger, self.session_id)
        self.sent_bin = set()
        time.sleep(2)
        while not inactive.is_set():
            #Spawn new qemu host and return the id if the machine was reachable, otherwise -1
            ret_id = int(Popen(["../distributor_service/qemu.sh", str(self.session_id), str(self.startup_delay)], stdout=PIPE, stderr=PIPE).communicate()[0])
            #logger.debug("id {}:spawn_host(): {}".format(qemu_id, ret_id))
            self.logger.debug("session {}:spawn_host(): ___________________________________".format(self.session_id))
            if self.session_id != ret_id:
                self.logger.info("session {}:spawn_host(): something went wrong while spawning a qemu: {}".format(self.session_id, ret_id))
                #so the qemu is killed instantly
                kill_qemu(self.logger, self.session_id)
                if not _continue:
                    inactive.set()
                    return ''
            else:
                self.logger.info("session {}:spawn_host(): successfully spawned qemu {}".format(self.session_id, ret_id))
                return '10.200.45.{}'.format(self.session_id)


    @staticmethod
    def clean_host(logger, qemu_id):
        logger.info('id {}: cleaning host before shutdown'.format(qemu_id))
        kill_qemu(logger, qemu_id)

