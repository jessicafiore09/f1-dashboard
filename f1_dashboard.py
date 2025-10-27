import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px

# ===== Config =====
BASE_DIR = "Stats"  # Change to your base path
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

def get_available_races(base_dir="Stats", start_year=2010):
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
tab1, tab2, tab3 = st.tabs(["Race Results", "Driver Analysis", "Compare Drivers"])

# --- Tab 1: Race Results ---
with tab1:
    years = sorted(races_dict.keys())
    year = st.selectbox("Select Year", years, key="race_results_year_tab1")

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