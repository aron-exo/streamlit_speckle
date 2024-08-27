import streamlit as st
import os
import uuid

def main():
    st.set_page_config(page_title="IFC Viewer", layout="wide")
    st.title("IFC Viewer")

    # File uploader
    uploaded_file = st.file_uploader("Choose an IFC file", type="ifc")

    if uploaded_file is not None:
        # Generate a unique filename
        file_id = uuid.uuid4()
        file_path = f"temp_{file_id}.ifc"
        
        # Save the uploaded file temporarily
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        
        # Debug info
        st.write(f"File uploaded: {uploaded_file.name}")
        st.write(f"File size: {os.path.getsize(file_path)} bytes")

        # Get the URL for the uploaded file
        file_url = st.get_serve_file_url(file_path)

        # HTML and JavaScript for IFC viewer
        viewer_html = f"""
        <div id="viewer-container" style="width: 100%; height: 600px;"></div>
        <script src="https://unpkg.com/three@0.133.1/build/three.min.js"></script>
        <script src="https://unpkg.com/web-ifc-viewer@1.0.207/dist/web-ifc-viewer.js"></script>
        <script>
            const container = document.getElementById('viewer-container');
            const viewer = new WebIFCViewer.Viewer({{container}});
            viewer.IFC.setWasmPath("https://unpkg.com/web-ifc@0.0.36/");
            
            async function loadIFC() {{
                try {{
                    const model = await viewer.IFC.loadIfcUrl("{file_url}");
                    viewer.shadowDropper.renderShadow(model.modelID);
                    viewer.context.renderer.postProduction.active = true;
                    console.log("IFC model loaded successfully");
                }} catch (error) {{
                    console.error("Error loading IFC model:", error);
                    document.getElementById('viewer-container').innerHTML = 'Error loading IFC model: ' + error.message;
                }}
            }}
            
            loadIFC();
        </script>
        """

        # Render the viewer
        st.components.v1.html(viewer_html, height=600)

        # Add JavaScript to log any errors
        st.components.v1.html("""
        <script>
            window.onerror = function(message, source, lineno, colno, error) {
                console.error("JavaScript error:", message, "at", source, ":", lineno);
                document.getElementById('viewer-container').innerHTML += '<br>JavaScript error: ' + message;
            }
        </script>
        """)

        # Clean up the temporary file
        os.remove(file_path)

if __name__ == "__main__":
    main()