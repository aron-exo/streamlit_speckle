import streamlit as st
from streamlit_javascript import st_javascript

def main():
    st.set_page_config(page_title="IFC Viewer", layout="wide")
    st.title("IFC Viewer")

    # File uploader
    uploaded_file = st.file_uploader("Choose an IFC file", type="ifc")

    if uploaded_file is not None:
        # Save the uploaded file temporarily
        with open("temp.ifc", "wb") as f:
            f.write(uploaded_file.getvalue())

        # HTML and JavaScript for IFC viewer
        viewer_html = """
        <div id="viewer-container" style="width: 100%; height: 600px;"></div>
        <script src="https://unpkg.com/three@0.133.1/build/three.min.js"></script>
        <script src="https://unpkg.com/web-ifc-viewer@1.0.207/dist/web-ifc-viewer.js"></script>
        <script>
            const container = document.getElementById('viewer-container');
            const viewer = new WebIFCViewer.Viewer({container});
            viewer.IFC.setWasmPath("https://unpkg.com/web-ifc@0.0.36/");
            
            async function loadIFC() {
                const model = await viewer.IFC.loadIfcUrl("temp.ifc");
                viewer.shadowDropper.renderShadow(model.modelID);
                viewer.context.renderer.postProduction.active = true;
            }
            
            loadIFC();
        </script>
        """

        # Render the viewer
        st.components.v1.html(viewer_html, height=600)

if __name__ == "__main__":
    main()