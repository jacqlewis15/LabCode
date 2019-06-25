

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
SENSOR_ADDRESS = ["80:ea:ca:10:02:dd", "81:ea:ca:20:00:b3",
                        "82:ea:ca:30:01:ee","83:ea:ca:40:01:00"]
SENSOR_LOCATION = ["TPMS1", "TPMS2","TPMS3","TPMS4"]

# set 2
# 1 - 80:EA:CA:10:01:E7
# 2 - 81:EA:CA:20:00:B0
# 3 - 82:EA:CA:30:00:50
# 4 - 83:EA:CA:40:01:A6

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
    slope = 0.000147513
    yint = 0.545090
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
        # wait = time.time()
        for dev in devices:
            entry = 0
            for saddr in SENSOR_ADDRESS:
                entry += 1
                if (dev.addr == saddr):
                    for (adtype, desc, value) in dev.getScanData():
                        # print "  %s = %s" % (desc, value)
                        if (desc == "Manufacturer"):
                            ManuData = value

                    if (ManuData == ""):
                        print "No data received, end decoding"
                        continue

                    # print ManuData[16:]
                    pressure = toPressure(hexify(ManuData[16:24]))
                    temp = toTemp(hexify(ManuData[24:32]))
                    tim = round(time.time()-start,1)
                    contents += str(tim) + " " + str(pressure) + "\n"

                    print(SENSOR_LOCATION[entry-1])
                    print(time.strftime("%H:%M:%S"))
                    print("Pressure data: %s" % (str(pressure)))
                    print("Temperature data: %s" % (str(temp)))
        # print(time.time()-wait)
        
    except KeyboardInterrupt:
        writeFile("test.txt",contents)
        print("written")
        break
    # except: continue
    #     os.popen("sudo hciconfig hci0 reset")
        # os.popen("sudo /etc/init.d/bluetooth restart")

