import streamlit as st
import os
import tempfile
import zipfile
import rarfile
import json
import geopandas as gpd
from pyproj import Proj, Transformer
from specklepy.objects import Base
from specklepy.objects.geometry import Line, Point
from specklepy.api.client import SpeckleClient
from specklepy.transports.server import ServerTransport
from specklepy.api import operations
import uuid

# Define your projection (example using UTM Zone 18N)
transformer = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True)

# Utility functions
def inches_to_feet(inches):
    return inches / 12

def feet_to_internal_units(feet):
    return feet * 0.3048  # Convert feet to meters (Revit's internal unit)

def convert_to_revit_units(lon, lat):
    x, y = transformer.transform(lon, lat)
    return feet_to_internal_units(x), feet_to_internal_units(y)

def create_unique_speckle_classes():
    unique_id = uuid.uuid4().hex[:8]  # Generate a unique identifier

    def create_unique_class(base_name, base_class, speckle_type=None, **attrs):
        class_name = f"{base_name}_{unique_id}"
        class_attrs = attrs.copy()
        if speckle_type:
            class_attrs['speckle_type'] = speckle_type
        return type(class_name, (base_class,), class_attrs)

    Level = create_unique_class("Level", Base, 
                                speckle_type="Objects.BuiltElements.Level",
                                name=None, 
                                elevation=None)

    Parameter = create_unique_class("Parameter", Base,
                                    name=None,
                                    value=None)

    def revit_pipe_init(self, family, type, baseCurve, diameter_inches, level, systemName="", systemType="", parameters=None):
        Base.__init__(self)
        self.family = family
        self.type = type
        self.baseCurve = baseCurve
        self.diameter = diameter_inches / 12  # Convert inches to feet
        self.level = level
        self.systemName = systemName
        self.systemType = systemType
        self.parameters = Base()
        if parameters:
            for param in parameters:
                setattr(self.parameters, param.name, param.value)

    RevitPipe = create_unique_class("RevitPipe", Base,
                                    speckle_type="Objects.BuiltElements.Revit.RevitPipe",
                                    family=None,
                                    type=None,
                                    baseCurve=None,
                                    diameter=None,
                                    level=None,
                                    systemName=None,
                                    systemType=None,
                                    parameters=None,
                                    elementId=None,
                                    __init__=revit_pipe_init)

    return {
        "Level": Level,
        "Parameter": Parameter,
        "RevitPipe": RevitPipe
    }

# Create Speckle classes with unique names
SpeckleClasses = create_unique_speckle_classes()
def find_global_origin(geojson_data_list):
    min_x, min_y = float('inf'), float('inf')
    
    for data in geojson_data_list:
        features = [feature for feature in data['features'] if feature['geometry']['type'] == 'LineString']
        
        for feature in features:
            coordinates = feature['geometry']['coordinates']
            for lon, lat in coordinates:
                x, y = convert_to_revit_units(lon, lat)
                min_x = min(min_x, x)
                min_y = min(min_y, y)
    
    return min_x, min_y

def process_all_pipes(data, global_origin):
    pipes = []
    features = [feature for feature in data['features'] if feature['geometry']['type'] == 'LineString']
    
    if not features:
        return None

    global_origin_x, global_origin_y = global_origin

    for feature in features:
        coordinates = feature['geometry']['coordinates']
        
        for i in range(len(coordinates) - 1):
            start_lon, start_lat = coordinates[i]
            end_lon, end_lat = coordinates[i + 1]
            start_x, start_y = convert_to_revit_units(start_lon, start_lat)
            end_x, end_y = convert_to_revit_units(end_lon, end_lat)

            start_x -= global_origin_x
            start_y -= global_origin_y
            end_x -= global_origin_x
            end_y -= global_origin_y

            start = Point(x=start_x, y=start_y, z=0)
            end = Point(x=end_x, y=end_y, z=0)
            
            diameter_inches = 200 / 25.4  # Convert 200 mm to inches
            system_name = 'Domestic Cold Water'
            system_type = 'Supply'

            level = SpeckleClasses["Level"](name="Level 0", elevation=0)
            pipe = SpeckleClasses["RevitPipe"](
                family="Standard Pipe Types",
                type="Standard",
                baseCurve=Line(start=start, end=end),
                diameter_inches=diameter_inches,
                level=level,
                systemName=system_name,
                systemType=system_type,
                parameters=[SpeckleClasses["Parameter"](name="Comments", value="Pipe from GeoJSON")]
            )
            pipes.append(pipe)

    return pipes

