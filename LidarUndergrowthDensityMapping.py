import glob, os, zipfile, re, shutil, sys, time, pathlib, subprocess
from os import walk
from qgis.PyQt.QtGui import *


"""
#################################################################################
User variables
"""

lasToolsDirectory = 'C:\\LAStools\\bin\\' #Make sure this has double back slashes
compressOptions = 'COMPRESS=LZW|PREDICTOR=2|NUM_THREADS=8|BIGTIFF=IF_SAFER|TILED=YES'

#Run the script and a prompt will appear for you to enter in the zip folder


"""
#################################################################################
First we get the initial zip folder
"""

#This provides a prompt to the user asking them to input the path to the zip folder
qid = QInputDialog()
promptTitle = "Path To Zip Folder"
promptLabel = "(please ensure that your lastools directory is C:/LAStools/bin/, and that your QGIS project coordinate system matches the input data) \n \nEnter below the full path of the zip folder with tifs and las files inside \n \nMake sure you include the folder name and extension, e.g C:/Temp/ElvisZip.zip \n"
mode = QLineEdit.Normal
promptInitialText = "Full path here, e.g  C:/Temp/ElvisZip.zip"
zipFolderFromElvis, ok = QInputDialog.getText(qid, promptTitle, promptLabel, mode, promptInitialText)


#Determining where the folder path ends and where the file name starts
for x in range(len(zipFolderFromElvis)):
    if zipFolderFromElvis[x] == '/':
        lastSlashIndex = x
        
for x in range(len(zipFolderFromElvis)):
    if zipFolderFromElvis[x] == chr(92):
        lastSlashIndex = x

path = zipFolderFromElvis[:lastSlashIndex]
zipName = zipFolderFromElvis[lastSlashIndex + 1:-4]

#Replace backslashes with forward slashes
path = path.replace(chr(92),'/')
path = path.replace('\u202a','')



"""
#################################################################################
Unzipping the elvis package
"""


#This makes sure you are running this is QGIS, where the processing module is available
try:
    import processing
except:
    print("You need to run this in QGIS")
    time.sleep(3)
    sys.exit()

#Set the directory to where the zip folder is
try:
    os.chdir(path)
except:
    print("The path seems invalid, are you sure this folder exists?")
    time.sleep(1)
    goFixItUp
path = path.replace(os.sep, '/')

#Extract the zip folder
try:
    with zipfile.ZipFile(path + '/' + zipName + '.zip','r') as zip_ref:
        zip_ref.extractall(zipName + "Extract")
except:
    print("Ok whatever zip folder you typed in seems invalid...")
    time.sleep(1)
    goFixItUp


"""
#################################################################################
Sort the contents of the extracted zip
"""


#Ok now look around in the extracted folder for nested zip folders
filePathsList = glob.glob(path + '/' + zipName + 'Extract/**/*', recursive=True)

#Only grab actual zip folders
zipList = []
for b in filePathsList:
    if (b[-4:]) == '.zip':
       zipList.append(b.replace(chr(92),'/'))

count = 0
#Extract all the internal zip folders into a temp folder
for z in zipList:
    count = count + 1
    with zipfile.ZipFile(z,"r") as zip_ref:
        zip_ref.extractall(zipName + 'Extract/Unzipped/UnzippedFolder' + str(count))


#Set up new folders to put the relevant files into
os.makedirs(path + '/' + zipName + 'Tif/', exist_ok = True)
os.makedirs(path + '/' + zipName + 'LasLaz/', exist_ok = True)

count = 0
#Move all of the relevant files into their folders
filePathsList = glob.glob(path + '/' + zipName + 'Extract/**/*', recursive=True)
for filePath in filePathsList:
    filePath = filePath.replace(chr(92),'/')
    fileName = filePath.split("/")[-1]
    
    if filePath[-4:] == '.tif':
        shutil.move(filePath, path + '/' + zipName + 'Tif/' + fileName)
        count = count + 1
        
    if filePath[-4:] == '.las':
        shutil.move(filePath, path + '/' + zipName + 'LasLaz/' + fileName)
        count = count + 1
        
    if filePath[-4:] == '.laz':
        shutil.move(filePath, path + '/' + zipName + 'LasLaz/' + fileName)
        count = count + 1

print ('Yeah successfully sorted ' + str(int(count)) + ' files')
#Delete the temp folders
shutil.rmtree(path + '/' + zipName + 'Extract/')



"""
#################################################################################
This is where we make a temp bat file that runs the las tools .exes
"""

#Create directories for the normalis
os.makedirs(path + '/' + zipName + 'LasNorm/', exist_ok = True)
os.makedirs(path + '/' + zipName + 'Merged/', exist_ok = True)

