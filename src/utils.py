from random import choice, random
from string import ascii_uppercase


class IterableBytes:
    """A collection of bytes which can be added to or subtracted from.
    Represents each OSI stacks growing and shrinking amount of data."""

    def __init__(self, packet_num, packet_size):
        self.bytes = generate_random_letters(packet_num * packet_size)
        self.chunk_size = packet_size
        self.pos = 0

    @property
    def remaining_bytes(self):
        return len(self.bytes) - self.pos

    def get_chunk(self):
        # Return the next chunk of bytes from the pool of byte
        if self.pos >= len(self.bytes):
            return None
        chunk = self.bytes[self.pos : self.pos + self.chunk_size]
        self.pos += self.chunk_size
        return chunk

    def put_chunk(self, bts):
        #
        self.bytes += bts

    def __eq__(self, other):
        return self.bytes == other.bytes

    def __str__(self):
        return f"{self.bytes}"

    def __bool__(self):
        return len(self.bytes) - self.pos > 0


def validate_packet(packet):
    """Ensure a packet has data AND that data is bytes."""
    if not hasattr(packet, "data"):
        raise AttributeError("Packet does not contain data")
    if not isinstance(packet.data, bytes):
        data_type = type(packet.data).__name__
        raise TypeError(f"Expected packet data to be bytes, got {data_type}")


def generate_random_letters(nbytes):
    """Generate a bytestring of nbytes,
    consisting only of uppercase easily printable characters.
    (65-90 in the ascii table."""
    letters = "".join(choice(ascii_uppercase) for _ in range(nbytes))
    return letters.encode()


def should(chance):
    """Determine whether or not we should do
    something based on the chance.
    True if we should, else False."""
    return random() < chance
