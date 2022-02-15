from maix import camera, mjpg, display, image
import socket, select
import _maix, time
from io import BytesIO

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

localIP   = '192.168.1.192'
localPort = 6667
bufferSize = 1024

server   = None
mjpgPort = 9999

frameRate = 30.0


# Bind to address and ip
#UDPServerSocket.bind((localIP, localPort))
#print("UDP server up and listening")

# Start webcam server
queue  = Queue(maxsize=100)
server = mjpg.MjpgServerThread("0.0.0.0", mjpgPort, mjpg.BytesImageHandlerFactory(q=queue) ) 
server.start()


while True:
    # Show camera image on LCD display
    img = camera.capture()
    display.show( img )
    # Stream over network
    streamingImg = img
    jpg = _maix.rgb2jpg(
                    streamingImg.convert("RGB").tobytes(),
                    streamingImg.width,
                    streamingImg.height,
                )
    
    queue.put(mjpg.BytesImage(jpg))
    time.sleep( 1.0 / frameRate ) # need to delay for atleast 100ms otherwise there is too much lag in sending   
 

