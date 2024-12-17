"""
Main GUI for Lipshultz group UV-vis plotting utility "mainGUI.py"

programmed by: Noah Schwartzapfel
currently maintained by: Noah Schwartzapfel

for easy processing of Shimadzu UV-vis data into custom plots
containing several data series with normalization of maxima

made to run on Streamlit community cloud

see GitHub for commit history (i'm lazy)
"""
import streamlit as st # for GUI business
from streamlit_extras.grid import grid # b/c streamlit hates nested GUI elements
from scipy.constants import h,c,e # for unit conversions
from finalprojectlib import DataWrapper, Plotter # for data processing and formatting and plot generation
import io # for handling byte data
from plotly.io import write_image # for generating images
from xml.etree.ElementTree import ParseError # if file parsing fails
import zipfile # for generating zip folders
from datetime import datetime # for getting time of day of error
import traceback # for getting exception tracebacks
import hashlib # for getting hashes for file content comparison

# takes a number (having to do with photon energy) in whatever units and outputs it into nm 
def to_nm(num, units):
    if units == "wavenumbers":
        return (1/num) * (10**7) 
    elif units == "electronvolts":
        return ((h/e)*c/num) * (10**9)
    elif units == "wavelength":
        return num

# applies to_nm() to a range, yes im this lazy, it saves time
def range_to_nm(xRange, units):
    nmRange = []
    for num in xRange:
        nmRange.append(to_nm(num, units))
    return sorted(nmRange)

# writes image data as bytes
# (this took a while to understand)
def generate_download(fig, format):
    buffer = io.BytesIO()
    write_image(fig, file = buffer, format = format) # writing image to buffer
    buffer.seek(0)

    return buffer

# generates error folder containing txt file of exception and data file 
def getErrorFolder(ex, data = None):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") # gets time of error
    folderName = f"error_{timestamp}"
    
    zipBuffer = io.BytesIO()
    with zipfile.ZipFile(zipBuffer, "w", zipfile.ZIP_DEFLATED) as zipFile:
        zipFile.writestr(f"{folderName}/exception.txt", f"{type(ex).__name__}: {str(ex)}\n\n{traceback.format_exc()}") # prints <exception name>: <exception description>\n\n<traceback> to txt file

        if data is not None: # writes XML file
            zipFile.writestr(f"{folderName}/error_data.xml", data)

    zipBuffer.seek(0)

    return zipBuffer, folderName

def handleException(ex):
    st.header("🚨Error!🚨") # you can use emoji inline what a wonder of modern technology
    st.exception(ex)
    st.divider()
    
    if dataWrapper is not None:
        dataWrapper.raw.seek(0)
        byteData = dataWrapper.raw.read()
        errorZip, folderName = getErrorFolder(ex, data = byteData) # generates zip folder of exception and data (if present)
    else:
        errorZip, folderName = getErrorFolder(ex)
    
    st.download_button(
    label="➡️Download Error Folder⬅️",
    data = errorZip,
    file_name = f"{folderName}.zip",
    mime="application/zip",
    type = "primary"
    )
    
    st.write("""
    Please send this folder along with a description of what happened
    to either Noah Schwartzapfel or whoever is managing this app.\n
    Noah's email: njschwartzapfel@gmail.com
    """) # if someone else is managing this they'd put their info here

# used to get file hash to compare file contents
def getHash(file):
    file.seek(0)
    hash = hashlib.sha256(file.read()).hexdigest()
    file.seek(0)

    return hash

# whether to include the developer tools menu at bottom
developerMode = True

# VVV where the actual GUI begins VVV
st.title("UV-Vis Analysis Tool")

# tabs
uploadAndSelect, mainPlot = st.tabs(["Upload Data & Select Plots", "Main Plot"])
sidebar = st.sidebar

