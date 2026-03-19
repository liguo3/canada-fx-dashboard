import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Macro Dashboard", layout="wide")

# =========================
# SIDEBAR
# =========================
st.sidebar.title("Macro Dashboard")

country = st.sidebar.selectbox(
    "Country",
    ["Canada"]
)

category = st.sidebar.selectbox(
    "Category",
    ["Inflation", "Retail Sales"]
)

# =========================
# CANADA - INFLATION
# =========================
def show_canada_inflation():
    DATA_FILE = Path("data/canada_inflation_rate.csv")
    NEXT_RELEASE_DATE = pd.Timestamp("2026-04-20")

    st.title("Canada Inflation Rate")

    if not DATA_FILE.exists():
        st.error("File dati non trovato: data/canada_inflation_rate.csv")
        return

    df = pd.read_csv(DATA_FILE)

    required_cols = ["date", "inflation_rate", "release_date"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error("Nel CSV mancano queste colonne: " + ", ".join(missing_cols))
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df["inflation_rate"] = pd.to_numeric(df["inflation_rate"], errors="coerce")

    df = df.dropna(subset=["date", "release_date"]).sort_values("date")
    df = df[df["date"] >= "2000-01-01"].copy()

    if df.empty:
        st.warning("Nessun dato disponibile.")
        return

    df_plot = df.dropna(subset=["inflation_rate"]).copy()
    last_row = df_plot.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ultimo mese disponibile", last_row["date"].strftime("%Y-%m"))
    c2.metric("Inflation Rate", f"{last_row['inflation_rate']:.2f}%")
    c3.metric("Release date", last_row["release_date"].strftime("%Y-%m-%d"))
    c4.metric("Next release date", NEXT_RELEASE_DATE.strftime("%Y-%m-%d"))

    chart_type = st.radio(
        "Tipo di grafico",
        ["Barre", "Linea"],
        horizontal=True,
        key="inflation_chart_type"
    )

    fig = go.Figure()

    customdata = (
        df_plot[["date", "release_date"]]
        .assign(
            date=lambda x: x["date"].dt.strftime("%Y-%m"),
            release_date=lambda x: x["release_date"].dt.strftime("%Y-%m-%d"),
        )
        .to_numpy()
    )

    hovertemplate = (
        "Dato riferito a: %{customdata[0]}<br>"
        "Data di rilascio: %{customdata[1]}<br>"
        "Inflation Rate: %{y:.2f}%<extra></extra>"
    )

    if chart_type == "Barre":
        fig.add_trace(
            go.Bar(
                x=df_plot["date"],
                y=df_plot["inflation_rate"],
                name="Inflation Rate",
                marker_color="royalblue",
                customdata=customdata,
                hovertemplate=hovertemplate,
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=df_plot["date"],
                y=df_plot["inflation_rate"],
                name="Inflation Rate",
                mode="lines",
                line=dict(width=2),
                customdata=customdata,
                hovertemplate=hovertemplate,
            )
        )

    fig.update_layout(
        height=550,
        xaxis_title="Mese del dato",
        yaxis_title="Inflation Rate (%)",
        hovermode="closest",
        xaxis=dict(
            rangeslider=dict(visible=True),
            type="date",
            rangeselector=dict(
                buttons=[
                    dict(count=5, label="5Y", step="year", stepmode="backward"),
                    dict(count=10, label="10Y", step="year", stepmode="backward"),
                    dict(count=20, label="20Y", step="year", stepmode="backward"),
                    dict(label="All", step="all"),
                ]
            ),
        ),
    )

    st.plotly_chart(fig, use_container_width=True)


# =========================
# CANADA - RETAIL SALES
# =========================
def show_canada_retail_sales():
    RETAIL_FILE = Path("data/canada_retail_sales.csv")
    RETAIL_NEXT_RELEASE_DATE = pd.Timestamp("2026-03-20")

    def re_reference_chained_series(df, chained_col, nominal_col, base_year):
        df = df.copy()
        base_mask = df["date"].dt.year == base_year

        base_nominal = df.loc[base_mask, nominal_col].mean()
        base_chained = df.loc[base_mask, chained_col].mean()

        if pd.isna(base_nominal) or pd.isna(base_chained) or base_chained == 0:
            return pd.Series(index=df.index, dtype="float64")

        factor = base_nominal / base_chained
        return df[chained_col] * factor

    st.title("Canada Retail Sales")

    if not RETAIL_FILE.exists():
        st.info("File retail sales non trovato. Esegui prima scripts/update_retail_sales.py")
        return

    retail = pd.read_csv(RETAIL_FILE)

    required_cols = [
        "date",
        "release_date",
        "retail_sales_current_dollars",
        "retail_sales_chained_2017_dollars",
    ]
    missing_cols = [col for col in required_cols if col not in retail.columns]

    if missing_cols:
        st.error("Nel CSV retail mancano queste colonne: " + ", ".join(missing_cols))
        return

    retail["date"] = pd.to_datetime(retail["date"], errors="coerce")
    retail["release_date"] = pd.to_datetime(retail["release_date"], errors="coerce")
    retail["retail_sales_current_dollars"] = pd.to_numeric(
        retail["retail_sales_current_dollars"], errors="coerce"
    )
    retail["retail_sales_chained_2017_dollars"] = pd.to_numeric(
        retail["retail_sales_chained_2017_dollars"], errors="coerce"
    )

    retail = retail.dropna(subset=["date", "release_date"]).sort_values("date")
    retail = retail[retail["date"] >= "2000-01-01"].copy()

    if retail.empty:
        st.warning("Nessun dato retail disponibile.")
        return

    retail["current_dollars_mom"] = retail["retail_sales_current_dollars"].pct_change() * 100

    available_base_years = sorted(
        retail.loc[
            retail["retail_sales_chained_2017_dollars"].notna()
            & retail["retail_sales_current_dollars"].notna(),
            "date"
        ].dt.year.unique().tolist()
    )
    available_base_years = [y for y in available_base_years if 2017 <= y <= 2025]

    default_base_year = 2017 if 2017 in available_base_years else available_base_years[0]

    retail["chained_selected_base_dollars"] = re_reference_chained_series(
        retail,
        "retail_sales_chained_2017_dollars",
        "retail_sales_current_dollars",
        default_base_year,
    )

    latest_release_row = retail.dropna(subset=["release_date"]).iloc[-1]

    m1, m2, m3 = st.columns(3)
    m1.metric("Ultimo mese disponibile", latest_release_row["date"].strftime("%Y-%m"))
    m2.metric("Release date", latest_release_row["release_date"].strftime("%Y-%m-%d"))
    m3.metric("Next release date", RETAIL_NEXT_RELEASE_DATE.strftime("%Y-%m-%d"))

    c1, c2, c3 = st.columns([2, 2, 2])

    selected_series = c1.multiselect(
        "Serie retail sales",
        ["Current dollars", "Chained dollars"],
        default=["Current dollars"],
        key="retail_series_multi",
    )

    retail_view = c2.radio(
        "Visualizzazione",
        ["Dollari", "Variazione % m/m"],
        horizontal=True,
        key="retail_view_mode",
    )

    retail_chart_type = c3.radio(
        "Tipo di grafico retail",
        ["Barre", "Linea"],
        horizontal=True,
        key="retail_chart_type",
    )

    chained_base_year = None
    if "Chained dollars" in selected_series:
        chained_base_year = st.selectbox(
            "Base year per chained dollars",
            available_base_years,
            index=available_base_years.index(default_base_year),
            key="retail_base_year",
        )

        retail["chained_selected_base_dollars"] = re_reference_chained_series(
            retail,
            "retail_sales_chained_2017_dollars",
            "retail_sales_current_dollars",
            chained_base_year,
        )
        retail["chained_selected_base_mom"] = retail["chained_selected_base_dollars"].pct_change() * 100
    else:
        retail["chained_selected_base_mom"] = pd.Series(index=retail.index, dtype="float64")

    if not selected_series:
        st.warning("Seleziona almeno una serie.")
        return

    fig_retail = go.Figure()

    chained_level_label = (
        f"Chained dollars ({chained_base_year} base)"
        if chained_base_year is not None
        else "Chained dollars"
    )
    chained_mom_label = (
        f"Chained dollars ({chained_base_year} base) m/m"
        if chained_base_year is not None
        else "Chained dollars m/m"
    )

    series_map = {
        "Current dollars": {
            "level_col": "retail_sales_current_dollars",
            "mom_col": "current_dollars_mom",
            "color": "royalblue",
            "label_level": "Current dollars",
            "label_mom": "Current dollars m/m",
        },
        "Chained dollars": {
            "level_col": "chained_selected_base_dollars",
            "mom_col": "chained_selected_base_mom",
            "color": "darkorange",
            "label_level": chained_level_label,
            "label_mom": chained_mom_label,
        },
    }

    for series_name in selected_series:
        cfg = series_map[series_name]

        if retail_view == "Dollari":
            y_col = cfg["level_col"]
            trace_name = cfg["label_level"]
            y_axis_title = "Retail sales (dollars)"
            hover_value = "%{y:,.0f}"
        else:
            y_col = cfg["mom_col"]
            trace_name = cfg["label_mom"]
            y_axis_title = "Variazione % m/m"
            hover_value = "%{y:.2f}%"

        retail_plot = retail.dropna(subset=[y_col]).copy()

        customdata = (
            retail_plot[["date", "release_date"]]
            .assign(
                date=lambda x: x["date"].dt.strftime("%Y-%m"),
                release_date=lambda x: x["release_date"].dt.strftime("%Y-%m-%d"),
            )
            .to_numpy()
        )

        hovertemplate = (
            "Dato riferito a: %{customdata[0]}<br>"
            "Data di rilascio: %{customdata[1]}<br>"
            f"{trace_name}: {hover_value}<extra></extra>"
        )

        if retail_chart_type == "Barre":
            fig_retail.add_trace(
                go.Bar(
                    x=retail_plot["date"],
                    y=retail_plot[y_col],
                    name=trace_name,
                    marker_color=cfg["color"],
                    customdata=customdata,
                    hovertemplate=hovertemplate,
                )
            )
        else:
            fig_retail.add_trace(
                go.Scatter(
                    x=retail_plot["date"],
                    y=retail_plot[y_col],
                    name=trace_name,
                    mode="lines",
                    line=dict(color=cfg["color"], width=2),
                    customdata=customdata,
                    hovertemplate=hovertemplate,
                )
            )

    if retail_view == "Dollari":
        chart_title = "Retail Sales Canada"
        y_axis_title = "Retail sales (dollars)"
    else:
        chart_title = "Retail Sales Canada — variazione % m/m"
        y_axis_title = "Variazione % m/m"

    fig_retail.update_layout(
        title=chart_title,
        height=550,
        xaxis_title="Mese del dato",
        yaxis_title=y_axis_title,
        hovermode="closest",
        barmode="group",
        xaxis=dict(
            rangeslider=dict(visible=True),
            type="date",
            rangeselector=dict(
                buttons=[
                    dict(count=5, label="5Y", step="year", stepmode="backward"),
                    dict(count=10, label="10Y", step="year", stepmode="backward"),
                    dict(count=20, label="20Y", step="year", stepmode="backward"),
                    dict(label="All", step="all"),
                ]
            ),
        ),
    )

    st.plotly_chart(fig_retail, use_container_width=True)

    st.caption(
        "Cambiare il base year dei chained dollars modifica il livello della serie, "
        "non la dinamica reale sottostante."
    )


# =========================
# ROUTER
# =========================
if country == "Canada" and category == "Inflation":
    show_canada_inflation()

elif country == "Canada" and category == "Retail Sales":
    show_canada_retail_sales()