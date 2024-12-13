"""
finalprojectlib
"""
import numpy as np
import xml.etree.ElementTree as ET
import os
import io
from pathlib import Path
from plotly.subplots import make_subplots
import scipy.constants as cnst
from codechembook.chemtools import chemSymbols as cs
import plotly.colors as pc
from tkinter.filedialog import askopenfilename

def fileParser(file, makeDataFolder = False):
    """
    Converts raw or pre-compiled UV-vis data into wavelength and absorbance data arrays

    Required parameters:

        file: file, str, pathlib.Path, list of str, generator
        data file to parse

    Optional Parameters:

        makeDataFolder: bool (default: False)
        if True, a folder "Compiled Data" is created containing CSV files with wavelength and abosrbance data each as columns. No such folder created if False.
    
    Returns:
        wavelengths: list of Numpy arrays, where each array corresponds to a given series's wavelength data
        absorbances: list of Numpy arrays, where each array corresponds to a given series's absorbance data
        names: list of strings, where each string is the name of the data series
    """

    if isinstance(file, io.BytesIO):
        # If file is an UploadedFile (streaming byte data)
        file_stream = io.BytesIO(file.read())  # Wrap file content as a BytesIO object
    elif isinstance(file, (str, Path)):
        # If file is a Path or string (file path)
        file_stream = open(file, "rb")  # Open file as binary stream
    else:
        raise TypeError("Unsupported file type. Must be an UploadedFile or a Path-like object.")
    
    wavelengths = []
    absorbances = []
    names = []
    
    tree = ET.parse(file_stream)
    root = tree.getroot()
    namespaces = {"ss":"urn:schemas-microsoft-com:office:spreadsheet", 
    "ns0":"urn:schemas-microsoft-com:office:spreadsheet"}

    series = [series for series in root.findall(".//ns0:Worksheet", namespaces)] # list of each data series

    for worksheet in series:
        wlList = []
        absList = []
        rows = worksheet.findall(".//ns0:Row", namespaces)[1:] #list of all rows skipping first row
        for i,row in enumerate(rows): # iterates through list of all row elements indexed by i
            cellsInRow = row.findall("ns0:Cell", namespaces) # returns list of cells for given row
            
            cellData = [cell.find("ns0:Data", namespaces) for cell in cellsInRow] # extracts data from each sell and puts them in list 
            
            # stores first and second sell data to wavelength and absorbance data respectively
            wl = cellData[0]
            absorb = cellData[1]

            # if looking at first row in row list (second row overall as first is skipped), store the third data element as the name
            if i == 0:
                name = cellData[2]

            # evaluates whether each data value is good to add to the dataset
            try:
                (int(wl.text), float(absorb.text), str(name.text)) #tests if the .text attribute returns the proper data types
            except:
                print(f"BADROWERROR: ROW #{i+2}")
                wlValue = "BAD ROW"
                absValue = "BAD ROW"
            else:
                wlValue=int(wl.text)
                absValue=float(absorb.text)
                nameValue = str(name.text)
            finally:
                wlList.append(wlValue)
                absList.append(absValue)

        wavelengths.append(np.array(wlList))
        absorbances.append(np.array(absList))
        names.append(nameValue)
    
    # writes to folder CSV files for each data series
    if makeDataFolder:
        dataFolderName = "Compiled Data"
        os.makedirs(dataFolderName, exist_ok=True)

        for i in range(len(series)):
            colPackagedData = np.column_stack((wavelengths[i], absorbances[i]))
            np.savetxt(os.path.join(dataFolderName, f"{names[i]}.csv"), colPackagedData, fmt=["%d", "%f"], delimiter = ",", header = "wavelength(nm),absorbance", comments = "")

    # in case the user has a CSV instead, code block WIP
    """
    elif (fileType == ".csv") or file.is_dir():
        if file.is_dir():
            series = list(file.glob("*.csv"))
        else:
            series = [file]

        for trace in series:
            cols = np.genfromtxt(trace, delimiter = ",", dtype = None, unpack = True)

            if len(cols) == 2:
                for col in cols:
                    if "wavelength" in str(col[0]):
                        wlArray = int(col[1:])
                    elif "abs" in str(col[0]):
                        absArray = float(col[1:])
                wavelengths.append(wlArray)
                absorbances.append(absArray)
            else:
                print("incorrecrly formatted CSV")
    """
    return wavelengths, absorbances, names
    

