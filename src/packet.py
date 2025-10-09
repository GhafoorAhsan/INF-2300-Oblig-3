class Packet:
    """Represent a packet of data.
    Note - DO NOT REMOVE or CHANGE the data attribute!
    The simulation assumes this is present!"""

    def __init__(self, binary_data, seqnum, acknum, checksum):
        self.data = binary_data
        self.seqnum = seqnum # Sequence number
        self.acknum = acknum # Acknowledgement number
        self.checksum = checksum # Error detection 

    def __str__(self):
        return f"Packet(Sequence num={self.seqnum}, Acknowledgement num={self.acknum}, Error-Detection num ={self.checksum}, Binary Data={self.data})"
