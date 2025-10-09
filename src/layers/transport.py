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
        self.last_ack_sent = 0  # Cumulative ACK value = next expected seq 

        # Statistics
        self.sent = 0  # Total number of packets sent
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

    def checksum(self, data):
        """Compute a simple checksum."""
        sum = 0
        for i in data:
            sum += 1
        return sum 

    def from_app(self, binary_data): # Sending data down the stack
        # packet = Packet(binary_data)

        # 1) Window check (half-open [base, base+N), modulo)
        if not self.in_window(self.next_seqnum, self.base, self.send_window):
            # No space leading to queue payload for later
            self.app_queue.append(binary_data)
            if self.logger:
                self.logger.debug(f"Application window full, the queued {len(self.app_queue)}, Application base = {self.base}, next seqnum = {self.next_seqnum}")
            return

        # 2) Build DATA packet for next sequence number 
        checksum = 0 # TODO: Placeholder for checksum calculation
        packet = Packet(binary_data, packet.self.next_seqnum, -1, checksum) # Fill in seqnum, is_ack = False, payload

        # 3) Send and buffer for potential retransmission
        self.network_layer.send(copy(packet))
        self.sent += 1
        self.send_buffer[self.next_seqnum] = packet
        if self.logger:
            in_process = (self.next_seqnum - self.base) % self.seqnum_space + 1
            self.logger.debug(f"Sent packet {packet}. Base = {self.base}, next seqnum = {self.next_seqnum}, in-process = {in_process}, Window = {self.send_window}")

        # 4) Start the single timer if the window was empty before this send
        if self.base == self.next_seqnum and not self.timer_active:
            self.reset_timer(self.timeout_action) # TODO: implement timeout_action
            self.timer_active = True
            if self.logger:
                self.logger.debug(f"Starting timer at seqnum {self.base}")

        # 5) Advance next_seqnum (modulo the sequence number space)
        self.next_seqnum = self.mod_seqnum(self.next_seqnum + 1)

        # self.network_layer.send(packet)

    def from_network(self, packet): # Receiving data up the stack
        self.application_layer.receive_from_transport(packet.data)
        # Implement me!

    def reset_timer(self, callback, *args):
        # This is a safety-wrapper around the Timer-objects, which are
        # separate threads. If we have a timer-object already,
        # stop it before making a new one so we don't flood
        # the system with threads!
        if self.timer:
            if self.timer.is_alive():
                self.timer.cancel()
        # callback(a function) is called with *args as arguments
        # after self.timeout seconds.
        self.timer = Timer(self.timeout, callback, *args)
        self.timer.start()
