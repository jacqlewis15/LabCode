
# Jacqueline Lewis
# btpressure.py


# This file constructs a communication with bluetooth pressure sensors
# to monitor, record, and display the production of gas in a reaction.
# The system is optimized for display on two different screen resolutions,
# with instructions for switching between the two labeled as low_res.


# for use on device
# - enable bluetooth
#   - sudo apt-get install python-pip libglib2.0-dev 
#   - sudo pip install bluepy
# - tkinter
#   - sudo apt-get install python-tk
#   - sudo pip install tkcolorpicker
# - must modify btle.py  (for pi only)
#   - /usr/local/lib/python2.7/dist-packages/bluepy/btle.py
#   - add line "time.sleep(0.1)" after line 294 in doc
#   - this is in class BluepyHelper, def _stopHelper first if statement


# To run program:
#   > sudo python btpressure.py
#   - the sudo command is needed as the bluetooth scan requires root access
# In program:
#   - file name and individual labels can only be updated when the program is
#       not running
#   - color and time between pictures can be updated at any time
#   - to set a baseline, leave the program running and press the
#       set baseline button. Then select the lower and upper bound
#       of the desired region to set as the baseline on the raw graph
#   - the program automatically saves the raw pressure and temperature
#       data every 5 minutes to avoid loss of a dataset after error
#   - when the run is stopped, the data will be written to the file
#       and processed such that all intermediate data points with no
#       collected value are given one by linear interpolation


from bluepy.btle import Scanner, DefaultDelegate
import time
import struct
from Tkinter import *
from tkcolorpicker import askcolor
import tkMessageBox
import os,subprocess

# file reading/writing from 15-112: 
# http://www.kosbie.net/cmu/spring-16/15-112/notes/
#       notes-strings.html#basicFileIO

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
    # the graph space.
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
        font = "Arial 12" # "Arial 10" for low_res
        for i in range(5):
            x1,y1 = xl,yl+i*(yu-yl)/4.0
            x2,y2 = xu,yl+i*(yu-yl)/4.0
            # determines graph marking
            val = round(self.ylim[1]-(self.ylim[1]-self.ylim[0])/4.0*i,2)
            canvas.create_line(x1,y1,x2,y2)
            canvas.create_text(self.axisLimits[0]-5,y2,
                anchor="e",text=str(val),font=font)
        
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
                font=font)

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
        # Arial 10,8 for low_res
        font1 = "Arial 12 bold"
        font2 = "Arial 10 bold"
        canvas.create_text((x2-x1)/2+x1,y1+5,text=self.title,font=font1)
        canvas.create_text((x2-x1)/2+x1,y2-5,text=self.xaxis,font=font2)
        canvas.create_text(x1+5,(y2-y1)/2+y1,text=self.yaxis,font=font2)

# This class updates the graph class to allow for multiple datasets on
# the same plot, as well as functionalities for use on a normalized graph.
class Multigraph(Graph):

    # This function updates the addPoint fcn in the graph class to work
    # on a multigraph: adding a point to the proper dataset.
    def addPoint(self,point,idx):
        while len(self.points) <= idx:
            self.points.append([])
        self.points[idx].append(point)

    # This function removes the given points from a given dataset.
    def removePoints(self,i,points):        
        for item in points[::-1]:
            self.points[i].pop(item)

    # This function shifts all points in the graph based on a specified 
    # baseline, where one baseline is provided per dataset.
    def shiftPoints(self,baseline):
        for i in range(len(baseline)):
            if baseline[i] == 0: continue
            self.points[i] = map(lambda (x,y): (x,y - baseline[i]),
                self.points[i])

    # This function modifies the drawPoints fcn to draw multiple
    # datasets with specified colors.
    def drawPoints(self,canvas,data):
        for i in range(len(self.points)):
            for point in self.points[i]:
                x,y = self.getCoord(point)
                if y == None: continue
                x1,y1 = x-2,y-2
                x2,y2 = x+2,y+2
                canvas.create_oval(x1,y1,x2,y2,fill=data.color[i],
                    outline=data.color[i])

    # This function draws the graph, and includes passing data to drawPoints.
    def drawGraph(self,canvas,data):
        canvas.create_rectangle(self.axisLimits,fill="white")
        self.drawAxes(canvas)
        self.drawPoints(canvas,data)
        self.drawLabels(canvas)

