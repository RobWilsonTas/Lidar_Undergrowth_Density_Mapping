import glob, os, zipfile, re, shutil, sys, time, pathlib, subprocess, multiprocessing
from os import walk
from PyQt5.QtWidgets import QFileDialog

"""
#################################################################################
User variables
"""

lasToolsDirectory = 'C:\\ProgramData\\LAStools\\bin\\' #Make sure this has double back slashes
compressOptions = 'COMPRESS=LZW|PREDICTOR=2|NUM_THREADS=8|BIGTIFF=IF_SAFER|TILED=YES'

#Run the script and a prompt will appear for you to enter in the zip folder

"""
#################################################################################
First we get the initial zip folder
"""

#This provides a prompt to the user asking them to input the path to the zip folder
infoBox = QMessageBox()
infoBox.setWindowTitle("Before you choose the zip folder with lidar data in it")
infoBox.setText("Ensure that the folder '" + lasToolsDirectory + "' contains LasTools's .exes\n\nAlso make sure that your QGIS project CRS matches the crs of the lidar data.")
infoBox.setStandardButtons(QMessageBox.Ok)
infoBox.exec_()

#Get the zip from the user
zipFolderFromElvis, _ = QFileDialog.getOpenFileName(None, "Select ZIP file", "", "ZIP files (*.zip)")
zipName = os.path.splitext(os.path.basename(zipFolderFromElvis))[0]

"""
#################################################################################
Make all the directories and unzip
"""

processingFolder = os.path.join(os.path.dirname(zipFolderFromElvis), zipName + "Processing")
extractFolder = os.path.join(processingFolder, "extract")
tifFolder = os.path.join(processingFolder, "tif")
lasLazFolder = os.path.join(processingFolder, "laslaz")
lasNormFolder = os.path.join(processingFolder, "lasnorm")
mergedFolder = os.path.join(processingFolder, "merged")
vegDensFolder = os.path.join(processingFolder, "vegdens")

os.makedirs(processingFolder, exist_ok=True)
os.makedirs(tifFolder, exist_ok=True)
os.makedirs(lasLazFolder, exist_ok=True)
os.makedirs(lasNormFolder, exist_ok=True)
os.makedirs(mergedFolder, exist_ok=True)
os.makedirs(vegDensFolder, exist_ok=True)

#This makes sure you are running this is QGIS, where the processing module is available
try:
    import processing
except:
    raise Exception("You need to run this in QGIS")

#Extract the zip folder
try:
    with zipfile.ZipFile(zipFolderFromElvis, "r") as zipFile:
        zipFile.extractall(extractFolder)
except:
    raise Exception("Ok whatever zip folder you gave seems invalid...")

"""
#################################################################################
Sort the contents of the extracted zip
"""

#Ok now look around in the extracted folder for nested zip folders
filePathsList = glob.glob(os.path.join(extractFolder, "**", "*"), recursive=True)

#Get a list of all the zip folders inside the extract
zipList = []
for filePath in filePathsList:
    if filePath.lower().endswith(".zip"):
        zipList.append(filePath)

#Unzip them all
count = 0
for zipPath in zipList:
    count = count + 1
    unzippedFolder = os.path.join(extractFolder, "Unzipped", "UnzippedFolder" + str(count))
    os.makedirs(unzippedFolder, exist_ok=True)
    with zipfile.ZipFile(zipPath, "r") as zipFile:
        zipFile.extractall(unzippedFolder)

#Go through all of the files inside the extracted folder
count = 0
filePathsList = glob.glob(os.path.join(extractFolder, "**", "*"), recursive=True)
for filePath in filePathsList:
    if not os.path.isfile(filePath):
        continue
    fileName = os.path.basename(filePath)
    fileExtension = os.path.splitext(fileName)[1].lower()

    #If it's a tif, assume it's an elevation model
    if fileExtension == ".tif":
        shutil.move(filePath, os.path.join(tifFolder, fileName))
        count = count + 1

    #The point clouds could be las or laz
    elif fileExtension == ".las" or fileExtension == ".laz":
        shutil.move(filePath, os.path.join(lasLazFolder, fileName))
        count = count + 1

print('Yeah successfully sorted ' + str(int(count)) + ' files')
#Delete the temp folder
shutil.rmtree(extractFolder)

"""
#################################################################################
This is where we make a temp bat file that runs the las tools .exes
"""

#Lasground the point clouds so they're normalised
lasGroundResult = subprocess.run([os.path.join(lasToolsDirectory, "lasground_new64.exe"),  "-i", os.path.join(lasLazFolder, "*.las"), os.path.join(lasLazFolder, "*.laz"),
    "-cores", str(multiprocessing.cpu_count()), "-wilderness", "-compute_height", "-replace_z", "-odir", lasNormFolder,
    "-olas", "-demo"], cwd=lasToolsDirectory, capture_output=True, text=True)
    
