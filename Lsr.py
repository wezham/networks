#!/usr/bin/env/python3.6

import sys 
import socket as s
from socket import socket
import time
import threading
import pdb
import copy
import queue

UPDATE_ROUTING_INTERVAL = 30.0
LINK_STATE_INTERVAL = 1.0
LOCALHOST = "127.0.0.1"


######################################################
# Graph is our network 
######################################################

class Network:
    def __init__(self, root):
        self.routers = list()
        self.router_hash = {}

    def exists_in_network(self, identity):
        if self.router_hash.get(identity):
            return True
        else:
            return False
    
    def retrieve_router(self, identity):
        return self.router_hash.get(identity)

    def add_router(self, identity):
        switch = Switch(identity)
        self.router_hash[identity] = switch
        self.routers.append(switch)
        return switch
    
    def enable_switches_and_links(self, list_of_ids):
        for identifier in list_of_ids:
            if not self.router_hash.get(identifier).enabled:
                self.flip_switch_and_links(identifier, True)
        

    def disable_switches_and_links(self, list_of_ids):
        for identifier in list_of_ids:
            if self.router_hash.get(identifier).enabled:
                # print(f"I need to disable the following {identifier}")
                self.flip_switch_and_links(identifier, False)

    def flip_switch_and_links(self, identifier, boolean_val):
        for switch in self.routers: 
            if switch.identity == identifier:
                switch.toggle_status(boolean_val)
            else: 
                switch.toggle_link_if_exists(identifier, boolean_val)

    def print_network(self):
        for switch in self.routers:
            if switch.enabled:
                print(f"{switch.identity} connected to:")
                for link in switch.links:
                    if link.enabled:
                        print(f"Link {link.edge_id} & Cost: {link.cost}") 


######################################################
# Graph Consists of Switches 
######################################################

class Switch: 
    def __init__(self, identity):
        self.identity = identity
        self.previous = ""
        self.links = list()
        self.distance = 0
        self.enabled = True
        self.num_links = 0
        self.num_enabled_links = 0

    def toggle_status(self, status):
        # print(f"{self.identity} is {status}")
        self.enabled = status
    
    def toggle_link_if_exists(self, identifier, status):
        for link in self.links:
            if link.edge_id == identifier:
                # print(f"{self.identity} => {link.edge_id} = {status}")
                link.enabled = status
                if status == False: 
                    self.num_enabled_links -= 1
                else: 
                    self.num_enabled_links += 1

    def add_link(self, destination_id, cost):
        link = Link(edge_id=destination_id, cost=float(cost))
        self.links.append(link)
        self.num_links += 1
        self.num_enabled_links += 1

    def __lt__(self, other):
        return self.distance < other.distance
    
    def __gt__(self, other):
        return self.distance > other.distance

######################################################
# Switches consists of links 
######################################################
       
class Link: 
    def __init__(self, edge_id, cost):
        self.edge_id = edge_id
        self.cost = cost
        self.enabled = True
        
######################################################
# End Graph Classes
######################################################

class NRouter:
    def __init__(self, nrouter_id, port, cost, graph):
        self.id = nrouter_id
        self.port = int(port) 
        self.cost = cost
        self.enabled = True
        self.heartbeat_thread = threading.Timer(0.5, self.__check_heartbeats)
        self.expected_heartbeats = 0
        self.actual_heartbeats = 0
        self.graph = graph
    
    def __check_heartbeats(self):
        if self.enabled:
            self.expected_heartbeats += 1
            if (self.expected_heartbeats - self.actual_heartbeats) >= 6:
                # print(f"Failed heartbeat Test. Turning off {self.id}")
                self.graph.flip_switch_and_links(self.id, False)
                self.enabled = False
                self.expected_heartbeats = 0
                self.actual_heartbeats = 0
        
        if not self.enabled and (self.actual_heartbeats - self.expected_heartbeats >= 6): ## node has restarted
            # print(f"{self.id} has restarted")
            self.enabled = True
            self.actual_heartbeats = self.expected_heartbeats
            self.graph.flip_switch_and_links(self.id, True)

        self.heartbeat_thread.cancel()
        self.heartbeat_thread = threading.Timer(0.5, self.__check_heartbeats)
        self.heartbeat_thread.start()