# This class defines a selectable button object with rectangle, text, and
# event properties specific to the object.
class Icon(object):

    def __init__(self,coords,fill,text,textSpecs,fcn):
        # corners of rectangle for button
        self.left = coords[0]
        self.top = coords[1]
        self.right = coords[2]
        self.bot = coords[3]
        # fill color of button
        self.fill = fill
        # displayed text
        self.text = text
        # location, style, and size of text
        self.tLeft = textSpecs[0]
        self.tTop = textSpecs[1]
        self.anchor = textSpecs[2]
        self.font = textSpecs[3]
        self.tFill = textSpecs[4]
        # function to run when button is pressed
        self.fcn = fcn

    # This function updates the fill color of the button.
    def updateFill(self,fill):
        self.fill = fill

    # This function updates the text color of the button.
    def updateTextFill(self,fill):
        self.tFill = fill

    # This function updates the text of the button.
    def updateText(self,data,text):
        self.text = text

    # This function determines if a point is within the button.
    def isIn(self,x,y):
        return ((self.left < x < self.right) and (self.top < y < self.bot))

    # This function runs the specified function when the button is pressed.
    def click(self,data): 
        # if not function has been specified, nothing happens
        if self.fcn != None: self.fcn(self,data)

    # This function draws the button with text.
    def drawIcon(self,canvas):
        canvas.create_rectangle(self.left,self.top,self.right,self.bot,
            fill=self.fill)
        canvas.create_text(self.tLeft,self.tTop,text=self.text,
            anchor=self.anchor,font=self.font,fill=self.tFill)

# This class determines the interaction between the device and the 
# BLE sensor. The current settings do not include print statemtents for
# discovering new devices.
class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData): pass

