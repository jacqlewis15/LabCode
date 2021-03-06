
# Jacqueline Lewis
# bscan.py

# for use on raspi
# - enable bluetooth
#   - sudo apt-get install python-pip libglib2.0-dev (maybe)
#   - sudo pip install bluepy
# - must modify btle.py 
#   - /usr/local/lib/python2.7/dist-packages/bluepy/btle.py
#   - add line "time.sleep(0.1)" after line 294 in doc
#   - this is in class BluepyHelper, def _stopHelper first if statement

from bluepy.btle import Scanner, DefaultDelegate
import time
import struct
import os

#Enter the MAC address of the sensor from the lescan
SENSOR_ADDRESS = ["80:ea:ca:10:07:11", "81:ea:ca:20:06:6a",
                        "82:ea:ca:30:0b:9c","83:ea:ca:40:06:90"]
SENSOR_LOCATION = ["TPMS1", "TPMS2","TPMS3","TPMS4"]

# set 1
# 1 - 80:ea:ca:10:02:dd
# 2 - 81:ea:ca:20:00:b3
# 3 - 82:ea:ca:30:01:ee
# 4 - 83:ea:ca:40:01:00

# set 2
# 1 - 80:ea:ca:10:07:53
# 2 - 81:ea:ca:20:05:36
# 3 - 82:ea:ca:30:0c:f7
# 4 - 83:ea:ca:40:0c:22

# set 3
# 1 - 80:ea:ca:10:06:1b
# 2 - 81:ea:ca:20:06:33
# 3 - 82:ea:ca:30:0b:ba
# 4 - 83:ea:ca:40:08:25

# set 4
# 1 - 80:ea:ca:10:07:11
# 2 - 81:ea:ca:20:06:6a
# 3 - 82:ea:ca:30:0b:9c
# 4 - 83:ea:ca:40:06:90

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData): pass

def writeFile(path, contents):
    with open(path, "wt") as f:
        f.write(contents)

def hexify(txt):
    hx = ""
    for i in range(len(txt)//2):
        hx = txt[2*i] + txt[2*i+1] + hx
    dec = int(hx, 16)
    return dec

def toPressure(dec): #return dec
    slope = 0.000146885
    yint = 0.626175
    return round(dec*slope+yint,1)

def toTemp(dec): #return dec
    slope = 0.00977033
    yint = 0.0214060
    return round(dec*slope+yint,1)

scanner = Scanner().withDelegate(ScanDelegate())


ManuDataHex = []
ReadLoop = True
contents = ""
start = time.time()
while(True):
    try:
        devices = scanner.scan(2.0)
        ManuData = ""
        for dev in devices:
            entry = 0
            for saddr in SENSOR_ADDRESS:
                entry += 1
                if (dev.addr == saddr):
                    for (adtype, desc, value) in dev.getScanData():
                        if (desc == "Manufacturer"): ManuData = value
                    if (ManuData == ""): continue
                    pressure = toPressure(hexify(ManuData[16:24]))
                    temp = toTemp(hexify(ManuData[24:32]))
                    tim = round(time.time()-start,1)
                    contents += str(tim) + " " + str(pressure) + "\n"

                    print(SENSOR_LOCATION[entry-1])
                    print(time.strftime("%H:%M:%S"))
                    print("Pressure data: %s" % (str(pressure)))
                    print("Temperature data: %s" % (str(temp)))

    except KeyboardInterrupt:
        writeFile("test.txt",contents)
        print("written")
        break
    # except:
    #     os.popen("sudo hciconfig hci0 reset")
        

