from copy import copy
from threading import Timer
from packet import Packet 
from collections import deque
from threading import RLock

class TransportLayer:
    """The transport layer receives chunks of data from the application layer
    and must make sure it arrives on the other side unchanged and in order.
    """

    def __init__(self):
        # Logging and timer variables
        self.logger = None
        self.timer = None
        self.timeout = 0.4  # Seconds, must be >= 2 * one-way delay + margin
        self.timer_active = False # True if the single GBN timer is running 

        # Sender state for Go-Back-N
        self.base = 0  # The sequence number of the oldest unacknowledged packet
        self.next_seqnum = 0  # The sequence number of the next packet to send
        self.send_window = 5  # Window size N, max unACKed packets in flight.
        self.seqnum_space = 2 * self.send_window  # Size of sequence number space. >= 2 * N to avoid wrap-around
        self.send_buffer = {}  # Seqnum -> Packet, in flight, for RTX
        self.app_queue = deque()  # FIFO of app data waiting to send when the window is full.

        # Receiver state for Go-Back-N
        self.expected_seqnum = 0  # Receiver’s next in-order seq to accept/deliver.
        self.last_ack_send = 0  # Last cumulative ACK value sent 

        # Statistics
        self.send = 0  # Total number of packets send
        self.retransmitted = 0  # Total number of packets retransmitted
        self.timeout_num = 0  # Total number of timeouts
        self.duplicate_acks = 0  # Count of received duplicate ACKs at the sender
        self.rx_corrupted_data = 0  # Corrupted data segments observed (checksum failed).
        self.rx_corrupted_acks = 0  # Corrupted ACK segments observed (checksum failed).

        # Layers above and below
        self.application_layer = None
        self.network_layer = None

        self.closed = False
        self.lock = RLock() # Protects all shared state and timer operations 

    def drain_app_queue(self):
        """ Try to send queued app data while window allows """
        with self.lock:
            while self.app_queue and self.in_window(self.next_seqnum, self.base, self.send_window):
                payload = self.app_queue.popleft()
                self.from_app(payload)

    def close(self):
        """ Close transport. Stop timer, ignore further I/O"""
        self.closed = True
        self.stop_timer()

    def with_logger(self, logger):
        self.logger = logger
        return self

    def register_above(self, layer):
        self.application_layer = layer

    def register_below(self, layer):
        self.network_layer = layer

    def mod_seqnum(self, num):
        """Wrap sequence numbers into the configured sequence space."""
        return num % self.seqnum_space 
    
    def in_window(self, seqnum, base, N):
        """True if seqnum is inside [base, base + N) modulo sequence space. 
            Circular window check using modular distance.        
        """
        return (seqnum - base) % self.seqnum_space < N

    def dbg(self, msg):
        if self.logger:
            self.logger.debug(msg)

    def st(self):
        """Compact state string for logs."""
        return f"base={self.base} n={self.next_seqnum} inbuf={len(self.send_buffer)}"
    
    def from_app(self, binary_data): # Sending data down the stack
        """
        Sender entry point.
        - Enforce window.
        - Build DATA packet with current next_seqnum.
        - Buffer for possible retransmission
        - Start timer if this was the first in-flight segment. 
        """
        with self.lock:
            if self.closed:
                return
            # Window full -> queue app data 
            if len(self.send_buffer) >= self.send_window:
                self.app_queue.append(binary_data)
                self.dbg(f"APP queue (full) q={len(self.app_queue)} | {self.st()}")
                return
            # Seqnum not inside window -> queue app data 
            if not self.in_window(self.next_seqnum, self.base, self.send_window):
                self.app_queue.append(binary_data)
                self.dbg(f"APP queue (win) q={len(self.app_queue)} | {self.st()}")
                return 
            assert self.in_window(self.next_seqnum, self.base, self.send_window)
            # Build segment at "olf_next"
            old_next = self.next_seqnum
            self.dbg(f"BUILD seq={old_next} | {self.st()}")
            pkt = Packet.make_data(old_next, binary_data)
            assert pkt.seqnum == old_next, f"Packet seq mismatch: built {pkt.seqnum}, expected {old_next}"
            was_empty = (len(self.send_buffer) == 0)
            self.send_buffer[old_next] = pkt
            # Start timer for oldest unACKed if nothing in flight before 
            if was_empty and not self.timer_active:
                self.reset_timer(self.on_timeout)
                self.dbg(f"TIMER start | {self.st()}")
            # Send the packet down to network
            self.dbg(f"SEND data seq={old_next} | {self.st()}")
            self.network_layer.send(copy(pkt))
            self.send += 1
            # Advance next seqnum modulo space
            self.next_seqnum = self.mod_seqnum(old_next + 1)
            inflight_after = len(self.send_buffer)
            assert inflight_after <= self.send_window
            assert self.timer_active == (inflight_after > 0)

    def ack_advances(self, acknum: int) -> bool:
        """True if cumulative ACK "acknum" moves "base" forward modulo the seq space."""
        dist = (acknum - self.base) % self.seqnum_space
        return 0 < dist <= self.send_window

    def from_network(self, packet): # Receiving data up the stack
        """
            Upcall for both ACKs and DATA.
            Sender side:
                - Validate checksum.
                - If ACK advances: slide window, manage timer, drain app queue.
                - Else, count duplicate ACKs.
            Receiver side:
                - If in-order DATA: Deliver, advance expected_seqnum, send cumulative ACK.
                - Else or corrupt: re-ACK last in-order.  
        """
        with self.lock:
            if self.closed:
                return
            # ACK --> sender side. acknum >= 0 signifies an ACK segment 
            if packet.acknum >= 0:
                if packet.is_corrupt():
                    self.rx_corrupted_acks += 1
                    self.dbg("RX ACK corrupt → ignore")
                    return 
                acknum = packet.acknum % self.seqnum_space
                if self.ack_advances(acknum):
                    # Slide base up to acknum, with exclusize pop
                    self.dbg(f"ACK advance → {acknum} | {self.st()}")
                    seq = self.base
                    while seq != acknum:
                        self.send_buffer.pop(seq, None)
                        seq = self.mod_seqnum(seq + 1)
                    self.base = acknum
                    # Timer management, stop if no inflight, else restart for new oldest 
                    if not self.send_buffer:
                        self.next_seqnum = self.base
                        self.stop_timer()
                    else:
                        self.reset_timer(self.on_timeout)
                    # Try to send queued app data 
                    self.drain_app_queue()
                else:
                    # Duplicate cumulative ACK
                    self.duplicate_acks += 1
                    self.dbg(f"ACK dup  = {acknum} | {self.st()}")
                return 
            # Data -> receiver side 
            if packet.is_corrupt():
                # Corrupt data --> re-ACK expected_seqnum
                self.rx_corrupted_data += 1
                self.last_ack_send = self.expected_seqnum
                # Re-ACK last in-order (expected_seqnum)
                ack = Packet.make_ack(self.expected_seqnum)
                self.network_layer.send(ack)
                self.dbg(f"RX DATA corrupt → reACK {self.expected_seqnum}")
                return
            seq = packet.seqnum % self.seqnum_space
            if seq == self.expected_seqnum:
                # Deliver in-order -> deliver up
                if self.application_layer:
                    self.application_layer.receive_from_transport(packet.data)
                # Advance receiver state and ACK next expected
                self.expected_seqnum = self.mod_seqnum(self.expected_seqnum + 1)
                self.last_ack_send = self.expected_seqnum
                ack = Packet.make_ack(self.expected_seqnum)
                self.network_layer.send(ack)
                self.dbg(f"DELIVER seq={seq} → exp={self.expected_seqnum}")
            else:
                # Out-of-order or duplicate -> drop and re-ACK last in-order (expected_seqnum)
                ack = Packet.make_ack(self.last_ack_send)
                self.network_layer.send(ack)
                self.dbg(f"DROP oo seq={seq} → reACK {self.last_ack_send}")

    def reset_timer(self, callback, *args):
        """
        Restart/Start the single sender timer.
        Always cancels any running timer before starting a new one.
        """
        with self.lock:
            if self.closed:
                return
            if self.timer:
                if self.timer.is_alive():
                    self.timer.cancel()
            self.timer = Timer(self.timeout, callback, args=args)
            self.timer.daemon = True
            self.timer.start()
            self.timer_active = True

    def stop_timer(self):
        """
        Stop the sender timer if active.
        """
        with self.lock:
            if not self.timer_active:
                return
            if self.timer:
                if self.timer.is_alive():
                    self.timer.cancel()
            self.timer_active = False 
            self.timer = None
            self.dbg("TIMER stop")

    def on_timeout(self):
        """
        Timeout handler for GBN.
        Retransmit all unACKed packets in [base, next_seqnum).
        Restart the timer if anything remains in-flight.
        """
        with self.lock:
            if self.closed or not self.timer_active:
                return
            self.timeout_num += 1
            self.dbg(f"TIMEOUT → RTX {self.base}..{self.next_seqnum} | {self.st()}")
            # Go Back N: resend everything unACKed
            seq = self.base 
            while seq != self.next_seqnum:
                pkt = self.send_buffer.get(seq)
                if pkt is not None:
                    self.network_layer.send(copy(pkt))
                    self.retransmitted += 1
                seq = self.mod_seqnum(seq + 1)
            if self.closed:
                return
            if self.send_buffer:
                # Keep timer running for the oldest unACKed
                self.reset_timer(self.on_timeout)
            else:
                # Nothing in flight: stop and try draining queued app data 
                self.stop_timer()
                self.drain_app_queue()

    def stats(self):
        return (f"sent={self.send} rtx={self.retransmitted} "
            f"timeouts={self.timeout_num} dupACKs={self.duplicate_acks} "
            f"corrupt_d={self.rx_corrupted_data} corrupt_ack={self.rx_corrupted_acks}")
