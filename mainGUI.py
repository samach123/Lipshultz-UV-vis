import streamlit as st
from streamlit_extras.grid import grid
import numpy as np
from plotly.subplots import make_subplots
from scipy.constants import h,c,e
from finalprojectlib import DataWrapper, Plotter
import io
from plotly.io import write_image
from xml.etree.ElementTree import ParseError
import zipfile
from datetime import datetime
import traceback

# takes a number (having to do with photon energy) in whatever units and outputs it into nm 
def to_nm(num, units):
    if units == "wavenumbers":
        return (1/num) * (10**7) 
    elif units == "joules":
        return (h*c/num) * (10**9)
    elif units == "electronvolts":
        return ((h/e)*c/num) * (10**9)
    else:
        return num

# applies to_nm() to a range, yes im this lazy it saves time
def range_to_nm(xRange, units):
    nmRange = []
    for num in xRange:
        nmRange.append(to_nm(num, units))
    return sorted(nmRange)

# writes image data as bytes to buffer
# (this took a while to understand)
def generate_download(fig, format):
    buffer = io.BytesIO()
    write_image(fig, file = buffer, format = format)
    buffer.seek(0)

    return buffer

# generates error folder containing txt file of exception and data file 
def getErrorFolder(ex, data = None):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folderName = f"error_{timestamp}"
    zipBuffer = io.BytesIO()
    

    with zipfile.ZipFile(zipBuffer, "w", zipfile.ZIP_DEFLATED) as zipFile:
        zipFile.writestr(f"{folderName}/exception.txt", f"{type(ex).__name__}: {str(ex)}\n\n{traceback.format_exc()}")

        if data is not None:
            zipFile.writestr(f"{folderName}/error_data.xml", data)

    zipBuffer.seek(0)

    return zipBuffer, folderName

