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


def find_global_origin(geojson_data_list):
    min_x, min_y = float('inf'), float('inf')
    for data in geojson_data_list:
        features = data['features']
        for feature in features:
            if feature['geometry']['type'] == 'LineString':
                coordinates = feature['geometry']['coordinates']
                for lon, lat in coordinates:
                    x, y = convert_to_revit_units(lon, lat)
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
    return min_x, min_y

def create_unique_speckle_classes():
    unique_id = uuid.uuid4().hex[:8]  # Generate a unique identifier

    class RevitPipe(Base, speckle_type="Objects.BuiltElements.Revit.Pipe"):
        baseCurve: "RevitCurve" = None
        type: "RevitPipeType" = None
        level: "RevitLevel" = None
        systemName: str = None
        diameter: float = None

    class RevitCurve(Base, speckle_type="Objects.BuiltElements.Revit.Curve"):
        baseLine: Line = None
        units: str = None

    class RevitPipeType(Base, speckle_type="Objects.BuiltElements.Revit.PipeType"):
        name: str = None
        family: str = None

    class RevitLevel(Base, speckle_type="Objects.BuiltElements.Revit.Level"):
        name: str = None
        elevation: float = None
        units: str = None

    return {
        "RevitPipe": RevitPipe,
        "RevitCurve": RevitCurve,
        "RevitPipeType": RevitPipeType,
        "RevitLevel": RevitLevel
    }

# Create Speckle classes with unique names
SpeckleClasses = create_unique_speckle_classes()

def create_revit_pipe(start_point, end_point, diameter, level_elevation):
    base_curve = SpeckleClasses["RevitCurve"](
        baseLine=Line(start=start_point, end=end_point),
        units="m"
    )
    
    pipe_type = SpeckleClasses["RevitPipeType"](
        name="Standard",
        family="Pipe Types"
    )
    
    level = SpeckleClasses["RevitLevel"](
        name="Level 0",
        elevation=level_elevation,
        units="m"
    )
    
    return SpeckleClasses["RevitPipe"](
        baseCurve=base_curve,
        type=pipe_type,
        level=level,
        systemName="Domestic Cold Water",
        diameter=diameter
    )

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
            
            diameter = 0.2  # 200 mm in meters
            level_elevation = 0  # Assuming all pipes are at ground level

            pipe = create_revit_pipe(start, end, diameter, level_elevation)
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

# ... (other functions like find_global_origin and process_all_pipes remain the same)

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

        # Process the GeoJSON data into pipes
        global_origin = find_global_origin(geojson_data_list)
        all_pipes = []
        for data in geojson_data_list:
            pipes = process_all_pipes(data, global_origin)
            if pipes:
                all_pipes.extend(pipes)

        if not all_pipes:
            st.error("No pipes could be created from the provided data.")
            return

        # Create a Base object and add pipes to it
        base = Base()
        base["@Pipes"] = all_pipes
    
        if st.button("Upload to Speckle"):
            try:
                st.info("Initiating Speckle upload process...")
                
                # Ensure the client is authenticated
                if not client.account:
                    st.error("Speckle client is not authenticated. Please check your token.")
                    return
    
                # Create a new transport
                transport = ServerTransport(client=client, stream_id=stream_id)
    
                # Send the object
                st.info("Sending object to Speckle...")
                object_id = operations.send(base, [transport])
                st.success(f"Object sent successfully. Object ID: {object_id}")
    
                # Create the commit
                st.info("Creating commit...")
                commit = client.commit.create(stream_id, object_id, message="Sent RevitPipes from Streamlit app")
                    
                if commit and hasattr(commit, 'id'):
                    result_url = f"{speckle_host}/streams/{stream_id}/commits/{commit.id}"
                    st.success(f"Successfully processed and uploaded all pipes to Speckle.")
                    st.markdown(f"[View Results on Speckle]({result_url})")

                    # Embed Speckle viewer
                    speckle_viewer_url = f"https://speckle.xyz/embed?stream={stream_id}&commit={commit.id}"
                    st.markdown(f"""
                    <iframe src="{speckle_viewer_url}" width="100%" height="600px" frameborder="0"></iframe>
                    """, unsafe_allow_html=True)
                else:
                    st.error("Failed to create commit. Please check your Speckle configuration and try again.")
            except Exception as e:
                st.error(f"An error occurred during the Speckle upload process: {str(e)}")

if __name__ == "__main__":
    main()
