def _ones_complement_16bit_sum(data: bytes) -> int: 
    """
    16-bit one's-complement checksum
    - Pad odd-lenght data with one zero byte.
    - Add 16-bit words, fold carry bits, and return bitwise complement 
    Used for basic error detection in simulated packets.
    """
    if len(data) % 2 == 1:
        data += b"\x00" # pad to even lenght 
    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1] # combine two bytes
        total = (total + word) & 0xFFFF # add, keep low 16 bits
        total = (total & 0xFFFF) + (total >> 16) # fold carry around
    return (~total) & 0xFFFF # return one's complement 


class Packet:
    """Represent a packet of data.
    Note - DO NOT REMOVE or CHANGE the data attribute!
    The simulation assumes this is present!"""

    def __init__(self, binary_data, seqnum, acknum, checksum):
        self.data = binary_data # payload bytes
        self.seqnum = seqnum # Sequence number
        self.acknum = acknum # Acknowledgement number
        self.checksum = checksum # Computed check  

    @staticmethod
    def compute_checksum(seqnum: int, acknum: int, payload: bytes) -> int:
        """
        Checksum over header + payload.
        Header layout (big-ednian):
        4B seqnum |4B acknum |4B payload length 
        """
        header = bytearray()
        header += int(seqnum).to_bytes(4, "big", signed=True)
        header += int(acknum).to_bytes(4, "big", signed=True)
        header += len(payload or b"").to_bytes(4, "big", signed=False)
        return _ones_complement_16bit_sum(bytes(header) + (payload or b""))
    
    def is_corrupt(self) -> bool:
        """
        Return True if recomputed checksum does not match stored value. 
        """
        return self.checksum != Packet.compute_checksum(self.seqnum, self.acknum, self.data)
    
    @classmethod
    def make_data(cls, seqnum: int, payload: bytes):
        """
        Construct a DATA packet.
        acknum = -1 marks it as data, and not ACK
        """
        ck = cls.compute_checksum(seqnum, -1, payload)
        return cls(payload, seqnum, -1, ck)
    
    @classmethod
    def make_ack(cls, acknum: int):
        """
        Construct an ACK packet.
        seqnum = 0, empty payload
        """
        ck = cls.compute_checksum(0, acknum, b"")
        return cls(b"", 0, acknum, ck)

    def __str__(self):
        kind = "ACK" if self.acknum >= 0 else "DATA"
        return f"<{kind} seq={self.seqnum} ack={self.acknum} len={len(self.data)} cksum=0x{self.checksum:04x}>"