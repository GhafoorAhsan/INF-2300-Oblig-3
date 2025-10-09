from logging import getLogger

from layers import ApplicationLayer, NetworkLayer, TransportLayer
from utils import IterableBytes


# Represents one complete communication stack in the simulator 
# A small model of how data moves through the Application, Transport, and Network layers of the OSI model
# Will have two stacks --> Alice (the sender)
# When connected, Alice can send packets to Bob through these layers, and the Network layer can simulate problems --> packet loss, corruption, delay

# Open Systems Interconnection (OSI)
class OSIStack:
    def __init__(self, name, packet_num, packet_size):
        # Every layer in this stack will have a named logger
        logger = getLogger(name)
        self.name = name

        # Generate all the layers we need for the simulation.

        # The application layer is where data originates. 
        # It uses IterableBytes to generate chunks of random uppercase ASCII data.
        # For example, if packet_num=10 and packet_size=4, it will produce 10 data chunks like ["ABCD", "XJHY", ...].
        self.app_layer = ApplicationLayer(IterableBytes(packet_num, packet_size)).with_logger(logger)

        # The layer where reliability is handled (Go-Back-N).
        # It ensures that even if packets are lost or corrupted in the network, the receiver still gets the full correct message in order
        self.transport_layer = TransportLayer().with_logger(logger)

        # Simulates the unreliable channel.
        # It can randomly drop, corrupt, or delay packets based on the configuration settings.
        self.network_layer = NetworkLayer().with_logger(logger)

        # Connect all the layers, each layer knows the layer above and below it.
        self.app_layer.register_below(self.transport_layer)
        self.transport_layer.register_above(self.app_layer)
        self.transport_layer.register_below(self.network_layer)
        self.network_layer.register_above(self.transport_layer)

    def __str__(self):
        return f"{self.name}"

    # Returns the latest data chunk being sent — useful for debugging or logging.
    def get_current(self):
        return self.app_layer.binary_data[-1]

    def connect(self, other_stack):
        # The network layer of one stack will be connected to the network layer of the other_stack.
        # See: 'network.py' for mor details.
        self.network_layer.recipient = other_stack.network_layer

    def tick(self):
        self.app_layer.send_next_packet()

    # The total payload Bob has received so far (what reached his application layer)
    @property
    def received(self):
        return self.app_layer.payload

    # The original data Alice intended to send. (Used to compare for correctness.)
    @property
    def original_data(self):
        return self.app_layer.payload
