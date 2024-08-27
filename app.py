import streamlit as st
from specklepy.objects import Base
from specklepy.objects.geometry import Mesh
from specklepy.transports.server import ServerTransport
from specklepy.api import operations
from specklepy.api.client import SpeckleClient
import numpy as np
import plotly.graph_objects as go

def load_ifc_file(file):
    # This function would typically send the file to a Speckle server
    # For demonstration, we'll create a dummy Speckle object
    base = Base()
    base.name = "Dummy IFC Object"
    mesh = Mesh.create(vertices=[0,0,0, 1,0,0, 1,1,0, 0,1,0, 0,0,1, 1,0,1, 1,1,1, 0,1,1],
                       faces=[4,0,1,2,3, 4,4,5,6,7, 4,0,4,7,3, 4,1,5,6,2, 4,0,1,5,4, 4,3,2,6,7])
    base.geometry = mesh
    return base

def extract_meshes(obj):
    meshes = []
    if isinstance(obj, Mesh):
        meshes.append(obj)
    elif hasattr(obj, 'geometry') and isinstance(obj.geometry, Mesh):
        meshes.append(obj.geometry)
    elif isinstance(obj, Base):
        for member_name, member_value in obj.members.items():
            if isinstance(member_value, list):
                for item in member_value:
                    meshes.extend(extract_meshes(item))
            else:
                meshes.extend(extract_meshes(member_value))
    return meshes

def main():
    st.title("IFC File Viewer (using Speckle)")

    uploaded_file = st.file_uploader("Choose an IFC file", type=["ifc"])

    if uploaded_file is not None:
        speckle_object = load_ifc_file(uploaded_file)
        
        meshes = extract_meshes(speckle_object)
        
        if meshes:
            fig = go.Figure()
            for mesh in meshes:
                vertices = np.array(mesh.vertices).reshape(-1, 3)
                i, j, k = mesh.faces[1::4], mesh.faces[2::4], mesh.faces[3::4]
                
                fig.add_trace(go.Mesh3d(x=vertices[:, 0], y=vertices[:, 1], z=vertices[:, 2],
                                        i=i, j=j, k=k, color='lightblue', opacity=0.7))
            
            fig.update_layout(scene=dict(aspectmode='data'))
            st.plotly_chart(fig)
        else:
            st.write("No meshes found in the IFC file.")
    else:
        st.write("Please upload an IFC file.")

if __name__ == "__main__":
    main()