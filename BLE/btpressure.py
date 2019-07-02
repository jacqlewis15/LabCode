
# Jacqueline Lewis
# btpressure.py

# for use on raspi
# - enable bluetooth
#   - sudo apt-get install python-pip libglib2.0-dev 
#   - sudo pip install bluepy
# - tkinter
#   - sudo apt-get install python-tk
#   - sudo pip install tkcolorpicker
# - must modify btle.py 
#   - /usr/local/lib/python2.7/dist-packages/bluepy/btle.py
#   - add line "time.sleep(0.1)" after line 294 in doc
#   - this is in class BluepyHelper, def _stopHelper first if statement


# NOTES
# - add settings to look at one plot at a time, with button to return to all
# - add graph zoom features (box zoom?) and back out


from bluepy.btle import Scanner, DefaultDelegate
import time
import struct
from Tkinter import *
from tkcolorpicker import askcolor
import os,subprocess


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

class Multigraph(Graph):

    def addPoint(self,point,idx):
        while len(self.points) <= idx:
            self.points.append([])
        self.points[idx].append(point)

    def drawPoints(self,canvas,data):
        for i in range(len(self.points)):
            for point in self.points[i]:
                x,y = self.getCoord(point)
                if y == None: continue
                x1,y1 = x-2,y-2
                x2,y2 = x+2,y+2
                canvas.create_oval(x1,y1,x2,y2,fill=data.color[i],
                    outline=data.color[i])

    # This function draws the graph.
    def drawGraph(self,canvas,data):
        canvas.create_rectangle(self.axisLimits,fill="white")
        self.drawAxes(canvas)
        self.drawPoints(canvas,data)
        self.drawLabels(canvas)

class Icon(object):

    def __init__(self,coords,fill,text,textSpecs,fcn):
        self.left = coords[0]
        self.top = coords[1]
        self.right = coords[2]
        self.bot = coords[3]
        self.fill = fill
        self.text = text
        self.tLeft = textSpecs[0]
        self.tTop = textSpecs[1]
        self.anchor = textSpecs[2]
        self.font = textSpecs[3]
        self.tFill = textSpecs[4]
        self.fcn = fcn

    def updateFill(self,fill):
        self.fill = fill

    def updateTextFill(self,fill):
        self.tFill = fill

    def updateText(self,data,text):
        self.text = text

    def isIn(self,x,y):
        return ((self.left < x < self.right) and (self.top < y < self.bot))

    def click(self,data): 
        if self.fcn != None: self.fcn(self,data)

    def drawIcon(self,canvas):
        canvas.create_rectangle(self.left,self.top,self.right,self.bot,
            fill=self.fill)
        canvas.create_text(self.tLeft,self.tTop,text=self.text,
            anchor=self.anchor,font=self.font,fill=self.tFill)

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData): pass

