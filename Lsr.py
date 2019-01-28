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
    def __init__(self, root, lock):
        self.root_id = root
        self.routers = list()
        self.router_hash = {}
        self.root_node = ""
        self.lock = lock

    def add_switch_by_packets(self, packet_array, identity, broadcast_hash):
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
            packet_length = len(packet_array)
            enabled_switches = [l.edge_id for l in self.router_hash.get(identity).links if l.enabled]
            num_enabled_switches = len(enabled_switches)
            num_links = len(self.router_hash.get(identity).links)
            if packet_length < num_links: ## Then a link is offline 
                self.__find_broken_ids(identity, packet_array, broadcast_hash)
            elif packet_length > num_enabled_switches:
                print("A node has come back online")
                self.enable_deactived_links(packet_array, enabled_switches, broadcast_hash)

    def enable_deactived_links(self, packet_array, enabled_switches, broadcast_hash):
        packet_ids = [item.split(" ", 1)[0] for item in packet_array]
        to_be_enabled = list(set(packet_ids) - set(enabled_switches))
        for identifier in to_be_enabled:
            print(f"Active Flipping for {identifier}")
            self.flip_links_and_switch(identifier, True)
            for k in broadcast_hash.keys():
                if k != identifier:
                    broadcast_hash[k] += 3
        return True

    def __find_broken_ids(self, identity, packet_array, broadcast_hash):
        packet_ids = [item.split(" ", 1)[0] for item in packet_array]
        link_ids = [link.edge_id for link in self.router_hash.get(identity).links]
        to_be_disabled = list(set(link_ids)-set(packet_ids))
        print(f"ID: {identity}")
        print(f"PIDS: {packet_ids}")
        print(f"LIDS: {link_ids}")
        for identifier in to_be_disabled:
            if self.router_hash.get(identifier).enabled:
                print(f"I need to disable the following {to_be_disabled}")
                broadcast_hash.pop(identifier) ## Remove sequence number as if it never existed
                for k in broadcast_hash.keys():
                    broadcast_hash[k] += 3
                self.flip_links_and_switch(identifier, False)

    def flip_links_and_switch(self, id_to_flip, switch_value):
        for switch in self.routers:
            if switch.identity == id_to_flip:
                print(f"Flipping Switch {switch.identity} to {switch_value}")
                switch.enabled = switch_value
            else:
                for link in switch.links:
                    if link.edge_id == id_to_flip:
                        print(f"Flipping link from {switch.identity} to {link.edge_id} to {switch_value}")
                        link.enabled = switch_value
        return True

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
        self.enabled = True

class Switch: 
    def __init__(self, identity):
        self.identity = identity
        self.previous = ""
        self.links = list()
        self.distance = 0
        self.enabled = True

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
        self.enabled = True

