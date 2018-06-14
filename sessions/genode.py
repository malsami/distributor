import socket
import struct
import re
import os
import logging
import xmltodict
import dicttoxml
import time
import xml.dom.minidom # for xml parsing in the logfiles
from session import AbstractSession
import sys
sys.path.append('../') # so we can find taskgen
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


    
# This class is a pretty simple implementation for the communication with a
# genode::Taskloader instance. There are no error handling mechanism and all
# errors are passed on to the caller. Furthmore, the communication is not
# asyncron, which means that every call is blocking.
class GenodeSession(AbstractSession):

    def __init__(self, host, port):
        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self._socket = socket.create_connection((host, port))
        self.host = host
        self.logger = logging.getLogger("GenodeSession({})".format(host))
        if not len(self.logger.handlers):
            self.hdlr = logging.FileHandler('{}/../log/session{}.log'.format(self.script_dir, self.host.split('.')[-1]))
            self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            self.hdlr.setFormatter(self.formatter)
            self.logger.addHandler(self.hdlr)
            self.logger.setLevel(logging.DEBUG)
        self.logger.info("=====================================================")
        self.logger.info("host {}: Connection established".format(self.host))
        self.logger.info("=====================================================")
        self._socket.settimeout(10.0) # wait 10 seconds for responses...
        self.tset = None
        self.admctrl = None
        self.sent_bin = set()

    def start(self, taskset, admctrl=None):
        self.logger.info("=====================================================")
        self.logger.info("host {}: NEW taskset".format(self.host))
        self.logger.info("=====================================================")
        for st in taskset:
            self.logger.debug("host {}: taskid: {} has object_id: {}".format(self.host,st["id"],id(st)))
        self.logger.debug("host {}: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX".format(self.host))
        self._clear()
        self.tset = taskset
        self.admctrl = admctrl
        self._optimize()
        self._send_descs()
        self.logger.debug("=====================================================")
        self.logger.info("host {}: taskset DESCS_SENT".format(self.host))
        self.logger.debug("=====================================================")
        self._send_bins()
        self.logger.debug("=====================================================")
        self.logger.info("host {}: taskset BINS_SENT".format(self.host))
        self.logger.debug("=====================================================")
        self._start()
        self.logger.info("=====================================================")
        self.logger.info("host {}: taskset STARTED".format(self.host))
        self.logger.info("=====================================================")

    def stop(self):
        self._stop()

    def close(self):
        try:
            self._clear()
        except socket.error:
            pass
        self._close()    

    def removeSet(self):
        self.tset = None
        
    def finished(self):
        if self.tset is None:
            self.logger.info("host {}:finished(): there is no tset yet".format(self.host))
            return False
        done = True
        self.logger.info("host {}:finished(): check for finished".format(self.host))
        for task in self.tset:
            self.logger.debug("host {}:finished(): task_id: {} | len(task.jobs): {} | task numberofjobs: {}".format(self.host, task["id"], len(task.jobs), task["numberofjobs"]))
            for j in task.jobs:
                self.logger.debug("host {}:finished(): object_id: {} | task_id: {} | job start: {} | job end: {}".format(self.host, id(task), task["id"], j.start_date, j.end_date))
            done = done and ((len(task.jobs)==task["numberofjobs"]) and task.jobs[-1].end_date is not None)
        
        # if all jobs are done, we are not running anymore
        self.logger.info("host {}:finished(): done is {}".format(self.host, done))
        return done

    
    def run(self):
        # wait for a new event
        self.logger.debug("host {}:run(): called run".format(self.host))
        try:
            timeout = self._socket.gettimeout()
            self._socket.settimeout(0.1) # Non blocking
            data = self._socket.recv(4)
            self.logger.debug("host {}:run(): data_dump from read_size: {}".format(self.host, data))
            size = int.from_bytes(data, 'little')
        except socket.error as e:
            self.logger.debug('host {}:run(): error while receiving: {}'.format(self.host, e))
            self.logger.info('host {}:run(): nothing to receive'.format(self.host))
            return False
        finally:
            self._socket.settimeout(timeout)

        # receive event
        self.logger.debug('host {}:run(): Receiveing new event of {} bytes.'.format(self.host, size))
        data = b''
        while len(data) < size:
            data += self._socket.recv(size-len(data))

        self.logger.debug("host {}:run(): data_dump: {}".format(self.host, data))
        # parse xml
        try:
            ascii = data.decode("ascii").replace('\x00', '')
            #ascii should now be just a string
            #to make sure no corrupted xml files still get parsed correctly, we fix it if it is broken
            temp = ascii.split("</profile>")
            ascii = temp[0]+'</profile>'
            #now we can be certain the parser will not have issues
            profile = xmltodict.parse(ascii)
            self.logger.info('host {}:run(): new Profile translates to: \n{}\n'.format(self.host, xml.dom.minidom.parseString(ascii).toprettyxml()))
        except:
            self.logger.error('host {}:run(): XML event data not parseable.'.format(self.host))
            return False

        # parse profile
        try:
            events = profile['profile']['events']['event']#returns a list of dict with each dict holding the information of an event
            self.logger.debug("host {}:run(): profile_dump: {}".format(self.host, profile))
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
                self.logger.debug("host {}:run(): task_id: {} |received event of type {} with timestamp {}".format(self.host, _task_id, _type, _timestamp))
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
                    #TODO this is fine, but aparently not working on the genode system.
                    #if we receive this, we do nothing so far
                    if not task.jobs or not((len(task.jobs)==task["numberofjobs"]) and task.jobs[-1].end_date is not None):
                    	self.logger.critical("host {}:run(): JOBS_DONE from Genode is received but jobs is not number of jobs long yet.".format(self.host))
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
                    self.logger.critical("host {}:run(): Unknown event type {}".format(self.host,_type))

        except (ValueError,TypeError) as e:
            self.logger.critical("host {}:run(): 'profile'-node of event has unknown structure"+
                                 " and can not be parsed. TaskSet stopped.\nError: {}".format(self.host, e ))
            return False

        return True # task-set changed
    

    def _get_task_by_id(self, task_id):
        # the taskset is a list, we have to loop over all items...
        for task in self.tset:
            if task.id == task_id:
                return task
        return None


    def _optimize(self):
        if self.admctrl is None:
            self.logger.debug("host {}:_optimize(): admctrl is None".format(self.host))
            return

        if not isinstance(self.admctrl, dict):
            raise TypeError("admctrl must be of type dict") 

        # convert admctrl dict to xml.
        xml = self._dicttoxml(self.admctrl).encode('ascii')
        
        self.logger.debug('host {}:_optimize(): Send optimiziaton goal.'.format(self.host))
        meta = struct.pack('II', MagicNumber.OPTIMIZE, len(xml))
        self._send(len(meta),meta)
        self._send(len(xml),xml)

    def _send(self,size, data):
        self.logger.debug('host {}:_send():  have {} to send.'.format(self.host,size))
        sent = 0
        while sent < size:
            amount = min(size-sent,4096)
            sent += self._socket.send(data[sent:sent+amount])
            #self.logger.debug('host {}:_send(): {}/{}.'.format(self.host,sent,size))
        self.logger.debug('host {}:_send(): {} sent successful.'.format(self.host,sent))
        

    def _dicttoxml(self, d):
        # genode can't handle `<?xml version="1.0" encoding="utf-8"?>` at
        # the documents beginning. `full_document=False` removes it.
        return xmltodict.unparse(d, pretty=True, full_document=False)
        
    def _close(self):
        self.tset = None
        self.admctrl=None
        self._socket.close()
        self.logger.debug('host {}:_close(): Close connection.'.format(self.host))
        
    def _stop(self):
        meta = struct.pack('I', MagicNumber.STOP)
        self.logger.debug('host {}:_stop(): Stop tasks on server.'.format(self.host))
        self._send(len(meta),meta)
        
    def _clear(self):
        self.run()
        self.tset = None
        self.admctrl = None
        self.logger.debug('host {}:_clear(): Clear tasks on server.'.format(self.host))
        meta = struct.pack('I', MagicNumber.CLEAR)
        self._send(len(meta),meta)
        time.sleep(2)
        #temp = self._socket.recv(4)
        #msg = int.from_bytes(temp, 'little')
        #if msg != MagicNumber.GO_SEND:
        #    self.logger.critical('host {}:_clear(): this is weired. that shouldnt happen. received: {} as int that is: {}'.format(self.host, temp, msg))
        #else:
        #    self.logger.critical('host {}:_clear(): went well'.format(self.host))
            
    def _send_descs(self):
        if not isinstance(self.tset, TaskSet):
            raise TypeError("_send_descs(): taskset must be type TaskSet") 
        list_item_to_name = lambda x : "periodictask"
        description = dicttoxml.dicttoxml(self.tset.description(), attr_type=False, root=False, item_func=list_item_to_name)
        self.logger.info('host {}:_send_descs(): Description about to send: \n{}\n '.format(self.host, xml.dom.minidom.parseString(description).toprettyxml()))
        
        
        self.logger.debug("host {}:_send_descs(): Sending taskset description.".format(self.host))
        meta = struct.pack('II', MagicNumber.SEND_DESCS, len(description))
        self._send(len(meta),meta)
        self._send(len(description),description)

    
    def _send_bins(self):
        if not isinstance(self.tset, TaskSet):
            raise TypeError("_send_bins(): taskset must be type TaskSet") 

        names = self.tset.binaries()
        self.logger.debug('host {}:_send_bins(): sent_bin is \n{}\n and names is\n {}.'.format(self.host, self.sent_bin, names))
        binaries = []

        #binaries = names
        for name in names:
            if name not in self.sent_bin:
                binaries.append(name)
                self.sent_bin.add(name)
        
        self.logger.debug('host {}:_send_bins(): Sending {} binary file(s).'.format(self.host, len(binaries)))
        self.logger.debug('host {}:_send_bins(): have to send {} of {}.'.format(self.host, len(binaries), len(names)))
        
        meta = struct.pack('II', MagicNumber.SEND_BINARIES, len(binaries))
        self._send(len(meta),meta)

        for name in binaries:
            # Wait for 'go' message.
            msg = int.from_bytes(self._socket.recv(4), 'little')
            if msg != MagicNumber.GO_SEND:
                self.logger.critical('host {}:_send_bins(): Invalid answer received, aborting: {}'.format(self.host, msg))
                break

            path = "{}/../../taskgen/bin/{}".format(self.script_dir, name)
            file = open(path, 'rb').read()
            size = os.stat(path).st_size
            self.logger.debug('host {}:_send_bins(): Sending {} of size {}.'.format(self.host, name,size))
            meta = struct.pack('15scI', name.encode('ascii'), b'\0', size)
            self._send(len(meta),meta)
            self._send(len(file),file)
            self.logger.debug('host {}: {} sent.'.format(self.host,name))
            

    def _start(self):
        self.logger.debug('host {}:_start():  Starting tasks on server.'.format(self.host))
        meta = struct.pack('I', MagicNumber.START)
        self._send(len(meta),meta)
        





        