def seriesFormat(wavelengths, absorbances, xRange = None, normalize = True, normMethod = "maxdiv", normRange = None, xType = "wavelength", inclusion = None):
    """
    takes in parsed absorbance and wavelength data and outputs formatted data for later plotting

    Required parameters:

    wavelengths: list or Numpy array of Numpy arrays
    corresponds to the wavelength data for each data series

    absorbances: wavelengths: list or Numpy array of Numpy arrays
    corresponds to the absorbance data for each data series

    Optional parameters:

    selector: int, tuple, list, numpy.array (default: None)
    selects which of the data series to display in the plot (inclusive, exclusive), e.g. selector = 2 will display the third data series, selector = (2,5) will display the second through fourth data series

    xRange: tuple, list, numpy.array (default: None)
    specifies range to plot (inclusive, exclusive), if None, plots across whole x-axis domain

    normalize: bool (default: True)
    whether to normalize the data, normalize = False returns the raw data

    normMethod: str (default: "maxminus")
    specifies normalization method

    options:
    "maxminus" - finds the maximum absorbance value and subtracts it from every other value
    "maxdiv" - finds the maximum absorbance value and and divides every other value by it

    normRange: tuple, list, numpy.array, str (default: None)
    specifies range to look for maximum value for normalization

    options:
    tuple, list, or numpy.array: denotes normalization range (inclusive, exclusive)
    normalization ranges can be specified for each trace as a tuple, list, or numpy.array of ranges

    None: normRange is whole x-axis domain

    xType: str (default: "wavelength")
    format of x-axis data

    options:
    "wavelength" - wavelength in nanometers
    "wavenumbers" - wavenumbers in inverse centimeters
    "joules" - energy in joules
    "electronvolts" or "ev"- energy in electronvolts

    Returns:
        plotX: list of Numpy arrays where each array is the normalized and sliced x-data
        plotY: list of Numpy arrays where each array is the normalized and sliced absorbance data
        xAxisTitle: str which corresponds to x-axis title according to xType
    """

    # generates a boolean mask for each trace according to the desired range
    if xRange is not None:
        rangeMasks = []
        for i,wl in enumerate(wavelengths):
            rangeMask = (wl >= xRange[0]) & (wl < xRange[1])
            rangeMasks.append(rangeMask) # adding the ith trace's mask to a list
    else:
        rangeMasks = []
        for wl in wavelengths:
            rangeMasks.append(np.array([True for i in range(len(wl))]))
        
    # generates a boolean mask for each trace according to the desired normalization range 
    normMasks = []
    if normRange is not None:
        for i,wl in enumerate(wavelengths):
            if type(normRange[0]) in [int, float]: # one norm range for all traces
                normMask = (wl >= normRange[0]) & (wl <= normRange[1])
                normMasks.append(normMask)
                normRange = [normRange for i in range(len(wavelengths))] #if normRange is a single tuple (a,b), this redefines it do be list((a,b)), makes things easier down the line
            
            else: # i.e. if each trace has its own norm range
                normMask = (wl >= normRange[i][0]) & (wl < normRange[i][1])
                normMasks.append(normMask)
    else:
        for wl in wavelengths:
                allMask = np.array([True for i in range(len(wl))]) # creates bool mask that is [T,T,..,T] as long as each wl trace, selects entire wl range
                normMasks.append(allMask)   
    # normalization: computing normalization value and scaling absorbances
    if normalize:
        maxWLs = []
    
        for i, absorb in enumerate(absorbances):
            maxAbsorb = absorb[(normMasks[i]) & (~np.isnan(absorb))].max() # looks for max item of masked absorbance array, skipping nans
            if normMethod == "maxdiv":
                absorbances[i] = absorb/maxAbsorb
            elif normMethod == "maxminus":
                absorbances[i] = absorb - maxAbsorb   

            # adding max norm points to list
            indexArray = np.where(absorb == maxAbsorb)
            for index in indexArray:
                if normRange is None:
                    maxWL = wavelengths[i][index].item()
                elif (wavelengths[i][index] >= normRange[i][0]) and (wavelengths[i][index] < normRange[i][1]): # <-- this is where it made things easier down the line
                    maxWL = wavelengths[i][index].item()

            maxWLs.append(maxWL)
    else:
        maxWLs = None

    # slicing the wavelength and absorbance arrays
    for i,rangeMask in enumerate(rangeMasks):
        wavelengths[i] = wavelengths[i][rangeMask]
        absorbances[i] = absorbances[i][rangeMask]
    
    plotX = list(wavelengths)
    plotY = list(absorbances)

    # formatting x-axis title according to desired x unit

    # transforms wavelength x-data into proper units
    match xType:
        case "wavelength":
            xAxisTitle = "wavelength (nm)"

        case "wavenumbers":
            for i,wn in enumerate(plotX):
                plotX[i] = (10**7)/wn #cm^-1
            
            xAxisTitle = f"wavenumbers (cm{cs("^-")}{cs("^1")})"

        case "joules":
            for i,jl in enumerate(plotX):
                plotX[i] = (cnst.h * cnst.c * (10**-9))/jl #J

            xAxisTitle = "energy (J)"

        case "electronvolts" | "ev":
            for i,eV in enumerate(plotX):
                plotX[i] = (cnst.h * cnst.c * (10**9))/(cnst.e * eV) #eV
            
            xAxisTitle = "energy (eV)"
    
    if inclusion is not None:
        plotDataSeries = [plotX, plotY, maxWLs]

        for i,series in enumerate(plotDataSeries):
            if series is maxWLs:
                continue

            temp = []
            for include,trace in zip(inclusion, series):
                if include:
                    temp.append(trace)
                else:
                    continue

            plotDataSeries[i] = temp

        return *plotDataSeries, xAxisTitle

    else:
        return plotX, plotY, maxWLs, xAxisTitle
            
    
