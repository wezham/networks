#!/usr/bin/env/python3.6

import sys 
import socket as s
from socket import socket
import time
import threading
import pdb
import copy
import queue

UPDATE_ROUTING_INTERVAL = 30
LINK_STATE_INTERVAL = 1
debug = 0
LOCALHOST = "127.0.0.1"

class Network:
    def __init__(self, root):
        self.root_id = root
        self.routers = list()
        self.router_hash = {}
        self.root_node = ""

    def add_switch_by_packets(self, packet_array, identity):
        if identity not in self.router_hash:
            switch = Switch(identity)
            for n in packet_array:
                neighbour_id, cost = n.split(" ", 1)
                link_id = neighbour_id
                switch_link = Link(link_id, float(cost))
                switch.add_link(switch_link)
            self.routers.append(switch) 
            self.router_hash[identity] = switch
        else:
            if debug:
                print("Already Exists")
        #self.print_network()

    def add_root_router(self, neighbours, root):
        switch = Switch(root.id)
        self.router_hash[root.id] = switch
        for nei in neighbours:
            link_id = nei.id
            switch_link = Link(link_id, float(nei.cost))
            switch.add_link(switch_link)
        self.routers.append(switch)
        self.root_node = switch

    def print_network(self):
        for switch in self.routers:
            print(f"{switch.identity} connected to:")
            for link in switch.links:
                print(f"Link {link.edge_id} & Cost: {link.cost}") 
            
class Link: 
    def __init__(self, edge_id, cost):
        self.edge_id = edge_id
        self.cost = cost

class Switch: 
    def __init__(self, identity):
        self.identity = identity
        self.previous = ""
        self.links = list()
        self.distance = 0

    def add_link(self, switch_link):
        if type(switch_link) == Link:
            self.links.append(switch_link)
        else:
            raise TypeError("Incorrect type for neighbour")

    def __lt__(self, other):
        return self.distance < other.distance
    
    def __gt__(self, other):
        return self.distance > other.distance

class NRouter:
    def __init__(self, nrouter_id, port, cost):
        self.id = nrouter_id
        self.port = int(port) 
        self.cost = cost

