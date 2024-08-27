import streamlit as st
import ifcopenshell
import pyvista as pv
import tempfile
import numpy as np

def load_ifc_file(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_file_path = tmp_file.name
    return ifcopenshell.open(tmp_file_path)

def extract_geometry(product):
    if product.Representation:
        for representation in product.Representation.Representations:
            for item in representation.Items:
                if item.is_a('IfcExtrudedAreaSolid'):
                    return extract_extruded_area_solid(item)
    return None

def extract_extruded_area_solid(item):
    profile = item.SweptArea
    if profile.is_a('IfcRectangleProfileDef'):
        width = profile.XDim
        depth = profile.YDim
        extrusion_depth = item.Depth
        vertices = [
            (0, 0, 0),
            (width, 0, 0),
            (width, depth, 0),
            (0, depth, 0),
            (0, 0, extrusion_depth),
            (width, 0, extrusion_depth),
            (width, depth, extrusion_depth),
            (0, depth, extrusion_depth)
        ]
        faces = [
            [0, 1, 2, 3],
            [4, 5, 6, 7],
            [0, 4, 7, 3],
            [1, 5, 6, 2],
            [0, 1, 5, 4],
            [3, 2, 6, 7]
        ]
        return vertices, faces
    return None

def main():
    st.title("IFC File Viewer")

    uploaded_file = st.file_uploader("Choose an IFC file", type=["ifc"])

    if uploaded_file is not None:
        model = load_ifc_file(uploaded_file)

        products = model.by_type("IfcProduct")

        plotter = pv.Plotter()

        for product in products:
            geometry = extract_geometry(product)
            if geometry:
                vertices, faces = geometry
                mesh = pv.PolyData(vertices, faces)
                plotter.add_mesh(mesh, show_edges=True, color='lightblue')

        # Set camera position
        plotter.camera_position = 'xy'
        plotter.camera.zoom(1.5)

        # Render the plot as an image
        image = plotter.screenshot()
        
        # Display the image in Streamlit
        st.image(image, caption='IFC Model Visualization', use_column_width=True)

if __name__ == "__main__":
    main()