class DataWrapper:
    """
    DataWrapper objects accept the raw XML data and incorporate fileParser() and seriesFormat() to parse and format the data.

    Constructor:
        DataWrapper(raw: str or pathlib.Path, **kwargs):
            raw (default None): specifies path of raw XML file
            **kwargs: extra keyword arguments to save to object as attributes at construction-time
    
    Attributes:
        raw (str or pathlib.Path): specifies path of raw XML file
        x (list of numpy.array): parsed wavelength data (generated by DataWrapper.parseData())
        y (list of numpy.array): parsed absorbance data (generated by DataWrapper.parseData())
        names (list of str): names of each data series (generated by DataWrapper.parseData())
        plotX (list of numpy.array): normalized and formatted x-axis data (generated by DataWrapper.formatData())
        plotY (list of numpy.array): normalized and formatted absorbance data (generated by DataWrapper.formatData())
        xAxisTitle (str): title of x-axis according to xType (generated by DataWrapper.formatData())
        maxWLs (list of str): list of wavelengths of maximum absorbance for each data series (generated by DataWrapper.formatData())
    
    Methods:
        update(**kwargs): updates/sets attribute corresponding to keyword in kwargs to specified value
        askForFile(): opens file dialog box to select raw data file
        parseData(makeDataFolder = False): runs fileParser() with raw data file and returns x, y and names
        formatData(**kwargs): runs seriesFormat(), passing keywords through kwargs, returning formatted x and y data, xAxisTitle, and maxWLs
    """
    
    def __init__(self, raw = None, **kwargs):
        self.raw = raw

        for attribute, value in kwargs.items():
            setattr(self, attribute, value)

    def __getattr__(self, attr):
        return None

    def __repr__(self):
        attrStr = ", ".join([f"{attribute} = {value!r}" for attribute,value in self.__dict__.items()])
        return f"{super().__repr__()}\nDataWrapper({attrStr})"
    
    def update(self, **kwargs):
        for attribute, value in kwargs.items():
            setattr(self, attribute, value)
    
    def askForFile(self):
        rawData = askopenfilename(title = "Select the Raw Data File", filetypes = [("XML Files", "*.xml"), ("All Files", "*.*")])
        self.raw = rawData 

    def parseData(self, makeDataFolder = False):
        self.x, self.y, self.names = fileParser(self.raw, makeDataFolder = makeDataFolder)

    def formatData(self, **kwargs):
        self.update(**kwargs)
        self.plotX, self.plotY, self.maxWLs, self.xAxisTitle = seriesFormat(self.x, self.y, **kwargs)
        
    def setPlotTitles(self):
        titles = []
        
        for name in self.names:
            segments = name.split("-")
            title = "-".join(segments[0:3])
            if title not in titles:
                titles.append(title)
        
        self.titles = titles
    
    def setUnits(self):
        match self.xAxisTitle:
            case "wavelength (nm)":
                self.units = "nm"
            
            case xAxisTitle if "cm" in xAxisTitle:
                self.units = f"cm{cs("^-")}{cs("^1")}"
            
            case "energy (J)":
                self.units = "J"
            
            case "energy (eV)":
                self.units = "eV"