# this is the section where the raw XML file is inputted,
# parsed, and each trace is layed out for formatting
with uploadAndSelect:
    try:
        fileUploadPanel = st.container()
        miniPlotPanel = st.container()
    
        with fileUploadPanel:
            st.header("File Upload")
            dataWrapper = None
            dataUpload = st.file_uploader("Choose raw data file", type=["xml"]) # just XML for now, i'd do CSV but that means people can edit the CSVs in excel, and people editing stuff gives me, the programmer, great pain

            # to whoever doesn't know:
            # st.session_state is a dict containing data that's maintained after every rerun
            if "raw" not in st.session_state: # initializing raw data
                st.session_state["raw"] = None
            
            # if there's another upload who's contents are different
            # (st.file_uploader returns a different object at every rerun so you have to compare the hashes, whyyyyy)
            if (dataUpload is not None) and (getHash(dataUpload) != st.session_state["raw"]):
                st.session_state = {}
                st.session_state["raw"] = getHash(dataUpload)
            
            if dataUpload is not None:
                dataWrapper = DataWrapper(raw = dataUpload)
                try:
                    dataWrapper.parseData()
                    st.success("File parsed successfully!")
                    plotter = Plotter(dataWrapper)
                except ParseError as ex:
                    st.error("Error: Invalid File")
                    st.exception(ex)
                    dataWrapper = None # prevents rest of GUI from generating
            
            else:
                dataWrapper = None 
           
            st.divider()
        
        with miniPlotPanel: # each trace will be in its own plotly plot to select normalization range (and to actually include it or not in the main plot)
            if dataWrapper is not None:
                numTraces = int(len(dataWrapper.x))

                st.header("Trace Selection")
                normalize = st.toggle("Normalize?", value = True, key = "normalizeToggle") # whether to normalize or just use raw data

                gridSpec = [1] * numTraces # one row for each trace
                miniPlotGrid = grid(*gridSpec)
                
                if "includeList" not in st.session_state:
                    st.session_state["includeList"] = [True for i in range(numTraces)] # include everything by default

                # initially full domain for each trace
                normRange = [(minX,maxX) for minX,maxX in zip(dataWrapper.minX, dataWrapper.maxX)]
                
                # initializing the normRange and fig states for each trace in session_state
                for i,(x,y) in enumerate(zip(dataWrapper.x, dataWrapper.y)):
                    if f"normRange_{i}" not in st.session_state:
                        st.session_state[f"normRange_{i}"] = (dataWrapper.minX[i],dataWrapper.maxX[i])
                    
                    if f"include_{i}" not in st.session_state:
                        st.session_state[f"include_{i}"] = True

                for i,(x, y, name) in enumerate(zip(dataWrapper.x, dataWrapper.y, dataWrapper.names)):
                    plotContainer = miniPlotGrid.container()
                    options = miniPlotGrid.container()
                    
                    with options:
                        include = st.toggle("Include?", value = st.session_state[f"include_{i}"], key = f"includeToggle_{i}") # whether to include trace in main plot
                        
                        if include is not st.session_state[f"include_{i}"]:
                            st.session_state["includeList"][i] = include
                            st.session_state[f"include_{i}"] = include
                            st.rerun() # carries changes to session_state back to top of code

                        with plotContainer:
                            st.subheader(name)
                            
                            currentFig = plotter.miniPlots[i]

                            # generates the miniplot with norm bounds drawn if normalize toggle is on
                            plotter.updateMiniPlot(i, normRange = st.session_state[f"normRange_{i}"] if normalize else None)
                
                            if normalize:
                                # listens for selection
                                selectEvent = st.plotly_chart(currentFig, on_select = "rerun", selection_mode = "box", key = f"chart_{i}")
                            
                                if selectEvent["selection"]["box"] != []:
                                    selectRange = selectEvent["selection"]["box"][0]["x"] # whoever the people are that program plotly need to realize that just because you *can* nest dicts in dicts doesn't mean you always *should*
                                    st.session_state[f"normRange_{i}"] = (float(min(selectRange)), float(max(selectRange)))
                                    st.rerun()
                            else:
                                plotter.updateMiniPlot(i)
                                st.plotly_chart(currentFig, key = f"chart_{i}")

                        if normalize:
                            normRangeSelection = st.slider("Select range to normalize against:",
                            min_value = dataWrapper.minX[i],
                            max_value = dataWrapper.maxX[i],
                            value = st.session_state[f"normRange_{i}"], # if you select on the plot, the slider is updated too
                            step = 0.01,
                            key = f"slider_{i}"
                            )
                            normRange[i] = normRangeSelection

                            if normRangeSelection != st.session_state[f"normRange_{i}"]:
                                st.session_state[f"normRange_{i}"] = normRangeSelection
                                st.rerun() # ditto but for manually using the slider
                                
                        else:
                            normRange = None
                
            if dataWrapper is not None:
                with sidebar: # used when going to main plot tab, easy to see which plots are selected and where the normalization is
                    for i,name in enumerate(dataWrapper.names):
                        st.subheader(name)
                        st.plotly_chart(plotter.miniPlots[i])
                        include = st.toggle("Include?", value = st.session_state[f"include_{i}"], key = f"includeToggleSidebar_{i}") # whether to include trace in main plot
                        
                        if include is not st.session_state[f"include_{i}"]:
                            st.session_state["includeList"][i] = include
                            st.session_state[f"include_{i}"] = include
                            st.rerun()

                        st.divider()



    except Exception as ex:
        handleException(ex)

