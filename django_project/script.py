import sys
import time
# sys.path.insert(0, '/usr/share/qgis/python')
sys.path.insert(0, '/usr/share/qgis/python/plugins')
sys.path.insert(0, '/usr/share/qgis/python')
sys.path.append('/usr/lib/python3/dist-packages')
# sys.path.insert(0, "/usr/lib/qt5/bin")
print(sys.path)
import os
# os.environ['LD_LIBRARY_PATH'] = '/usr/lib/python3'
# QT HEADLESS MODE
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# os.environ["QT_PLUGIN_PATH"] = "/usr/lib/x86_64-linux-gnu/qt5/plugins"

start_time = time.time()
from qgis.core import *
# Supply path to qgis install location
QgsApplication.setPrefixPath("/usr/bin/qgis", True)
 
# Create a reference to the QgsApplication.  Setting the
# second argument to False disables the GUI.
qgs = QgsApplication([], False)
 
# Load providers
qgs.initQgis()

# append processing plugins
import processing
from processing.core.Processing import Processing
Processing.initialize()

# Put your pyqgis code here:
print("Success!")
import uuid
from cplus.models.base import ImplementationModel, Scenario, SpatialExtent, LayerType, NcsPathway
from cplus.tasks.analysis import ScenarioAnalysisTask
from cplus.utils.conf import settings_manager


analysis_scenario_name = 'Test'
analysis_scenario_description = 'Test'
analysis_extent = SpatialExtent(bbox=[878529.3786140494, 911063.0818645271, 7216308.751738624, 7279753.465204147])
analysis_priority_layers_groups = [
    {'name': 'Climate Resilience', 'value': '0', 'layers': []},
    {'name': 'Finance - Net Present value', 'value': '0', 'layers': []},
    {'name': 'Finance - Years Experience', 'value': '0', 'layers': []},
    {'name': 'Finance - Carbon', 'value': '0', 'layers': []},
    {'name': 'Livelihood', 'value': '0', 'layers': []},
    {'name': 'Policy', 'value': '0', 'layers': []},
    {'name': 'Ecological infrastructure', 'value': '0', 'layers': []},
    {'name': 'Finance - Market Trends', 'value': '0', 'layers': []},
    {'name': 'Biodiversity', 'value': '0', 'layers': []}
]
analysis_implementation_models = []

im_model = ImplementationModel(
    uuid=uuid.UUID('1c8db48b-717b-451b-a644-3af1bee984ea'),
    name='Alien Plant Removal',
    description='This model involves the removal of invasive alien plant species that negatively impact native ecosystems. By eradicating these plants, natural habitats can be restored, allowing native flora and fauna to thrive.',
    path='',
    layer_type=LayerType.UNDEFINED,
    user_defined=False,
    pathways=[
        NcsPathway(
            uuid=uuid.UUID('5fe775ba-0e80-4b70-a53a-1ed874b72da3'),
            name='Alien Plant Removal',
            description='Alien Plant Class.',
            path='/home/web/media/ncs_pathways/Final_Alien_Invasive_Plant_priority_norm.tif',
            layer_type=LayerType.RASTER,
            carbon_paths=[]
        )
    ],
    priority_layers=[
        {
            "uuid": "c931282f-db2d-4644-9786-6720b3ab206a",
            "name": "Social norm",
            "description": "Placeholder text for social norm ",
            "selected": True,
            "path": "social_int_clip_norm.tif"
        },
        {
            "uuid": "88c1c7dd-c5d1-420c-a71c-a5c595c1c5be",
            "name": "Ecological Infrastructure",
            "description": "Placeholder text for ecological infrastructure",
            "selected": False,
            "path": "ei_all_gknp_clip_norm.tif"
        },
        {
            "uuid": "9ab8c67a-5642-4a09-a777-bd94acfae9d1",
            "name": "Biodiversity norm",
            "description": "Placeholder text for biodiversity norm",
            "selected": False,
            "path": "biocombine_clip_norm.tif"
        },
    ],
    layer_styles={
        "scenario_layer": {
            "color": "#6f6f6f",
            "style": "solid",
            "outline_width": "0",
            "outline_color": "35,35,35,0"
        },
        "model_layer": {"color_ramp": "Greys"}
    }
)
analysis_implementation_models.append(im_model)

scenario = Scenario(
    uuid=uuid.uuid4(),
    name=analysis_scenario_name,
    description=analysis_scenario_description,
    extent=analysis_extent,
    models=analysis_implementation_models,
    weighted_models=[],
    priority_layer_groups=analysis_priority_layers_groups,
)


analysis_task = ScenarioAnalysisTask(
    analysis_scenario_name,
    analysis_scenario_description,
    analysis_implementation_models,
    analysis_priority_layers_groups,
    analysis_extent,
    scenario,
)

analysis_task.run()
print(f'execution time: {time.time() - start_time} seconds')
 
# Finally, exitQgis() is called to remove the
# provider and layer registries from memory
qgs.exitQgis()