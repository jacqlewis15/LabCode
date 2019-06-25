

# for use on raspi
# - enable bluetooth
#   - sudo apt-get install python-pip libglib2.0-dev 
#   - sudo pip install bluepy
# - must modify btle.py 
#   - /usr/local/lib/python2.7/dist-packages/bluepy/btle.py
#   - add line "time.sleep(0.1)" after line 294 in doc
#   - this is in class BluepyHelper, def _stopHelper first if statement


# NOTES
# - UI with pressure v time graph
# - possible normalized graph too
# - be able to label up to 16 chambers (starting with 8)
# - choose color-blind friendly colors
# - have time delay between data points/time delay curve 
#   - freq at beginning, slows down later
# - update graph to increase the time axis as time passes
# - curve fit the graph
# - add settings to look at one plot at a time, with button to return to all

# - start/stop button for pressure reading
# - save data every few minutes with final save at stop
# - spot for filename
# - 

from bluepy.btle import Scanner, DefaultDelegate
import time
import struct
from Tkinter import *
from tkcolorpicker import askcolor

#Enter the MAC address of the sensor from the lescan
SENSOR_ADDRESS = ["80:ea:ca:10:02:dd", "81:ea:ca:20:00:b3",
                        "82:ea:ca:30:01:ee","83:ea:ca:40:01:00"]
SENSOR_LOCATION = ["TPMS1", "TPMS2","TPMS3","TPMS4"]



class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData): pass

def readFile(path):
    with open(path, "rt") as f:
        return f.read()

def writeFile(path, contents):
    with open(path, "wt") as f:
        f.write(contents)

####################################
# Graph Class 
####################################

