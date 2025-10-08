#!/usr/bin/env python3

from logging import basicConfig
from logging import DEBUG as LOGGER_DEBUG
from random import seed
from sys import exit
from signal import signal, SIGINT

from config import PACKET_NUM, PACKET_SIZE, RANDOM_SEED, RANDOM_RUN
from osi import OSIStack

"""
Written by: Raymon Skjørten Hansen
Email: raymon.s.hansen@uit.no
Course: INF-2300 - Networking
UiT - The Arctic University of Norway
May 9th, 2019
"""

# Format the logger to look nice and include the name of the OSI stack
f_str = "[%(name)6s - %(levelname)8s] %(filename)12s:%(lineno)3d - %(message)s"
basicConfig(level=LOGGER_DEBUG, format=f_str)


def sigint_handler(signum, frame):
    # Try to exit nicely in case of SIGINT.
    print("Simulation interrupted. Exiting...\n")
    exit()


class Sim:
    def __init__(self):
        # Make both of our OSI stacks and connect them
        self.alice = OSIStack("Alice", PACKET_NUM, PACKET_SIZE)
        self.bob = OSIStack("Bob", 0, 0)

        self.alice.connect(self.bob)
        self.bob.connect(self.alice)

    def should_continue(self):
        # We continue so long as the data isn't received
        return self.bob.received != self.alice.original_data

    def run(self):
        # This is the main program loop
        while self.should_continue():
            self.alice.tick()
            # Traps 'Ctrl-C' and try to exit nicely.
            signal(SIGINT, sigint_handler)


if __name__ == "__main__":
    if not RANDOM_RUN:
        seed(RANDOM_SEED)
    sim = Sim()
    sim.run()
    print("Finished!")
