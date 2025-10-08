class ApplicationLayer:
    """The application layer will either send a continous
    chunk of bytes to the transport layer below, or receive chunks.
    Data received must be in correct order and uncorrupted."""
    def __init__(self, iterable_bytes):
        self.payload = iterable_bytes

    def with_logger(self, logger):
        self.logger = logger
        return self

    def register_below(self, layer):
        self.transport_layer = layer

    def send_next_packet(self):
        if not self.payload:
            return

        next_bytes = self.payload.get_chunk()
        self.transport_layer.from_app(next_bytes)

    def receive_from_transport(self, binary_data):
        self.payload.put_chunk(binary_data)
