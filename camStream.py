from maix import camera, mjpg, display, image
import socket, select
import _maix, time
from io import BytesIO
import argparse

from pythonosc import osc_message_builder
from pythonosc import udp_client
from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import asyncio

class Queue(object):
    def __init__(self, maxsize):
        self.__list = []
        self.maxs = maxsize

    def data(self):
        return self.__list

    def empty(self):
        return self.__list == []

    def size(self):
        return len(self.__list)

    def put(self, item):
        while len(self.__list) > 10:
            self.__list.pop(0) 
        self.__list.append(item)

    def get(self):
        if self.size():
            return self.__list.pop(0)
        return None

    def clear(self):
        self.__list = []

def setCamThresh(address, *args):
    print(f"{address}: {args}")

# Toggles tracking of the laser dot
def setLaserTracking(address, *args):
    laserTracking = args[0] 

    if args[0]:
        print("Starting laser point tracking")
    else: 
        print("Stopping laser point tracking")

server   = None
mjpgPort = 9999
frameRate = 30.0

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--ip", default="127.0.0.1", help="The ip of the OSC server")
parser.add_argument("--port", type=int, default=5005, help="The port the OSC server is listening on")
args = parser.parse_args()

# Start the OSC client
client = udp_client.SimpleUDPClient(args.ip, args.port)

# Start the OSC server
serverIP = "192.168.1.247"
serverPort = 5005
dispatcher = dispatcher.Dispatcher()
dispatcher.map("/augCanvas/setThresh", print)

# Start webcam server
queue  = Queue(maxsize=100)
server = mjpg.MjpgServerThread("0.0.0.0", mjpgPort, mjpg.BytesImageHandlerFactory(q=queue) ) 
server.start()

camID = 69
laser_threshold =  (64, 100, -128, 127, -128, 127) # threshold for bright spot
laserTracking = False

async def loop():
    
    # Main Loop
    while True:

        # Show camera image on LCD display
        img = camera.capture()

        if laserTracking:    
            ma = img.find_blobs([ laser_threshold  ]) #
            for i in ma:
                img.draw_rectangle(i["x"], i["y"], i["x"] + i["w"], i["y"] + i["h"], (255, 0, 0), 1)
                client.send_message("/augCanvas/trackDot", [ camID, i["x"], i["y"], i["w"], i["h"] ])

        # Show camera image on LCD display
        display.show(img)
   
        # Stream over network
        streamingImg = img
        jpg = _maix.rgb2jpg(
                    streamingImg.convert("RGB").tobytes(),
                    streamingImg.width,
                    streamingImg.height,
                )
    
        queue.put(mjpg.BytesImage(jpg))
        time.sleep( 1.0 / frameRate ) # need to delay for atleast 100ms otherwise there is too much lag in sending   
        await asyncio.sleep(1)

async def init_main():
    print("setting up server")
    server = AsyncIOOSCUDPServer((serverIP, serverPort), dispatcher, asyncio.get_event_loop())

    transport, protocol = await server.create_serve_endpoint()  # Create datagram endpoint and start serving

    await loop()  # Enter main loop of program
    print("closing server")
    transport.close()  # Clean up serve endpoint
 
asyncio.run(init_main()) 

