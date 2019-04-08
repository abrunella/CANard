"""CanQueue

This module provides a queue-based method of interaction with the CAN bus. Incoming messages are serviced by a thread and are added to the receive queue. Outgoing messages are enqueued and transmitted by the transmission thread.

"""

from canard import can
import threading

try:
    import queue
except ImportError:
    import Queue as queue

import time


def indirect_caller(instance, name, args=(), kwargs=None):
    """Indirect function caller for instance methods and threading"""
    if kwargs is None:
        kwargs = {}
    return getattr(instance, name)(*args, **kwargs)


class CanQueue:
    """Queue-based interface to the CAN bus"""

    def __init__(self, can_dev, maxsize=0):
        self.can_dev = can_dev       
        self.recv_thread = threading.Thread(target=indirect_caller, args=(self, 'recv_task'))
        self.send_thread = threading.Thread(target=indirect_caller, args=(self, 'send_task'))
        self.recv_queue = queue.Queue(maxsize=maxsize)
        self.send_queue = queue.Queue(maxsize=maxsize)
        self._recv_stopevent = threading.Event()
        self._send_stopevent = threading.Event()
        
        
    def start(self):
        """Start the CAN device and queue processes"""
        self.can_dev.start()
        self.recv_thread.start()
        self.send_thread.start()

    def stop(self):
        """Stop the CAN device and queue processes"""
        
        # Stop the receive thread
        self._recv_stopevent.set()
        self.recv_thread.join(1)
        
        # Stop the send thread
        self._send_stopevent.set()
        self.send_thread.join(1)
        self.can_dev.stop()

    def send(self, msg):
        """Enqueue a message for sending"""
        self.send_queue.put(msg)

    def recv(self, timeout=1, filter=None):
        """Receive one message from the queue"""
        try:
            start_time = time.time()
            while True:
                msg = self.recv_queue.get(timeout=timeout)

                # TODO: Move filter to receive task
                if not filter:
                    return msg
                elif filter == msg.id:
                    return msg
                # ensure we haven't gone over the timeout
                if time.time() - start_time > timeout:
                    return None

        except queue.Empty:
            return None

    def recv_all(self, overrun=100):
        """Receive a list of all items in the queue"""
        result = []
        ctr = 0;

        # Loop through all items in the queue and add them to the list (up to "overrun" items)
        while (not self.recv_queue.empty()) and ctr < overrun:
            result.append(self.recv_queue.get())
            ctr += 1

        return result

    def recv_task(self):
        """CAN receiver, called by the receive process"""
        while not self._recv_stopevent.isSet():
            msg = self.can_dev.recv()
            self.recv_queue.put(msg)
           
    def send_task(self):
        """CAN transmitter, called by the transmit process"""
        while not self._send_stopevent.isSet():
            try:
                msg = self.send_queue.get(timeout=0.1)
                self.can_dev.send(msg)
            except queue.Empty:
                continue
