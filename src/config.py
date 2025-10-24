"""Main config file used to control key aspects of a particular simulation run.
"""
# Tips: Make it work for one thing at a time:
# - Start with dropped packets only
# - Then corrupted packets only
# - Then delayed packets only

# Keep the number of packets low in the beginning

# Number of packets per simulation --> Packets sent from Alice to Bob
PACKET_NUM = 10

# The size of each packet in bytes.
# The data in each packet will be uppercase ASCII letters only!
# Each packet contains 4 bytes (characters). F.eks. "ABCD"
PACKET_SIZE = 4

# PACKET_NUM * PACKET_SIZE = Total number of bytes sent ( 10 * 4 = 40 bytes)

# The seed ensures a new run is identical to the last
RANDOM_SEED = 84737869  # I love you! :)
# If you don't want an identical run, set this to True
RANDOM_RUN = False

# The chance that each packet is dropped
DROP_CHANCE = 0.0

# The chance that the data in a packet is changed
CORRUPT_CHANCE = 0.0

# The chance that the packet is delayed
DELAY_CHANCE = 0.0

# Delay in seconds
DELAY_AMOUNT = 0.5
