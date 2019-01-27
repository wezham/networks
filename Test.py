from Lsr import Router
from Lsr import *
import tempfile
import subprocess
import threading

def test_router(router, router_id, port, cost):
    if router.id != router_id:
        print(f"Something Wrong with ID's in {router_id}")
        exit()
    if router.port != port and type(router.port) != int: 
        print(f"Error creating port numbers with correct types for {router_id}")
        exit()
    if router.cost != cost or type(router.cost) != float:
        print(f"Error creating cost with correct cost for {router_id}")
        exit()
    
    print(f"Succesfuly created router {router_id}")
    return True


def test_router_packet_construction(router, expected_string):
    print("Testing Router packet construction for broadcast")
    try: 
        packet = router.construct_packet()
        if packet == expected_string:
            print("Router packet construction is succesful")
        else: 
            print("Unable to construct packet succefully please revise")
    except Exception as e:
        print("Error in code for method for creating packet")
        exit()

def test_router_and_neighbour_creation(txt_file, id, port):
    print(f"Testing creation with {txt_file}, {id}, {port}")
    router = Router(text_file=txt_file, id=id, port=port)
    if len(router.neighbours) == int(router.neighbour_count):
        router_b = router.neighbours[0]
        router_f = router.neighbours[1]
        test_router(router_b, "B", 5001, float(6.5))
        test_router(router_f, "F", 5005, float(2.2))    
    test_router_packet_construction(router, "A\r\nID:B Cost:6.5\r\nID:F Cost:2.2")    
    if router.send_message(b"A\r\nID:B Cost:6.5\r\nID:F Cost:2.2", 5001) == 36: 
        print("Succesfully sending UDP packet")

#test_router_and_neighbour_creation("configA.txt", "A", "5000")

print("Testing Network creation")
network = Network("A")
network.add_switch_by_packets(['B 6.5', 'F 2.2'], "A") 
network.add_switch_by_packets(['A 6.5', 'F 2.2'], "B") 
network.add_switch_by_packets(['A 2.2', 'B 3.0'], "F") 
network.print_network()


router_a = Router(text_file='configA.txt', router_id="A", port="5000")
router_b = Router(text_file='configBb.txt', router_id="B", port="5001")
router_f = Router(text_file='configFf.txt', router_id="F", port="5005")
try: 
    threading.Thread(target=router_b.listen_for_broadcast).start()
    threading.Thread(target=router_f.listen_for_broadcast).start()
    threading.Thread(target=router_a.listen_for_broadcast).start()    
    threading.Thread(target=router_a.broadcast).start()
    threading.Thread(target=router_b.broadcast).start()
    threading.Thread(target=router_f.broadcast).start()
except Exception as e:
    print("Unable to start threads")
except KeyboardInterrupt:
    exit()


