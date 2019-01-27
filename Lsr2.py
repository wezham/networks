#!/usr/bin/env/python3.6

import sys 
import socket as s
from socket import socket
import time
import threading

LOCALHOST = "127.0.0.1"

class Graph:
    def __init__(self):
        self.light_routers = list()

class NRouter:
    def __init__(self, id, port, cost):
        self.id = id
        self.port = int(port) 
        self.cost = float(cost) 
        self.neighbours = []

class Router:
    def __init__(self, id, port, text_file):
        self.graph = Graph()
        self.id = id
        self.port = int(port) 
        self.txt_file = text_file 
        self.neighbours = list()
        self.neighbour_count = 0
        self.__init_neighbours()
        self.udp_client = ""
        self.__init__client()
        self.sender = ""
        self.lsp = ""
        self.sequence_num = 0
       
    
    def __init_neighbours(self):
        f = open(self.txt_file, "r")
        count = 0
        for line in f:
            if count == 0:
                self.neighbour_count = line.rstrip()
                count+=1
            else:
                n = line.split(" ")
                neighbour = NRouter(id=n[0], cost=n[1], port=n[2])
                self.neighbours.append(neighbour)
    
    def __init__client(self):
        client = socket(s.AF_INET, s.SOCK_DGRAM)
        client.bind((LOCALHOST, self.port))
        self.udp_client = client 

    def send_message(self, message, port):
        return self.udp_client.sendto(message ,(LOCALHOST, port))
    
    def debug_packet(self):
        base_string = self.id
        for n in self.neighbours:
            base_string += f"\r\n{id} Cost:{cost}\r\n"

    def __neig_string(self):
        base_string = ""
        for n in self.neighbours:
            base_string += f"\r\nID:{n.id} Cost:{n.cost}"
        
        print(base_string)
        self.lsp = base_string.encode()
        return self.lsp

    def construct_packet(self):
        if self.lsp == "":
            string = f"{self.id}\r\nSEQ:{self.sequence_num}".encode() + self.__neig_string()
        else:    
            string = f"{self.id}\r\nSEQ:{self.sequence_num}".encode() + self.lsp
           
        self.sequence_num +=1
        return string
        
    def broadcast(self):
        packet = self.construct_packet()
        for n in self.neighbours:
            self.send_message(packet, n.port)
            time.sleep(0.1)
        self.broadcast()
        
    def deconstruct_packet(self, packet):
        deconstructed = packet[0].decode().split("\r\n")
        print(f"I am {self.id} packet is {deconstructed}")

    def listen_for_broadcast(self):
        time.sleep(0.1)
        packet = self.udp_client.recvfrom(1024)
        self.deconstruct_packet(packet)
        self.listen_for_broadcast()

    def routify(self):
        return "ROUTES"


router_f = Router(text_file="configFf.txt", id="F", port="5005")
try: 
    threading.Thread(target=router_f.listen_for_broadcast).start()    
    threading.Thread(target=router_f.broadcast).start()
except:
    print("Unable to start threads")
