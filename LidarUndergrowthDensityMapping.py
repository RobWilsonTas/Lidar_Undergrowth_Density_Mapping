#
#Run the script and a prompt will appear
#


#This provides a prompt to the user asking them to input the path to the zip folder
from qgis.PyQt.QtGui import *
qid = QInputDialog()
title = "Path To Zip Folder"
label = "Enter the full path of the zip folder with tifs and las files inside \n \nMake sure you include the folder name and extention, i.e C:/Temp/ElvisZip.zip \n \nAlso please ensure that the zip folder is basically by itself in its folder"
mode = QLineEdit.Normal
default = "Full path here, i.e  C:/Temp/ElvisZip.zip"
zipFolderFromElvis, ok = QInputDialog.getText(qid, title, label, mode, default)



#Determining where the folder path ends and where the file name starts
for x in range(len(zipFolderFromElvis)):
    if zipFolderFromElvis[x] == '/':
        lastSlashIndex = x
        
for x in range(len(zipFolderFromElvis)):
    if zipFolderFromElvis[x] == chr(92):
        lastSlashIndex = x

path = zipFolderFromElvis[:lastSlashIndex]
zipName = zipFolderFromElvis[lastSlashIndex:]
path = path.replace(chr(92),'/')



#####################################
#####################################
######## This first section is for unzipping the elvis package
#####################################
#####################################

import glob, os, zipfile, re, shutil, sys, time
from os import walk
import pathlib

try:
    #This makes sure you are running this is QGIS, where the processing module is available
    import processing
    
#The below is for if you run this script not in qgis
except:
    print("You need to run this in QGIS")
    time.sleep(3)
    sys.exit()

#Set the directory to where the zip folder is
try:
    os.chdir(path)
except:
    print("Ok whatever path you put in seems invalid...")
    time.sleep(4)
    purposefullyEndingScriptByGivingAnErrorAboutThisVariableNotBeingDefined
path = path.replace(os.sep, '/')

#Extract the zip folder
try:
    with zipfile.ZipFile(path+zipName,'r') as zip_ref:
        zip_ref.extractall("FilesExtract")
except:
    print("Ok whatever zip folder you typed in seems invalid...")
    time.sleep(4)
    purposefullyEndingScriptByGivingAnErrorAboutThisVariableNotBeingDefined

#Ok now look around in the extracted folder for nested zip folders
archives = os.listdir(path)
archives = [ar for ar in archives if ar.endswith(".zip")]
for a in archives:
    archive = zipfile.ZipFile( path+'\\'+a )
    filelist = archive.namelist()
    
#Check that they're actually zip folders
ziplist = []
for b in filelist:
    if (b[-4:]) == '.zip':
       ziplist.append(b)
       
#Extract all the nested zip folders into a temp folder
count = 0
for c in ziplist:
    count = count + 1
    with zipfile.ZipFile(path + '/FilesExtract/' + c,"r") as zip_ref:
        zip_ref.extractall("SubFiles/Extract"+str(count))

#Set up new folders to put the relevant files into
os.makedirs(path + '/Tif/', exist_ok = True)
os.makedirs(path + '/LasLaz/', exist_ok = True)

#Move all of the relevant files into their folders
count = 0
for (dir_path, dir_names, file_names) in walk(path):
    for d in file_names:
        dir_path = dir_path.replace(os.sep, '/')
    
        fullPath = dir_path + '/' + d
        if fullPath[-4:] == '.tif':
            shutil.move(fullPath, path + '/Tif/' + d)
            count = count + 0.5
            
        if fullPath[-4:] == '.las':
            shutil.move(fullPath, path + '/LasLaz/' + d)
            count = count + 1
            
        if fullPath[-4:] == '.laz':
            shutil.move(fullPath, path + '/LasLaz/' + d)
            count = count + 1
            
#Delete the temp folders
shutil.rmtree(path + '/FilesExtract/')
shutil.rmtree(path + '/SubFiles/')

print ('Yeah successfully sorted ' + str(int(count)) + ' files')

#Let's get all the tifs ready for merging
path_to_tif = path + '/Tif/'
os.chdir(path_to_tif)
tifList = []
for fname in glob.glob("*.tif"):
    uri = path_to_tif + fname
    tifList.append(uri)

#Merging tifs. This will work if the script is run in QGIS and the merged tif doesn't already exist
processing.run("gdal:merge", {'INPUT':tifList,'PCT':False,'SEPARATE':False,'NODATA_INPUT':None,'NODATA_OUTPUT':None,'OPTIONS':'COMPRESS=LZW|PREDICTOR=2|ZLEVEL=9|NUM_THREADS=4|BIGTIFF=IF_SAFER','EXTRA':'','DATA_TYPE':5,'OUTPUT':path + '/Tif/MergedDEM.tif',})



#######################################
###########
###########The next section is for taking the las data and getting a density raster made up
###########
#######################################

#This is where we make a temp bat file that runs the las tools .exes
import subprocess

os.makedirs(path + '/LasNorm/', exist_ok = True)
os.makedirs(path + '/Merged/', exist_ok = True)

pathWithBackslashes = path.replace('/',chr(92))

