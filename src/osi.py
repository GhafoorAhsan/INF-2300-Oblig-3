from logging import getLogger

from layers import ApplicationLayer, NetworkLayer, TransportLayer
from utils import IterableBytes


class OSIStack:
    def __init__(self, name, packet_num, packet_size):
        # Every layer in this stack will have a named logger
        logger = getLogger(name)
        self.name = name

        # Generate all the layers we need for the simulation.
        self.app_layer = ApplicationLayer(
            IterableBytes(packet_num, packet_size)
        ).with_logger(logger)
        self.transport_layer = TransportLayer().with_logger(logger)
        self.network_layer = NetworkLayer().with_logger(logger)

        # Connect all the layers
        self.app_layer.register_below(self.transport_layer)
        self.transport_layer.register_above(self.app_layer)
        self.transport_layer.register_below(self.network_layer)
        self.network_layer.register_above(self.transport_layer)

    def __str__(self):
        return f"{self.name}"

    def get_current(self):
        return self.app_layer.binary_data[-1]

    def connect(self, other_stack):
        # The network layer of one stack will be connected
        # to the network layer of the other_stack.
        # See: 'network.py' for mor details.
        self.network_layer.recipient = other_stack.network_layer

    def tick(self):
        self.app_layer.send_next_packet()

    @property
    def received(self):
        return self.app_layer.payload

    @property
    def original_data(self):
        return self.app_layer.payload
