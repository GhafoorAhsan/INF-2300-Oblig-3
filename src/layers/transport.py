from copy import copy
from threading import Timer

from packet import Packet 

from collections import deque



class TransportLayer:
    """The transport layer receives chunks of data from the application layer
    and must make sure it arrives on the other side unchanged and in order.
    """

    def __init__(self):
        # Logging and timer variables
        self.logger = None
        self.timer = None
        self.timeout = 0.4  # Seconds
        self.timer_active = False # True if the single GBN timer for the oldest unACKed segment at base is running.

        # Sender state for Go-Back-N
        self.base = 0  # The sequence number of the oldest unacknowledged packet
        self.next_seqnum = 0  # The sequence number of the next packet to send
        self.send_window = 5  # Window size N, max unACKed packets in flight.
        self.seqnum_space = 2 * self.send_window  # Size of sequence number space. >= 2 * N to avoid wrap-around
        self.send_buffer = {}  # In-flight (unACKed) segments keyed by seqnum to Packet for retransmission
        self.app_queue = deque()  # FIFO of app data waiting to send when the window is full.

        # Receiver state for Go-Back-N
        self.expected_seqnum = 0  # Receiver’s next in-order seq to accept/deliver.
        self.last_ack_send = 0  # Cumulative ACK value = next expected seq 

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

    def with_logger(self, logger):
        self.logger = logger
        return self

    def register_above(self, layer):
        self.application_layer = layer

    def register_below(self, layer):
        self.network_layer = layer

    def mod_seqnum(self, num):
        """Helper to keep sequence numbers within the sequence number space."""
        return num % self.seqnum_space 
    
    def in_window(self, seqnum, base, N):
        """Helper to check if a sequence number is within the window [base, base + N) modulo the sequence space."""
        return (seqnum - base) % self.seqnum_space < N

    def dbg(self, msg):
        if self.logger:
            self.logger.debug(msg)

    def st(self):
        # short state string
        return f"base={self.base} n={self.next_seqnum} inbuf={len(self.send_buffer)}"
    
    def from_app(self, binary_data): # Sending data down the stack

        # Window guard (robust: use actual inflight count)
        if len(self.send_buffer) >= self.send_window:
            self.app_queue.append(binary_data)
            self.dbg(f"APP queue (full) q={len(self.app_queue)} | {self.st()}")
            return

        # Window guard
        if not self.in_window(self.next_seqnum, self.base, self.send_window):
            self.app_queue.append(binary_data)
            self.dbg(f"APP queue (win) q={len(self.app_queue)} | {self.st()}")
            return 
        
        assert self.in_window(self.next_seqnum, self.base, self.send_window)

        old_next = self.next_seqnum
        self.dbg(f"BUILD seq={old_next} | {self.st()}")

        
        # Build DATA 
        pkt = Packet.make_data(old_next, binary_data)

        assert pkt.seqnum == old_next, f"Packet seq mismatch: built {pkt.seqnum}, expected {old_next}"

        was_empty = (len(self.send_buffer) == 0)

        self.send_buffer[old_next] = pkt

        if was_empty and not self.timer_active:
            self.reset_timer(self.on_timeout)
            self.dbg(f"TIMER start | {self.st()}")

        # Send + Buffer
        self.dbg(f"SEND data seq={old_next} | {self.st()}")
        self.network_layer.send(copy(pkt))
        self.send += 1

        # Post-send ghost drop: if this seq got cumulatively ACKed already, remove it
        ahead = (old_next - self.base) % self.seqnum_space
        inflight_now = (self.next_seqnum - self.base) % self.seqnum_space
        if inflight_now > 0 and ahead >= inflight_now:
            self.send_buffer.pop(old_next, None)
            self.dbg(f"GHOST-DROP seq={old_next}")
            if not self.send_buffer and self.timer_active:
                self.stop_timer()


        # Advance next seqnum using the snapshot
        self.next_seqnum = self.mod_seqnum(old_next + 1)

        inflight_after = len(self.send_buffer)
        assert inflight_after <= self.send_window
        assert self.timer_active == (inflight_after > 0)

    def ack_advances(self, acknum: int) -> bool:
        """True iff cumulative ACK 'acknum' moves base forward modulo the seq space."""
        dist = (acknum - self.base) % self.seqnum_space
        return 0 < dist <= self.send_window

    def from_network(self, packet): # Receiving data up the stack
        # ACK --> sender side 
        if packet.acknum >= 0:
            if packet.is_corrupt():
                self.rx_corrupted_acks += 1
                self.dbg("RX ACK corrupt → ignore")
                return 
            
            acknum = packet.acknum % self.seqnum_space
            if self.ack_advances(acknum):
                # Slide window cumulatively up to (but not including) acknum
                self.dbg(f"ACK advance → {acknum} | {self.st()}")
                seq = self.base
                while seq != acknum:
                    self.send_buffer.pop(seq, None)
                    seq = self.mod_seqnum(seq + 1)
                self.base = acknum

                # Timer management
                if not self.send_buffer:
                    self.next_seqnum = self.base
                    self.stop_timer()
                else:
                    self.reset_timer(self.on_timeout)

                # Drain app queue while there is space 
                while self.app_queue and self.in_window(self.next_seqnum, self.base, self.send_window):
                    payload = self.app_queue.popleft()
                    self.from_app(payload)

                inflight = len(self.send_buffer)
                assert inflight <= self.send_window
                assert self.timer_active == (inflight > 0)
            
            else:
                self.duplicate_acks += 1
                self.dbg(f"ACK dup  = {acknum} | {self.st()}")
            return 
        
        # Data -> receiver side 
        # DATA packets use acknum == -1
        if packet.is_corrupt():
            self.rx_corrupted_data += 1
            self.last_ack_send = self.expected_seqnum
            # Re-ACK last in-order (expected_seqnum)
            ack = Packet.make_ack(self.expected_seqnum)
            self.network_layer.send(ack)
            self.dbg(f"RX DATA corrupt → reACK {self.expected_seqnum}")
            return
        
        seq = packet.seqnum % self.seqnum_space
        if seq == self.expected_seqnum:
            # Deliver in-order
            if self.application_layer:
                self.application_layer.receive_from_transport(packet.data)

            # Advance receiver state
            self.expected_seqnum = self.mod_seqnum(self.expected_seqnum + 1)
            self.last_ack_send = self.expected_seqnum

            # Send cumulative ACK (next expected)
            ack = Packet.make_ack(self.expected_seqnum)
            self.network_layer.send(ack)
            self.dbg(f"DELIVER seq={seq} → exp={self.expected_seqnum}")
        else:
            # Out-of-order or duplicate -> drop and re-ACK last in-order (expected_seqnum)
            ack = Packet.make_ack(self.last_ack_send)
            self.network_layer.send(ack)
            self.dbg(f"DROP oo seq={seq} → reACK {self.last_ack_send}")


    def reset_timer(self, callback, *args):
        if self.timer:
            if self.timer.is_alive():
                self.timer.cancel()
        self.timer = Timer(self.timeout, callback, args=args)
        self.timer.start()
        self.timer_active = True

    def stop_timer(self):
        if self.timer:
            if self.timer.is_alive():
                self.timer.cancel()
        self.timer_active = False 
        self.timer = None
        self.dbg("TIMER stop")


    def on_timeout(self):
        self.timeout_num += 1
        self.dbg(f"TIMEOUT → RTX {self.base}..{self.next_seqnum} | {self.st()}")
        seq = self.base 
        while seq != self.next_seqnum:
            pkt = self.send_buffer.get(seq)
            if pkt is not None:
                self.network_layer.send(copy(pkt))
                self.retransmitted += 1
            seq = self.mod_seqnum(seq + 1)
        
        if self.send_buffer:
            self.reset_timer(self.on_timeout)
        else:
            self.stop_timer()

        assert self.timer_active == (len(self.send_buffer) > 0)