def hexify(txt):
    hx = ""
    for i in range(len(txt)//2):
        hx = txt[2*i] + txt[2*i+1] + hx
    dec = int(hx, 16)
    return dec

def toPressure(dec):
    slope = 0.000146885
    yint = 0.626175
    return round(dec*slope+yint,1)

def toTemp(dec):
    slope = 0.00977033
    yint = 0.0214060
    return round(dec*slope+yint,1)

def emptyGraph(data,coords,title):
    # xlim,ylim,xaxis,yaxis,points,title,coord
    return Multigraph((0,100),(0,16),"time (s)","pressure (psi)",[],
        title,coords)

def editIcon(idx,data):
    def f(self,data):
        if idx != "time" and data.running: return
        data.editing = self
        data.editText = str(idx)
    return f

def legendIcon(idx,data):
    def f(self,data):
        _,color = askcolor()
        if color != None: 
            data.color[idx] = color
            self.fill = color
    return f

def buttonIcon(idx,data):
    if idx == 0: return editIcon("folder",data)
    elif idx == 1: return editIcon("time",data)
    elif idx == 2:
        def f(self,data):
            if data.running:
                self.updateTextFill("black")
                self.updateText(data,"Start")
                stop(data)
            elif data.editing == None:
                self.updateTextFill("red")
                self.updateText(data,"Stop")
                start(data)
        return f
    elif idx == 3:
        def f(self,data): pass
            # fix save!!!
            # make baseline code a button
            #   starts run, can select baseline
            #   don't need to keep points before baseline
        return f

def start(data): 
    # data.running = True
    initTest(data)
    data.basing = True
    data.stableSince = time.time()
    data.error = "Establishing baseline"

def stop(data): 
    data.running = False
    save(data)
    process(data)

def initNameIcons(data):
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
            coords = left,top,right,bottom
            fill = "white"
            textSpecs = left+5,top+bheight/2,"w",font,"black"
            data.icons.append(Icon(coords,fill,text,textSpecs,
                editIcon(idx,data)))

def initLegendIcons(data):
    vTop = 2*data.margin
    vBot = data.height*3/4
    bheight = (vBot-vTop-15*(data.margin/2))/16
    left = data.width-4.5*data.margin
    right = data.width-3.5*data.margin
    for i in range(16):
        top = vTop+(data.margin/2+bheight)*i
        coords = left,top,right,top+bheight
        fill = data.color[i]
        text = str(i+1)
        textSpecs = (left-0.5*data.margin,top+bheight/2,
            "e","Arial 10 bold","black")
        data.icons.append(Icon(coords,fill,text,textSpecs,
            legendIcon(i,data)))

def initButtonIcons(data):
    bwidth = data.width/3/5
    bheight = data.height/4/5

    top = data.height*3/4+bheight*15/5
    bot = top+bheight 
    for i in range(3):
        left = data.width/6+bwidth*(i*12+1)/5
        right = left+bwidth*11/5
        coords = left,top,right,bot
        fill = "white"
        font,anchor,tFill = "Arial 10 bold","w","black"
        if i == 0: 
            text = "Filename: " + data.fileName
        elif i == 1: 
            text = "Time between points (minutes): " + str(data.spacing)
        elif i == 2: 
            text = "Start" if not data.running else "Stop"
            tFill = "red" if data.running else "black"
            font,anchor = "Arial 15 bold","center"
            left = left+(right-left)/2-5
        elif i == 3:
            text = "Set baseline"
            anchor = "center"
            left = left+(right-left)/2-5
            font = "Arial 15 bold"
        tTop = top+bheight/2
        textSpecs = left+5,tTop,anchor,font,tFill
        data.icons.append(Icon(coords,fill,text,textSpecs,
            buttonIcon(i,data)))

def initIcons(data):
    data.icons = []
    initNameIcons(data)
    initLegendIcons(data)
    initButtonIcons(data)

def color(val):
    if val: return "red"
    else: "black"

def emptyList():
    return [[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]]

def initTest(data):
    data.baseline = [0]*16
    data.basetemp = [0]*16
    data.midPoints = emptyList()
    data.midTemps = emptyList()
    data.rawGraph = emptyGraph(data,(2*data.margin,data.margin,
        data.width/2-3*data.margin,data.height*3/4-data.margin),"Raw Data")
    data.normGraph = emptyGraph(data,(data.width/2-2*data.margin,
        data.margin,data.width-7*data.margin,data.height*3/4-data.margin),
            "Normalized Data")
    data.pressures = [""] * 16
    data.highPoint = 0
    data.startTime = time.time()
    data.lastTime = time.time()
    data.lastSave = time.time()

def init(data):
    data.scanner = Scanner().withDelegate(ScanDelegate())
    data.sAddr = ["80:ea:ca:10:02:dd", "81:ea:ca:20:00:b3",
                  "82:ea:ca:30:01:ee","83:ea:ca:40:01:00",
                  "","","","","","","","","","","",""]
    data.color = ["#3CA4BB","#BE1E1E","#E9E610","#09BB0C",
                  "#030100","#131178","#E23D95","#5ECA92",
                  "#FF9203","white","white","white",
                  "white","white","white","white"]
    data.margin = data.width/80
    data.label = [""]*16
    data.label[0] = "one"
    data.label[1] = "two"
    data.label[2] = "three"
    data.label[3] = "four"
    
    initTest(data)

    data.fileName = "test.txt"
    data.newData = ""
    data.spacing = 3
    data.filler = "None"

    data.editing = None
    data.time = 0
    data.pipe = False
    data.editText = ""
    data.error = ""

    data.basing = False
    data.running = False

    data.scanner = Scanner().withDelegate(ScanDelegate())
    initIcons(data)

def mousePressed(event, data):
    if data.editing != None: return
    for icon in data.icons:
        if icon.isIn(event.x,event.y): icon.click(data)

def clearEdit(data):
    data.pipe = False
    data.editing.text = piping(data,data.editing.text)
    data.editing = None
    data.editText = ""

def keyPressed(event, data): 
    if data.editing != None:
        if event.keysym == "Return":
            if data.editText == "folder":
                name = data.editing.text.split(" ")[-1].strip("|")
                makeFolder(name)
                try: 
                    if not isValidFile(name): writeFile(name,"")
                    clearEdit(data)
                    data.fileName = name
                except: pass
            elif data.editText == "time":
                num = data.editing.text.split(" ")[-1].strip("|")
                try: 
                    data.spacing = float(num)
                    clearEdit(data)
                except: pass
            elif data.editText in map(str,range(16)):
                data.label[int(data.editText)] = (
                    data.editing.text.split(" ")[-1].strip("|"))
                clearEdit(data)
        elif event.keysym == "BackSpace":
            if len(data.editing.text.split(" ")[-1].strip("|")) > 0:
                data.editing.updateText(data,data.editing.text.strip("|")[:-1])
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
    folders = foldName.split("/")[:-1]
    for i in range(len(folders)):
        if not isValidFolder("/".join(folders[:i+1])):
            subprocess.check_call(["mkdir","/".join(folders[:i+1])])

def piping(data,text):
    if data.pipe: return text.strip("|") + "|"
    elif "|" in text: return text.strip("|")
    else: return text

def runScan(data):
    try:
        devices = data.scanner.scan(2.0)
        ManuData = ""
        for dev in devices:
            entry = 0
            for saddr in data.sAddr:
                if (dev.addr == saddr):
                    for (adtype, desc, value) in dev.getScanData():
                        if (desc == "Manufacturer"): ManuData = value
                    if (ManuData == ""): continue
                    pressure = toPressure(hexify(ManuData[16:24]))
                    temp = toTemp(hexify(ManuData[24:32]))
                    data.midPoints[entry].append(pressure)
                    data.midTemps[entry].append(temp)
                entry += 1
    except: os.popen("sudo hciconfig hci0 reset")

def average(lst):
    if lst == []: return None
    total = 0
    for i in range(len(lst)):
        total += lst[i]
    return round(total/(len(lst)),2)

def averagePoints(data):
    for i in range(len(data.midPoints)):
        avg = average(data.midPoints[i])
        temp = average(data.midTemps[i])
        if i == 0: data.newData += "\n" + str(
            round(data.lastTime-data.startTime,2))
        if data.label[i] != "": 
            if avg == None:
                data.newData += "," + data.filler + "," + data.filler
            else:
                if avg > data.highPoint: data.highPoint = avg
                data.rawGraph.addPoint((data.lastTime-data.startTime,avg),i)
                norm = avg - data.baseline[i]
                data.normGraph.addPoint((data.lastTime-data.startTime,norm),i)
                data.newData += "," + str(avg) + "," + str(temp)
                data.pressures[i] = avg
        else: continue
    data.midPoints = emptyList()

def scaleGraphs(data):
    if (data.lastTime - data.startTime 
        > data.rawGraph.xlim[1]):
        newX = data.lastTime - data.startTime
        if data.highPoint > data.rawGraph.ylim[1]:
            data.rawGraph.updateLimits((0,int(newX*1.5)),
                (0,int(data.highPoint*1.5)))
            data.normGraph.updateLimits((0,int(newX*1.5)),
                (0,int(data.highPoint*1.5)))
        else:
            data.rawGraph.updateLimits((0,int(newX*1.5)),
                data.rawGraph.ylim)
            data.normGraph.updateLimits((0,int(newX*1.5)),
                data.normGraph.ylim)
    elif data.highPoint > data.rawGraph.ylim[1]:
            data.rawGraph.updateLimits(data.rawGraph.xlim,
                (0,int(data.highPoint*1.5)))
            data.normGraph.updateLimits(data.normGraph.xlim,
                (0,int(data.highPoint*1.5)))

def save(data):
    try: contents = readFile(data.fileName)
    except: 
        contents = "Time"
        for i in range(len(data.midPoints)):
            if data.label[i] == "": continue
            contents += "," + data.label[i] + ",Temp"
    contents += data.newData
    contents = contents.strip()
    writeFile(data.fileName, contents)
    data.newData = ""

def interpolate(data,x1,x2,y1,y2,x):
    if data.filler in (x1,x2,y1,y2,x): return data.filler
    return str(round(float(y1)+(float(x)-
        float(x1))*(float(y2)-float(y1))/(float(x2)-float(x1)),2))

def process(data):
    # post-processing of data in file
    contents = readFile(data.fileName)
    lines = contents.split("\n")
    points = []
    for line in lines:
        points.append(line.split(","))
    
    for j in range(1,len(points[0])):
        if j % 2 == 1: LB = 0,data.baseline[j/2]
        else: LB = 0,data.basetemp[(j-1)/2]
        UB = None
        for i in range(1,len(points)):
            if points[i][j] == data.filler: 
                if UB == None:
                    move = 1
                    while (UB == None):
                        if i + move >= len(points): 
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
            else:
                LB = points[i][0],points[i][j]
                UB = None
    for i in range(len(points)):
        points[i] = (",").join(points[i])
    contents = ("\n").join(points)
    writeFile(data.fileName,contents)
    print(data.baseline,data.basetemp)

def timerFired(data):
    if data.running: runScan(data)
    if data.running and (time.time() - data.lastTime > data.spacing * 60):
        data.lastTime = time.time()
        averagePoints(data)
        scaleGraphs(data)
    # every 5 minutes write output file (ensure minimal data loss) 
    if data.running and (time.time() - data.startTime > 5 * 60):
        data.lastSave = time.time()
        save(data)
    if data.editing != None and data.time % 5 == 0:
        data.pipe = not data.pipe
        data.editing.updateText(data,piping(data,data.editing.text))
    if data.basing:
        runScan(data)
        enoughPoints = True
        for i in range(len(data.midPoints)):
            if len(data.midPoints[i]) > 0: 
                data.pressures[i] = data.midPoints[i][-1]
            if len(data.midPoints[i]) > 1:
                if data.midPoints[i][-2] != data.midPoints[i][-1]:
                    data.stableSince = time.time()
            elif data.label[i] != "": enoughPoints = False
        if time.time() - data.stableSince > 60 and enoughPoints:
            data.basing = False
            for i in range(len(data.midPoints)):
                if data.label[i] != "": 
                    data.baseline[i] = data.midPoints[i][-1]
                    data.basetemp[i] = data.midTemps[i][-1]
            data.running = True
            data.midPoints = emptyList()
            data.midTemps = emptyList()
            data.error = ""

    data.time += 1

def drawPressures(canvas,data):
    vTop = 2*data.margin
    vBot = data.height*3/4
    bheight = (vBot-vTop-15*(data.margin/2))/16
    left = data.width-3*data.margin
    for i in range(16):
        top = vTop+(data.margin/2+bheight)*i+bheight/2
        text = "" if (data.label[i] == "") else str(data.pressures[i])
        canvas.create_text(left,top,text=text,
            anchor="w",font="Arial 10 bold",fill="black")

def redrawAll(canvas, data):
    canvas.create_rectangle(-5,-5,data.width+5,data.height+5,fill="gray72")
    data.rawGraph.drawGraph(canvas,data)
    data.normGraph.drawGraph(canvas,data)
    for icon in data.icons:
        icon.drawIcon(canvas)
    drawPressures(canvas,data)
    canvas.create_text(data.width/2-0.5*data.margin,
        data.height*3/4-0.5*data.margin,text=data.error,font = "Arial 12 bold",
        fill="red")

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
    # print(data.color)

run(1600, 800)