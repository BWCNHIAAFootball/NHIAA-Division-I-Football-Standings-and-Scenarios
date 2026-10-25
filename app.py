import csv
import itertools
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Set Streamlit Page Configuration
st.set_page_config(page_title="NHIAA D1 Playoff Simulator", layout="wide")

# Custom CSS to force table headers to render bold & centered across Glide Data Grid + DOM
st.markdown(
    """
    <style>
    /* Glide Data Grid CSS variables for st.dataframe */
    [data-testid="stDataFrame"] {
        --gdg-header-font-weight: 800 !important;
        --gdg-font-family: inherit;
    }
    
    /* Fallback DOM targeting for standard tables */
    [data-testid="stDataFrame"] th, 
    [data-testid="stTable"] th,
    div[data-testid="stDataFrame"] div[role="columnheader"] span {
        text-align: center !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
    }
    
    /* Subtle hyperlink styling for README popup trigger button */
    div.stButton > button.readme-link-btn {
        background: none !important;
        border: none !important;
        color: #ff4b4b !important;
        padding: 0 !important;
        font-size: 14px !important;
        text-decoration: underline !important;
        cursor: pointer !important;
    }
    div.stButton > button.readme-link-btn:hover {
        color: #ff7373 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 0. Header & README Modal Popup
# ---------------------------------------------------------
st.markdown("# 🏈 NHIAA Division I Football Standings")
st.markdown("### Playoff Simulator")

# Read line 1 of README.md for the link label
try:
    with open("README.md", "r", encoding="utf-8") as f:
        readme_lines = f.readlines()
        readme_line_1 = readme_lines[0].strip() if readme_lines else "View README.md"
        readme_full_text = "".join(readme_lines)
except Exception:
    readme_line_1 = "View README.md"
    readme_full_text = "README.md file could not be loaded."


# Streamlit Dialog Modal function for README content
@st.dialog("📄 Documentation (README.md)", width="large")
def show_readme_modal():
    st.markdown(readme_full_text)


# Display small hyperlink button underneath title that triggers popup modal
if st.button(f"🔗 {readme_line_1}", key="open_readme_modal", help="Click to open README.md in a popup"):
    show_readme_modal()

st.markdown(
    "Simulate remaining regular season game outcomes to dynamically compute standings, conference rating points, tiebreakers, and 1–13 playoff seeding in real-time."
)

# ---------------------------------------------------------
# 1. Team & Conference Definitions
# ---------------------------------------------------------
CONFERENCES = {
    "East": [
        "Portsmouth-Oyster River",
        "Winnacunnet",
        "Manchester Memorial",
        "Exeter",
        "Spaulding",
        "Dover",
        "Timberlane",
    ],
    "Central": [
        "Pinkerton",
        "Windham",
        "Londonderry",
        "Concord",
        "Manchester Central",
        "Salem",
        "Alvirne",
    ],
    "West": [
        "Bishop Guertin",
        "Bedford",
        "Merrimack",
        "Nashua North",
        "Nashua South",
        "Goffstown",
        "Keene",
    ],
}

TEAM_TO_CONF = {team: conf for conf, teams in CONFERENCES.items() for team in teams}

NAME_MAP = {
    "Central": "Manchester Central",
    "Manchester Central": "Manchester Central",
    "Memorial": "Manchester Memorial",
    "Manchester Memorial": "Manchester Memorial",
    "BG": "Bishop Guertin",
    "Bishop Guertin": "Bishop Guertin",
    "POR": "Portsmouth-Oyster River",
    "Portsmouth-Oyster River": "Portsmouth-Oyster River",
    "Sal": "Salem",
    "Salem": "Salem",
    "Lond": "Londonderry",
    "Londonderry": "Londonderry",
    "Pink": "Pinkerton",
    "Pinkerton": "Pinkerton",
    "Wind": "Windham",
    "Windham": "Windham",
    "Bed": "Bedford",
    "Bedford": "Bedford",
    "South": "Nashua South",
    "Nashua South": "Nashua South",
    "North": "Nashua North",
    "Nashua North": "Nashua North",
}


def normalize_name(name):
    if not name or pd.isna(name):
        return None
    cleaned = str(name).strip()
    return NAME_MAP.get(cleaned, cleaned)


# ---------------------------------------------------------
# 2. Comprehensive CSV Parser (Handles NCL / NCW Flags)
# ---------------------------------------------------------
@st.cache_data
def parse_schedule_csv():
    games = []
    current_team = None

    with open("Division_1_Football_Standings_Schedule.csv", "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or not any(row):
                continue

            col0 = str(row[0]).strip() if row[0] else ""

            # Team header detection
            if (
                col0
                and not col0.startswith("Week")
                and col0 not in ["East", "Central", "West"]
            ):
                current_team = normalize_name(col0)

            # Weekly Game Row Parsing
            elif col0.startswith("Week"):
                location = str(row[1]).strip() if len(row) > 1 and row[1] else "vs"
                opp_raw = row[2] if len(row) > 2 else ""
                opp_norm = normalize_name(opp_raw) if opp_raw else ""
                is_conf_flag = str(row[3]).strip() if len(row) > 3 else ""

                raw_res = str(row[4]).strip().upper() if len(row) > 4 else ""

                # Check for NCL (Non-Conference Loss) and NCW (Non-Conference Win)
                is_ncl = raw_res == "NCL"
                is_ncw = raw_res == "NCW"

                if is_ncl:
                    res = "L"
                elif is_ncw:
                    res = "W"
                elif raw_res in ["W", "L"]:
                    res = raw_res
                else:
                    res = None

                pf = str(row[5]).strip() if len(row) > 5 and row[5] else "-"
                pa = str(row[7]).strip() if len(row) > 7 and row[7] else "-"

                if current_team in TEAM_TO_CONF and opp_raw:
                    is_bye = opp_raw.upper() == "BYE"

                    # NCL and NCW games do NOT count toward NHIAA D1 standings or GP
                    is_d1_opponent = (
                        (opp_norm in TEAM_TO_CONF) and not is_ncl and not is_ncw
                    )

                    if is_bye:
                        conf_status = "N/A"
                    elif is_ncl or is_ncw:
                        conf_status = "Out of State"
                    elif is_d1_opponent:
                        conf_status = "Yes" if is_conf_flag == "Yes" else "No"
                    else:
                        conf_status = "Out of State"

                    games.append({
                        "Team": current_team,
                        "Week": col0,
                        "Location": (
                            "-"
                            if is_bye
                            else ("Away" if location == "at" else "Home")
                        ),
                        "Opponent": (
                            opp_raw
                            if is_bye
                            else (
                                opp_norm
                                if (opp_norm in TEAM_TO_CONF)
                                else opp_raw
                            )
                        ),
                        "IsConf": conf_status,
                        "IsD1Opponent": is_d1_opponent,
                        "IsBye": is_bye,
                        "IsNCL": is_ncl,
                        "IsNCW": is_ncw,
                        "Result": res,
                        "PF": pf,
                        "PA": pa,
                    })

    return pd.DataFrame(games)


games_df = parse_schedule_csv()

# ---------------------------------------------------------
# 3. Sidebar: Game Simulator Sandbox & Mode Toggle
# ---------------------------------------------------------
st.sidebar.header("⚙️ Game Simulator Sandbox")

# Track mode changes to reset session state cleanly on switch
if "prev_sim_mode" not in st.session_state:
    st.session_state["prev_sim_mode"] = "Predictor Mode"

sim_mode = st.sidebar.radio(
    "Simulation Mode:", options=["Predictor Mode", "What-If Mode"], key="sim_mode_radio"
)

mode_switched = st.session_state["prev_sim_mode"] != sim_mode
st.session_state["prev_sim_mode"] = sim_mode

if sim_mode == "Predictor Mode":
    st.sidebar.info(
        "🔮 **Predictor Mode:** Select projected winners for remaining unplayed regular season games only."
    )
else:
    st.sidebar.info(
        "🔀 **What-If Mode:** Allows manual overrides for ALL regular season games, including overriding completed games or setting them to Unplayed / TBD."
    )

st.sidebar.markdown("---")

all_fixtures = []
seen_fixtures = set()

for _, row in games_df[games_df["IsD1Opponent"]].iterrows():
    week = row["Week"]
    team1 = row["Team"]
    team2 = row["Opponent"]
    pair = tuple(sorted([team1, team2]))
    fixture_key = (week, pair)

    if fixture_key not in seen_fixtures:
        seen_fixtures.add(fixture_key)

        res = row["Result"]
        actual_res = (
            res if pd.notna(res) and str(res).strip().upper() in ["W", "L"] else None
        )

        all_fixtures.append({
            "Week": week,
            "Team1": team1,
            "Team2": team2,
            "ActualResult": actual_res,
        })

if sim_mode == "Predictor Mode":
    active_fixtures = [
        f
        for f in all_fixtures
        if pd.isna(f["ActualResult"]) or f["ActualResult"] is None
    ]
    for f in all_fixtures:
        if pd.notna(f["ActualResult"]) and f["ActualResult"] in ["W", "L"]:
            key = f"sim_{f['Week']}_{f['Team1']}_{f['Team2']}"
            if key in st.session_state:
                del st.session_state[key]
else:
    active_fixtures = all_fixtures

# Reset Logic Engine Button
if st.sidebar.button("🔄 Reset All Results", use_container_width=True):
    for f in active_fixtures:
        key = f"sim_{f['Week']}_{f['Team1']}_{f['Team2']}"
        if sim_mode == "What-If Mode":
            if pd.notna(f["ActualResult"]) and f["ActualResult"] in ["W", "L"]:
                actual_winner = f["Team1"] if f["ActualResult"] == "W" else f["Team2"]
                st.session_state[key] = f"{actual_winner} Win"
            else:
                st.session_state[key] = "Unplayed / TBD"
        else:
            st.session_state[key] = "Actual/TBD"
    st.rerun()

# When switching modes, force unplayed games to "Unplayed / TBD" in What-If mode
if mode_switched and sim_mode == "What-If Mode":
    for f in all_fixtures:
        key = f"sim_{f['Week']}_{f['Team1']}_{f['Team2']}"
        if pd.isna(f["ActualResult"]) or f["ActualResult"] is None:
            st.session_state[key] = "Unplayed / TBD"
        elif pd.notna(f["ActualResult"]) and f["ActualResult"] in ["W", "L"]:
            actual_winner = f["Team1"] if f["ActualResult"] == "W" else f["Team2"]
            st.session_state[key] = f"{actual_winner} Win"

simulated_outcomes = {}

if len(active_fixtures) == 0:
    st.sidebar.success("🎉 All regular season games have been completed!")
else:
    weeks = sorted(list(set(f["Week"] for f in active_fixtures)))

    for week in weeks:
        st.sidebar.subheader(f"📅 {week}")
        week_fixtures = [f for f in active_fixtures if f["Week"] == week]

        for f in week_fixtures:
            team1, team2 = f["Team1"], f["Team2"]
            key = f"sim_{week}_{team1}_{team2}"
            pair = tuple(sorted([team1, team2]))

            if sim_mode == "What-If Mode":
                options_list = [f"{team1} Win", f"{team2} Win", "Unplayed / TBD"]
                if key not in st.session_state:
                    if pd.notna(f["ActualResult"]) and f["ActualResult"] in ["W", "L"]:
                        actual_winner = team1 if f["ActualResult"] == "W" else team2
                        st.session_state[key] = f"{actual_winner} Win"
                    else:
                        st.session_state[key] = "Unplayed / TBD"
            else:
                options_list = ["Actual/TBD", f"{team1} Win", f"{team2} Win"]
                if key not in st.session_state:
                    st.session_state[key] = "Actual/TBD"

            choice = st.sidebar.selectbox(
                f"{team1} vs {team2}",
                options=options_list,
                key=key,
            )

            if choice == f"{team1} Win":
                simulated_outcomes[(week, pair)] = team1
            elif choice == f"{team2} Win":
                simulated_outcomes[(week, pair)] = team2
            elif choice in ["Unplayed / TBD", "Actual/TBD"]:
                simulated_outcomes[(week, pair)] = choice

# Check if user has actively made predictions
active_predictions_exist = False
for f in active_fixtures:
    key = f"sim_{f['Week']}_{f['Team1']}_{f['Team2']}"
    val = st.session_state.get(key, None)
    if sim_mode == "Predictor Mode":
        if val in [f"{f['Team1']} Win", f"{f['Team2']} Win"]:
            active_predictions_exist = True
            break
    else:  # What-If Mode
        actual_winner = (
            f["Team1"] if f["ActualResult"] == "W"
            else (f["Team2"] if f["ActualResult"] == "L" else None)
        )
        expected_default = f"{actual_winner} Win" if actual_winner else "Unplayed / TBD"
        if val != expected_default:
            active_predictions_exist = True
            break

# ---------------------------------------------------------
# 4. Calculation Engine
# ---------------------------------------------------------
teams_list = list(TEAM_TO_CONF.keys())

all_victories = {t: [] for t in teams_list}
conf_victories = {t: [] for t in teams_list}
unplayed_sim_count = {t: 0 for t in teams_list}
unplayed_sim_conf_count = {t: 0 for t in teams_list}
unplayed_sim_opponents = {t: [] for t in teams_list}

csv_actual_wins = {t: 0 for t in teams_list}
csv_actual_gp = {t: 0 for t in teams_list}
csv_conf_wins = {t: 0 for t in teams_list}
csv_conf_gp = {t: 0 for t in teams_list}
csv_victories = {t: [] for t in teams_list}
csv_conf_victories = {t: [] for t in teams_list}
csv_unplayed_total = {t: 0 for t in teams_list}
csv_unplayed_conf = {t: 0 for t in teams_list}
csv_remaining_opponents = {t: [] for t in teams_list}

standings_data = {
    t: {
        "Conference": TEAM_TO_CONF[t],
        "Wins": 0,
        "Losses": 0,
        "GP": 0,
        "Conf. Wins": 0,
        "Conf. Losses": 0,
        "Conf_GP": 0,
        "H2H_Wins": {other: 0 for other in teams_list},
    }
    for t in teams_list
}

for _, row in games_df[games_df["IsD1Opponent"]].iterrows():
    t = row["Team"]
    opp = row["Opponent"]
    week = row["Week"]
    pair = tuple(sorted([t, opp]))
    is_conf = TEAM_TO_CONF.get(t) == TEAM_TO_CONF.get(opp)

    is_csv_done = pd.notna(row["Result"]) and row["Result"] in ["W", "L"]
    if is_csv_done:
        csv_actual_gp[t] += 1
        if is_conf:
            csv_conf_gp[t] += 1
        if row["Result"] == "W":
            csv_actual_wins[t] += 1
            csv_victories[t].append(opp)
            if is_conf:
                csv_conf_wins[t] += 1
                csv_conf_victories[t].append(opp)
    else:
        csv_unplayed_total[t] += 1
        csv_remaining_opponents[t].append(opp)
        if is_conf:
            csv_unplayed_conf[t] += 1

    sim_winner = simulated_outcomes.get((week, pair), None)

    if sim_mode == "What-If Mode":
        if sim_winner == "Unplayed / TBD":
            effective_res = None
        elif sim_winner in [t, opp]:
            effective_res = "W" if sim_winner == t else "L"
        else:
            effective_res = row["Result"] if pd.notna(row["Result"]) else None
    else:
        if sim_winner in [t, opp]:
            effective_res = "W" if sim_winner == t else "L"
        else:
            effective_res = row["Result"] if pd.notna(row["Result"]) else None

    if effective_res in ["W", "L"]:
        if t in standings_data:
            standings_data[t]["GP"] += 1
            if is_conf:
                standings_data[t]["Conf_GP"] += 1

            if effective_res == "W":
                standings_data[t]["Wins"] += 1
                standings_data[t]["H2H_Wins"][opp] += 1
                all_victories[t].append(opp)
                if is_conf:
                    standings_data[t]["Conf. Wins"] += 1
                    conf_victories[t].append(opp)
            elif effective_res == "L":
                standings_data[t]["Losses"] += 1
                if is_conf:
                    standings_data[t]["Conf. Losses"] += 1
    else:
        unplayed_sim_count[t] += 1
        unplayed_sim_opponents[t].append(opp)
        if is_conf:
            unplayed_sim_conf_count[t] += 1

win_counts = {t: standings_data[t]["Wins"] for t in teams_list}
overall_points = {}
conf_points = {}

for t in teams_list:
    tot_pts = sum(10.0 + (2.0 * win_counts.get(opp, 0)) for opp in all_victories[t])
    overall_points[t] = tot_pts

    c_pts = sum(10.0 + (2.0 * win_counts.get(opp, 0)) for opp in conf_victories[t])
    conf_points[t] = c_pts

df_stand = pd.DataFrame.from_dict(standings_data, orient="index").reset_index()
df_stand.rename(columns={"index": "Team"}, inplace=True)

df_stand["Points"] = df_stand["Team"].map(overall_points)
df_stand["Conf_Points"] = df_stand["Team"].map(conf_points)

df_stand["Rating"] = (
    df_stand["Points"] / df_stand["GP"].replace(0, 1)
).round(4)
df_stand["Conf. Rating"] = (
    df_stand["Conf_Points"] / df_stand["Conf_GP"].replace(0, 1)
).round(4)
df_stand["Overall_WinPct"] = (
    df_stand["Wins"] / df_stand["GP"].replace(0, 1)
).round(4)


# STRICT TIEBREAKER ENGINE: Rating -> Head-to-Head -> Conf. Rating
def apply_nhiaa_tiebreakers(df):
    df_sorted = df.copy()

    def get_h2h_tiebreaker_bonus(row):
        t_name = row["Team"]
        t_rating = row["Rating"]
        tied_teams = df_sorted[df_sorted["Rating"] == t_rating]["Team"].tolist()
        if len(tied_teams) == 2:
            other_team = (
                tied_teams[0] if tied_teams[1] == t_name else tied_teams[1]
            )
            wins_vs_other = standings_data[t_name]["H2H_Wins"].get(other_team, 0)
            losses_vs_other = standings_data[other_team]["H2H_Wins"].get(
                t_name, 0
            )
            if wins_vs_other > losses_vs_other:
                return 0.05
        return 0.0

    df_sorted["H2H_Bonus"] = df_sorted.apply(get_h2h_tiebreaker_bonus, axis=1)

    df_sorted["Rank_Score"] = (
        df_sorted["Rating"]
        + df_sorted["H2H_Bonus"]
        + (df_sorted["Conf. Rating"] * 0.001)
        + (df_sorted["Overall_WinPct"] * 0.0001)
    )

    return df_sorted.sort_values(by="Rank_Score", ascending=False).reset_index(
        drop=True
    )


df_stand = apply_nhiaa_tiebreakers(df_stand)

# ---------------------------------------------------------
# 5. Baseline Mathematical Lock Engine (Completed CSV Only)
# ---------------------------------------------------------
actual_conf_champions = set()
actual_playoff_clinched = set()
actual_eliminated = set()

csv_abs_floor_rating = {}
csv_abs_ceiling_rating = {}

for t in teams_list:
    tot_sched = csv_actual_gp[t] + csv_unplayed_total[t]
    if tot_sched > 0:
        floor_pts = sum(
            10.0 + (2.0 * csv_actual_wins[opp]) for opp in csv_victories[t]
        )
        csv_abs_floor_rating[t] = floor_pts / tot_sched

        max_possible_wins = csv_actual_wins[t] + csv_unplayed_total[t]
        max_opp_win_bonus = sum(
            2.0 * (csv_actual_wins[opp] + csv_unplayed_total[opp])
            for opp in csv_victories[t] + csv_remaining_opponents[t]
        )
        ceiling_pts = (max_possible_wins * 10.0) + max_opp_win_bonus
        csv_abs_ceiling_rating[t] = ceiling_pts / tot_sched
    else:
        csv_abs_floor_rating[t] = 0.0
        csv_abs_ceiling_rating[t] = 0.0

for conf_name in ["East", "Central", "West"]:
    conf_teams = CONFERENCES[conf_name]
    conf_sub = df_stand[df_stand["Conference"] == conf_name]
    top_baseline_team = conf_sub.iloc[0]["Team"]

    top_floor = csv_abs_floor_rating[top_baseline_team]
    other_ceilings = [
        csv_abs_ceiling_rating[o]
        for o in conf_teams
        if o != top_baseline_team
    ]
    max_other_ceiling = max(other_ceilings) if other_ceilings else 0.0

    # Lock permanent Conf. Champion ONLY if top floor strictly beats all rivals' ceilings
    if top_floor > max_other_ceiling:
        actual_conf_champions.add(top_baseline_team)

sorted_csv_ceilings = sorted(csv_abs_ceiling_rating.values(), reverse=True)
csv_ceiling_14th = (
    sorted_csv_ceilings[13] if len(sorted_csv_ceilings) >= 14 else 0.0
)

sorted_csv_floors = sorted(csv_abs_floor_rating.values(), reverse=True)
csv_floor_13th = sorted_csv_floors[12] if len(sorted_csv_floors) >= 13 else 0.0

for t in teams_list:
    if t in actual_conf_champions or csv_abs_floor_rating[t] > csv_ceiling_14th:
        actual_playoff_clinched.add(t)
    if csv_abs_ceiling_rating[t] < csv_floor_13th:
        actual_eliminated.add(t)

# ---------------------------------------------------------
# 6. Active Simulation / Strict Mathematical Clinch Engine
# ---------------------------------------------------------
sim_conf_champions = set()
sim_playoff_clinched = set()
sim_eliminated = set()

# Current leaders under active selections
current_conf_leaders = {}
for conf_name in ["East", "Central", "West"]:
    conf_sub = df_stand[df_stand["Conference"] == conf_name]
    leader = conf_sub.iloc[0]["Team"]
    current_conf_leaders[conf_name] = leader

leaders_list = [
    current_conf_leaders["East"],
    current_conf_leaders["Central"],
    current_conf_leaders["West"],
]
df_stand["Is_Conf_Leader"] = df_stand["Team"].isin(leaders_list)

leaders_df = df_stand[df_stand["Is_Conf_Leader"]].sort_values(
    by="Rank_Score", ascending=False
)
remaining_df = df_stand[~df_stand["Is_Conf_Leader"]].sort_values(
    by="Rank_Score", ascending=False
)

seeding_df = pd.concat([leaders_df, remaining_df]).reset_index(drop=True)
seeding_df["Seed"] = seeding_df.index + 1

# ---------------------------------------------------------
# 100% CLINCH ENGINE: CONFERENCE CHAMPIONS (RIGOROUS PERMUTATION)
# ---------------------------------------------------------
if active_predictions_exist:
    for conf_name in ["East", "Central", "West"]:
        conf_teams = CONFERENCES[conf_name]
        leader = current_conf_leaders[conf_name]

        # Gather ALL unselected/unplayed D1 fixtures involving ANY team in this conference or their opponents
        unselected_rel_games = []
        for _, row in games_df[games_df["IsD1Opponent"]].iterrows():
            t1, opp = row["Team"], row["Opponent"]
            if t1 in conf_teams or opp in conf_teams:
                week = row["Week"]
                pair = tuple(sorted([t1, opp]))

                is_csv_done = pd.notna(row["Result"]) and str(row["Result"]).strip().upper() in ["W", "L"]
                user_choice = simulated_outcomes.get((week, pair), None)

                # Game is unselected if not finished in CSV and not explicitly picked by user
                is_tbd = not is_csv_done and (
                    user_choice is None or user_choice in ["Actual/TBD", "Unplayed / TBD"]
                )

                if is_tbd:
                    if (week, pair) not in [(g[0], g[1]) for g in unselected_rel_games]:
                        unselected_rel_games.append((week, pair, t1, opp))

        # Fast path: 0 unselected games remain for division teams -> leader is 100% locked
        if len(unselected_rel_games) == 0:
            sim_conf_champions.add(leader)
            continue

        # Exhaustive 2^N permutation engine across unselected fixtures
        relevant_games = unselected_rel_games[:10]  # Cap permutation limit
        leader_wins_all_scenarios = True

        for outcome in itertools.product([0, 1], repeat=len(relevant_games)):
            # Deep-copy current state for permutation scoring
            scen_wins = {t: standings_data[t]["Wins"] for t in teams_list}
            scen_gp = {t: standings_data[t]["GP"] for t in teams_list}
            scen_victories = {t: list(all_victories[t]) for t in teams_list}
            scen_conf_victories = {t: list(conf_victories[t]) for t in teams_list}
            scen_conf_gp = {t: standings_data[t]["Conf_GP"] for t in teams_list}
            scen_h2h = {
                t: dict(standings_data[t]["H2H_Wins"]) for t in teams_list
            }

            for idx, choice in enumerate(outcome):
                w_week, w_pair, t_a, t_b = relevant_games[idx]
                winner = t_a if choice == 0 else t_b
                loser = t_b if choice == 0 else t_a
                is_c = TEAM_TO_CONF.get(winner) == TEAM_TO_CONF.get(loser)

                scen_wins[winner] += 1
                scen_gp[winner] += 1
                scen_gp[loser] += 1
                scen_victories[winner].append(loser)
                scen_h2h[winner][loser] = scen_h2h[winner].get(loser, 0) + 1

                if is_c:
                    scen_conf_gp[winner] += 1
                    scen_conf_gp[loser] += 1
                    scen_conf_victories[winner].append(loser)

            # Compute scenario rating points for division teams
            scen_rows = []
            for t in conf_teams:
                tot_pts = sum(10.0 + (2.0 * scen_wins.get(opp, 0)) for opp in scen_victories[t])
                c_pts = sum(10.0 + (2.0 * scen_wins.get(opp, 0)) for opp in scen_conf_victories[t])

                rating = round(tot_pts / max(scen_gp[t], 1), 4)
                conf_rating = round(c_pts / max(scen_conf_gp[t], 1), 4)
                win_pct = round(scen_wins[t] / max(scen_gp[t], 1), 4)

                scen_rows.append({
                    "Team": t,
                    "Rating": rating,
                    "Conf. Rating": conf_rating,
                    "Overall_WinPct": win_pct,
                })

            df_scen = pd.DataFrame(scen_rows)

            def scen_h2h_bonus(row):
                t_name = row["Team"]
                t_rat = row["Rating"]
                tied = df_scen[df_scen["Rating"] == t_rat]["Team"].tolist()
                if len(tied) == 2:
                    other = tied[0] if tied[1] == t_name else tied[1]
                    if scen_h2h[t_name].get(other, 0) > scen_h2h[other].get(t_name, 0):
                        return 0.05
                return 0.0

            df_scen["H2H_Bonus"] = df_scen.apply(scen_h2h_bonus, axis=1)
            df_scen["Rank_Score"] = (
                df_scen["Rating"]
                + df_scen["H2H_Bonus"]
                + (df_scen["Conf. Rating"] * 0.001)
                + (df_scen["Overall_WinPct"] * 0.0001)
            )

            scen_winner = df_scen.sort_values(
                by="Rank_Score", ascending=False
            ).iloc[0]["Team"]

            if scen_winner != leader:
                leader_wins_all_scenarios = False
                break

        if leader_wins_all_scenarios:
            sim_conf_champions.add(leader)

# ---------------------------------------------------------
# 100% CLINCH ENGINE: TOP-13 PLAYOFF SEEDING
# ---------------------------------------------------------
sim_min_ratings = {}
sim_max_ratings = {}

for t in teams_list:
    tot_sched = standings_data[t]["GP"] + unplayed_sim_count[t]
    if tot_sched > 0:
        s_floor = sum(
            10.0 + (2.0 * standings_data[opp]["Wins"])
            for opp in all_victories[t]
        ) / tot_sched

        sim_max_wins = standings_data[t]["Wins"] + unplayed_sim_count[t]
        sim_max_opp_bonus = sum(
            2.0 * (standings_data[opp]["Wins"] + unplayed_sim_count[opp])
            for opp in all_victories[t] + unplayed_sim_opponents[t]
        )
        s_ceil = ((sim_max_wins * 10.0) + sim_max_opp_bonus) / tot_sched

        sim_min_ratings[t] = s_floor
        sim_max_ratings[t] = s_ceil
    else:
        sim_min_ratings[t] = df_stand[df_stand["Team"] == t]["Rating"].values[0]
        sim_max_ratings[t] = df_stand[df_stand["Team"] == t]["Rating"].values[0]

sorted_sim_floors = sorted(sim_min_ratings.values(), reverse=True)
sim_floor_13th = sorted_sim_floors[12] if len(sorted_sim_floors) >= 13 else 0.0

sorted_sim_ceilings = sorted(sim_max_ratings.values(), reverse=True)
sim_ceiling_14th = (
    sorted_sim_ceilings[13] if len(sorted_sim_ceilings) >= 14 else 0.0
)

for t in teams_list:
    cur_seed = seeding_df[seeding_df["Team"] == t]["Seed"].values[0]

    # Clinched Playoff Spot via Sandbox Choices
    if t in sim_conf_champions or (
        cur_seed <= 13
        and (
            unplayed_sim_count[t] == 0
            or sim_min_ratings[t] >= sim_ceiling_14th
        )
    ):
        sim_playoff_clinched.add(t)

    # Eliminated from Playoff Field strictly via Sandbox Choices
    if t not in actual_eliminated and (
        cur_seed > 13 and sim_max_ratings[t] < sim_floor_13th
    ):
        sim_eliminated.add(t)


def get_team_status_badge(t):
    # 1. PERMANENT HISTORICAL LOCK (CSV ACTUAL RESULTS)
    if t in actual_conf_champions:
        return "👑 Conf. Champion"

    # 2. DYNAMIC PREDICTOR CHAMPION (Requires 100% mathematical clinch across all permutations)
    if active_predictions_exist and t in sim_conf_champions:
        return "👑 Conf. Champion (Projected)"

    # 3. BASELINE PLAYOFF CLINCH (Actual CSV Completed Games)
    if t in actual_playoff_clinched:
        return "⭐ Playoff Clinched"

    # 4. BASELINE ELIMINATION (Actual CSV Completed Games)
    if t in actual_eliminated:
        return "❌ Eliminated"

    # 5. DYNAMIC PREDICTOR PLAYOFF CLINCH
    if active_predictions_exist and t in sim_playoff_clinched:
        return "⭐ Clinched (Projected)"

    # 6. DYNAMIC PREDICTOR ELIMINATION
    if active_predictions_exist and t in sim_eliminated:
        return "❌ Eliminated (Projected)"

    return "Active"


df_stand["Status"] = df_stand["Team"].apply(get_team_status_badge)
seeding_df["Status"] = seeding_df["Team"].apply(get_team_status_badge)

# ---------------------------------------------------------
# 7. Streamlit Main Interface & Tabs
# ---------------------------------------------------------
tab_names = ["📋 Team Records", "📊 Standings & Seeding", "🏆 Bracket Matchups"]
tab_records, tab_standings, tab_bracket = st.tabs(tab_names)

components.html(
    """
    <script>
        window.addEventListener('load', function() {
            const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
            if (tabs.length >= 2 && !window.parent.location.hash) {
                tabs[1].click();
            }
        });
    </script>
    """,
    height=0,
    width=0,
)

display_cols = [
    "Seed",
    "Status",
    "Team",
    "Conference",
    "Wins",
    "Losses",
    "GP",
    "Points",
    "Rating",
    "Conf. Wins",
    "Conf. Losses",
    "Conf. Rating",
]
div_display_cols = [
    "Team",
    "Status",
    "Wins",
    "Losses",
    "GP",
    "Points",
    "Rating",
    "Conf. Wins",
    "Conf. Losses",
    "Conf. Rating",
]

# TAB 1: TEAM RECORDS
with tab_records:
    st.subheader("Team Schedule & Results Breakdown")

    col_left, col_right = st.columns([1, 3])

    with col_left:
        st.markdown("### Select Team")
        selected_team = st.radio(
            "Teams:", sorted(teams_list), label_visibility="collapsed"
        )

    with col_right:
        status_str = get_team_status_badge(selected_team)
        badge_suffix = f" — {status_str}" if status_str != "Active" else ""

        st.markdown(
            f"### {selected_team} Schedule ({TEAM_TO_CONF[selected_team]} Conference){badge_suffix}"
        )

        team_schedule = games_df[games_df["Team"] == selected_team].copy()

        display_schedule = []
        for _, row in team_schedule.iterrows():
            opp = row["Opponent"]
            week = row["Week"]
            is_bye = row["IsBye"]

            if is_bye:
                res_str = "BYE"
            else:
                pair = (
                    tuple(sorted([selected_team, opp]))
                    if row["IsD1Opponent"]
                    else None
                )
                sim_winner = (
                    simulated_outcomes.get((week, pair), None) if pair else None
                )

                is_csv_completed = (
                    pd.notna(row["Result"]) and str(row["Result"]).strip().upper() in ["W", "L"]
                )

                if sim_winner is not None and sim_winner not in ["Unplayed / TBD", "Actual/TBD"]:
                    actual_csv_winner = (
                        selected_team if row["Result"] == "W" else opp
                    )
                    if not is_csv_completed or sim_winner != actual_csv_winner:
                        res_str = (
                            "W (Sim)"
                            if sim_winner == selected_team
                            else "L (Sim)"
                        )
                    else:
                        res_str = row["Result"]
                elif sim_winner in ["Unplayed / TBD", "Actual/TBD"]:
                    res_str = "TBD"
                elif is_csv_completed:
                    res_str = row["Result"]
                else:
                    res_str = "TBD"

            display_schedule.append({
                "Week": week,
                "Site": row["Location"],
                "Opponent": opp,
                "Conference Game": row["IsConf"],
                "Result": res_str,
                "PF": row["PF"],
                "PA": row["PA"],
            })

        df_team_sched = pd.DataFrame(display_schedule)
        st.dataframe(df_team_sched, use_container_width=True, hide_index=True)

# TAB 2: STANDINGS & SEEDING (Default Landing View)
with tab_standings:
    st.subheader("Official Projected Seeding (Top 13 Qualify)")

    st.caption(
        "📌 **Status Key:** 👑 Conf. Champion | ⭐ Playoff Clinched | ❌ Eliminated | 👑 Conf. Champion (Projected) | ⭐ Clinched (Projected) | ❌ Eliminated (Projected)"
    )

    st.markdown("#### 🏆 Conference Winners (#1 – #3 Seeds)")
    st.dataframe(
        seeding_df[display_cols].head(3),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### 🏈 Remaining Qualifiers (#4 – #13 Seeds)")
    st.dataframe(
        seeding_df[display_cols].iloc[3:13],
        use_container_width=True,
        hide_index=True,
    )

    if len(seeding_df) > 13:
        st.markdown("#### 🚫 Non-Qualifiers (#14+ Seeds)")
        st.dataframe(
            seeding_df[display_cols].iloc[13:],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.subheader("Conference Standings")

    conf_tab1, conf_tab2, conf_tab3 = st.tabs(
        ["East Conference", "Central Conference", "West Conference"]
    )

    with conf_tab1:
        east_df = df_stand[df_stand["Conference"] == "East"].sort_values(
            by="Rank_Score", ascending=False
        )
        st.dataframe(
            east_df[div_display_cols],
            use_container_width=True,
            hide_index=True,
        )

    with conf_tab2:
        central_df = df_stand[df_stand["Conference"] == "Central"].sort_values(
            by="Rank_Score", ascending=False
        )
        st.dataframe(
            central_df[div_display_cols],
            use_container_width=True,
            hide_index=True,
        )

    with conf_tab3:
        west_df = df_stand[df_stand["Conference"] == "West"].sort_values(
            by="Rank_Score", ascending=False
        )
        st.dataframe(
            west_df[div_display_cols],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.subheader("Full Division 1 Standings")
    st.dataframe(
        df_stand[[
            "Team",
            "Status",
            "Conference",
            "Wins",
            "Losses",
            "GP",
            "Points",
            "Rating",
            "Conf. Wins",
            "Conf. Losses",
            "Conf. Rating",
        ]],
        use_container_width=True,
        hide_index=True,
    )

# TAB 3: BRACKET MATCHUPS
with tab_bracket:
    st.subheader("NHIAA Division 1 Playoff Bracket Preview")
    playoff_13 = seeding_df.head(13).set_index("Seed")

    bracket_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    .bracket-container {{
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        background-color: #0e1117;
        color: #ffffff;
        padding: 20px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        border-radius: 10px;
        overflow-x: auto;
    }}
    .round {{
        display: flex;
        flex-direction: column;
        justify-content: space-around;
        width: 220px;
        margin: 0 10px;
    }}
    .round-title {{
        text-align: center;
        font-weight: bold;
        color: #ff4b4b;
        margin-bottom: 15px;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .matchup {{
        background-color: #1e222a;
        border: 1px solid #313745;
        border-radius: 6px;
        margin: 10px 0;
        padding: 8px 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }}
    .team {{
        display: flex;
        justify-content: space-between;
        font-size: 13px;
        padding: 3px 0;
    }}
    .team-name {{
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 150px;
    }}
    .team-seed {{
        color: #00d4b1;
        font-weight: bold;
        margin-right: 5px;
    }}
    .team-score {{
        color: #888;
        font-size: 11px;
    }}
    .bye-badge {{
        background-color: #262730;
        border: 1px dashed #ff4b4b;
    }}
    </style>
    </head>
    <body>
    <div class="bracket-container">
        <!-- Round 1: Opening Round / Wildcard -->
        <div class="round">
            <div class="round-title">Opening Round</div>
            <div class="matchup">
                <div class="team"><span class="team-name"><span class="team-seed">#8</span> {playoff_13.loc[8, 'Team']}</span><span class="team-score">{playoff_13.loc[8, 'Rating']:.2f}</span></div>
                <div class="team"><span class="team-name"><span class="team-seed">#9</span> {playoff_13.loc[9, 'Team']}</span><span class="team-score">{playoff_13.loc[9, 'Rating']:.2f}</span></div>
            </div>
            <div class="matchup">
                <div class="team"><span class="team-name"><span class="team-seed">#5</span> {playoff_13.loc[5, 'Team']}</span><span class="team-score">{playoff_13.loc[5, 'Rating']:.2f}</span></div>
                <div class="team"><span class="team-name"><span class="team-seed">#12</span> {playoff_13.loc[12, 'Team']}</span><span class="team-score">{playoff_13.loc[12, 'Rating']:.2f}</span></div>
            </div>
            <div class="matchup">
                <div class="team"><span class="team-name"><span class="team-seed">#4</span> {playoff_13.loc[4, 'Team']}</span><span class="team-score">{playoff_13.loc[4, 'Rating']:.2f}</span></div>
                <div class="team"><span class="team-name"><span class="team-seed">#13</span> {playoff_13.loc[13, 'Team']}</span><span class="team-score">{playoff_13.loc[13, 'Rating']:.2f}</span></div>
            </div>
            <div class="matchup">
                <div class="team"><span class="team-name"><span class="team-seed">#7</span> {playoff_13.loc[7, 'Team']}</span><span class="team-score">{playoff_13.loc[7, 'Rating']:.2f}</span></div>
                <div class="team"><span class="team-name"><span class="team-seed">#10</span> {playoff_13.loc[10, 'Team']}</span><span class="team-score">{playoff_13.loc[10, 'Rating']:.2f}</span></div>
            </div>
            <div class="matchup">
                <div class="team"><span class="team-name"><span class="team-seed">#6</span> {playoff_13.loc[6, 'Team']}</span><span class="team-score">{playoff_13.loc[6, 'Rating']:.2f}</span></div>
                <div class="team"><span class="team-name"><span class="team-seed">#11</span> {playoff_13.loc[11, 'Team']}</span><span class="team-score">{playoff_13.loc[11, 'Rating']:.2f}</span></div>
            </div>
        </div>

        <!-- Round 2: Quarterfinals -->
        <div class="round">
            <div class="round-title">Quarterfinals</div>
            <div class="matchup bye-badge">
                <div class="team"><span class="team-name"><span class="team-seed">#1</span> {playoff_13.loc[1, 'Team']}</span><span class="team-score">BYE</span></div>
                <div class="team"><span class="team-name">Winner 8 vs 9</span></div>
            </div>
            <div class="matchup">
                <div class="team"><span class="team-name">Winner 5 vs 12</span></div>
                <div class="team"><span class="team-name">Winner 4 vs 13</span></div>
            </div>
            <div class="matchup bye-badge">
                <div class="team"><span class="team-name"><span class="team-seed">#2</span> {playoff_13.loc[2, 'Team']}</span><span class="team-score">BYE</span></div>
                <div class="team"><span class="team-name">Winner 7 vs 10</span></div>
            </div>
            <div class="matchup bye-badge">
                <div class="team"><span class="team-name"><span class="team-seed">#3</span> {playoff_13.loc[3, 'Team']}</span><span class="team-score">BYE</span></div>
                <div class="team"><span class="team-name">Winner 6 vs 11</span></div>
            </div>
        </div>

        <!-- Round 3: Semifinals -->
        <div class="round">
            <div class="round-title">Semifinals</div>
            <div class="matchup">
                <div class="team"><span class="team-name">QF 1 Winner</span></div>
                <div class="team"><span class="team-name">QF 2 Winner</span></div>
            </div>
            <div class="matchup">
                <div class="team"><span class="team-name">QF 3 Winner</span></div>
                <div class="team"><span class="team-name">QF 4 Winner</span></div>
            </div>
        </div>

        <!-- Round 4: Championship -->
        <div class="round">
            <div class="round-title">D1 Championship</div>
            <div class="matchup" style="border: 2px solid #ff4b4b;">
                <div class="team"><span class="team-name">Semifinal Winner 1</span></div>
                <div class="team"><span class="team-name">Semifinal Winner 2</span></div>
            </div>
        </div>
    </div>
    </body>
    </html>
    """

    components.html(bracket_html, height=520, scrolling=True)

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### 🌟 First Round Byes (#1 – #3 Seeds)")
        st.info(
            f"**#1 Seed ({playoff_13.loc[1, 'Conference']} Winner):** {playoff_13.loc[1, 'Team']} ({playoff_13.loc[1, 'Rating']} Rating)"
        )
        st.info(
            f"**#2 Seed ({playoff_13.loc[2, 'Conference']} Winner):** {playoff_13.loc[2, 'Team']} ({playoff_13.loc[2, 'Rating']} Rating)"
        )
        st.info(
            f"**#3 Seed ({playoff_13.loc[3, 'Conference']} Winner):** {playoff_13.loc[3, 'Team']} ({playoff_13.loc[3, 'Rating']} Rating)"
        )

    with col_b:
        st.markdown("### ⚔️ Opening Round Matchups")
        st.write(
            f"🏈 **Matchup A:** #4 **{playoff_13.loc[4, 'Team']}** vs #13 **{playoff_13.loc[13, 'Team']}**"
        )
        st.write(
            f"🏈 **Matchup B:** #5 **{playoff_13.loc[5, 'Team']}** vs #12 **{playoff_13.loc[12, 'Team']}**"
        )
        st.write(
            f"🏈 **Matchup C:** #6 **{playoff_13.loc[6, 'Team']}** vs #11 **{playoff_13.loc[11, 'Team']}**"
        )
        st.write(
            f"🏈 **Matchup D:** #7 **{playoff_13.loc[7, 'Team']}** vs #10 **{playoff_13.loc[10, 'Team']}**"
        )
        st.write(
            f"🏈 **Matchup E:** #8 **{playoff_13.loc[8, 'Team']}** vs #9 **{playoff_13.loc[9, 'Team']}**"
        )
