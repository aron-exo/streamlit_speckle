import streamlit as st
import os
import tempfile
import zipfile
import rarfile
import json
import geopandas as gpd
from pyproj import Proj, transform
from specklepy.objects import Base
from specklepy.objects.geometry import Line, Point
from specklepy.api.client import SpeckleClient
from specklepy.transports.server import ServerTransport
from specklepy.api import operations

# Define your projection (example using UTM Zone 18N)
utm_proj = Proj(proj='utm', zone=18, ellps='WGS84')
latlon_proj = Proj(proj='latlong', datum='WGS84')

# Utility functions
def inches_to_feet(inches):
    return inches / 12

def feet_to_internal_units(feet):
    return feet * 0.3048  # Convert feet to meters (Revit's internal unit)

def convert_to_revit_units(lon, lat):
    x, y = transform(latlon_proj, utm_proj, lon, lat)
    return feet_to_internal_units(x), feet_to_internal_units(y)

# Function to create Speckle classes
def create_speckle_classes():
    class Level(Base, speckle_type="Objects.BuiltElements.Level"):
        name: str = None
        elevation: float = None

    class Parameter(Base):
        name: str = None
        value: object = None

    class RevitPipe(Base, speckle_type="Objects.BuiltElements.Revit.RevitPipe"):
        family: str = None
        type: str = None
        baseCurve: Line = None
        diameter: float = None
        level: Level = None
        systemName: str = None
        systemType: str = None
        parameters: Base = None
        elementId: str = None

        def __init__(self, family, type, baseCurve, diameter_inches, level, systemName="", systemType="", parameters=None):
            super().__init__()
            self.family = family
            self.type = type
            self.baseCurve = baseCurve
            self.diameter = inches_to_feet(diameter_inches)
            self.level = level
            self.systemName = systemName
            self.systemType = systemType
            self.parameters = Base()
            if parameters:
                for param in parameters:
                    setattr(self.parameters, param.name, param.value)

    return Level, Parameter, RevitPipe

# Create Speckle classes
Level, Parameter, RevitPipe = create_speckle_classes()

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
            
            diameter_inches = 200 / 25.4
            system_name = 'Domestic Cold Water'
            system_type = 'Supply'

            level = Level(name="Level 0", elevation=0)
            pipe = RevitPipe(
                family="Standard Pipe Types",
                type="Standard",
                baseCurve=Line(start=start, end=end),
                diameter_inches=diameter_inches,
                level=level,
                systemName=system_name,
                systemType=system_type,
                parameters=[Parameter(name="Comments", value="Pipe from GeoJSON")]
            )
            pipes.append(pipe)

    return pipes

def process_file(file_path):
    _, file_extension = os.path.splitext(file_path)
    if file_extension.lower() == '.geojson':
        with open(file_path, 'r') as f:
            return json.load(f)
    elif file_extension.lower() == '.shp':
        gdf = gpd.read_file(file_path)
        return json.loads(gdf.to_json())
    else:
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
        input_method = st.radio("", ("Upload File", "Upload Folder"))

        geojson_data_list = []
        
        if input_method == "Upload File":
            uploaded_file = st.file_uploader("Choose a file", type=['geojson', 'zip', 'rar', 'shp'])

            if uploaded_file is not None:
                file_extension = os.path.splitext(uploaded_file.name)[1].lower()

                with tempfile.TemporaryDirectory() as temp_dir:
                    if file_extension in ['.zip', '.rar']:
                        file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        if file_extension == '.zip':
                            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_dir)
                        else:  # .rar
                            with rarfile.RarFile(file_path, 'r') as rar_ref:
                                rar_ref.extractall(temp_dir)
                        
                        geojson_data_list = process_directory(temp_dir)
                    else:
                        data = process_file(uploaded_file)
                        if data:
                            geojson_data_list.append(data)

        elif input_method == "Upload Folder":
            uploaded_folder = st.file_uploader("Choose a folder", type=['geojson', 'shp'], accept_multiple_files=True)
            
            if uploaded_folder:
                with tempfile.TemporaryDirectory() as temp_dir:
                    for uploaded_file in uploaded_folder:
                        file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                    
                    geojson_data_list = process_directory(temp_dir)

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
