import streamlit as st
import ifcopenshell
import pyvista as pv
from pyvista import examples

# Set up the Streamlit app
st.title("IFC File Viewer")

# File uploader for IFC files
uploaded_file = st.file_uploader("Choose an IFC file", type=["ifc"])

if uploaded_file is not None:
    # Load the IFC file
    model = ifcopenshell.open(uploaded_file)

    # Extract geometries
    products = model.by_type("IfcProduct")

    # Initialize PyVista plotter
    plotter = pv.Plotter()

    # Iterate over the products to extract and visualize geometry
    for product in products:
        shape = product.Representation.Representations[0].Items[0]
        if shape.is_a("IfcFacetedBrep"):
            vertices = shape.Outer.CfsFaces[0].Bound.VertexLoop[0].Vertex.Point.Coordinates
            vertices = [list(map(float, v)) for v in vertices]
            faces = shape.Outer.CfsFaces
            face_indices = []
            for face in faces:
                loop = face.Bound.Loop
                indices = [product.Representation.Representations[0].Items.index(loop)]
                face_indices.append(indices)
            
            # Create a mesh for visualization
            mesh = pv.PolyData(vertices, face_indices)
            plotter.add_mesh(mesh, show_edges=True, color='white')

    # Show the visualization in Streamlit
    st.pyplot(plotter.show(screenshot=True))