class Router:
    def __init__(self, router_id, port, text_file):
        self.graph = Network(router_id)
        self.id = router_id
        self.port = int(port) 
        self.txt_file = text_file 
        self.neighbours = list()
        self.neighbour_count = 0
        self.heatbeat_count = 0
        self.neighbour_heartbeats = {}
        self.udp_client = ""
        self.__init_neighbours()
        self.__init__client()
        self.lsp = ""
        self.sequence_num = 0
        self.broadcast_hash = {}
        self.listen_thread= threading.Thread(target=self.listen_for_broadcast)
        self.broadcast_thread = threading.Timer(1.0, self.broadcast)
        self.routing_thread = threading.Timer(10.0, self.routify)
        self.broadcast_behalf = None
        self.lock = threading.Lock()

    def __init_neighbours(self):
        f = open(self.txt_file, "r")
        count = 0
        for line in f:
            if count == 0:
                self.neighbour_count = line.rstrip()
                count+=1
            else:
                n = line.split(" ")
                neighbour = NRouter(nrouter_id=n[0], cost=n[1], port=n[2])
                self.neighbours.append(neighbour)
                self.neighbour_heartbeats[n[0]] = 0
                
        self.graph.add_root_router(self.neighbours, self)

    def __init__client(self):
        client = socket(s.AF_INET, s.SOCK_DGRAM)
        client.bind((LOCALHOST, self.port))
        self.udp_client = client 

    def send_message(self, message, port):
        return self.udp_client.sendto(message ,(LOCALHOST, port))
    
    def debug_packet(self):
        base_string = self.id
        for n in self.neighbours:
            base_string += f"\r\n{n.id} {cost}\r\n"

    def __neig_string(self):
        base_string = ""
        for n in self.neighbours:
            base_string += f"\r\n{n.id} {n.cost}"
        
        self.lsp = base_string.encode()
        return self.lsp

    def construct_packet(self):
        if self.lsp == "":
            string = f"LSP\r\n{self.id}\r\nSEQ:{self.sequence_num}".encode() + self.__neig_string()
        else:    
            string = f"LSP\r\n{self.id}\r\nSEQ:{self.sequence_num}".encode() + self.lsp
           
        self.sequence_num +=1
        return string
    
    def construct_heartbeat(self):
        return True


    def broadcast(self):
        if debug:
            print("Broadcasting NOW BITCH")
        self.lock.acquire()
        packet = self.construct_packet()
        for n in self.neighbours:
            self.send_message(packet, n.port)
        self.lock.release()
        self.broadcast_thread.cancel()
        self.broadcast_thread = threading.Timer(1.0, self.broadcast)
        self.broadcast_thread.start()
    
    def __broadcast_on_behalf(self, packet, excepted):
        for n in self.neighbours:
            if n.id == excepted:
                continue
            else:
                self.lock.acquire()
                self.send_message(packet, n.port)
                self.lock.release()
                self.broadcast_behalf.cancel()
                
    
    def deconstruct_packet(self, packet):

        deconstructed = packet[0].decode().split("\r\n")
        if deconstructed[0] == "LSP":
            print(deconstructed)
            packet_id = deconstructed[1]
            try:
                sequence_num = deconstructed[2].split(":")[1]
            except Exception as e:
                print("Invalid format for sequence #")
                exit()

            self.graph.add_switch_by_packets(packet[0].decode().split("\r\n")[3:], packet_id)
            if self.__should_broadcast(packet_id, sequence_num):
                self.broadcast_behalf = threading.Timer(1.0, self.__broadcast_on_behalf,(packet[0], packet))
                self.broadcast_behalf.start()
                if debug:
                    print(f"Broadcasting on behalf of {packet_id}")

    def __should_broadcast(self, router_id, seq_num):
        if router_id in self.broadcast_hash:
            if seq_num > self.broadcast_hash.get(router_id):
                if debug:
                    print(f"{self.id} Broadcasting on behalf of {router_id} sn: {seq_num}")
                self.broadcast_hash[router_id] = seq_num
                return True
            else:
                if debug:
                    print(f"BH: {router_id}, snum: {seq_num}")
                return False
        else:
            self.broadcast_hash[router_id] = seq_num
            return True

    def listen_for_broadcast(self):
        while True: 
            if debug:
                print("Listening for BCast")
            packet = self.udp_client.recvfrom(1024)
            self.deconstruct_packet(packet)

    def __fetch_queue(self):
        router_queue = list()
        for router in copy.copy(self.graph.routers):
            if router.identity != self.graph.root_node.identity:
                router.distance = 10000
                router.previous = ""
            router_queue.append(router)
        return router_queue

    def __recurse_route(self, path, node):
        if type(node) == str:
            return path
        else: 
            path = node.identity + path
        return self.__recurse_route(path, node.previous)

    def print_route(self, path_list):
        print(f"I am router {self.id}")
        for switch in path_list.values():
            if switch.identity != self.id:
                route = self.__recurse_route("", switch)
                print(f"Least cost path to router {switch.identity}:{route} and the cost: {switch.distance}")
                
    def __djikstra_algo(self):
        self.lock.acquire()
        unvisited_nodes = self.__fetch_queue()
        visited = {}
        while unvisited_nodes:
            unvisited_nodes.sort()
            current = unvisited_nodes[0]
            unvisited_nodes = unvisited_nodes[1:]
            if debug:
                print(f"Visited {visited.keys()}")
                print(f"Looking at {current.identity} cost is {current.distance}")
            visited[current.identity] = True
            for link in current.links:
                if debug:
                    print(f"Looking at edge {current.identity}->{link.edge_id}")
                if link.edge_id not in visited:
                    destination = self.graph.router_hash.get(link.edge_id)
                    cost = current.distance + link.cost
                    if debug:
                        print(f"{link.edge_id} existing cost {destination.distance}")
                        print(f"New cost {cost}")
                    if cost < destination.distance:
                        destination.distance = cost
                        if debug:
                            print(f"{link.edge_id} new cost: {cost}")
                        destination.previous = current

        self.print_route(self.graph.router_hash)
        self.lock.release()

    def __print_djikstra(self):
        print("Djikstra")
        self.routing_thread.cancel()
        self.routing_thread = threading.Timer(20.0, self.routify)
        self.routing_thread.start()

    def routify(self):
        self.__djikstra_algo()
        timer2 = threading.Timer(10.0, self.__print_djikstra) 
        timer2.start()

    def run(self):
        try: 
            self.listen_thread.start()
            self.broadcast_thread.start()
            self.routing_thread.start()
        except Exception as e:
            print("Unable to start threads" + str(e))
        except KeyboardInterrupt:
            exit()

if len(sys.argv) != 5:
    print("Usage: python3 Lsr.py ID PORT TXT DEBUG")
    exit() 
else:
    router_id = sys.argv[1]
    port = sys.argv[2]
    text_file = sys.argv[3]
    debug = True if sys.argv[4] == "1" else False
    Router(router_id=router_id, port=port, text_file=text_file).run()
