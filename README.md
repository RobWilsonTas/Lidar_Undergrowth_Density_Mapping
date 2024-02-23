This script runs in QGIS and makes use of LasTools .exes to take and input of las and tif files, and produce a raster of undergrowth density

It also produces contours and steeply sloped areas, styled ready for a map export

This could be used for research work into vegetation structure, as well as producing maps for orienteering and bushbashing

_______________________________

The first part of the script contains what is in https://github.com/Mp3Robbo/Elvis_Lidar_Auto_Extractor to extract a zip folder from Elvis

Then it uses LasTools to normalise and merge the lidar data

Before grabbing the merged lidar data and determining the understory vegetation density

_______________________________

Because of this script's reliance on two programs, there is a likelihood for it to fall over

Also, if your data hasn't come from Elvis then you'll need to modify the script/your files to make it work

________________________________

Any issues let me know
