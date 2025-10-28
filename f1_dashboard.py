import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
from pathlib import Path
import plotly.graph_objects as go

# ===== Config =====
BASE_DIR = "f1 data"  # Change to your base path
START_YEAR = 2010

# Set page configuration
st.set_page_config(
    page_title="F1 Race Dashboard",
    layout="wide",       # <-- this makes all tabs full width
    initial_sidebar_state="expanded"
)

# ===== Helpers =====
def is_year_dir(name):
    return name.isdigit() and len(name) == 4

def clean_city_display(folder_name):
    return folder_name.lower().replace("-grand-prix", "").replace("-", " ").title()

def get_available_races(base_dir="f1 data", start_year=2010):
    races = {}
    if not os.path.isdir(base_dir):
        return races

    for year in sorted(os.listdir(base_dir)):
        year_path = os.path.join(base_dir, year)
        if not os.path.isdir(year_path) or not is_year_dir(year):
            continue
        if int(year) < start_year:
            continue

        city_folders = []
        for folder in os.listdir(year_path):
            folder_path = os.path.join(year_path, folder)
            if os.path.isdir(folder_path):
                display = clean_city_display(folder)
                city_folders.append((display, folder))

        if city_folders:
            city_folders.sort(key=lambda x: x[0])
            races[year] = {display: folder for display, folder in city_folders}

    return races

def load_race_data(year, folder_name):
    file_path = os.path.join(BASE_DIR, year, folder_name, "results.json")
    if not os.path.isfile(file_path):
        return pd.DataFrame(), None

    with open(file_path, "r") as f:
        data = json.load(f)

    races_list = data["MRData"]["RaceTable"].get("Races", [])
    if not races_list:
        return pd.DataFrame(), None

    race = races_list[0]
    results = race.get("Results", [])

    drivers = []
    for r in results:
        grid = int(r.get("grid", 0)) if str(r.get("grid", "")).isdigit() else None
        position = int(r["position"]) if r.get("position") and r["position"].isdigit() else None
        drivers.append({
            "Position": position,
            "Driver": f"{r['Driver']['givenName']} {r['Driver']['familyName']}",
            "Constructor": r["Constructor"]["name"],
            "Points": float(r["points"]) if r.get("points") else 0,
            "Grid": grid,
            "Position Gained": (grid - position) if position is not None and grid is not None else None,
            "Status": r.get("status", "")
        })

    df = pd.DataFrame(drivers).sort_values("Position").reset_index(drop=True)
    return df, race

# ===== Streamlit UI =====
st.title("F1 Race Dashboard")

races_dict = get_available_races(base_dir=BASE_DIR, start_year=START_YEAR)
if not races_dict:
    st.warning("No race data found in the directory.")

# ===== Tabs =====
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Race Results", "Driver Analysis", "Compare Drivers", "Track Analysis", "Position Movement by Lap"])



# --- Tab 1: Race Results ---
with tab1:
    # Sort years descending so latest year is first
    years = sorted(races_dict.keys(), reverse=True)
    year = st.selectbox("Select Year", years, index=0, key="race_results_year_tab1")

    cities = list(races_dict[year].keys())
    city_display = st.selectbox("Select City", cities, key="race_results_city_tab1")
    folder_name = races_dict[year][city_display]

    df, race_meta = load_race_data(year, folder_name)
    if df.empty or race_meta is None:
        st.warning(f"No race results found for {city_display} {year}.")
    else:
        round_number = race_meta.get("round", "N/A")
        st.subheader(f"Round {round_number} — {city_display} Grand Prix — {year}")
        st.markdown(f"**Circuit:** {race_meta['Circuit']['circuitName']} — **Date:** {race_meta['date']}")
        st.dataframe(df, use_container_width=True)