# This function splits a string hex number into a decimal number.
def hexify(txt):
    hx = ""
    for i in range(len(txt)//2):
        hx = txt[2*i] + txt[2*i+1] + hx
    dec = int(hx, 16)
    return dec

# This function converts a sensor value to a pressure value (PSI) based
# on manual calibration.
def toPressure(dec):
    slope = 0.000146885
    yint = 0.626175
    return round(dec*slope+yint,1)

# This function converts a sensor value to a temperature value (C) based
# on manual calibration.
def toTemp(dec):
    slope = 0.00977033
    yint = 0.0214060
    return round(dec*slope+yint,1)

##########################################
# UI
##########################################

# This function defines the graph specifications for a pressure vs. time
# graph with not datasets or points initially.
def emptyGraph(data,coords,title):
    # xlim,ylim,xaxis,yaxis,points,title,coord
    return Multigraph((0,20),(0,16),"time (min)","pressure (psi)",[],
        title,coords)

# This function returns functions specific to the button pressed, for
# the icons containing editable text.
def editIcon(idx,data):
    def f(self,data):
        # editing of all but the time button cannot be done while running
        if idx != "time" and data.running: return
        elif data.basing != None: return
        # allows the text to be edited by keyPressed
        data.editing = self
        data.editText = str(idx)
    return f

# This function returns functions specific to the button pressed, for
# the icons changing the color of the datasets.
def legendIcon(idx,data):
    def f(self,data):
        if data.basing != None: return
        # opens color choosing window
        _,color = askcolor()
        if color != None: 
            # updates color of specified dataset and legend
            data.color[idx] = color
            self.fill = color
    return f

# This function returns functions specific to the button pressed, for
# the icons which represent the final row of buttons.
def buttonIcon(idx,data):
    if idx == 0: return editIcon("folder",data)
    elif idx == 1: return editIcon("time",data)
    elif idx == 2:
        # start/stop button
        def f(self,data):
            # stops the run
            if data.running:
                stop(data)
                self.updateTextFill("black")
                self.updateText(data,"Start")
            # starts the run if no errors
            elif data.editing == None:
                if not start(data): return
                self.updateTextFill("red")
                self.updateText(data,"Stop")
        return f
    elif idx == 3:
        # set baseline button
        def f(self,data):
            # baseline can be set while running
            if data.running and data.editing == None: 
                self.updateTextFill("red")
                data.basing = self
        return f

# This function starts the run if no veto is received.
def start(data): 
    # checks to see if a file of this name already exists
    if isValidFile(data.fileName) and readFile(data.fileName) != "":
        # if so, confirmation to continue is required from the user
        cont = tkMessageBox.askyesno("Question",
                "A file with this name already exists. Continue anyway?")
        if not cont: return False
    # starts run and notifies calling function of success
    data.running = True
    initTest(data)
    return True

# This function stops the run, saves the data, and processes the data.
def stop(data): 
    data.running = False
    save(data)
    process(data)

# This function initializes all name icons for the datasets.
def initNameIcons(data):
    bwidth = data.width/3/5
    bheight = data.height/4/5
    # 2x8 grid of names
    for row in range(2):
        for col in range(8):
            # location of button
            left = data.width/6 + bwidth/5 * (col + 1) + bwidth * col
            right = left + bwidth
            top = data.height*3/4 + bheight/5 * (row + 1) + bheight * row
            bottom = top + bheight
            idx = row*8 + col
            # labels button appropriately
            text = str(idx + 1) + ": " + data.label[idx]
            font = "Arial %d bold" % (bheight/4)
            coords = left,top,right,bottom
            fill = "white"
            textSpecs = left+5,top+bheight/2,"w",font,"black"
            # creates the icon with desired specifications
            data.icons.append(Icon(coords,fill,text,textSpecs,
                editIcon(idx,data)))

# This function initializes the colored legend icons.
def initLegendIcons(data):
    vTop = 2*data.margin
    vBot = data.height*3/4
    bheight = (vBot-vTop-15*(data.margin/2))/16
    left = data.width-4.5*data.margin
    right = data.width-3.5*data.margin
    # includes low_res and high_res font options
    font = "Arial 10 bold" if data.width == 1600 else "Arial 8 bold"
    for i in range(16):
        top = vTop+(data.margin/2+bheight)*i
        coords = left,top,right,top+bheight
        # uses specified color for dataset
        fill = data.color[i]
        text = str(i+1)
        textSpecs = (left-0.5*data.margin,top+bheight/2,
            "e",font,"black")
        # creates the icon
        data.icons.append(Icon(coords,fill,text,textSpecs,
            legendIcon(i,data)))

# This function initializes the icons for the button functionality.
def initButtonIcons(data):
    bwidth = data.width/3/5
    bheight = data.height/4/5

    top = data.height*3/4+bheight*15/5
    bot = top+bheight 
    for i in range(4):
        left = data.width/6+bwidth*(i*12+1)/5
        right = left+bwidth*11/5
        coords = left,top,right,bot
        fill = "white"
        font,anchor,tFill = "Arial 10 bold","w","black"
        # each button has separate specifications, with low and high_res 
        if i == 0: 
            text = "Filename: " + data.fileName
        elif i == 1: # time button
            if data.width == 1600:
                text = "Time between points (minutes): " + str(data.spacing)
            else:
                text = "Minutes between points: " + str(data.spacing)
        elif i == 2: # start/stop button
            text = "Start" if not data.running else "Stop"
            tFill = "red" if data.running else "black"
            font,anchor = "Arial 15 bold","center"
            left = left+(right-left)/2-5
        elif i == 3: # baseline button
            text = "Set baseline"
            anchor = "center"
            left = left+(right-left)/2-5
            font = "Arial 15 bold"
        tTop = top+bheight/2
        textSpecs = left+5,tTop,anchor,font,tFill
        # creates the icon
        data.icons.append(Icon(coords,fill,text,textSpecs,
            buttonIcon(i,data)))

# This function initializes all icons in the UI.
def initIcons(data):
    data.icons = []
    initNameIcons(data)
    initLegendIcons(data)
    initButtonIcons(data)

# This function returns red or black based on a boolean.
def color(val):
    if val: return "red"
    else: "black"

# This function creates a length 16 list of empty lists.
def emptyList():
    return [[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]]

# This function resets variables to their initial values at the 
# beginning of each run.
def initTest(data):
    # baseline information
    data.baseline = [0]*16
    data.basetemp = [0]*16
    data.lb = None
    data.ub = None
    # collected values between display points
    data.midPoints = emptyList()
    data.midTemps = emptyList()
    # graphs
    data.rawGraph = emptyGraph(data,(2*data.margin,data.margin,
        data.width/2-3*data.margin,data.height*3/4-data.margin),"Raw Data")
    data.normGraph = emptyGraph(data,(data.width/2-2*data.margin,
        data.margin,data.width-7*data.margin,data.height*3/4-data.margin),
            "Normalized Data")
    # displayed pressure and temperature
    data.pressures = [""] * 16
    data.temps = [""] * 16
    # graph scaling observance
    data.highPoint = 0
    # timing information
    data.startTime = time.time()/data.convert
    data.lastTime = time.time()/data.convert
    data.lastSave = time.time()/data.convert

# This function initializes all data for the user interface when the file is
# started.
def init(data):
    # BLE communication
    data.scanner = Scanner().withDelegate(ScanDelegate())
    data.sAddr = ["80:ea:ca:10:02:dd","81:ea:ca:20:00:b3",
                  "82:ea:ca:30:01:ee","83:ea:ca:40:01:00",
                  "80:ea:ca:10:07:53","81:ea:ca:20:05:36",
                  "82:ea:ca:30:0c:f7","83:ea:ca:40:0c:22",
                  "80:ea:ca:10:06:1b","81:ea:ca:20:06:33",
                  "82:ea:ca:30:0b:ba","83:ea:ca:40:08:25",
                  "80:ea:ca:10:07:11","81:ea:ca:20:06:6a",
                  "82:ea:ca:30:0b:9c","83:ea:ca:40:06:90"]
    # color-blind friendly colors
    data.color = ["#3CA4BB","#BE1E1E","#E9E610","#09BB0C",
                  "#030100","#131178","#E23D95","#5ECA92",
                  "#FF9203","white","white","white",
                  "white","white","white","white"]
    # user interface display settings
    data.margin = data.width/80
    data.label = [""]*16
    data.convert = 60 # seconds to minutes
    # temporary values for testing purposes
    data.label = ["one","two","three","four","five","six","seven","eight",
                  "nine","ten","eleven","twelve","","","",""]
    
    initTest(data)

    # information for collecting and saving data
    data.fileName = "test.txt"
    data.newData = ""
    data.spacing = 3
    data.filler = "None"
    # editing data
    data.editing = None
    data.time = 0
    data.pipe = False
    data.editText = ""
    data.error = ""
    # function data (for getting baseline and running test)
    data.bound = None
    data.basing = None
    data.running = False

    initIcons(data)

# This function determines a baseline for each dataset and then updates
# the normalized graph to exhibit points with this value as the zerpoint.
def addBaseline(data):
    # for each dataset, the baseline is calculated
    for i in range(len(data.rawGraph.points)):
        avg = []
        # averages over all points of the dataset within user time bound
        for j in range(len(data.rawGraph.points[i])):
            if data.lb <= data.rawGraph.points[i][j][0] <= data.ub:
                avg.append(data.rawGraph.points[i][j][1])
        data.baseline[i] = average(avg)
    # sets the normalized graph to display baseline as zero
    data.normGraph.shiftPoints(data.baseline)
    # updates displayed pressure data by new baseline
    for i in range(len(data.pressures)):
        if data.pressures[i] == "": continue
        data.pressures[i] = str(float(data.pressures[i]) - data.baseline[i])

# This function reacts to user clicks in the user interface.
def mousePressed(event, data):
    # while editing, no other action can be taken
    if data.editing != None: return
    # presses an icon
    for icon in data.icons:
        if icon.isIn(event.x,event.y): icon.click(data)
    # places bound lines in the raw graph
    if data.basing != None and data.rawGraph.inGraph(event.x,event.y):
        # reads lower bound first
        if data.lb == None: 
            data.lb = data.rawGraph.getPoint((event.x,0))[0]
            data.bound = event.x
        # reads upper bound
        else: 
            data.ub = data.rawGraph.getPoint((event.x,0))[0]
            # ensures lower bound less than upper bound
            if data.ub < data.lb: 
                data.ub = data.lb
                data.lb = data.rawGraph.getPoint((event.x,0))[0]
            # sets baseline and ends editing baseline
            addBaseline(data)
            data.basing.updateTextFill("black")
            data.basing = data.bound = None

# This function stops editing an icon.
def clearEdit(data):
    data.pipe = False
    data.editing.text = piping(data,data.editing.text)
    data.editing = None
    data.editText = ""

# This function reacts to user key presses.
def keyPressed(event, data): 
    # must have an icon to edit
    if data.editing != None:
        # ends edit of icon if legal entry
        if event.keysym == "Return":
            if data.editText == "folder":
                # ensures all pipe symbols have been removed
                name = data.editing.text.split(" ")[-1].strip("|")
                try: # makes sure folder name is valid
                    makeFolder(name)
                    clearEdit(data)
                    data.fileName = name
                except: pass
            elif data.editText == "time":
                num = data.editing.text.split(" ")[-1].strip("|")
                try: # makes sure a float has been entered
                    data.spacing = float(num)
                    clearEdit(data)
                except: pass
            elif data.editText in map(str,range(16)):
                data.label[int(data.editText)] = (
                    data.editing.text.split(" ")[-1].strip("|"))
                clearEdit(data)
        # backspace
        elif event.keysym == "BackSpace":
            if len(data.editing.text.split(" ")[-1].strip("|")) > 0:
                data.editing.updateText(data,data.editing.text.strip("|")[:-1])
        # adds character to icon
        else:
            data.editing.updateText(data,
                data.editing.text.strip("|") + event.char)

# These functions determine if a path is a valid folder or file.

def isValidFolder(folder):
    return os.path.isdir(folder)

def isValidFile(file):
    return os.path.isfile(file)

# This function makes the folder as specified, if it does not exist.
def makeFolder(foldName):
    # makes super directories as well
    folders = foldName.split("/")[:-1]
    for i in range(len(folders)):
        if not isValidFolder("/".join(folders[:i+1])):
            subprocess.check_call(["mkdir","/".join(folders[:i+1])])

# This function adds and removes the piping character to show icon editing.
def piping(data,text):
    if data.pipe: return text.strip("|") + "|"
    elif "|" in text: return text.strip("|")
    else: return text

# This function runs the bluetooth scan.
def runScan(data):
    try: # scans for BLE sensors
        devices = data.scanner.scan(2.0)
        ManuData = ""
        for dev in devices:
            entry = 0
            # checks if data is wanted from found sensors
            for saddr in data.sAddr:
                if (dev.addr == saddr):
                    # collects pressure and temperature data from sensor
                    for (adtype, desc, value) in dev.getScanData():
                        if (desc == "Manufacturer"): ManuData = value
                    if (ManuData == ""): continue
                    pressure = toPressure(hexify(ManuData[16:24]))
                    temp = toTemp(hexify(ManuData[24:32]))
                    # includes new data in averaging
                    data.midPoints[entry].append(pressure)
                    data.midTemps[entry].append(temp)
                entry += 1
    # if scan fails, reopens bluetooth connection
    except: os.popen("sudo hciconfig hci0 reset")

# This function returns the average of a list of numbers.
def average(lst):
    if lst == []: return None
    total = 0
    for i in range(len(lst)):
        total += lst[i]
    return round(total/(len(lst)),1)

# This function generates the next points in each dataset by averaging
# all points found since last generation. Then it updates the graphs and
# user interface to display this information. It also stores the gathered
# information to be saved later.
def averagePoints(data):
    for i in range(len(data.midPoints)):
        avg = average(data.midPoints[i])
        temp = average(data.midTemps[i])
        # adds the time to the front of the new line of data to write
        if i == 0: data.newData += "\n" + str(
            round(data.lastTime-data.startTime,2))
        # only records data for named datasets
        if data.label[i] != "": 
            if avg == None: # no data was received during the timeframe
                data.newData += "," + data.filler + "," + data.filler
            else:
                # adds points to graphs
                if avg > data.highPoint: data.highPoint = avg
                data.rawGraph.addPoint((data.lastTime-data.startTime,avg),i)
                norm = avg - data.baseline[i]
                data.normGraph.addPoint((data.lastTime-data.startTime,norm),i)
                # records pressure and temperature data to write out
                data.newData += "," + str(avg) + "," + str(temp)
                data.pressures[i] = norm
                data.temps[i] = temp
        else: continue
    # resets recorded points for next timeframe
    data.midPoints = emptyList()

# This function scales the graphs to incorporate points outside of 
# the graph limits. The graphs are scaled so that the new points appear
# at 2/3 of the graph's height or width, depending on which axis is
# being scaled.
def scaleGraphs(data):
    # time increases past edge of graph
    if (data.lastTime - data.startTime 
        > data.rawGraph.xlim[1]):
        newX = data.lastTime - data.startTime
        # pressure increases past edge of graph too
        if data.highPoint > data.rawGraph.ylim[1]:
            data.rawGraph.updateLimits((0,int(newX*1.5)),
                (0,int(data.highPoint*1.5)))
            data.normGraph.updateLimits((0,int(newX*1.5)),
                (0,int(data.highPoint*1.5)))
        else: # pressure is not too high
            data.rawGraph.updateLimits((0,int(newX*1.5)),
                data.rawGraph.ylim)
            data.normGraph.updateLimits((0,int(newX*1.5)),
                data.normGraph.ylim)
    # pressure increases past edge of graph
    elif data.highPoint > data.rawGraph.ylim[1]:
            data.rawGraph.updateLimits(data.rawGraph.xlim,
                (0,int(data.highPoint*1.5)))
            data.normGraph.updateLimits(data.normGraph.xlim,
                (0,int(data.highPoint*1.5)))

# This function saves the data generated since the last save into a text
# file specified by the user. The data is saved with a top line of 
# dataset names, followed by lines with time followed by pressure and 
# temperature data for each dataset. Points per line are separated by commas.
def save(data):
    # the file may not exist or be empty: if so, add first line
    try: contents = readFile(data.fileName)
    except: 
        contents = "Time"
        for i in range(len(data.midPoints)):
            if data.label[i] == "": continue
            contents += "," + data.label[i] + ",Temp"
    if contents == "":
        contents = "Time"
        for i in range(len(data.midPoints)):
            if data.label[i] == "": continue
            contents += "," + data.label[i] + ",Temp"
    # add all collected data to contents of file and write out
    contents += data.newData
    contents = contents.strip()
    writeFile(data.fileName, contents)
    data.newData = ""

# This function uses linear interpolation using two points and a value 
# which are strings of floats. It outputs the calculated value as a string.
def interpolate(data,x1,x2,y1,y2,x):
    if data.filler in (x1,x2,y1,y2,x): return data.filler
    return str(round(float(y1)+(float(x)-
        float(x1))*(float(y2)-float(y1))/(float(x2)-float(x1)),2))

# This function runs post-processing on the text file to replace all 
# missing points within the run with linearly interpolated points.
# After processing, the only non-values will be at the end of the file,
# when no more data was received from said sensor before ending the run.
def process(data):
    # gathers current data in file and separates points into lists
    contents = readFile(data.fileName)
    lines = contents.split("\n")
    points = []
    for line in lines:
        points.append(line.split(","))
    # runs through columns of data
    for j in range(1,len(points[0])):
        # initial point is time of 0 and baseline
        if j % 2 == 1: LB = 0,data.baseline[j/2]
        else: LB = 0,data.basetemp[(j-1)/2]
        UB = None
        for i in range(1,len(points)):
            # for points with no scanned data, the value is calculated
            # via linear interpolation
            if points[i][j] == data.filler: 
                if UB == None: # finds upper bound point to interpolate with
                    move = 1
                    while (UB == None):
                        if i + move >= len(points): # no upper point exists
                            break
                        elif points[i+move][j] != data.filler: 
                            UB = points[i+move][0],points[i+move][j]
                            points[i][j] = interpolate(data,LB[0],
                                UB[0],LB[1],UB[1],points[i][0])
                            break
                        move += 1
                else: 
                    points[i][j] = interpolate(data,LB[0],UB[0],LB[1],UB[1],
                        points[i][0])
            else: # sets found point as new lower bound
                LB = points[i][0],points[i][j]
                UB = None
    # formats calculated data back into file format
    for i in range(len(points)):
        points[i] = (",").join(points[i])
    contents = ("\n").join(points)
    writeFile(data.fileName,contents)

# This function checks for time-sensitive operations every millisecond.
def timerFired(data):
    # during run, points are added to the graphs after user-stated time
    if data.running: runScan(data)
    if data.running and (time.time()/data.convert - data.lastTime 
                                                        > data.spacing):
        data.lastTime = time.time()/data.convert
        averagePoints(data)
        scaleGraphs(data)
    # every 5 minutes write output file (ensure minimal data loss) 
    if data.running and (time.time()/data.convert - data.startTime > 5):
        data.lastSave = time.time()/data.convert
        save(data)
    # updates pipe symbol in text being edited to make edit visible
    if data.editing != None and data.time % 5 == 0:
        data.pipe = not data.pipe
        data.editing.updateText(data,piping(data,data.editing.text))
    data.time += 1

# This function writes the current pressures and temperatures onto the UI.
def drawPressures(canvas,data):
    vTop = 2*data.margin
    vBot = data.height*3/4
    bheight = (vBot-vTop-15*(data.margin/2))/16
    left = data.width-3*data.margin
    # has high and low-res font sizes
    font = "Arial 10 bold" if data.width == 1600 else "Arial 8 bold"
    for i in range(16):
        # writes data next to legend
        top = vTop+(data.margin/2+bheight)*i+bheight/2
        if data.label[i] == "": text = ""
        elif data.pressures[i] == "": text = ""
        else: text = (str(data.pressures[i]) + ", " + str(data.temps[i]))
        canvas.create_text(left,top,text=text,
            anchor="w",font=font,fill="black")
    canvas.create_text(left,vTop-data.margin/2-bheight*0.5,text="P    T",
        anchor="w",font=font)

# This function draws the boundary lines on the graph.
def drawBoundLines(data, canvas):
    if data.bound != None:
        canvas.create_line(data.bound,data.rawGraph.axisLimits[1],
            data.bound,data.rawGraph.axisLimits[3],fill="light green",width="2")

# This function redraws the UI every millisecond
def redrawAll(canvas, data):
    canvas.create_rectangle(-5,-5,data.width+5,data.height+5,fill="gray72")
    data.rawGraph.drawGraph(canvas,data)
    data.normGraph.drawGraph(canvas,data)
    for icon in data.icons:
        icon.drawIcon(canvas)
    drawPressures(canvas,data)
    # writes an error message if necessary
    canvas.create_text(data.width/2-0.5*data.margin,
        data.height*3/4-0.5*data.margin,text=data.error,font = "Arial 12 bold",
        fill="red")
    drawBoundLines(data,canvas)

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
    # print("bye!")
    print(data.color)

run(1600, 800) # (1200,600) for low_res