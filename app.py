import streamlit as st
import ifcopenshell
import pandas as pd
import plotly.graph_objects as go

def load_ifc_file(file):
    return ifcopenshell.open(file)

def get_products(ifc_file):
    return ifc_file.by_type("IfcProduct")

def filter_products(products):
    return [p for p in products if p.Representation is not None and 
            not p.is_a("IfcOpeningElement") and 
            not p.is_a("IfcSite") and 
            not p.is_a("IfcAnnotation")]

def get_product_data(product):
    return {
        "id": product.id(),
        "type": product.is_a(),
        "name": product.Name,
        "guid": product.GlobalId
    }

def main():
    st.title("IFC File Viewer")

    uploaded_file = st.file_uploader("Choose an IFC file", type="ifc")

    if uploaded_file is not None:
        ifc_file = load_ifc_file(uploaded_file)
        products = get_products(ifc_file)
        filtered_products = filter_products(products)

        st.write(f"Total products: {len(products)}")
        st.write(f"Products with 3D representation: {len(filtered_products)}")

        product_data = [get_product_data(p) for p in filtered_products]
        df = pd.DataFrame(product_data)

        st.subheader("Product Data")
        st.dataframe(df)

        st.subheader("Product Types Distribution")
        type_counts = df['type'].value_counts()
        fig = go.Figure(data=[go.Pie(labels=type_counts.index, values=type_counts.values)])
        st.plotly_chart(fig)

if __name__ == "__main__":
    main()