def handleException(ex):
    st.header("🚨Error!🚨")
    st.exception(ex)
    st.divider()
    
    if dataWrapper is not None:
        dataWrapper.raw.seek(0)
        byteData = dataWrapper.raw.read()
        errorZip, folderName = getErrorFolder(ex, data = byteData)
        
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
        """)

errorTest = False

# title
st.title("UV-Vis Analysis Tool")

# tabs
uploadAndSelect, mainPlot = st.tabs(["Upload Data & Select Plots", "Main Plot"])

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
            if dataUpload is not None:
                dataWrapper = DataWrapper(dataUpload)
                try:
                    dataWrapper.parseData()
                    st.success("File parsed successfully!")
                except ParseError as ex:
                    st.error("Error: Invalid File")
                    st.exception(ex)
                    
                    dataWrapper = None
                    
            st.divider()
        
        with miniPlotPanel: # each trace will be in its own plotly plot to select normalization range (and to actually include it or not in the main plot)
            if dataWrapper is not None:
                st.header("Trace Selection")
                normalize = st.toggle("Normalize?", value = True, key = "normalize")
                numTraces = int(len(dataWrapper.names))
                gridSpec = [1] * numTraces # one row for each trace
                miniPlotGrid = grid(*gridSpec)

                minX = float(min([min(x) for x in dataWrapper.x]))
                maxX = float(max([max(x) for x in dataWrapper.x]))
                
                includeList = [True for i in range(len(dataWrapper.names))] # initializing boolean mask for which traces to include
                normRange = [(minX,maxX) for i in range(len(dataWrapper.names))] # initializing list of normalization ranges for each trace
                
                # initializing the normRange and fig states for each trace in session_state
                for i,(x,y) in enumerate(zip(dataWrapper.x, dataWrapper.y)):
                    if f"normRange_{i}" not in st.session_state: # selected normalization range
                        st.session_state[f"normRange_{i}"] = (minX,maxX)

                    if f"fig_{i}" not in st.session_state: # figure object
                        fig = make_subplots()
                        fig.add_scatter(x=x, y=y, mode="lines", showlegend=False)
                        fig.update_xaxes(title="Wavelength (nm)", range = [minX, maxX])
                        fig.update_yaxes(title="Absorbance")
                        fig.update_layout(template="simple_white")

                        st.session_state[f"fig_{i}"] = fig

                for i,(x, y, name) in enumerate(zip(dataWrapper.x, dataWrapper.y, dataWrapper.names)):
                    plotContainer = miniPlotGrid.container()
                    options = miniPlotGrid.container()
                    
                    with options:
                        include = st.toggle("Include?", value = True, key = f"key_{i}") # whether to include trace in main plot
                        includeList[i] = include

                        with plotContainer:
                            st.subheader(name)
                            currentFig = st.session_state[f"fig_{i}"]

                            if normalize:
                                normLeft,normRight = st.session_state[f"normRange_{i}"]
                            
                                currentFig["layout"]["shapes"] = [] # removes all previous vertical lines from fig

                                # vertical lines that show selected norm range
                                currentFig.add_shape(x0 = normLeft, x1 = normLeft, y0 = 0, y1 = 1, xref = "x", yref = "paper", type = "line", line = dict(color = "orange", dash = "dash", width = 2), opacity = 0.8)
                                currentFig.add_shape(x0 = normRight, x1 = normRight, y0 = 0, y1 = 1, xref = "x", yref = "paper", type = "line", line = dict(color = "orange", dash = "dash", width = 2), opacity = 0.8)
                
                            if normalize:
                                # listens for selection
                                selectEvent = st.plotly_chart(currentFig, on_select = "rerun", selection_mode = "box", key = f"chart_{i}")
                            
                                if selectEvent["selection"]["box"] != []:
                                    selectRange = selectEvent["selection"]["box"][0]["x"] # whoever the people are that program plotly need to realize that just because you *can* nest dicts in dicts doesn't mean you always *should*
                                    st.session_state[f"normRange_{i}"] = (float(min(selectRange)), float(max(selectRange)))
                                    st.rerun() # immediately carries updated session_state across the plot
                            else:
                                currentFig["layout"]["shapes"] = []
                                st.plotly_chart(currentFig, key = f"chart_{i}")

                        if normalize:
                            normRangeSelection = st.slider("Select range to normalize against:",
                            min_value = minX,
                            max_value = maxX,
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
                
                with st.popover("Error Testing (for developer use)", disabled = not errorTest):
                    error = st.button("Throw Error", key = "errorMiniPlot")
                    if error:
                        raise Exception

    except Exception as ex:
        handleException(ex)

with mainPlot:
    try:
        if dataWrapper is not None:
            if "fileType" not in st.session_state:
                st.session_state["fileType"] = "png"
            if "minZero" not in st.session_state:
                st.session_state["minZero"] = True
            st.header("Main Plot")
            dataWrapper.formatData(xRange = None, normalize = normalize, normRange = normRange, xType = "wavelength", inclusion = includeList, aboveZero = st.session_state["minZero"])
            plotter = Plotter(dataWrapper)
            

            unitsSelection = st.selectbox(
                    "Choose units for *x*-axis",
                    ["wavelength (nm)", "wavenumbers (cm⁻¹)", "energy (eV)"],
                    index = 0
                )
                
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

            xRange = st.slider(
                "Select range to plot over:",
                min_value = min_value,
                max_value = max_value,
                value=(min_value, max_value),
                key = f"slider_xRange"
            )

            plotter.dataObj.formatData(xRange = range_to_nm(xRange, units), normalize = normalize, normRange = normRange, xType = units, inclusion = includeList)
            plotter.updateMainPlot()
            st.plotly_chart(plotter.mainFig)
            
            minZero = st.toggle("Minimize at 0?", value = st.session_state["minZero"], key = "minZero")
            if minZero != st.session_state["minZero"]:
                st.session_state["minZero"] = minZero
                st.rerun()

            st.divider()
            st.subheader("Download")
            
            fileType = st.segmented_control(
                "Choose a file type:",
                ["PNG", "SVG", "JPEG"],
                selection_mode = "single",
                default = "PNG",
                key = "fileTypeSelection"
            ).lower()

            st.session_state["fileType"] = fileType

            mimeType = {
                "png": "image/png",
                "jpeg": "image/jpeg",
                "svg": "image/svg+xml"
            }[fileType]

            st.download_button(
                "Download an image of the plot",
                generate_download(plotter.mainFig, st.session_state["fileType"]),
                file_name = f"{", ".join(plotter.plotTitles)}.{fileType}",
                mime = mimeType,
                type = "secondary"
            )

            with st.popover("Error Testing (for developer use)", disabled = not errorTest):
                    error = st.button("Throw Error", key = "errorMainPlot")
                    if error:
                        raise Exception
    except Exception as ex:
        handleException(ex)


