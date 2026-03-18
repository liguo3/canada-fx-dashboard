import streamlit as st
import pandas as pd

st.set_page_config(page_title="Canada Dashboard", layout="wide")

st.title("Canada Dashboard")
st.subheader("Prima mini app")

data = pd.DataFrame({
    "giorno": ["Lun", "Mar", "Mer", "Gio", "Ven"],
    "usd_cad": [1.37, 1.365, 1.372, 1.368, 1.375]
})

st.line_chart(data.set_index("giorno"))
st.dataframe(data)