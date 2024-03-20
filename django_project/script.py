import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
sys.path.insert(0, '/usr/share/qgis/python')
sys.path.insert(0, '/usr/share/qgis/python/plugins')
print(sys.path)
import os
# os.environ['LD_LIBRARY_PATH'] = '/usr/lib/python3'
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import qgis
from qgis.core import *
 
# Supply path to qgis install location
QgsApplication.setPrefixPath("/usr/bin/qgis", True)
 
# Create a reference to the QgsApplication.  Setting the
# second argument to False disables the GUI.
qgs = QgsApplication([], False)
 
# Load providers
qgs.initQgis()
 
# Put your pyqgis code here:
print("Success!")
 
# Finally, exitQgis() is called to remove the
# provider and layer registries from memory
qgs.exitQgis()