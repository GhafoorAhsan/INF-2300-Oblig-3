# Reliable Transport Protocol — INF-2300 Oblig 3
This project implements a reliable transport layer protocol in Python based on the Go-Back-N (GBN) algorithm

# Prerequisites
Python 3.8+

# Layout
- Doc/
    - Report 
- src/
    - config.py --> test with different config 
    - osi.py
    - packet.py
    - README.md
    - result.txt --> results from test 
    - simulation.py
    - utils.py 
    - layers/
        - application.py
        - network.py
        - transport.py 
        - __init__.py 

# Quick start (run from the correct folders)
From /src: 
    run: 
        python3 simulation.py