class PingSession(GenodeSession):
    PING_TIMEOUT=4
    def __init__(self, host, port):
        GenodeSession.__init__(self, host, port)
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

            
class QemuSession(PingSession):
    LOG='/tmp/taskgen_qemusession_ip_kill.log'
    PingSession.PING_TIMEOUT=1 # speed up, localhost is fast

    
    def _kill_qemu(self):
        self.logger.error("host {}:_kill_qemu(): Qemu instance of {} is killed.".format(self.host, self.host))
        with open(self.LOG, "a") as log:
            log.write(self.host + "\n")

    def __init__(self, host, port):
        # open connection
        PingSession.__init__(self, host, port)

        #self._socket.settimeout(10.0) # wait 1 seconds for responses (localhost is fast)
        #self.logger = logging.getLogger("QemuSession")
        #self._host = host

        # create empty file
        #open(self.LOG, 'a').close()
    
    def start(self, taskset, admctrl=None):
        try:
            PingSession.start(self, taskset, admctrl)
        except socket.timeout as e:
            self.logger.error("host {}: an error occured during start: {}".format(self.host, e))
            self._kill_qemu()
            self.close()
            raise e

    def stop(self):
        try:
            PingSession.stop(self)
        except socket.timeout as e:
            self.logger.error("host {}: an error occured during stop: {}".format(self.host, e))
            self._kill_qemu()
            self.close()          
            raise e


    def close(self):
        try:
            PingSession.close(self)
        except socket.timeout as e:
            self.logger.error("host {}: an error occured during close: {}".format(self.host, e))
            self._kill_qemu()
            raise e

    def run(self):
        try:
            return PingSession.run(self)
        except:
            self.logger.error("host {}: an error occured during run".format(self.host))
            self._kill_qemu()
            raise socket.error("socket timeout or some other unknown error")

    def clear(self):
        try:
            PingSession._clear(self)
        except socket.timeout as e:
            self.logger.error("host {}: an error occured during clear: {}".format(self.host, e))
            self._kill_qemu()
            self.close()          
            raise e