# This class defines a graph object, and draws it.
class Graph(object):

    def __init__(self,xlim,ylim,xaxis,yaxis,points,title,coord):
        self.xlim = xlim # bounds on x data
        self.ylim = ylim # bounds on y data
        self.xaxis = xaxis # x axis label
        self.yaxis = yaxis # y axis label
        self.points = points # data points
        self.title = title # graph title
        self.coord = coord # tkinter graph space edges
        self.margin = 20
        self.limits() # tkinter graph edges
        self.scales() # conversion from data to tkinter space

    # This function determines the edges of the graph in the given
    # tkinter space.
    def limits(self):
        x1,y1,x2,y2 = self.coord
        self.axisLimits = (x1+self.margin*3,y1+self.margin,
            x2-self.margin,y2-self.margin*3)

    # This function determines the scaling factor from data point
    # to tkinter space for graphing.
    def scales(self):
        x1,y1,x2,y2 = self.axisLimits
        LB,UB = self.xlim
        self.xscale = (x2-x1)/float(UB-LB)
        LB,UB = self.ylim
        self.yscale = (y2-y1)/float(UB-LB)

    # This function converts a data point to a coordinate space
    # point.
    def getCoord(self,point):
        x,y = point
        xcoord = (x-self.xlim[0])*self.xscale+self.axisLimits[0]
        ycoord = (self.ylim[1]-y)*self.yscale+self.axisLimits[1]
        return xcoord,ycoord

    # This function converts a coordinate space point to a data
    # point.
    def getPoint(self,point):
        x,y = point
        xcoord = (x-self.axisLimits[0])/self.xscale+self.xlim[0]
        ycoord = self.ylim[1]-(y-self.axisLimits[1])/self.yscale
        return xcoord,ycoord

    # This function adds a new point to the data points.
    def addPoint(self,point):
        self.points.append(point)

    # This function updates the x and y limits of the data,
    # changing the scaling factor.
    def updateLimits(self,xlim,ylim):
        self.xlim = xlim
        self.ylim = ylim
        self.scales()

    # This function determines if a graph is empty.
    def isEmpty(self):
        return self.points == []

    # This function checks if a coordinate point is within 
    # the graph sapce.
    def inGraph(self,x,y):
        return (self.axisLimits[0] < x < self.axisLimits[2] and
            self.axisLimits[1] < y < self.axisLimits[3])

    # This function makes a log graph from a linear graph.
    def makeLogGraph(self, data):
        # This function checks if a point is within bounds.
        def inBound(point):
            x,y = point
            # if the bound isn't set, all points are in
            if data.bound[0] != None:
                if data.lb > x: return False
            if data.bound[1] != None:
                if data.ub < x: return False
            return True
        # This function gets the correct value out of a tuple.
        def getTuple(point,idx):
            return point[idx]
        # This function checks if a value is None.
        def notNone(point):
            x,y = point
            return y != None
        # gets the points in the log graph
        points = filter(notNone, map(yLog, filter(inBound,self.points)))
        ys = map(lambda x: getTuple(x,1), points)
        xs = map(lambda x: getTuple(x,0), points)
        ylow,xlow = min(ys),min(xs)
        yup,xup = max(ys),max(xs)
        # finds the lifetime of the data
        linReg(data,xs,ys)
        return Graph((xlow,xup),(ylow,yup),self.xaxis,self.yaxis,points,
            self.title,self.coord)

    # This function draws the graph.
    def drawGraph(self,canvas):
        canvas.create_rectangle(self.axisLimits,fill="white")
        self.drawAxes(canvas)
        self.drawPoints(canvas)
        self.drawLabels(canvas)

    # This function draws the graph axes, with numberings.
    def drawAxes(self,canvas):

        # y axes, in volts
        xl,yl,xu,yu = self.axisLimits
        # creates horizontal grid lines
        for i in range(5):
            x1,y1 = xl,yl+i*(yu-yl)/4.0
            x2,y2 = xu,yl+i*(yu-yl)/4.0
            # determines graph marking
            val = round(self.ylim[1]-(self.ylim[1]-self.ylim[0])/4.0*i,2)
            canvas.create_line(x1,y1,x2,y2)
            canvas.create_text(self.axisLimits[0]-5,y2,
                anchor="e",text=str(val),font="Arial 12")
        
        # x axes, in ns
        xl,yl,xu,yu = self.axisLimits
        # creates vertical grid lines
        for i in range(5):
            x1,y1 = xl+i*(xu-xl)/4.0,yl
            x2,y2 = xl+i*(xu-xl)/4.0,yu
            # determines graph marking
            val = round((self.xlim[0]+(self.xlim[1]-self.xlim[0])/4.0*i),2)
            canvas.create_line(x1,y1,x2,y2)
            canvas.create_text(x2,y2+20,anchor="n",text=str(val),
                font="Arial 12")

    # This function draws the points on the graph.
    def drawPoints(self,canvas):
        for point in self.points:
            x,y = self.getCoord(point)
            if y == None: continue
            x1,y1 = x-2,y-2
            x2,y2 = x+2,y+2
            canvas.create_oval(x1,y1,x2,y2,fill="black")

    # This function draws the graph labels.
    def drawLabels(self,canvas):
        x1,y1,x2,y2 = self.coord
        canvas.create_text((x2-x1)/2+x1,y1+5,text=self.title,
            font="Arial 12 bold")
        canvas.create_text((x2-x1)/2+x1,y2-5,text=self.xaxis,
            font = "Arial 10 bold")
        canvas.create_text(x1+5,(y2-y1)/2+y1,text=self.yaxis,
            font = "Arial 10 bold")


class Icon(object):

    def __init__(self,coords,text,textSpecs,fcn):
        self.left = coords[0]
        self.top = coords[1]
        self.right = coords[2]
        self.bot = coords[3]
        self.tLeft = textSpecs[0]
        self.tTop = textSpecs[1]
        self.anchor = textSpecs[2]
        self.font = textSpecs[3]
        self.tFill = textSpecs[4]
        self.fcn = fcn

    def isIn(self,coords):
        x,y = coords
        return ((self.left < x < self.right) and (self.top < y < self.bot))

    def click(self): fcn()

    def drawIcon(self,canvas,text=None,fill=None):
        canvas.create_rectangle(self.left,self.top,self.right,self.bot,
            fill="white")
        if text == None: text = self.text
        if fill == None: fill = self.fill
        canvas.create_text(self.tLeft,self.tTop,text=text,
            anchor=self.anchor,font=self.font,fill=fill)