class Router:
    def __init__(self, router_id, port, text_file):
        self.lock = threading.Lock()
        self.graph = Network(router_id, self.lock)
        self.id = router_id
        self.port = int(port) 
        self.txt_file = text_file 
        self.neighbours = list()
        self.neighbour_count = 0
        self.heatbeat_count = 0
        self.neighbour_heartbeats = {}
        self.expected_heartbeats = {}
        self.begin_heartbeating = False
        self.udp_client = ""
        self.__init_neighbours()
        self.__init__client()
        self.lsp = ""
        self.sequence_num = 0
        self.broadcast_hash = {}
        self.listen_thread= threading.Thread(target=self.listen_for_broadcast)
        self.broadcast_thread = threading.Timer(1.0, self.broadcast)
        self.routing_thread = threading.Timer(10.0, self.routify)
        self.heartbeat_thread = threading.Timer(0.5, self.__send_heartbeat)
        self.expected_beats_thread = threading.Timer(0.5, self.__check_heartbeats)
        self.broadcast_behalf = None
       

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
                self.expected_heartbeats[n[0]] = 0
                
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
            if n.enabled:
                base_string += f"\r\n{n.id} {n.cost}"
        
        self.lsp = base_string.encode()
        return self.lsp

    def construct_packet(self):
        string = f"LSP\r\n{self.id}\r\nSEQ:{self.sequence_num}".encode() + self.__neig_string()
        self.sequence_num +=1
        return string
    
    def __construct_heartbeat(self):
        return f"HEARTBEAT {self.id}".encode()

    def __send_heartbeat(self):
        heartbeat = self.__construct_heartbeat()
        self.lock.acquire()
        for n in self.neighbours:
            self.send_message(heartbeat, n.port)
        
        self.lock.release()
        self.heartbeat_thread.cancel()
        self.heartbeat_thread = threading.Timer(0.5, self.__send_heartbeat)
        self.heartbeat_thread.start()

    
    def __check_heartbeats(self):
        #if debug:
        print("Expected")
        print(self.expected_heartbeats)
        print("Actual")
        print(self.neighbour_heartbeats)
        print("______________________")
        for n in self.neighbours:
            if n.enabled:
                self.expected_heartbeats[n.id] += 1
            if (self.expected_heartbeats[n.id] - self.neighbour_heartbeats[n.id]) >= 4 and n.enabled: ## Failed node 
                print(f"Failed node {n.id} HAH")
                self.graph.flip_links_and_switch(n.id, False)
                n.enabled = False
                self.expected_heartbeats[n.id] = self.neighbour_heartbeats[n.id]
            if self.neighbour_heartbeats[n.id] - self.expected_heartbeats[n.id] >= 4: ## Node has come back online
                print(f"Neighbour {n.id} back online")
                self.graph.flip_links_and_switch(n.id, True)
                n.enabled = True
                self.expected_heartbeats[n.id] = self.neighbour_heartbeats[n.id]
                
        self.expected_beats_thread.cancel()
        self.expected_beats_thread = threading.Timer(0.5, self.__check_heartbeats)
        self.expected_beats_thread.start()

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
            if debug:
                print(deconstructed)
            packet_id = deconstructed[1]
            try:
                sequence_num = deconstructed[2].split(":")[1]
            except Exception as e:
                print("Invalid format for sequence #")
                exit()

            self.graph.add_switch_by_packets(packet[0].decode().split("\r\n")[3:], packet_id, self.broadcast_hash)
            if self.__should_broadcast(packet_id, sequence_num):
                self.broadcast_behalf = threading.Timer(1.0, self.__broadcast_on_behalf,(packet[0], packet))
                self.broadcast_behalf.start()
                if debug:
                    print(f"Broadcasting on behalf of {packet_id}")
        else:
            if not self.begin_heartbeating and all(item == 0 for item in self.neighbour_heartbeats.values()):
                self.begin_heartbeating = True
                self.expected_beats_thread.start()
            heartbeat = deconstructed[0].split(" ")
            if debug:
                print(heartbeat)
            self.neighbour_heartbeats[heartbeat[1]] += 1

    def __should_broadcast(self, router_id, seq_num):
        seq_num = int(seq_num)
        print(self.broadcast_hash)
        if router_id in self.broadcast_hash:
            if seq_num > self.broadcast_hash.get(router_id): ## Seq Number and 5 and record is 4. This is a new packet 
                #print(f"{self.id} Broadcasting on behalf of {router_id} sn: {seq_num}")
                self.broadcast_hash[router_id] = seq_num
                return True
            else:
                #print("Not new")
                return False
        else:
            ## This is a never seen before packet its probably just been added or going to be. Rebroadcast 
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
            if router.enabled:
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
            if switch.identity != self.id and switch.enabled:
                route = self.__recurse_route("", switch)
                print(f"Least cost path to router {switch.identity}:{route} and the cost: {switch.distance}")
    
    def __get_active_links(self, current_node):
        active_links = []
        for link in current_node.links:
            if link.enabled:
                active_links.append(link)
        return active_links

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
            for link in self.__get_active_links(current):
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
            self.heartbeat_thread.start()
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