#The open up a bat ready for writing
pathWithBackslashes = path.replace('/',chr(92))
myBat = open(pathWithBackslashes + r'\LasToolsTempRunner.bat','w+')

#Write into the bat as per the readme of lastools
myBat.write(r''':: set relevant variables
cd ''' + pathWithBackslashes + r'''
set LAStools=''' + lasToolsDirectory + r'''

:: print-out which LAStools version are we running
%LAStools%^
lastile -version

:: do the las ground thing
%LAStools%^
lasground_new -i ''' + zipName + r'''LasLaz/*.las -cores 4 -wilderness -compute_height -replace_z -odir ''' + zipName + r'''LasNorm -olas
%LAStools%^
lasground_new -i ''' + zipName + r'''LasLaz/*.laz -cores 4 -wilderness -compute_height -replace_z -odir ''' + zipName + r'''LasNorm -olas

:: now we're going to merge the normalised las tiles together, make sure the folders line up with the parameters
%LAStools%^
lasmerge -i ''' + zipName + r'''LasNorm/*.las -o ''' + zipName + r'''Merged/Merged.las -drop_z_below -0.5 -drop_z_above 2''')
myBat.close()

#Run the bat file 
print("Alright we're running LasTools's stuff from cmd")
subprocess.call([pathWithBackslashes + r'\LasToolsTempRunner.bat'])
os.remove(pathWithBackslashes + r'\LasToolsTempRunner.bat')


"""
#################################################################################
Sampling the lidar las file at various resolutions, to be later combined
"""

#Make the folder for the veg density rasters
os.makedirs(path + '/' + zipName + 'VegDens/', exist_ok = True)

