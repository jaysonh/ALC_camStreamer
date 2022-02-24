# Add the following line to the end of /etc/init.d/rc.final
# python3 /home/projects/camStream.py --boot 1 &

from maix import camera, mjpg, display, image
import socket, select
import _maix, time
from io import BytesIO
import argparse
import uuid
from pathlib import Path
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

# Load the arguments
parser = argparse.ArgumentParser()
parser.add_argument("--boot", type=int, default=0, help="Is this script being launched at bootup")
parser.add_argument("--serverIP", default="192.168.1.198", help="The ip for the ALC host")
parser.add_argument("--serverPort", type=int, default=666, help="The port for the ALC host")
parser.add_argument("--clientPort", default=667, type=int, help="The port for this client OSC")
parser.add_argument("--clientIP",   default="192.168.1.247", help="The IP for this device")
parser.add_argument("--stream", type=int, default=1, help="Toggle video stream")
args = parser.parse_args()

# First check if script is being launched from boot
# if it is then wait for 10 seconds before running
# to give time for network adapter to connect to wifi
if args.boot == 1:
    print("Launched from boot")
    time.sleep(10.0)

# Create unique ID for this camera
fileContents = Path('/home/projects/UNIQUE_ID').read_text()                     
fileContents = fileContents.replace('\n','') 
fileContents = fileContents.replace(' ','')
camID = fileContents                    
print("CameraID: ", camID)

# Toggles tracking of the laser dot
laserTracking = 0
def setLaserTrack(address, *args):
    global laserTracking
    laserTracking = args[0] 
    if args[0] == 1:
        print("Starting laser point tracking")
    else: 
        print("Stopping laser point tracking")

# Set the threshold values for point tracking
trackUpThresh  = 100
trackLowThresh = 70
def setLaserThresh(address, *args):
    global trackUpThresh;
    global trackLowThresh;
    if args[0] < args[1]: 
        trackLowThresh = args[0]
        trackUpThresh  = args[1]
        print("set track thresholds", trackLowThresh, " ", trackUpThresh)
    else:
        print("ERROR! lower thresh above upper thresh")

server    = None
mjpgPort  = 9999
frameRate = 30.0

# Start the OSC client
# for sending data to main control application
client = udp_client.SimpleUDPClient(args.serverIP, args.serverPort) # "192.168.1.198", 666)
oscSleep = 0.01 # seconds

# Start the OSC server
# for receiving commands from main control application
#serverIP = "192.168.1.247"
serverIP   = args.clientIP   #"192.168.1.247" 
serverPort = args.clientPort #667

dispatcher = dispatcher.Dispatcher()
dispatcher.map("/augCanvas/setThresh", setLaserThresh)
dispatcher.map("/augCanvas/setTrack",  setLaserTrack)

# Start webcam server
streamEnabled = args.stream
if streamEnabled == 1:
    queue  = Queue(maxsize=100)
    server = mjpg.MjpgServerThread("0.0.0.0", mjpgPort, mjpg.BytesImageHandlerFactory(q=queue) ) 
    server.start()

laser_threshold = ( 14, 36, -71, 81, 73, 41 )
#laser_threshold =  (64, 100, -128, 127, -128, 127) # threshold for bright spot
#laser_threshold = (28,-36,-14,68,-5,15) # threshold for green 

async def loop():
   
    start = time.time()
 
    # Main Loop
    while True:
        # Show camera image on LCD display
        img = camera.capture()

        if laserTracking == 1:    
            ma = img.find_blobs([ laser_threshold  ]) #
            if len(ma) > 0:
            #for i in ma:
                i = ma[0] # get the first (hopefuly largest) blob
                img.draw_rectangle(i["x"], i["y"], i["x"] + i["w"], i["y"] + i["h"], (255, 255, 255), 1)
                client.send_message("/augCanvas/laserPt", [ camID, 0, i["x"], i["y"], i["w"], i["h"] ] )   
        # Show camera image on LCD display
        display.show(img)
   
        # Stream over network
        if streamEnabled:
            streamingImg = img
            jpg = _maix.rgb2jpg(
                    streamingImg.convert("RGB").tobytes(),
                    streamingImg.width,
                    streamingImg.height,
                )
    
            queue.put(mjpg.BytesImage(jpg))
            time.sleep( 1.0 / frameRate ) # need to delay for atleast 100ms otherwise there is too much lag in sending   
        
        # sleep to let osc server receive and parse messages
        await asyncio.sleep( oscSleep )

async def init_main():
    print("setting up server")
    server = AsyncIOOSCUDPServer((serverIP, serverPort), dispatcher, asyncio.get_event_loop())

    transport, protocol = await server.create_serve_endpoint()  # Create datagram endpoint and start serving

    await loop()  # Enter main loop of program
    print("closing server")
    transport.close()  # Clean up serve endpoint
 
asyncio.run(init_main()) 