class Plotter:
    """
    Plotter objects accept a DataWrapper object
    """
    def __init__(self, dataObj):
        self.dataObj = dataObj

        plotTitles = []
        for name in self.dataObj.names:
            segments = name.split("-")
            title = "-".join(segments[0:3])
            if title not in plotTitles:
                plotTitles.append(title)
        
        self.plotTitles = plotTitles

        match self.dataObj.xAxisTitle:
            case "wavelength (nm)":
                self.units = "nm"
            
            case xAxisTitle if "cm" in xAxisTitle:
                self.units = f"cm{cs("^-")}{cs("^1")}"
            
            case "energy (J)":
                self.units = "J"
            
            case "energy (eV)":
                self.units = "eV"

    def __getattr__(self, attr):
        return None
    
    def __repr__(self):
        attrStr = ", ".join([f"{attribute} = {value!r}" for attribute,value in self.__dict__.items()])
        return f"{super().__repr__()}\nPlotter({attrStr})"
    
    def update(self, **kwargs):
        for attribute, value in kwargs.items():
            setattr(self, attribute, value)

    def updateMainPlot(self):
        fig = make_subplots()
        colors = pc.qualitative.D3
        traceColors = [colors[i % len(colors)] for i in range(len(self.dataObj.plotX))]
        
        for i, (color, wl, absorb) in enumerate(zip(traceColors, self.dataObj.plotX, self.dataObj.plotY)):
            fig.add_scatter(x = wl, y = absorb, mode = "lines", line = dict(color = color), showlegend = True, legendgroup = str(i))
        
        if self.dataObj.normalize is True:
            for i, (name, maxWL, color) in enumerate(zip(self.dataObj.names, self.dataObj.maxWLs, traceColors)):
                fig.update_traces(selector = i, name = f"{name}<br>max absorb @ {maxWL:3d}{self.units}")
        else:
             for i, (name, color) in enumerate(zip(self.dataObj.names, traceColors)):
                fig.update_traces(selector = i, name = name)
        
        fig.update_xaxes(title = self.dataObj.xAxisTitle)
        if self.dataObj.normalize is True:
            fig.update_yaxes(title = "absorbance<br>(normalized)", range = [0,1.1])
        else:
            fig.update_yaxes(title = "absorbance")
        

        fig.update_layout(template = "simple_white", title = f"{", ".join(self.plotTitles)}", title_x = 0.5, title_xanchor = "center")

        self.mainFig = fig

# test case
if __name__ == "__main__":
    data = DataWrapper(raw = r"G:\Shared drives\Chemistry_LipshultzGroup\Data\Alumni\ALM\ALM-I-UV_VIS\ALM-I-185\RAW DATA\ALM-I-185.xml")
    data.parseData()
    data.formatData(xRange = None, normalize = True)
    plotter = Plotter(data)
    plotter.updateMainPlot()
    plotter.mainFig.show()