#The bat normalises the point clouds and then merges them
myBat = open(pathWithBackslashes + r'\LasToolsTempRunner.bat','w+')
myBat.write(r''':: set relevant variables
cd ''' + pathWithBackslashes + r'''
set LAStools=C:\LAStools\bin\

:: print-out which LAStools version are we running
%LAStools%^
lastile -version
:: do the las ground thing
%LAStools%^
lasground_new -i LasLaz/*.las -cores 4 -wilderness -compute_height -replace_z -odir LasNorm -olas
%LAStools%^
lasground_new -i LasLaz/*.laz -cores 4 -wilderness -compute_height -replace_z -odir LasNorm -olas
:: now we're going to merge the normalised las tiles together, make sure the folders line up with the parameters
%LAStools%^
lasmerge -i LasNorm/*.las -o Merged/Merged.las''')
myBat.close()
print("Alright we're running LasTools's stuff from cmd")
subprocess.call([pathWithBackslashes + r'\LasToolsTempRunner.bat'])

os.remove(pathWithBackslashes + r'\LasToolsTempRunner.bat')



#######################################
###########
###########The next section is for taking the lastools output and making it look all nice as a bushbash map
###########
#######################################

os.makedirs(path + '/VegDens/', exist_ok = True)

#Now we can use grass to determine some densities
processing.run("grass7:r.in.lidar", {'input':pathWithBackslashes + '\\Merged\\Merged.las','method':0,'type':1,'base_raster':None,'zrange':[0.25,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':4,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/VegDens/UnderstoryDens.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})
processing.run("grass7:r.in.lidar", {'input':pathWithBackslashes + '\\Merged\\Merged.las','method':0,'type':1,'base_raster':None,'zrange':[-0.5,1.8],'zscale':1,'intensity_range':['nan','nan'],'intensity_scale':1,'percent':100,'pth':None,'trim':None,'resolution':4,'return_filter':'','class_filter':'','-e':True,'-n':True,'-o':True,'-i':False,'-j':False,'-d':False,'-v':False,'output':path + '/VegDens/TotalLowerDens.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

#Calculate the normalised veg density
processing.run("grass7:r.null", {'map':path + '/VegDens/UnderstoryDens.tif','setnull':'','null':0,'-f':False,'-i':False,'-n':False,'-c':False,'-r':False,'output':path + '/VegDens/UnderstoryDensNoNull.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

processing.run("qgis:rastercalculator", {'EXPRESSION':'\"UnderstoryDensNoNull@1\" / \"TotalLowerDens@1\"','LAYERS':[path + '/VegDens/TotalLowerDens.tif',path + '/VegDens/UnderstoryDensNoNull.tif'],'CELLSIZE':0,'EXTENT':None,'CRS':None,'OUTPUT':path + '/VegDens/UnderstoryDensNorm.tif'})

processing.run("grass7:r.neighbors", {'input':path + '/VegDens/UnderstoryDensNorm.tif','selection':None,'method':0,'size':3,'gauss':None,'quantile':'','-c':False,'-a':False,'weight':'','output':path + '/VegDens/UnderstoryDensNormNeig.tif','GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_RASTER_FORMAT_OPT':'','GRASS_RASTER_FORMAT_META':''})

#And now bring it in
iface.addRasterLayer(path + '/VegDens/UnderstoryDensNormNeig.tif', 'UnderstoryDensNormNeig' , '')
iface.addRasterLayer(path + '/VegDens/UnderstoryDensNorm.tif', 'UnderstoryDensNorm' , '')


#Time for some slope
path_to_tif = path + '/Tif/'
os.chdir(path_to_tif)
filelist = []
for fname in glob.glob("*.tif"):
    uri = path_to_tif + fname
    filelist.append(uri)

processing.run("gdal:merge", {'INPUT':filelist,'PCT':False,'SEPARATE':False,'NODATA_INPUT':None,'NODATA_OUTPUT':None,'OPTIONS':'COMPRESS=LZW|PREDICTOR=2|ZLEVEL=9|NUM_THREADS=4|BIGTIFF=IF_SAFER','EXTRA':'','DATA_TYPE':5,'OUTPUT':path + '/Merged/MergedDEM.tif'})

processing.run("native:slope", {'INPUT':path+ '/Merged/MergedDEM.tif','Z_FACTOR':1,'OUTPUT':path+ '/Merged/Slope.tif'})

#Now let's add that in and make it look nice
layer2 = iface.addRasterLayer(path+ '/Merged/Slope.tif', 'Slope' , '')

fnc = QgsColorRampShader()
fnc.setColorRampType(QgsColorRampShader.Interpolated)
lst = [QgsColorRampShader.ColorRampItem(40, QColor(255,255,0,0)),QgsColorRampShader.ColorRampItem(70, QColor(255,255,0,255))]
fnc.setColorRampItemList(lst)

shader = QgsRasterShader()
shader.setRasterShaderFunction(fnc)

renderer = QgsSingleBandPseudoColorRenderer(layer2.dataProvider(), 1, shader)
layer2.setRenderer(renderer)
layer2.triggerRepaint()


#Now let's make some contours and bring them in too
processing.run("gdal:contour", {'INPUT':path+ '/Merged/MergedDEM.tif','BAND':1,'INTERVAL':2,'FIELD_NAME':'ELEV','CREATE_3D':False,'IGNORE_NODATA':False,'NODATA':None,'OFFSET':0,'EXTRA':'','OUTPUT':path+ '/Merged/Contours2.gpkg'})

layer  = iface.addVectorLayer(path+ '/Merged/Contours2.gpkg', 'Contours2' , 'ogr')

symbol = QgsLineSymbol.createSimple({'line_style': 'solid', 'color': 'magenta', 'width': '0.2'})
layer.renderer().setSymbol(symbol)
layer.triggerRepaint()



print("All done")