# --- Tab 2: Driver Analysis ---
with tab2:
    years_list = sorted(races_dict.keys(), reverse=True)
    year_choice = st.selectbox("Select Year", years_list, key="driver_tab_year_tab2")

    drivers_set = set()
    for folder in races_dict[year_choice].values():
        df_race, _ = load_race_data(year_choice, folder)
        if not df_race.empty:
            drivers_set.update(df_race["Driver"].tolist())
    drivers_list = sorted(drivers_set)

    selected_driver = st.selectbox("Select Driver", drivers_list, key="driver_tab_driver_tab2")

    driver_data = []
    for folder in sorted(races_dict[year_choice].values(),
                         key=lambda f: int(load_race_data(year_choice, f)[1].get("round", 0)) if load_race_data(year_choice, f)[1] else 999):
        df_race, race_meta = load_race_data(year_choice, folder)
        if df_race.empty or race_meta is None:
            continue
        row = df_race[df_race["Driver"] == selected_driver]
        if not row.empty:
            driver_data.append({
                "Round": int(race_meta.get("round", 0)),
                "Grand Prix": clean_city_display(folder),
                "Position": row.iloc[0]["Position"],
                "Grid": row.iloc[0]["Grid"],
                "Position Gained": row.iloc[0]["Position Gained"],
                "Points (Season As Of Race)": row.iloc[0]["Points"]
            })
    if not driver_data:
        st.warning("No data available for this driver.")
    else:
        df_driver = pd.DataFrame(driver_data).sort_values("Round")
        st.dataframe(df_driver, use_container_width=True)

        fig_driver = px.line(
            df_driver,
            x="Grand Prix",
            y="Position",
            markers=True,
            title=f"{selected_driver} — {year_choice} Season",
            labels={"Position": "Finishing Position", "Grand Prix": "Grand Prix"},
            line_shape="linear",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )

        fig_driver.add_scatter(
            x=df_driver["Grand Prix"],
            y=df_driver["Grid"],
            mode="lines+markers",
            name="Grid",
            line=dict(width=3, dash="dash", color="plum"),
            marker=dict(size=8, color="plum")
        )

        fig_driver.update_layout(
            yaxis_autorange="reversed",
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis=dict(title="Grand Prix", showgrid=True),
            yaxis=dict(title="Position", showgrid=True, dtick=1),
        )

        st.plotly_chart(fig_driver, use_container_width=True)