class Router:
    def __init__(self, router_id, port, text_file):
        self.graph = Network(router_id)
        self.id = router_id
        self.port = int(port) 
        self.txt_file = text_file 
        self.neighbours = list()
        self.neighbour_hash = {}
        self.neighbour_count = 0
        self.neighbour_heartbeats = {}
        self.expected_heartbeats = {}
        self.begin_heartbeating = False
        self.udp_client = ""
        self.__initialise()
        self.lsp = ""
        self.sequence_num = 0
        self.broadcast_hash = {}
        self.listen_thread= threading.Thread(target=self.listen_for_broadcast)
        self.broadcast_thread = threading.Timer(LINK_STATE_INTERVAL, self.broadcast)
        self.routing_thread = threading.Timer(UPDATE_ROUTING_INTERVAL, self.routify)
        self.heartbeat_thread = threading.Timer(0.5, self.__send_heartbeat)
        self.lock = threading.Lock()

    ##############################################
    # Setup Methods  
    ##############################################

    def __initialise(self):
        root_switch = self.graph.add_router(self.id)
        f = open(self.txt_file, "r")
        count = 0
        for line in f:
            if count == 0:
                self.neighbour_count = line.rstrip()
                count+=1
            else:
                neighbour_id, cost, port = line.split(" ", 3)
                neighbour = NRouter(nrouter_id=neighbour_id, cost=cost, port=port, graph=self.graph)
                self.neighbours.append(neighbour)
                self.neighbour_hash[neighbour_id] = neighbour
                root_switch.add_link(destination_id=neighbour_id, cost=cost)

        self.__init_listener()

    def __init_listener(self):
        client = socket(s.AF_INET, s.SOCK_DGRAM)
        client.bind((LOCALHOST, self.port))
        self.udp_client = client 
    
    ##############################################
    # End Setup Methods  
    ##############################################

    ##########################################
    # Heartbeat related Functions 
    ##########################################

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
        

    ##########################################
    # End Hearbeat related functions 
    ##########################################
    
    def send_message(self, message, port):
        return self.udp_client.sendto(message ,(LOCALHOST, port))

    def broadcast(self):
        self.lock.acquire()
        packet = self.construct_packet()
        for n in self.neighbours:
            self.send_message(packet, n.port)
        self.lock.release()
        self.broadcast_thread.cancel()
        self.broadcast_thread = threading.Timer(LINK_STATE_INTERVAL, self.broadcast)
        self.broadcast_thread.start()
    
    def construct_packet(self):
        string = f"LSP\r\n{self.id}\r\nSEQ:{self.sequence_num}".encode() + self.__neig_string()
        self.sequence_num +=1
        return string
    
    def __neig_string(self):
        base_string = ""
        for n in self.neighbours:
            if n.enabled:
                base_string += f"\r\n{n.id} {n.cost}"
        
        self.lsp = base_string.encode()
        return self.lsp
        
    ########################################################
    # Start Listening Related functions
    ########################################################

    #### Listens for broadcasts
    def listen_for_broadcast(self):
        while True:
            packet = self.udp_client.recvfrom(1024)
            self.deconstruct_packet(packet)

    def find_set_difference(self, bigger_set, smaller_set):
        diff = set(bigger_set)-set(smaller_set)
        return list(diff)

    def should_create_links(self, router_id, ids_to_enable, neighb_array):
        if self.id in ids_to_enable:  ## If our Id is in the IDS to enable 
            for nei in neighb_array:
                identity, cost = nei.split(" ", 1)
                if identity == self.id:
                    router = self.graph.retrieve_router(router_id)
                    if not [l.edge_id for l in router.links if l.edge_id == identity]:
                        # print(f"Adding link from {router.identity} to {self.id}")
                        router.add_link(self.id, cost)

    def perform_network_check(self, neighb_array, identity):
        if not self.graph.exists_in_network(identity): 
            # print(f"{identity} does not exist. Creating with {neighb_array}")
            router = self.graph.add_router(identity)
            for neighbour in neighb_array: 
                neighbour_id, cost = neighbour.split(" ", 1)
                router.add_link(destination_id=neighbour_id, cost=cost)
            if self.neighbour_hash.get(identity, False): ## If we are looking at a neighbour then start the heartbeat check
                #print(f"Starting {identity} heartbeat thread")
                if not self.neighbour_hash.get(identity).heartbeat_thread.isAlive():
                    self.neighbour_hash.get(identity).heartbeat_thread.start()
        else:

            # Check for a given router, do the neighbours match up
            router_to_check = self.graph.retrieve_router(identity)
            packet_ids = [n.split(" ", 1)[0] for n in neighb_array]
            packet_length = len(packet_ids)
            if packet_length < router_to_check.num_enabled_links: # We know a packet has been removed   
                ids_to_disable = self.find_set_difference(bigger_set=[l.edge_id for l in router_to_check.links],smaller_set=packet_ids)
                self.graph.disable_switches_and_links(ids_to_disable)
            elif packet_length > router_to_check.num_enabled_links:
                ids_to_enable = self.find_set_difference(bigger_set=packet_ids, smaller_set=[l.edge_id for l in router_to_check.links if l.enabled])
                self.should_create_links(router_to_check.identity, ids_to_enable, neighb_array)
                self.graph.enable_switches_and_links(ids_to_enable)

    def handle_lsp_packet(self, packet):
        deconstructed = packet[0].decode().split("\r\n")
        packet_id = deconstructed[1]
        sequence_num = deconstructed[2].split(":")[1]
        if self.__should_broadcast(packet_id, int(sequence_num)): ## This is a new packet
            self.perform_network_check(packet[0].decode().split("\r\n")[3:], packet_id)
            self.__broadcast_on_behalf(packet=packet[0], excepted_id=packet_id)


    #### Takes in broadcasts and hands them to processors
    def deconstruct_packet(self, packet):
        deconstructed = packet[0].decode().split("\r\n")
        # print(f"{self.id} ==> {deconstructed}")
        if deconstructed[0] == "LSP":
            self.handle_lsp_packet(packet)    
        else:
            identity, heartbeat_id = deconstructed[0].split(" ")
            self.neighbour_hash.get(heartbeat_id).actual_heartbeats += 1

    ### Checks via sequence numbers if we should pass on a pakcet or if its been transmitted before 
    def __should_broadcast(self, lsp_id, seq_num):
        if lsp_id in self.broadcast_hash: ### Already seen before 
            if seq_num > self.broadcast_hash.get(lsp_id): ### This is a not propogated 
                self.broadcast_hash[lsp_id] = seq_num
                return True
            elif seq_num == 0 and self.broadcast_hash.get(lsp_id) > len(self.graph.routers):
                self.broadcast_hash[lsp_id] = 0
                return True
            else:
                return False
        else: ### Never seen before ( Base case )
            self.broadcast_hash[lsp_id] = seq_num
            return True

    def __packet_from_this_node(self, lsp_id, neighbour_id):
        return lsp_id == neighbour_id

    ### Broadcasts a LSP on behalf of another node 
    def __broadcast_on_behalf(self, packet, excepted_id):
        for n in self.neighbours:
            if self.__packet_from_this_node(excepted_id, n.id) or not n.enabled:
                continue
            else:
                self.lock.acquire()
                self.send_message(packet, n.port)
                self.lock.release()

    ########################################################
    # End Listening Related functions
    ########################################################

    ########################################################
    # Start Routing Thread related functions 
    ########################################################
    
    def print_route(self, path_list):
        print(f"I am router {self.id}")
        for switch in path_list.values():
            if switch.identity != self.id and switch.enabled:
                route = self.__recurse_route("", switch)
                print(f"Least cost path to router {switch.identity}:{route} and the cost: {switch.distance}")

    def __fetch_queue(self):
        router_queue = list()
        for router in copy.copy(self.graph.routers):
            if router.enabled:
                if router.identity != self.id:
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
            visited[current.identity] = True
            for link in self.__get_active_links(current):
                if link.edge_id not in visited:
                    destination = self.graph.router_hash.get(link.edge_id)
                    cost = current.distance + link.cost
                    if cost < destination.distance:
                        destination.distance = cost
                        destination.previous = current
                

        self.print_route(self.graph.router_hash)
        self.lock.release()

    def routify(self):
        self.__djikstra_algo()
        self.routing_thread.cancel()
        self.routing_thread = threading.Timer(25.0, self.routify)
        self.routing_thread.start()
    
    ########################################################
    # These are all functions relating to routing 
    ########################################################
    def start_neighbour_threads(self):
        for neighbour in self.neighbours:
            if not neighbour.heartbeat_thread.isAlive():
                neighbour.heartbeat_thread.start()

    def run(self):
        try: 
            self.listen_thread.start()
            self.broadcast_thread.start()
            self.routing_thread.start()
            self.heartbeat_thread.start()
            threading.Timer(float(self.neighbour_count)+1.0, self.start_neighbour_threads).start()

        except Exception as e:
            print("Unable to start threads" + str(e))
        except KeyboardInterrupt:
            exit()

if len(sys.argv) != 4:
    print("Usage: python3 Lsr.py ID PORT TXT")
    exit() 
else:
    router_id = sys.argv[1]
    port = sys.argv[2]
    text_file = sys.argv[3]
    Router(router_id=router_id, port=port, text_file=text_file).run()
