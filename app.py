import streamlit as st
import os

# Title of the app
st.title("IFC File Viewer using IFC.js")

# File uploader to allow users to upload an IFC file
uploaded_file = st.file_uploader("Choose an IFC file", type=["ifc"])

if uploaded_file is not None:
    # Save the uploaded file temporarily
    temp_ifc_path = os.path.join(os.getcwd(), "temp.ifc")
    with open(temp_ifc_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # HTML and JavaScript to load and display the IFC file using IFC.js
    html_code = f"""
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/ifc.js@0.0.145/dist/IFC.min.js"></script>
    </head>
    <body>
        <div id="ifc-container" style="width: 100%; height: 600px;"></div>
        <script>
            async function loadIFC() {{
                const container = document.getElementById('ifc-container');
                const ifcLoader = new IfcLoader();
                const model = await ifcLoader.load('{temp_ifc_path}');
                container.appendChild(model);
            }}
            loadIFC();
        </script>
    </body>
    </html>
    """

    # Display the HTML and JavaScript in the Streamlit app
    st.components.v1.html(html_code, height=600)

    # Optional: Clean up the temporary IFC file after it's loaded
    if os.path.exists(temp_ifc_path):
        os.remove(temp_ifc_path)
else:
    st.write("Please upload an IFC file to view it.")