# --- Tab 3: Compare Drivers ---
with tab3:
    compare_years = sorted(races_dict.keys(), reverse=True)
    compare_year = st.selectbox("Select Year", compare_years, key="compare_drivers_year_tab3")

    drivers_set = set()
    for folder in races_dict[compare_year].values():
        df_race, _ = load_race_data(compare_year, folder)
        if not df_race.empty:
            drivers_set.update(df_race["Driver"].tolist())
    drivers_list = sorted(drivers_set)

    selected_drivers = st.multiselect(
        "Select Drivers (1-3)",
        drivers_list,
        default=drivers_list[:1],
        max_selections=3,
        key="compare_drivers_tab3"
    )

    if selected_drivers:
        compare_data = []
        compare_champ_data = []

        for folder in sorted(races_dict[compare_year].values(),
                             key=lambda f: int(load_race_data(compare_year, f)[1].get("round", 0)) if load_race_data(compare_year, f)[1] else 999):
            df_race, race_meta = load_race_data(compare_year, folder)
            if df_race.empty or race_meta is None:
                continue

            round_num = int(race_meta.get("round", 0))
            grand_prix = clean_city_display(folder)

            dp_file = os.path.join(BASE_DIR, compare_year, folder, "driverPoints.json")
            if os.path.isfile(dp_file):
                with open(dp_file, "r") as f:
                    dp_json = json.load(f)
                standings = dp_json["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
                driver_points_dict = {
                    f"{d['Driver']['givenName']} {d['Driver']['familyName']}": float(d["points"])
                    for d in standings
                }
            else:
                driver_points_dict = {}

            for driver in selected_drivers:
                row = df_race[df_race["Driver"] == driver]
                if not row.empty:
                    points = row.iloc[0]["Points"]
                    compare_data.append({
                        "Round": round_num,
                        "Grand Prix": grand_prix,
                        "Driver": driver,
                        "Points (Season As Of Race)": points
                    })

                champ_points = driver_points_dict.get(driver, 0)
                compare_champ_data.append({
                    "Round": round_num,
                    "Grand Prix": grand_prix,
                    "Driver": driver,
                    "Driver Points": champ_points
                })

        # Graph 1: Points per race
        if compare_data:
            df_compare = pd.DataFrame(compare_data).sort_values(["Round", "Driver"])
            fig_points = px.line(
                df_compare,
                x="Grand Prix",
                y="Points (Season As Of Race)",
                color="Driver",
                markers=True,
                title=f"Drivers' Points per Race — {compare_year}",
                labels={"Points (Season As Of Race)": "Driver Points", "Grand Prix": "Grand Prix"},
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_points.update_traces(
                text=df_compare["Points (Season As Of Race)"],
                textposition="top center",
                textfont=dict(color="lightgrey", size=10),
                marker=dict(size=8)
            )
            st.plotly_chart(fig_points, use_container_width=True)

        # Graph 2: Championship points
        if compare_champ_data:
            df_champ = pd.DataFrame(compare_champ_data).sort_values(["Round", "Driver"])
            fig_champ = px.line(
                df_champ,
                x="Grand Prix",
                y="Driver Points",
                color="Driver",
                markers=True,
                title=f"Drivers' Championship Points — {compare_year}",
                labels={"Driver Points": "Championship Points", "Grand Prix": "Grand Prix"},
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_champ.update_traces(
                text=df_champ["Driver Points"],
                textposition="top center",
                textfont=dict(color="lightgrey", size=10),
                marker=dict(size=8)
            )
            st.plotly_chart(fig_champ, use_container_width=True)

# --- Tab 4: Track Analysis ---
with tab4:
    st.subheader("Track Analysis — Top 5 Finishers Over 5 Years")

    years_to_compare = ["2025", "2024", "2023", "2022", "2021"]
    available_years = [y for y in years_to_compare if y in races_dict]

    # Collect all track names across available years
    track_names = set()
    for year in available_years:
        for display in races_dict[year].keys():
            track_names.add(display)
    track_names = sorted(track_names)

    selected_track = st.selectbox("Select Track", track_names, key="track_analysis_tab4")

    # Prepare table data
    table_data = []
    positions_to_show = [1, 2, 3, 4, 5]

    for pos in positions_to_show:
        row = {"Track Name": f"{selected_track} — P{pos}"}
        for year in available_years:
            folder = races_dict[year].get(selected_track)
            if folder:
                df_race, _ = load_race_data(year, folder)
                if not df_race.empty:
                    driver = df_race.loc[df_race["Position"] == pos, "Driver"].values
                    row[f"{year}"] = driver[0] if len(driver) > 0 else "N/A"
                else:
                    row[f"{year}"] = "No Data"
            else:
                row[f"{year}"] = "N/A"
        table_data.append(row)

    df_track = pd.DataFrame(table_data)

    # Reorder columns to match desired order
    cols = ["Track Name"] + available_years
    df_track = df_track[cols]

    st.dataframe(df_track, use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import json

with tab5:
    # --- Select Year and Race ---
    years_list = sorted(os.listdir("/Users/jessicafiore/f1-dashboard/"), reverse=True)
    year_choice = st.selectbox("Select Year", "2025", key="tab5_year")

    races_path = f"/Users/jessicafiore/f1-dashboard/{year_choice}"
    all_races = [r for r in os.listdir(races_path) if r.endswith("Grand Prix")]
    race_choice = st.selectbox("Select Race", all_races, key="tab5_race")

    race_folder = os.path.join(races_path, race_choice, "Race")

    # --- Load lap times data for all drivers ---
    lap_data = []
    for driver in os.listdir(race_folder):
        driver_path = os.path.join(race_folder, driver, "laptimes.json")
        if not os.path.exists(driver_path):
            continue
        with open(driver_path) as f:
            data = json.load(f)
        if "pos" not in data or not data["pos"]:
            continue
        for lap, pos, stint, comp in zip(data["lap"], data["pos"], data["stint"], data["compound"]):
            if pos == "None":
                continue
            lap_data.append({
                "Driver": driver,
                "Lap": lap,
                "Position": int(pos),
                "Stint": int(stint),
                "Compound": comp
            })

    if not lap_data:
        st.warning("No lap positions found for this race.")
    else:
        df = pd.DataFrame(lap_data)

        # --- Order drivers by Lap 1 position ---
        lap1_df = df[df["Lap"] == 1].sort_values("Position")
        driver_order = lap1_df["Driver"].tolist()
        df["Driver"] = pd.Categorical(df["Driver"], categories=driver_order, ordered=True)

        # --- Vertical spacing ---
        spacing_factor = 1.5
        df["Position_display"] = df["Position"] * spacing_factor

        # --- Marker shapes per stint ---
        stint_shapes = {1: "circle", 2: "square", 3: "triangle-up", 4: "diamond", 5: "cross", 6: "x"}
        df["Marker"] = df["Stint"].map(lambda x: stint_shapes.get(x, "circle"))

        # --- Assign calm and consistent colors per driver ---
        calm_colors = [
            "#4B8BBE", "#306998", "#FFE873", "#FFD43B", "#646464", 
            "#9B9B9B", "#6A5ACD", "#20B2AA", "#FFB347", "#D2691E",
            "#B0C4DE", "#CFCFCF", "#8FBC8F", "#D8BFD8", "#A9A9A9",
            "#5F9EA0", "#778899", "#CD853F", "#87CEFA", "#BC8F8F"
        ]
        driver_colors = {driver: calm_colors[i % len(calm_colors)] for i, driver in enumerate(driver_order)}

        # --- Create figure ---
        fig = go.Figure()

        for driver in driver_order:
            df_driver = df[df["Driver"] == driver]
            color = driver_colors[driver]

            # Draw line
            fig.add_trace(go.Scatter(
                x=df_driver["Lap"],
                y=df_driver["Position_display"],
                mode="lines",
                line=dict(color=color, width=2),
                name=driver,
                legendgroup=driver,
                hoverinfo="skip"  # line itself will not show hover
            ))

            fig.update_layout(
            height=700,  # stretch the graph vertically
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(title='Lap', showgrid=True),
            yaxis=dict(title='Position', showgrid=True, dtick=1, autorange='reversed')
        )


            # Draw markers per stint on top with hover info
            for stint in df_driver["Stint"].unique():
                df_stint = df_driver[df_driver["Stint"] == stint]
                fig.add_trace(go.Scatter(
                    x=df_stint["Lap"],
                    y=df_stint["Position_display"],
                    mode="markers",
                    marker=dict(symbol=stint_shapes.get(stint, "circle"), size=10, color=color),
                    name=driver,
                    legendgroup=driver,
                    showlegend=False,
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Lap: %{x}<br>"
                        "Position: %{y:.0f}<br>"
                        "Stint: %{customdata[1]}<br>"
                        "Tyre: %{customdata[2]}<extra></extra>"
                    ),
                    customdata=df_stint[["Driver", "Stint", "Compound"]].values
                ))

        max_pos = df["Position"].max()
        fig.update_layout(
            yaxis=dict(
                autorange="reversed",
                title="Position",
                dtick=spacing_factor,
                tickvals=[i * spacing_factor for i in range(1, max_pos + 1)],
                ticktext=[str(i) for i in range(1, max_pos + 1)]
            ),
            xaxis=dict(title="Lap"),
            legend=dict(
                title="Driver",
                yanchor="top",
                y=1,
                x=-0.25,
                traceorder="normal",
                orientation="v"
            ),
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=150)
        )

        st.plotly_chart(fig, use_container_width=True)