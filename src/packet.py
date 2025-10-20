def _ones_complement_16bit_sum(data: bytes) -> int: 
    """16-bit one's-complement checksum"""
    if len(data) % 2 == 1:
        data += b"\x00"
    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total = (total + word) & 0xFFFF
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


class Packet:
    """Represent a packet of data.
    Note - DO NOT REMOVE or CHANGE the data attribute!
    The simulation assumes this is present!"""

    def __init__(self, binary_data, seqnum, acknum, checksum):
        self.data = binary_data
        self.seqnum = seqnum # Sequence number
        self.acknum = acknum # Acknowledgement number
        self.checksum = checksum # Error detection 

    @staticmethod
    def compute_checksum(seqnum: int, acknum: int, payload: bytes) -> int:
        """Checksum over header (seqnum, acknum, length) + payload."""
        header = bytearray()
        header += int(seqnum).to_bytes(4, "big", signed=True)
        header += int(acknum).to_bytes(4, "big", signed=True)
        header += len(payload or b"").to_bytes(4, "big", signed=False)
        return _ones_complement_16bit_sum(bytes(header) + (payload or b""))
    
    def is_corrupt(self) -> bool:
        return self.checksum != Packet.compute_checksum(self.seqnum, self.acknum, self.data)
    
    @classmethod
    def make_data(cls, seqnum: int, payload: bytes):
        ck = cls.compute_checksum(seqnum, -1, payload)
        return cls(payload, seqnum, -1, ck)
    
    @classmethod
    def make_ack(cls, acknum: int):
        ck = cls.compute_checksum(0, acknum, b"")
        return cls(b"", 0, acknum, ck)

    def __str__(self):
        kind = "ACK" if self.acknum >= 0 else "DATA"
        return f"<{kind} seq={self.seqnum} ack={self.acknum} len={len(self.data)} cksum=0x{self.checksum:04x}>"