def process_file(file):
    if isinstance(file, str):  # If it's a file path
        file_name = file
        file_extension = os.path.splitext(file)[1].lower()
        if file_extension == '.geojson':
            with open(file, 'r') as f:
                return json.load(f)
        elif file_extension == '.shp':
            gdf = gpd.read_file(file)
            return json.loads(gdf.to_json())
    else:  # If it's a Streamlit UploadedFile object
        file_name = file.name
        file_extension = os.path.splitext(file_name)[1].lower()
        if file_extension == '.geojson':
            return json.loads(file.getvalue().decode())
        elif file_extension == '.shp':
            with tempfile.NamedTemporaryFile(delete=False, suffix='.shp') as tmp_file:
                tmp_file.write(file.getvalue())
                tmp_file_path = tmp_file.name
            gdf = gpd.read_file(tmp_file_path)
            os.unlink(tmp_file_path)
            return json.loads(gdf.to_json())
    return None

def process_directory(directory):
    geojson_data_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            data = process_file(file_path)
            if data:
                geojson_data_list.append(data)
    return geojson_data_list

def main():
    st.title("GeoJSON/Shapefile to Revit Pipes Converter")

    # Access secrets
    speckle_token = st.secrets["speckle_token"]
    speckle_host = "https://app.speckle.systems/"

    # Set up Speckle client
    client = SpeckleClient(host=speckle_host)
    client.authenticate_with_token(speckle_token)

    # Fetch streams
    streams = client.stream.list()
    stream_names = [stream.name for stream in streams]
    stream_dict = {stream.name: stream.id for stream in streams}

    # Stream selection dropdown
    selected_stream = st.selectbox("Select a Stream", stream_names)

    if selected_stream:
        stream_id = stream_dict[selected_stream]

        st.write("Choose input method:")
        input_method = st.radio("Input method", ("Upload File", "Upload Folder"), label_visibility="collapsed")

        geojson_data_list = []

        if input_method == "Upload File":
            uploaded_file = st.file_uploader("Choose a file", type=['geojson', 'zip', 'shp'])

            if uploaded_file is not None:
                file_extension = os.path.splitext(uploaded_file.name)[1].lower()

                if file_extension == '.zip':
                    with tempfile.TemporaryDirectory() as temp_dir:
                        zip_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(zip_path, "wb") as f:
                            f.write(uploaded_file.getvalue())
                        
                        try:
                            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_dir)
                            geojson_data_list = process_directory(temp_dir)
                        except zipfile.BadZipFile:
                            st.error("The uploaded file is not a valid ZIP file.")
                            return
                else:
                    data = process_file(uploaded_file)
                    if data:
                        geojson_data_list.append(data)

        elif input_method == "Upload Folder":
            uploaded_files = st.file_uploader("Choose files from a folder", type=['geojson', 'shp'], accept_multiple_files=True)
            
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    data = process_file(uploaded_file)
                    if data:
                        geojson_data_list.append(data)

        if not geojson_data_list:
            st.error("No valid GeoJSON or Shapefile data found in the uploaded file(s) or folder.")
            return

        global_origin = find_global_origin(geojson_data_list)
        st.write(f"Global origin: {global_origin}")

        all_pipes = []
        for data in geojson_data_list:
            pipes = process_all_pipes(data, global_origin)
            if pipes is not None:
                all_pipes.extend(pipes)

        if not all_pipes:
            st.error("No pipes were found in the uploaded file(s) or folder.")
            return

        commit_obj = Base()
        commit_obj["@Revit Pipes From Python"] = all_pipes

        if st.button("Upload to Speckle"):
            transport = ServerTransport(client=client, stream_id=stream_id)

            object_id = operations.send(commit_obj, [transport])

            commit = client.commit.create(stream_id, object_id, message="Sent RevitPipes from Streamlit app")
            
            result_url = f"{speckle_host}/streams/{stream_id}/commits/{commit.id}"
            st.success(f"Successfully processed and uploaded all pipes to Speckle.")
            st.markdown(f"[View Results on Speckle]({result_url})")

            # Embed Speckle viewer
            speckle_viewer_url = f"https://speckle.xyz/embed?stream={stream_id}&commit={commit.id}"
            st.markdown(f"""
            <iframe src="{speckle_viewer_url}" width="100%" height="600px" frameborder="0"></iframe>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