if lasGroundResult.returncode != 0:
    raise Exception("lasground_new64 failed\n\n" + (lasGroundResult.stderr or lasGroundResult.stdout or "No error text returned"))

#Merge it all
lasMergeResult = subprocess.run([os.path.join(lasToolsDirectory, "lasmerge64.exe"), "-i", os.path.join(lasNormFolder, "*.las"),
    "-o", os.path.join(mergedFolder, "Merged.las"), "-drop_z_below", "-0.5",
    "-drop_z_above", "1.8"], cwd=lasToolsDirectory, capture_output=True, text=True)

if lasMergeResult.returncode != 0:
    raise Exception("lasmerge64 failed\n\n" + (lasMergeResult.stderr or lasMergeResult.stdout or "No error text returned"))

"""
#################################################################################
Sampling the lidar las file at various resolutions, to be later combined
"""

#Repeat the below for 3 different pixel sizes: 2, 3 and 4
for x in range (2,5):

    #Determining the density both for the understory 
    processing.run("grass7:r.in.lidar", {'input':os.path.join(mergedFolder, "Merged.las"),'method':0,'type':1,'base_raster':None,
        'zrange':[0.25,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,
        'resolution':x,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,
        'output':os.path.join(vegDensFolder, "UnderstoryDens" + str(x) + ".tif")})
    
    #Get the density of the understory & ground
    processing.run("grass7:r.in.lidar", {'input':os.path.join(mergedFolder, "Merged.las"),'method':0,'type':1,'base_raster':None,
        'zrange':[-0.5,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,
        'resolution':x,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,
        'output':os.path.join(vegDensFolder, "TotalLowerDens" + str(x) + ".tif")})

    #Set the lower density = 0 to null, so that we don't pretend we have information about places with no lidar returns
    processing.run("gdal:rastercalculator", {'INPUT_A':os.path.join(vegDensFolder, "TotalLowerDens" + str(x) + ".tif"),'BAND_A':1,
        'FORMULA':'where(A == 0, -1, A)','NO_DATA':-1,'EXTENT_OPT':0,'PROJWIN':None,'RTYPE':1,'OPTIONS':compressOptions,'EXTRA':'',
        'OUTPUT':os.path.join(vegDensFolder, "TotalLowerDensNulled" + str(x) + ".tif")})

    #Normalise the understory density, so it is between 0 and 1
    processing.run("gdal:rastercalculator", {'INPUT_A':os.path.join(vegDensFolder, "UnderstoryDens" + str(x) + ".tif"), 'BAND_A':1,
        'INPUT_B':os.path.join(vegDensFolder, "TotalLowerDensNulled" + str(x) + ".tif"), 'BAND_B':1,
        'FORMULA':'A / B', 'NO_DATA':-1, 'EXTENT_OPT':0, 'PROJWIN':None, 'RTYPE':5,
        'OPTIONS':compressOptions, 'EXTRA':'', 'OUTPUT':os.path.join(vegDensFolder, "UnderstoryDensNorm" + str(x) + ".tif")})
        
    #Fill in the holes using interpolation
    processing.run("grass7:r.fill.stats",{'input':os.path.join(vegDensFolder, "UnderstoryDensNorm" + str(x) + ".tif"),
        '-k':True, 'mode':0, '-m':False, 'distance':3, 'minimum':None, 'maximum':None, 'power':2, 'cells':4,
        'output':os.path.join(vegDensFolder, "UnderstoryDensNormFilled" + str(x) + ".tif"),
        'uncertainty':os.path.join(vegDensFolder, "Uncertainty" + str(x) + ".tif")})
        
#Determine the extent for the rasters to be combined to, then drop the lock
fourRaster = QgsRasterLayer(os.path.join(vegDensFolder, "UnderstoryDensNormFilled4.tif"))
fourRasterExtent = fourRaster.extent()
QgsProject.instance().addMapLayer(fourRaster, False)
QgsProject.instance().removeMapLayer(fourRaster.id())

#Resample the rasters, ready for combination
for x in range (2,5):
    processing.run("gdal:warpreproject", {'INPUT':os.path.join(vegDensFolder, "UnderstoryDensNormFilled" + str(x) + ".tif"),'SOURCE_CRS':None,
        'TARGET_CRS':None,'RESAMPLING':1,'NODATA':None,'TARGET_RESOLUTION':1,'OPTIONS':compressOptions,'DATA_TYPE':0,'TARGET_EXTENT':fourRasterExtent,
        'TARGET_EXTENT_CRS':None,'MULTITHREADING':True,'EXTRA':'','OUTPUT':os.path.join(vegDensFolder, "UnderstoryDensNormFilledResamp" + str(x) + ".tif")})


"""
#################################################################################
Creating and styling a the final density raster
"""

#Bring the resampled rasters together
processing.run("gdal:rastercalculator", {'INPUT_A':os.path.join(vegDensFolder, "UnderstoryDensNormFilledResamp2.tif"),'BAND_A':1,
    'INPUT_B':os.path.join(vegDensFolder, "UnderstoryDensNormFilledResamp3.tif"),'BAND_B':1,'INPUT_C':os.path.join(vegDensFolder, "UnderstoryDensNormFilledResamp4.tif"),'BAND_C':1,
    'FORMULA':'A+B+C','NO_DATA':-9999,'RTYPE':5,'OPTIONS':'','EXTRA':'','OUTPUT':os.path.join(vegDensFolder, "CombinedUnderstoryDensity.tif")})

#Style it so that there is a cumulative cut
finalLayer = iface.addRasterLayer(os.path.join(vegDensFolder, "CombinedUnderstoryDensity.tif"), 'CombinedUnderstoryDensity' , '')
provider = finalLayer.dataProvider()
minimum, maximum = provider.cumulativeCut(1, 0.01, 0.99, sampleSize=1000)
multiBandRenderer = QgsMultiBandColorRenderer(provider, 1, 1, 1)
contrastEnhancement = QgsContrastEnhancement(multiBandRenderer.dataType(1))
contrastEnhancement.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum, True)
contrastEnhancement.setMinimumValue(minimum)
contrastEnhancement.setMaximumValue(maximum)
finalLayer.setRenderer(multiBandRenderer)
for bandColour in ["Red", "Green", "Blue"]:
    getattr(finalLayer.renderer(), "set" + bandColour + "Band")(1)
    getattr(finalLayer.renderer(), "set" + bandColour + "ContrastEnhancement")(contrastEnhancement)
finalLayer.triggerRepaint()

"""
#################################################################################
Merge the dems together
"""

#Let's get all the tifs ready for merging
tifList = glob.glob(os.path.join(tifFolder, "*.tif"))

#Merging the DEM tifs together
processing.run("gdal:merge", {'INPUT':tifList,'PCT':False,'SEPARATE':False,'NODATA_INPUT':None,'NODATA_OUTPUT':None,
    'OPTIONS':compressOptions,'EXTRA':'','DATA_TYPE':5,'OUTPUT':os.path.join(mergedFolder, "MergedDEM.tif")})

"""
#################################################################################
Creating and styling a slope raster
"""

#Time for some slope
processing.run("native:slope", {'INPUT':os.path.join(mergedFolder, "MergedDEM.tif"),'Z_FACTOR':1,
    'OUTPUT':os.path.join(mergedFolder, "Slope.tif")})

#Now let's add that in and make it look nice
slopeLayer = iface.addRasterLayer(os.path.join(mergedFolder, "Slope.tif"), 'Slope' , '')

#Scale between transparent and yellow, where 35° is invisible and 65° is yellow
colorRamp = QgsColorRampShader()
colorRamp.setColorRampType(QgsColorRampShader.Interpolated)
colorRamp.setColorRampItemList([QgsColorRampShader.ColorRampItem(35, QColor(255, 255, 0, 0)),
    QgsColorRampShader.ColorRampItem(65, QColor(255, 255, 0, 255))])
rasterShader = QgsRasterShader()
rasterShader.setRasterShaderFunction(colorRamp)
renderer = QgsSingleBandPseudoColorRenderer(slopeLayer.dataProvider(), 1, rasterShader)
slopeLayer.setRenderer(renderer)
slopeLayer.triggerRepaint()

"""
#################################################################################
Creating and styling contours
"""

#Now let's make some contours and bring them in too
processing.run("gdal:contour", {'INPUT':os.path.join(mergedFolder, "MergedDEM.tif"),'BAND':1,'INTERVAL':2,'FIELD_NAME':'ELEV',
    'CREATE_3D':False,'IGNORE_NODATA':False,'NODATA':None,'OFFSET':0,'EXTRA':'','OUTPUT':os.path.join(mergedFolder, "Contours2.gpkg")})
contourLayer  = iface.addVectorLayer(os.path.join(mergedFolder, "Contours2.gpkg"), 'Contours2' , 'ogr')

#Thin lines so that the other layers can be seen beneath easily
symbol = QgsLineSymbol.createSimple({'line_style': 'solid', 'color': 'magenta', 'width': '0.12'})
contourLayer.renderer().setSymbol(symbol)
contourLayer.triggerRepaint()

print("All done")