with mainPlot:
    try:
        if dataWrapper is not None:
            minX = min(dataWrapper.minX)
            maxX = max(dataWrapper.maxX)
            
            # <initializing session_state>
            defaults = {
                "fileType": "png",
                "minZero": True,
                "mainRange": (minX, maxX),
                "min_value": minX,
                "max_value": maxX,
                "units": "wavelength"
            }

            for default in defaults:
                if default not in st.session_state:
                    st.session_state[default] = defaults[default]
            # </initializing session_state>

            # formatting the data and updating the plot
            dataWrapper.formatData(xRange_in_nm = range_to_nm(st.session_state["mainRange"], st.session_state["units"]), normalize = normalize, normRange = normRange, xType = st.session_state["units"], inclusion = st.session_state["includeList"], aboveZero = st.session_state["minZero"])
            plotter.updateMainPlot()
            
            st.header("Main Plot")
            st.plotly_chart(plotter.mainFig)
                
            unitsSelection = st.selectbox(
                    "Choose units for x-axis",
                    ["wavelength (nm)", "wavenumbers (cm⁻¹)", "energy (eV)"],
                    index = 0,
                    key = "unitsSelection"
                )
            
            # just removes the units in the () to compare with session_state
            units_to_compare = {"wavelength (nm)":"wavelength", 
                "wavenumbers (cm⁻¹)":"wavenumbers",
                "energy (eV)":"electronvolts"}[unitsSelection] # this is a clever trick from chatGPT, having a variable key at the end of an explicit dict
            
            if units_to_compare != st.session_state["units"]:
                match unitsSelection:
                    case "wavelength (nm)":
                        units = "wavelength"
                        min_value = minX
                        max_value = maxX
                    case "wavenumbers (cm⁻¹)":
                        units = "wavenumbers"
                        min_value = (10**7)/maxX
                        max_value = (10**7)/minX
                    case "energy (eV)":
                        units = "electronvolts"
                        min_value = (h*c/e)/(maxX * (10**-9))
                        max_value = (h*c/e)/(minX * (10**-9))
                
                st.session_state["units"] = units

                # VVV used for x-range slider VVV
                st.session_state["mainRange"] = (min_value,max_value)
                st.session_state["min_value"] = min_value
                st.session_state["max_value"] = max_value

                st.rerun()

            
            xRange = st.slider(
                "Select range to plot over:",
                min_value = st.session_state["min_value"],
                max_value = st.session_state["max_value"],
                value = st.session_state["mainRange"],
                key = f"slider_mainRange"
            )

            if xRange != st.session_state["mainRange"]:
                st.session_state["mainRange"] = xRange
                st.rerun()

            
            minZero = st.toggle("Minimize at 0?", value = st.session_state["minZero"], key = "minZeroToggle")
            if minZero is not st.session_state["minZero"]:
                st.session_state["minZero"] = minZero
                st.rerun()
            
            st.divider()

            st.subheader("Downloads")
            with st.container():
                colLeft,colRight = st.columns(2)

                with colLeft:
                    fileType = st.segmented_control(
                        "Choose a file type:",
                        ["PNG", "SVG", "JPEG"],
                        selection_mode = "single",
                        default = "PNG",
                        key = "fileTypeSelection"
                    ).lower()

                    st.session_state["fileType"] = fileType # this session_state value is being used after this so i don't need to do the whole rerun thing

                    mimeType = {
                        "png": "image/png",
                        "jpeg": "image/jpeg",
                        "svg": "image/svg+xml"
                    }[fileType] # for streamlit to know what kind of data it's working with (generated from chatGPT of course)

                    st.download_button(
                        "Download an image of the plot",
                        generate_download(plotter.mainFig, st.session_state["fileType"]),
                        file_name = f"{", ".join(plotter.plotTitles)}.{fileType}",
                        mime = mimeType,
                        type = "secondary"
                    ) # image of plot
                
                with colRight:
                    st.download_button(
                        "Download the formatted CSV data",
                        dataWrapper.makeFolder(),
                        file_name = f"{", ".join(plotter.plotTitles)}.zip",
                        mime = "application/zip",
                        type = "secondary"
                    ) # zip of formatted CSV data

    except Exception as ex:
        handleException(ex)

try:
    with st.popover("Developer Tools", disabled = not developerMode, use_container_width = True):
        error = st.button("Throw Error", key = "errorButton") # error testing
        if error:
            raise Exception

        showSessionState = st.button("Show st.session_state", key = "showSessionStateButton") # checking session_state
        if showSessionState:
            st.code(f"st.session_state = {st.session_state}")

        showInclusionList = st.button("Show inclusion list", key = "showIncludeList") # to see inclusion list
        if showInclusionList:
            st.code(f"{st.session_state["includeList"]}")

except Exception as ex:
    handleException(ex)