def hexify(txt):
    hx = ""
    for i in range(len(txt)//2):
        hx = txt[2*i] + txt[2*i+1] + hx
    dec = int(hx, 16)
    return dec

def toPressure(dec):
    slope = 0.000142940
    yint = 0.0316052
    return round(dec*slope+yint,1)

def toTemp(dec):
    slope = 0.00977033
    yint = 0.0214060
    return round(dec*slope+yint,1)


# ManuDataHex = []
# ReadLoop = True
# contents = ""
# try:
#     while (ReadLoop):
#         devices = scanner.scan(2.0)
#         ManuData = ""

#         for dev in devices:
#             entry = 0
#             for saddr in SENSOR_ADDRESS:
#                 entry += 1
#                 if (dev.addr == saddr):
#                     for (adtype, desc, value) in dev.getScanData():
#                         # print "  %s = %s" % (desc, value)
#                         if (desc == "Manufacturer"):
#                             ManuData = value

#                     if (ManuData == ""):
#                         print "No data received, end decoding"
#                         continue

#                     # print ManuData[16:]
#                     pressure = toPressure(hexify(ManuData[16:24]))
#                     temp = toTemp(hexify(ManuData[24:32]))
#                     contents += str(pressure) + " - - " + str(temp) + "\n"

#                     print(SENSOR_LOCATION[entry-1])
#                     print("Pressure data: %s" % (str(pressure)))
#                     print("Temperature data: %s" % (str(temp)))
    
# except:
#     writeFile("test.txt",contents)
#     print("written")

def emptyGraph(data,coords):
    # xlim,ylim,xaxis,yaxis,points,title,coord
    return Graph((0,100),(0,16),"time (s)","pressure (psi)",[],
        "Pressure v. Time",coords)

def initIcons(data):
    data.icons = []
    bwidth = data.width/3/5
    bheight = data.height/4/5
    for row in range(2):
        for col in range(8):
            left = data.width/6 + bwidth/5 * (col + 1) + bwidth * col
            right = left + bwidth
            top = data.height*3/4 + bheight/5 * (row + 1) + bheight * row
            bottom = top + bheight
            idx = row*4 + col
            text = str(idx + 1) + ": " + data.label[idx]
            font = "Arial %d bold" % (bheight/4)
            canvas.create_rectangle(left,top,right,bottom,fill="white")
            canvas.create_text(left+5,top+bheight/2,text=text,font=font,
                anchor="w")


def init(data):
    data.scanner = Scanner().withDelegate(ScanDelegate())
    data.sAddr = ["80:ea:ca:10:02:dd", "81:ea:ca:20:00:b3",
                  "82:ea:ca:30:01:ee","83:ea:ca:40:01:00",
                  "","","","","","","","","","","",""]
    data.margin = 20
    data.sVal = [0]*16
    data.label = [""]*16
    data.rawGraph = emptyGraph(data,(2*data.margin,data.margin,
        data.width/2-3*data.margin,data.height*3/4-data.margin))
    data.normGraph = emptyGraph(data,(data.width/2,
        data.margin,data.width-5*data.margin,data.height*3/4-data.margin))

    data.color = ['#3CA4BB','#BE1E1E','#E9E610','#09BB0C',
                  '#030100','#131178','#E23D95','#5ECA92',
                  '#FF9203',"white","white","white",
                  "white","white","white","white"]

    data.fileName = "test.txt"
    data.newData = ""
    data.betTime = "3"

    data.running = False
    data.startTime = time.time()

    initIcons(data)

def mousePressed(event, data):
    if data.width-1.5*data.margin < event.x < data.width-0.5*data.margin:
        space = (data.height*3/4-2*data.margin)/16
        idx = (event.y-2*data.margin)/space
        if (2*data.margin+space*idx < event.y < 
            1.5*data.margin+space*(idx+1)):
            tup,color = askcolor()
            if color != None: data.color[idx] = color

def keyPressed(event, data):
    pass

def timerFired(data):
    # every 5 minutes write output file (ensure minimal data loss) 
    if data.running and (time.time() - data.startTime > 5 * 60):
        contents = readFile(data.fileName)
        writeFile(data.fileName, contents + data.newData)

def drawNames(canvas, data):
    margin = 20
    bwidth = data.width/3/5
    bheight = data.height/4/5
    for row in range(2):
        for col in range(8):
            left = data.width/6 + bwidth/5 * (col + 1) + bwidth * col
            right = left + bwidth
            top = data.height*3/4 + bheight/5 * (row + 1) + bheight * row
            bottom = top + bheight
            idx = row*4 + col
            text = str(idx + 1) + ": " + data.label[idx]
            font = "Arial %d bold" % (bheight/4)
            canvas.create_rectangle(left,top,right,bottom,fill="white")
            canvas.create_text(left+5,top+bheight/2,text=text,font=font,
                anchor="w")

def drawLegend(canvas, data):
    # NOTE #
    # will have to update graph object to take more sets of points
    margin = 20
    vTop = 2*margin
    vBot = data.height*3/4
    bheight = (vBot-vTop-15*(margin/2))/16
    left = data.width-1.5*margin
    right = data.width-0.5*margin
    for i in range(16):
        top = vTop+(margin/2+bheight)*i
        canvas.create_rectangle(left,top,right,top+bheight,
            fill=data.color[i])
        text = str(i+1)
        canvas.create_text(left-0.5*margin,top+bheight/2,
            anchor="e",text=text,font="Arial 10 bold")

def drawButtons(canvas, data):
    bwidth = data.width/3/5
    bheight = data.height/4/5

    top = data.height*3/4+bheight*15/5
    bot = top+bheight 
    for i in range(3):
        left = data.width/6+bwidth*(i*12+1)/5
        right = left+bwidth*11/5
        canvas.create_rectangle(left,top,right,bot,fill="white")
        font,anchor,fill = "Arial 10 bold","w","black"
        if i == 0: 
            text = "Filename: " + data.fileName
        elif i == 1: 
            text = "Time between points: " + data.betTime + " minutes"
        else: 
            text = "Start" if not data.running else "Stop"
            fill = "red" if data.running else "black"
            font,anchor = "Arial 15 bold","center"
            left = left+(right-left)/2-5
        canvas.create_text(left+5,top+bheight/2,anchor=anchor,text=text,
            font=font)

def redrawAll(canvas, data):
    canvas.create_rectangle(-5,-5,data.width+5,data.height+5,fill="gray72")
    drawNames(canvas,data)
    data.rawGraph.drawGraph(canvas)
    data.normGraph.drawGraph(canvas)
    drawLegend(canvas,data)
    drawButtons(canvas,data)

####################################
# use the run function as-is
####################################

def run(width=300, height=300):
    def redrawAllWrapper(canvas, data):
        canvas.delete(ALL)
        redrawAll(canvas, data)
        canvas.update()    

    def mousePressedWrapper(event, canvas, data):
        mousePressed(event, data)
        redrawAllWrapper(canvas, data)

    def keyPressedWrapper(event, canvas, data):
        keyPressed(event, data)
        redrawAllWrapper(canvas, data)

    def timerFiredWrapper(canvas, data):
        timerFired(data)
        redrawAllWrapper(canvas, data)
        # pause, then call timerFired again
        canvas.after(data.timerDelay, timerFiredWrapper, canvas, data)
    # Set up data and call init
    class Struct(object): pass
    data = Struct()
    data.width = width
    data.height = height
    data.timerDelay = 100 # milliseconds
    init(data)
    # create the root and the canvas
    root = Tk()
    canvas = Canvas(root, width=data.width, height=data.height)
    canvas.pack()
    # set up events
    root.bind("<Button-1>", lambda event:
                            mousePressedWrapper(event, canvas, data))
    root.bind("<Key>", lambda event:
                            keyPressedWrapper(event, canvas, data))
    timerFiredWrapper(canvas, data)
    # and launch the app
    root.mainloop()  # blocks until window is closed
    print("bye!")

run(1600, 800)