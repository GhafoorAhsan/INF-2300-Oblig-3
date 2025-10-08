from copy import copy
from secrets import token_bytes
from threading import Timer

from config import DROP_CHANCE, CORRUPT_CHANCE, DELAY_CHANCE, DELAY_AMOUNT
from utils import validate_packet, should


class NetworkLayer:
    """Simulate an unreliable network which might drop,
    corrupt or delay packets."""

    def with_logger(self, logger):
        self.logger = logger
        return self

    def register_above(self, layer):
        self.transport_layer = layer

    def send(self, packet):
        # Make sure we only send packets which have valid data in them
        validate_packet(packet)
        packet = copy(packet)

        # Should we DROP this packet?
        if should(DROP_CHANCE):
            self.logger.warning(f"Dropping {packet}")
            return

        # Should we CORRUPT this packet?
        if should(CORRUPT_CHANCE):
            self.logger.warning(f"Corrupting {packet}")
            packet.data = token_bytes(len(packet.data))

        # Should we DELAY this packet?
        if should(DELAY_CHANCE):
            self.logger.warning(f"Delaying {packet}")
            # We actually delay this! A Timer object is a subclass of Thread.
            # This will basically call:
            # 'self.recipient.receive(packet)' after DELAY_AMOUNT
            # seconds have passed, from a separate thread. So other packets
            # will arrive in the meantime.
            timer_object = Timer(
                DELAY_AMOUNT, self.recipient.receive, (packet,)
            )
            timer_object.start()
            return

        self.recipient.receive(packet)

    def receive(self, packet):
        self.transport_layer.from_network(packet)
