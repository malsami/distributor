import socket
import code
import struct
import re
import os
import sys
import subprocess
from collections import Iterable
import logging
import xmltodict
from abc import ABCMeta, abstractmethod
from session import AbstractSession
sys.path.append('../')
from taskgen.taskset import TaskSet
from taskgen.task import Job
import taskgen
import time
import json

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
        self._socket = socket.create_connection((host, port))
        
        self.logger = logging.getLogger("GenodeSession({})".format(host))
        self.hdlr = logging.FileHandler('./log/session.log')
        self.formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(self.formatter)
        logger.addHandler(self.hdlr)
        logger.setLevel(logging.DEBUG)

        self.logger.debug("Connection establishment")
        self._socket.settimeout(10.0) # wait 10 seconds for responses...

    def start(self, taskset, admctrl=None):
        self._clear()
        
        self._optimize(admctrl)
        self._send_descs(taskset)
        self._send_bins(taskset)
        self._start()

    def stop(self):
        self._stop()

    def close(self):
        try:
            self._clear()
        except socket.error:
            pass
        self._close()    

        
    def is_running(self, taskset):
        done = True
        for task in taskset:
            done = done and ((len(task.jobs)==task["numberofjobs"]) and task.jobs[-1].end_date is not None)
        
        # if all jobs are done, we are not running anymore
        return not done

    
    def run(self, taskset):
        # wait for a new event
        try:
            timeout = self._socket.gettimeout()
            self._socket.settimeout(0.1) # Non blocking
            data = self._socket.recv(4)
            size = int.from_bytes(data, 'little')
        except:
            return False
        finally:
            self._socket.settimeout(timeout)

        # receive event
        self.logger.debug('Receiveing new event of {} bytes.'.format(size))
        data = b''
        while len(data) < size:
            data += self._socket.recv(1024)

        # parse xml
        try:
            ascii = data.decode("ascii").replace('\x00', '')
            #ascii should now be just a string
            #to make sure no corrupted xml files still get parsed correctly, we fix it if it is broken
            temp = ascii.split("</profile>")
            ascii = temp[0]+'</profile>'
            #now we can be certain the parser will not have issues
            profile = xmltodict.parse(ascii)
        except:
            self.logger.error('XML event data not parseable.')
            return False

        # parse profile
        try:
            events = profile['profile']['events']['event']#returns a list of dict with each dict holding the information of an event

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
                task = self._get_task_by_id(taskset, _task_id)
                
                # update job of task
                if _type == "START":
                    # add a new job and set its start date.
                    if not task.jobs or task.jobs[-1].start_date is not None:
                        task.jobs.append(Job())
                    task.jobs[-1].start_date = _timestamp
                elif _type == "EXIT":
                    if not task.jobs or task.jobs[-1].end_date is not None:
                        task.jobs.append(Job())
                    # take last job of the list and set its end date.
                    task.jobs[-1].end_date = _timestamp
                elif _type == "JOBS_DONE":
                    #TODO this is fine, but aparently not working on the genode system.
                    #if we receive this, we do nothing so far
                    if not task.jobs or not((len(task.jobs)==task["numberofjobs"]) and task.jobs[-1].end_date is not None):
                    	self.logger.critical("JOBS_DONE from Genode is received but jobs is not number of jobs long yet.")
                elif _type == "NOT_SCHEDULED":
                	#TODO kommt wenn die periode kommen würde, aber optimizer oder rta start verhindern
                    pass
                else:
                    self.logger.critical("Unknown event type {}".format(_type))

        except ValueError:
            self.logger.critical("'profile'-node of event has unknown structure"+
                                 " and can not be parsed. TaskSet stopped.")
            return False

        return True # task-set changed
    

    def _get_task_by_id(self, taskset, task_id):
        # the taskset is a list, we have to loop over all items...
        for task in taskset:
            if task.id == task_id:
                return task
        return None


    def _optimize(self, admctrl):
        if admctrl is None:
            return

        if not isinstance(admctrl, dict):
            raise TypeError("admctrl must be of type dict") 

        # convert admctrl dict to xml.
        xml = self._dicttoxml(admctrl).encode('ascii')
        
        self.logger.debug('Send optimiziaton goal.')
        meta = struct.pack('II', MagicNumber.OPTIMIZE, len(xml))
        self._socket.send(meta)
        self._socket.send(xml)

    def _dicttoxml(self, d):
        # genode can't handle `<?xml version="1.0" encoding="utf-8"?>` at
        # the documents beginning. `full_document=False` removes it.
        return xmltodict.unparse(d, pretty=True, full_document=False)
        
    def _close(self):
        self._socket.close()
        self.logger.debug('Close connection.')
        
    def _stop(self):
        meta = struct.pack('I', MagicNumber.STOP)
        self.logger.debug('Stop tasks on server.')
        self._socket.send(meta)
        
    def _clear(self):
        self.logger.debug('Clear tasks on server.')
        meta = struct.pack('I', MagicNumber.CLEAR)
        self._socket.send(meta)
            
    def _send_descs(self, taskset):
        if not isinstance(taskset, TaskSet):
            raise TypeError("taskset must be type TaskSet") 
        
        description = self._dicttoxml(taskset.description())
        description = description.encode('ascii')
        
        self.logger.debug("Sending taskset description.")
        meta = struct.pack('II', MagicNumber.SEND_DESCS, len(description))
        self._socket.send(meta)
        self._socket.send(description)

    
    def _send_bins(self, taskset):
        if not isinstance(taskset, TaskSet):
            raise TypeError("taskset must be type TaskSet") 

        binaries = taskset.binaries()
        self.logger.debug('Sending {} binary file(s).'.format(len(binaries)))
        
        meta = struct.pack('II', MagicNumber.SEND_BINARIES, len(binaries))
        self._socket.send(meta)

        # get the path to the bin folder
        root_path = os.path.dirname(sys.modules['__main__'].__file__)
        
        for name in binaries:
            # Wait for 'go' message.
            msg = int.from_bytes(self._socket.recv(4), 'little')
            if msg != MagicNumber.GO_SEND:
                self.logger.critical('Invalid answer received, aborting: {}'.format(msg))
                break

            self.logger.debug('Sending {}.'.format(name))
            path = "{}/bin/{}".format(root_path, name)
            file = open(path, 'rb').read()
            size = os.stat(path).st_size
            meta = struct.pack('15scI', name.encode('ascii'), b'\0', size)
            self._socket.send(meta)
            self._socket.send(file)

    def _start(self):
        self.logger.debug('Starting tasks on server.')
        meta = struct.pack('I', MagicNumber.START)
        self._socket.send(meta)
        





        

class PingSession(GenodeSession):
    PING_TIMEOUT=4
    
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
        self.logger.info("Qemu instance of {} is killed.".format(self._host))
        with open(self.LOG, "a") as log:
            log.write(self._host + "\n")

    def __init__(self, host, port):
        # open connection
        PingSession.__init__(self, host, port)

        self._socket.settimeout(10.0) # wait 1 seconds for responses (localhost is fast)
        self.logger = logging.getLogger("QemuSession")
        self._host = host

        # create empty file
        open(self.LOG, 'a').close()
    
    def start(self, taskset, admctrl=None):
        try:
            PingSession.start(self, taskset, admctrl)
        except socket.timeout as e:
            self._kill_qemu()
            raise e

    def stop(self):
        try:
            PingSession.stop(self)
        except socket.timeout as e:
            self._kill_qemu()            
            raise e


    def close(self):
        try:
            PingSession.close(self)
        except socket.timeout as e:
            self._kill_qemu()
            raise e

    def event(self):
        try:
            return PingSession.event(self)
        except socket.timeout as e:
            self._kill_qemu()
            raise e
