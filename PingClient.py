#!/usr/bin/python2.7

# Use the flag -n to run Q1 and use the flag -s to run Q2

import sys 
import socket as s
from socket import socket
import time

def initiate_ping(host, port):
    #print("Attempting to initiate connection to host {} at port {}...".format(host, port))
    message = "Hello world"
    client = socket(s.AF_INET, s.SOCK_DGRAM)
    client.settimeout(1)
    client.bind(("127.0.0.1", 9091))
    count = 1 
    timeout = False
    while count <= 10:
        client.sendto(message ,(host, port))
        try:
            start = time.time()
            ret_message = client.recvfrom(1024)
        except:
            print("ping to {} seq = {} time out \r".format(host, count))
            count += 1 
            continue 

        end = time.time()
        calculated_time = int((end - start)*1000) 
        print("ping to {} seq = {} rtt = {} ms \r".format(host, count, calculated_time))
        count +=1


def initiate_smarter_ping(host, port):
    #print("Attempting to initiate connection to host {} at port {}...".format(host, port))
    message = "Hello world"
    client = socket(s.AF_INET, s.SOCK_DGRAM)
    client.settimeout(1)
    client.bind(("127.0.0.1", 9091))
    # Set neccesary variables 
    count = 1 
    average = 0
    retransmitions = 0
    timeout = False
    minimum = 10000
    maximum = 0

    while count <= 10:
        client.sendto(message ,(host, port))
        try:
            start = time.time()
            ret_message = client.recvfrom(1024)
        except:
            print("ping to {} seq = {} time out, retransmitting \r".format(host, count))
            timeout = True
            retransmitions += 1
            continue 
            
        end = time.time()
        calculated_time = int((end - start)*1000) 
        if calculated_time > maximum: 
            maximum = calculated_time
        if calculated_time < minimum:
            minimum = calculated_time

        average += calculated_time
        if not timeout: 
            print("ping to {} seq = {} rtt = {} ms \r".format(host, count, calculated_time))
        else: 
            print("ping to {} seq = {} (RXT) rtt = {} ms \r".format(host, count, calculated_time))
        timeout = False
        count +=1

    print("\nStatistics:")
    print("{}".format("-"*len("Statistics:")))
    print("Minimum RTT = {}".format(minimum))
    print("Maximum RTT = {}".format(maximum))
    print("# Retransmissions = {}".format(retransmitions))

def init_ping():
    if len(sys.argv) != 4:
        print("Usage: python PingClient.py host port flag (-n for 1st question, -s for 2nd) ")
        exit()
    else: 
        host = sys.argv[1]
        port = int(sys.argv[2]) ## Must be an integer as per the python docs
        flag = sys.argv[3]
        flag = initiate_smarter_ping(host=host, port=port) if flag == "-s" else initiate_ping(host=host, port=port)



init_ping()