#Determining the density both for the understory and the understory & ground
processing.run("grass7:r.in.lidar", {'input':path + '/' + zipName + 'Merged/Merged.las','method':0,'type':1,'base_raster':None,'zrange':[0.25,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':2,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/' + zipName + 'VegDens/UnderstoryDens1.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.in.lidar", {'input':path + '/' + zipName + 'Merged/Merged.las','method':0,'type':1,'base_raster':None,'zrange':[-0.5,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':2,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/' + zipName + 'VegDens/TotalLowerDens1.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

processing.run("grass7:r.in.lidar", {'input':path + '/' + zipName + 'Merged/Merged.las','method':0,'type':1,'base_raster':None,'zrange':[0.25,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':3,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/' + zipName + 'VegDens/UnderstoryDens2.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.in.lidar", {'input':path + '/' + zipName + 'Merged/Merged.las','method':0,'type':1,'base_raster':None,'zrange':[-0.5,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':3,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/' + zipName + 'VegDens/TotalLowerDens2.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

processing.run("grass7:r.in.lidar", {'input':path + '/' + zipName + 'Merged/Merged.las','method':0,'type':1,'base_raster':None,'zrange':[0.25,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':4,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/' + zipName + 'VegDens/UnderstoryDens3.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.in.lidar", {'input':path + '/' + zipName + 'Merged/Merged.las','method':0,'type':1,'base_raster':None,'zrange':[-0.5,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':4,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/' + zipName + 'VegDens/TotalLowerDens3.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

#Remove nulls from the understory density (but not the total density) so that areas empty of vegetation can be calculated
processing.run("grass7:r.null", {'map':path + '/' + zipName + 'VegDens/UnderstoryDens1.tif','setnull':'','null':0,'-f':False,'-i':False,'-n':False,'-c':False,'-r':False,'output':path + '/' + zipName + 'VegDens/UnderstoryDens1NoNull.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.null", {'map':path + '/' + zipName + 'VegDens/UnderstoryDens2.tif','setnull':'','null':0,'-f':False,'-i':False,'-n':False,'-c':False,'-r':False,'output':path + '/' + zipName + 'VegDens/UnderstoryDens2NoNull.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.null", {'map':path + '/' + zipName + 'VegDens/UnderstoryDens3.tif','setnull':'','null':0,'-f':False,'-i':False,'-n':False,'-c':False,'-r':False,'output':path + '/' + zipName + 'VegDens/UnderstoryDens3NoNull.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

#Calculate the normalised veg density
processing.run("qgis:rastercalculator", {'EXPRESSION':'\"UnderstoryDens1NoNull@1\" / \"TotalLowerDens1@1\"','LAYERS':[path + '/' + zipName + 'VegDens/TotalLowerDens1.tif',path + '/' + zipName + 'VegDens/UnderstoryDens1NoNull.tif'],'CELLSIZE':0,'EXTENT':None,'CRS':None,'OUTPUT':path + '/' + zipName + 'VegDens/UnderstoryDens1Norm.tif'})
processing.run("qgis:rastercalculator", {'EXPRESSION':'\"UnderstoryDens2NoNull@1\" / \"TotalLowerDens2@1\"','LAYERS':[path + '/' + zipName + 'VegDens/TotalLowerDens2.tif',path + '/' + zipName + 'VegDens/UnderstoryDens2NoNull.tif'],'CELLSIZE':0,'EXTENT':None,'CRS':None,'OUTPUT':path + '/' + zipName + 'VegDens/UnderstoryDens2Norm.tif'})
processing.run("qgis:rastercalculator", {'EXPRESSION':'\"UnderstoryDens3NoNull@1\" / \"TotalLowerDens3@1\"','LAYERS':[path + '/' + zipName + 'VegDens/TotalLowerDens3.tif',path + '/' + zipName + 'VegDens/UnderstoryDens3NoNull.tif'],'CELLSIZE':0,'EXTENT':None,'CRS':None,'OUTPUT':path + '/' + zipName + 'VegDens/UnderstoryDens3Norm.tif'})

#Fill in the holes using interpolation
processing.run("grass7:r.fill.stats", {'input':path + '/' + zipName + 'VegDens/UnderstoryDens1Norm.tif','-k':True,'mode':0,'-m':False,'distance':3,'minimum':None,'maximum':None,'power':2,'cells':4,'output':path + '/' + zipName + 'VegDens/UnderstoryDens1NormFilled.tif','uncertainty':path + '/' + zipName + 'VegDens/Uncertainty1.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.fill.stats", {'input':path + '/' + zipName + 'VegDens/UnderstoryDens2Norm.tif','-k':True,'mode':0,'-m':False,'distance':3,'minimum':None,'maximum':None,'power':2,'cells':4,'output':path + '/' + zipName + 'VegDens/UnderstoryDens2NormFilled.tif','uncertainty':path + '/' + zipName + 'VegDens/Uncertainty2.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.fill.stats", {'input':path + '/' + zipName + 'VegDens/UnderstoryDens3Norm.tif','-k':True,'mode':0,'-m':False,'distance':3,'minimum':None,'maximum':None,'power':2,'cells':4,'output':path + '/' + zipName + 'VegDens/UnderstoryDens3NormFilled.tif','uncertainty':path + '/' + zipName + 'VegDens/Uncertainty3.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

#Determine the extent for the rasters to be combined to
threeRaster = QgsRasterLayer(path + '/' + zipName + 'VegDens/UnderstoryDens1NormFilled.tif')
threeRasterExtent = threeRaster.extent()
QgsProject.instance().addMapLayer(threeRaster, False)
QgsProject.instance().removeMapLayer(threeRaster.id())

#Resample the rasters, ready for combination
processing.run("gdal:warpreproject", {'INPUT':path + '/' + zipName + 'VegDens/UnderstoryDens1NormFilled.tif','SOURCE_CRS':None,'TARGET_CRS':None,'RESAMPLING':1,'NODATA':None,'TARGET_RESOLUTION':1,'OPTIONS':compressOptions,'DATA_TYPE':0,'TARGET_EXTENT':threeRasterExtent,'TARGET_EXTENT_CRS':None,'MULTITHREADING':True,'EXTRA':'','OUTPUT':path + '/' + zipName + 'VegDens/UnderstoryDens1NormFilledResamp.tif'})
processing.run("gdal:warpreproject", {'INPUT':path + '/' + zipName + 'VegDens/UnderstoryDens2NormFilled.tif','SOURCE_CRS':None,'TARGET_CRS':None,'RESAMPLING':1,'NODATA':None,'TARGET_RESOLUTION':1,'OPTIONS':compressOptions,'DATA_TYPE':0,'TARGET_EXTENT':threeRasterExtent,'TARGET_EXTENT_CRS':None,'MULTITHREADING':True,'EXTRA':'','OUTPUT':path + '/' + zipName + 'VegDens/UnderstoryDens2NormFilledResamp.tif'})
processing.run("gdal:warpreproject", {'INPUT':path + '/' + zipName + 'VegDens/UnderstoryDens3NormFilled.tif','SOURCE_CRS':None,'TARGET_CRS':None,'RESAMPLING':1,'NODATA':None,'TARGET_RESOLUTION':1,'OPTIONS':compressOptions,'DATA_TYPE':0,'TARGET_EXTENT':threeRasterExtent,'TARGET_EXTENT_CRS':None,'MULTITHREADING':True,'EXTRA':'','OUTPUT':path + '/' + zipName + 'VegDens/UnderstoryDens3NormFilledResamp.tif'})


"""
#################################################################################
Creating and styling a the final density raster
"""

#Bring the resampled rasters together
processing.run("gdal:rastercalculator", {'INPUT_A':path + '/' + zipName + 'VegDens/UnderstoryDens1NormFilledResamp.tif','BAND_A':1,'INPUT_B':path + '/' + zipName + 'VegDens/UnderstoryDens2NormFilledResamp.tif','BAND_B':1,'INPUT_C':path + '/' + zipName + 'VegDens/UnderstoryDens3NormFilledResamp.tif','BAND_C':1,
'FORMULA':'A+B+C','NO_DATA':-9999,'RTYPE':5,'OPTIONS':'','EXTRA':'','OUTPUT':path + '/' + zipName + 'VegDens/CombinedUnderstoryDensity.tif'})

#Style it so that there is a cumulative cut
finalLayer = iface.addRasterLayer(path + '/' + zipName + 'VegDens/CombinedUnderstoryDensity.tif', 'CombinedUnderstoryDensity' , '')
provider=finalLayer.dataProvider()
statsRed = provider.cumulativeCut(1,0.01,0.99,sampleSize=1000) #adjust these values depending on the stretch you want
minimum = statsRed[0]
maximum = statsRed[1]
renderer=finalLayer.renderer()
myType = renderer.dataType(1)
myEnhancement = QgsContrastEnhancement(myType)
Renderer = QgsMultiBandColorRenderer(provider,1,1,1) 
contrast_enhancement = QgsContrastEnhancement.StretchToMinimumMaximum
myEnhancement.setContrastEnhancementAlgorithm(contrast_enhancement,True)
myEnhancement.setMinimumValue(minimum)#where the minimum value goes in
myEnhancement.setMaximumValue(maximum)
finalLayer.setRenderer(Renderer)
finalLayer.renderer().setRedBand(1)#band 1 is red
finalLayer.renderer().setGreenBand(1)
finalLayer.renderer().setBlueBand(1)
finalLayer.renderer().setRedContrastEnhancement(myEnhancement)#the same contrast enhancement is applied to all
finalLayer.renderer().setGreenContrastEnhancement(myEnhancement)
finalLayer.renderer().setBlueContrastEnhancement(myEnhancement)
finalLayer.triggerRepaint() #refresh


"""
#################################################################################
Merge the dems together
"""

#Let's get all the tifs ready for merging
path_to_tif = path + '/' + zipName + 'Tif/'
os.chdir(path_to_tif)
tifList = []
for fname in glob.glob("*.tif"):
    uri = path_to_tif + fname
    tifList.append(uri)

#Merging the DEM tifs together
processing.run("gdal:merge", {'INPUT':tifList,'PCT':False,'SEPARATE':False,'NODATA_INPUT':None,'NODATA_OUTPUT':None,'OPTIONS':compressOptions,'EXTRA':'','DATA_TYPE':5,'OUTPUT':path +  '/' + zipName + 'Merged/MergedDEM.tif'})


"""
#################################################################################
Creating and styling a slope raster
"""

#Time for some slope
processing.run("native:slope", {'INPUT':path + '/' + zipName + 'Merged/MergedDEM.tif','Z_FACTOR':1,'OUTPUT':path + '/' + zipName + 'Merged/Slope.tif'})

#Now let's add that in and make it look nice
slopeLayer = iface.addRasterLayer(path + '/' + zipName + 'Merged/Slope.tif', 'Slope' , '')

#Scale between transparent and yellow, where 35° is invisible and 65° is yellow
fnc = QgsColorRampShader()
fnc.setColorRampType(QgsColorRampShader.Interpolated)
lst = [QgsColorRampShader.ColorRampItem(35, QColor(255,255,0,0)),QgsColorRampShader.ColorRampItem(65, QColor(255,255,0,255))]
fnc.setColorRampItemList(lst)

shader = QgsRasterShader()
shader.setRasterShaderFunction(fnc)

renderer = QgsSingleBandPseudoColorRenderer(slopeLayer.dataProvider(), 1, shader)
slopeLayer.setRenderer(renderer)
slopeLayer.triggerRepaint()

"""
#################################################################################
Creating and styling contours
"""

#Now let's make some contours and bring them in too
processing.run("gdal:contour", {'INPUT':path + '/' + zipName + 'Merged/MergedDEM.tif','BAND':1,'INTERVAL':2,'FIELD_NAME':'ELEV','CREATE_3D':False,'IGNORE_NODATA':False,'NODATA':None,'OFFSET':0,'EXTRA':'','OUTPUT':path + '/' + zipName + 'Merged/Contours2.gpkg'})

contourLayer  = iface.addVectorLayer(path + '/' + zipName + 'Merged/Contours2.gpkg', 'Contours2' , 'ogr')

#Thin lines so that the other layers can be seen beneath easily
symbol = QgsLineSymbol.createSimple({'line_style': 'solid', 'color': 'magenta', 'width': '0.12'})
contourLayer.renderer().setSymbol(symbol)
contourLayer.triggerRepaint()


print("All done")
