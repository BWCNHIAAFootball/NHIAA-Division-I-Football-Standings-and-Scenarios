import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import csv

# Set Streamlit Page Configuration
st.set_page_config(page_title="NHIAA D1 Playoff Simulator", layout="wide")

# Custom CSS to force all dataframe table headers to be bold and centered
st.markdown(
    """
    <style>
    /* Target Streamlit dataframe header cells */
    [data-testid="stDataFrame"] th, 
    [data-testid="stTable"] th,
    div[data-testid="stDataFrame"] div[role="columnheader"] {
        text-align: center !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("# 🏈 NHIAA Division I Football Standings")
st.markdown("### Playoff Simulator")
st.markdown("Simulate remaining regular season game outcomes to dynamically compute standings, conference rating points, tiebreakers, and 1–13 playoff seeding in real-time.")

# ---------------------------------------------------------
# 1. Team & Conference Definitions
# ---------------------------------------------------------
CONFERENCES = {
    'East': ['Portsmouth-Oyster River', 'Winnacunnet', 'Manchester Memorial', 'Exeter', 'Spaulding', 'Dover', 'Timberlane'],
    'Central': ['Pinkerton', 'Windham', 'Londonderry', 'Concord', 'Manchester Central', 'Salem', 'Alvirne'],
    'West': ['Bishop Guertin', 'Bedford', 'Merrimack', 'Nashua North', 'Nashua South', 'Goffstown', 'Keene']
}

TEAM_TO_CONF = {team: conf for conf, teams in CONFERENCES.items() for team in teams}

NAME_MAP = {
    'Central': 'Manchester Central', 'Manchester Central': 'Manchester Central',
    'Memorial': 'Manchester Memorial', 'Manchester Memorial': 'Manchester Memorial',
    'BG': 'Bishop Guertin', 'Bishop Guertin': 'Bishop Guertin',
    'POR': 'Portsmouth-Oyster River', 'Portsmouth-Oyster River': 'Portsmouth-Oyster River',
    'Sal': 'Salem', 'Salem': 'Salem', 
    'Lond': 'Londonderry', 'Londonderry': 'Londonderry',
    'Pink': 'Pinkerton', 'Pinkerton': 'Pinkerton',
    'Wind': 'Windham', 'Windham': 'Windham',
    'Bed': 'Bedford', 'Bedford': 'Bedford',
    'South': 'Nashua South', 'Nashua South': 'Nashua South',
    'North': 'Nashua North', 'Nashua North': 'Nashua North'
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
    
    with open('Division_1_Football_Standings_Schedule.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or not any(row):
                continue
            
            col0 = str(row[0]).strip() if row[0] else ''
            
            # Team header detection
            if col0 and not col0.startswith('Week') and col0 not in ['East', 'Central', 'West']:
                current_team = normalize_name(col0)
            
            # Weekly Game Row Parsing
            elif col0.startswith('Week'):
                location = str(row[1]).strip() if len(row) > 1 and row[1] else 'vs'
                opp_raw = row[2] if len(row) > 2 else ''
                opp_norm = normalize_name(opp_raw) if opp_raw else ''
                is_conf_flag = str(row[3]).strip() if len(row) > 3 else ''
                
                raw_res = str(row[4]).strip().upper() if len(row) > 4 else ''
                
                # Check for NCL (Non-Conference Loss) and NCW (Non-Conference Win)
                is_ncl = raw_res == 'NCL'
                is_ncw = raw_res == 'NCW'
                
                if is_ncl:
                    res = 'L'
                elif is_ncw:
                    res = 'W'
                elif raw_res in ['W', 'L']:
                    res = raw_res
                else:
                    res = None
                
                pf = str(row[5]).strip() if len(row) > 5 and row[5] else '-'
                pa = str(row[7]).strip() if len(row) > 7 and row[7] else '-'
                
                if current_team in TEAM_TO_CONF and opp_raw:
                    is_bye = opp_raw.upper() == 'BYE'
                    
                    # NCL and NCW games do NOT count toward NHIAA D1 standings or GP
                    is_d1_opponent = (opp_norm in TEAM_TO_CONF) and not is_ncl and not is_ncw
                    
                    if is_bye:
                        conf_status = 'N/A'
                    elif is_ncl or is_ncw:
                        conf_status = 'Out of State'
                    elif is_d1_opponent:
                        conf_status = 'Yes' if is_conf_flag == 'Yes' else 'No'
                    else:
                        conf_status = 'Out of State'
                    
                    games.append({
                        'Team': current_team,
                        'Week': col0,
                        'Location': '-' if is_bye else ('Away' if location == 'at' else 'Home'),
                        'Opponent': opp_raw if is_bye else (opp_norm if (opp_norm in TEAM_TO_CONF) else opp_raw),
                        'IsConf': conf_status,
                        'IsD1Opponent': is_d1_opponent,
                        'IsBye': is_bye,
                        'IsNCL': is_ncl,
                        'IsNCW': is_ncw,
                        'Result': res,
                        'PF': pf,
                        'PA': pa
                    })
                    
    return pd.DataFrame(games)

games_df = parse_schedule_csv()

# ---------------------------------------------------------
# 3. Sidebar: Game Simulator Sandbox & Mode Toggle
# ---------------------------------------------------------
st.sidebar.header("⚙️ Game Simulator Sandbox")

# Simulation Mode Radio Select
sim_mode = st.sidebar.radio(
    "Simulation Mode:",
    options=["Predictor Mode", "What-If Mode"]
)

# Inline mode descriptions displayed directly next to/underneath controls
if sim_mode == "Predictor Mode":
    st.sidebar.info("🔮 **Predictor Mode:** Select projected winners for remaining unplayed regular season games only.")
else:
    st.sidebar.info("🔀 **What-If Mode:** Allows manual overrides for ALL regular season games, including already completed matchups.")

st.sidebar.markdown("---")

# Build unique weekly fixtures from CSV (D1 Opponents only for standings rating calculations)
all_fixtures = []
seen_fixtures = set()

for _, row in games_df[games_df['IsD1Opponent']].iterrows():
    week = row['Week']
    team1 = row['Team']
    team2 = row['Opponent']
    pair = tuple(sorted([team1, team2]))
    fixture_key = (week, pair)
    
    if fixture_key not in seen_fixtures:
        seen_fixtures.add(fixture_key)
        
        res = row['Result']
        actual_res = res if pd.notna(res) and str(res).strip().upper() in ['W', 'L'] else None
        
        all_fixtures.append({
            'Week': week,
            'Team1': team1,
            'Team2': team2,
            'ActualResult': actual_res  # 'W', 'L', or None
        })

# Filter active fixtures based on selected mode
if sim_mode == "Predictor Mode":
    active_fixtures = [f for f in all_fixtures if pd.isna(f['ActualResult']) or f['ActualResult'] is None]
    # Clean session state for completed games when in Predictor Mode
    for f in all_fixtures:
        if pd.notna(f['ActualResult']) and f['ActualResult'] in ['W', 'L']:
            key = f"sim_{f['Week']}_{f['Team1']}_{f['Team2']}"
            if key in st.session_state:
                del st.session_state[key]
else:  # What-If Mode
    active_fixtures = all_fixtures

# Reset Button Logic
if st.sidebar.button("🔄 Reset All Results", use_container_width=True):
    for f in active_fixtures:
        key = f"sim_{f['Week']}_{f['Team1']}_{f['Team2']}"
        if key in st.session_state:
            if sim_mode == "What-If Mode" and pd.notna(f['ActualResult']) and f['ActualResult'] in ['W', 'L']:
                actual_winner = f['Team1'] if f['ActualResult'] == 'W' else f['Team2']
                st.session_state[key] = f"{actual_winner} Win"
            else:
                st.session_state[key] = "Actual/TBD"
    st.rerun()

simulated_outcomes = {}

if len(active_fixtures) == 0:
    st.sidebar.success("🎉 All regular season games have been completed!")
else:
    weeks = sorted(list(set(f['Week'] for f in active_fixtures)))
    
    for week in weeks:
        st.sidebar.subheader(f"📅 {week}")
        week_fixtures = [f for f in active_fixtures if f['Week'] == week]
        
        for f in week_fixtures:
            team1, team2 = f['Team1'], f['Team2']
            key = f"sim_{week}_{team1}_{team2}"
            pair = tuple(sorted([team1, team2]))
            
            # Initialize default selectbox values
            if key not in st.session_state:
                if sim_mode == "What-If Mode" and pd.notna(f['ActualResult']) and f['ActualResult'] in ['W', 'L']:
                    actual_winner = team1 if f['ActualResult'] == 'W' else team2
                    st.session_state[key] = f"{actual_winner} Win"
                else:
                    st.session_state[key] = "Actual/TBD"
            
            choice = st.sidebar.selectbox(
                f"{team1} vs {team2}",
                options=["Actual/TBD", f"{team1} Win", f"{team2} Win"],
                key=key
            )
            
            if choice == f"{team1} Win":
                simulated_outcomes[(week, pair)] = team1
            elif choice == f"{team2} Win":
                simulated_outcomes[(week, pair)] = team2
            else:
                simulated_outcomes[(week, pair)] = None

# ---------------------------------------------------------
# 4. Calculation Engine
# ---------------------------------------------------------
teams_list = list(TEAM_TO_CONF.keys())

all_victories = {t: [] for t in teams_list}
conf_victories = {t: [] for t in teams_list}

standings_data = {
    t: {
        'Conference': TEAM_TO_CONF[t], 
        'Wins': 0, 'Losses': 0, 'GP': 0, 
        'Conf. Wins': 0, 'Conf. Losses': 0, 'Conf_GP': 0,
        'H2H_Wins': {other: 0 for other in teams_list}
    }
    for t in teams_list
}

# Tally Wins, Losses, and Head-to-Head Record (Only D1 standings games count)
for _, row in games_df[games_df['IsD1Opponent']].iterrows():
    t = row['Team']
    opp = row['Opponent']
    week = row['Week']
    pair = tuple(sorted([t, opp]))
    is_conf = TEAM_TO_CONF.get(t) == TEAM_TO_CONF.get(opp)
    
    # Check for active simulation override
    sim_winner = simulated_outcomes.get((week, pair), None)
    
    if sim_winner is not None:
        effective_res = 'W' if sim_winner == t else 'L'
    else:
        effective_res = row['Result'] if pd.notna(row['Result']) else None
        
    if effective_res in ['W', 'L']:
        if t in standings_data:
            standings_data[t]['GP'] += 1
            if is_conf:
                standings_data[t]['Conf_GP'] += 1
                
            if effective_res == 'W':
                standings_data[t]['Wins'] += 1
                standings_data[t]['H2H_Wins'][opp] += 1
                all_victories[t].append(opp)
                if is_conf:
                    standings_data[t]['Conf. Wins'] += 1
                    conf_victories[t].append(opp)
            elif effective_res == 'L':
                standings_data[t]['Losses'] += 1
                if is_conf:
                    standings_data[t]['Conf. Losses'] += 1

# Calculate Opponent-Value Rating Points (Base 10 + 2 per Opponent Win)
win_counts = {t: standings_data[t]['Wins'] for t in teams_list}
overall_points = {}
conf_points = {}

for t in teams_list:
    tot_pts = sum(10.0 + (2.0 * win_counts.get(opp, 0)) for opp in all_victories[t])
    overall_points[t] = tot_pts
    
    c_pts = sum(10.0 + (2.0 * win_counts.get(opp, 0)) for opp in conf_victories[t])
    conf_points[t] = c_pts

df_stand = pd.DataFrame.from_dict(standings_data, orient='index').reset_index()
df_stand.rename(columns={'index': 'Team'}, inplace=True)

df_stand['Points'] = df_stand['Team'].map(overall_points)
df_stand['Conf_Points'] = df_stand['Team'].map(conf_points)

df_stand['Rating'] = (df_stand['Points'] / df_stand['GP'].replace(0, 1)).round(4)
df_stand['Conf. Rating'] = (df_stand['Conf_Points'] / df_stand['Conf_GP'].replace(0, 1)).round(4)
df_stand['Overall_WinPct'] = (df_stand['Wins'] / df_stand['GP'].replace(0, 1)).round(4)

def get_h2h_bonus(row):
    t_name = row['Team']
    t_rating = row['Rating']
    tied_teams = df_stand[df_stand['Rating'] == t_rating]['Team'].tolist()
    if len(tied_teams) == 2:
        other_team = tied_teams[0] if tied_teams[1] == t_name else tied_teams[1]
        wins_vs_other = standings_data[t_name]['H2H_Wins'].get(other_team, 0)
        losses_vs_other = standings_data[other_team]['H2H_Wins'].get(t_name, 0)
        if wins_vs_other > losses_vs_other:
            return 0.05
    return 0.0

df_stand['H2H_Bonus'] = df_stand.apply(get_h2h_bonus, axis=1)

df_stand['Adjusted_Rating'] = (
    df_stand['Rating'] + 
    df_stand['H2H_Bonus'] + 
    (df_stand['Conf. Rating'] * 0.001) + 
    (df_stand['Overall_WinPct'] * 0.0001)
)

df_stand = df_stand.sort_values(by='Adjusted_Rating', ascending=False).reset_index(drop=True)

# ---------------------------------------------------------
# 5. Conference Leaders & Playoff Seeding
# ---------------------------------------------------------
conf_leaders = []
for conf_name in ['East', 'Central', 'West']:
    top_team = df_stand[df_stand['Conference'] == conf_name].iloc[0]['Team']
    conf_leaders.append(top_team)

df_stand['Is_Conf_Leader'] = df_stand['Team'].isin(conf_leaders)

leaders_df = df_stand[df_stand['Is_Conf_Leader']].sort_values(by='Adjusted_Rating', ascending=False)
remaining_df = df_stand[~df_stand['Is_Conf_Leader']].sort_values(by='Adjusted_Rating', ascending=False)

seeding_df = pd.concat([leaders_df, remaining_df]).reset_index(drop=True)
seeding_df['Seed'] = seeding_df.index + 1

# ---------------------------------------------------------
# 6. Streamlit Main Interface & Tabs
# ---------------------------------------------------------
tab_names = ["📋 Team Records", "📊 Standings & Seeding", "🏆 Bracket Matchups"]
tab_records, tab_standings, tab_bracket = st.tabs(tab_names)

# Force "Standings & Seeding" (Tab index 1) as initial view
components.html(
    f"""
    <script>
        window.addEventListener('load', function() {{
            const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
            if (tabs.length >= 2 && !window.parent.location.hash) {{
                tabs[1].click();
            }}
        }});
    </script>
    """,
    height=0, width=0
)

# Column subsets for tables
display_cols = ['Seed', 'Team', 'Conference', 'Wins', 'Losses', 'GP', 'Points', 'Rating', 'Conf. Wins', 'Conf. Losses', 'Conf. Rating']
div_display_cols = ['Team', 'Wins', 'Losses', 'GP', 'Points', 'Rating', 'Conf. Wins', 'Conf. Losses', 'Conf. Rating']

# ---------------------------------------------------------
# TAB 1: TEAM RECORDS
# ---------------------------------------------------------
with tab_records:
    st.subheader("Team Schedule & Results Breakdown")
    
    col_left, col_right = st.columns([1, 3])
    
    with col_left:
        st.markdown("### Select Team")
        selected_team = st.radio("Teams:", sorted(teams_list), label_visibility="collapsed")
        
    with col_right:
        st.markdown(f"### {selected_team} Schedule ({TEAM_TO_CONF[selected_team]} Conference)")
        
        team_schedule = games_df[games_df['Team'] == selected_team].copy()
        
        display_schedule = []
        for _, row in team_schedule.iterrows():
            opp = row['Opponent']
            week = row['Week']
            is_bye = row['IsBye']
            
            if is_bye:
                res_str = "BYE"
            else:
                pair = tuple(sorted([selected_team, opp])) if row['IsD1Opponent'] else None
                sim_winner = simulated_outcomes.get((week, pair), None) if pair else None
                
                is_csv_completed = pd.notna(row['Result']) and row['Result'] in ['W', 'L']
                
                if sim_winner is not None:
                    actual_csv_winner = selected_team if row['Result'] == 'W' else opp
                    if not is_csv_completed or sim_winner != actual_csv_winner:
                        res_str = "W (Sim)" if sim_winner == selected_team else "L (Sim)"
                    else:
                        res_str = row['Result']
                elif is_csv_completed:
                    res_str = row['Result']
                else:
                    res_str = "TBD"
                
            display_schedule.append({
                'Week': week,
                'Site': row['Location'],
                'Opponent': opp,
                'Conference Game': row['IsConf'],
                'Result': res_str,
                'PF': row['PF'],
                'PA': row['PA']
            })
            
        df_team_sched = pd.DataFrame(display_schedule)
        st.dataframe(df_team_sched, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# TAB 2: STANDINGS & SEEDING (Default Landing View)
# ---------------------------------------------------------
with tab_standings:
    st.subheader("Official Projected Seeding (Top 13 Qualify)")
    
    st.markdown("#### 🏆 Conference Winners (#1 – #3 Seeds)")
    st.dataframe(
        seeding_df[display_cols].head(3),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("#### 🏈 Remaining Qualifiers (#4 – #13 Seeds)")
    st.dataframe(
        seeding_df[display_cols].iloc[3:13],
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("Conference Standings")
    
    conf_tab1, conf_tab2, conf_tab3 = st.tabs(["East Conference", "Central Conference", "West Conference"])
    
    with conf_tab1:
        east_df = df_stand[df_stand['Conference'] == 'East'].sort_values(by='Adjusted_Rating', ascending=False)
        st.dataframe(
            east_df[div_display_cols],
            use_container_width=True,
            hide_index=True
        )
        
    with conf_tab2:
        central_df = df_stand[df_stand['Conference'] == 'Central'].sort_values(by='Adjusted_Rating', ascending=False)
        st.dataframe(
            central_df[div_display_cols],
            use_container_width=True,
            hide_index=True
        )
        
    with conf_tab3:
        west_df = df_stand[df_stand['Conference'] == 'West'].sort_values(by='Adjusted_Rating', ascending=False)
        st.dataframe(
            west_df[div_display_cols],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")
    st.subheader("Full Division 1 Standings")
    st.dataframe(
        df_stand[['Team', 'Conference', 'Wins', 'Losses', 'GP', 'Points', 'Rating', 'Conf. Wins', 'Conf. Losses', 'Conf. Rating']],
        use_container_width=True,
        hide_index=True
    )

# ---------------------------------------------------------
# TAB 3: BRACKET MATCHUPS
# ---------------------------------------------------------
with tab_bracket:
    st.subheader("NHIAA Division 1 Playoff Bracket Preview")
    playoff_13 = seeding_df.head(13).set_index('Seed')

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
        st.info(f"**#1 Seed ({playoff_13.loc[1, 'Conference']} Winner):** {playoff_13.loc[1, 'Team']} ({playoff_13.loc[1, 'Rating']} Rating)")
        st.info(f"**#2 Seed ({playoff_13.loc[2, 'Conference']} Winner):** {playoff_13.loc[2, 'Team']} ({playoff_13.loc[2, 'Rating']} Rating)")
        st.info(f"**#3 Seed ({playoff_13.loc[3, 'Conference']} Winner):** {playoff_13.loc[3, 'Team']} ({playoff_13.loc[3, 'Rating']} Rating)")

    with col_b:
        st.markdown("### ⚔️ Opening Round Matchups")
        st.write(f"🏈 **Matchup A:** #4 **{playoff_13.loc[4, 'Team']}** vs #13 **{playoff_13.loc[13, 'Team']}**")
        st.write(f"🏈 **Matchup B:** #5 **{playoff_13.loc[5, 'Team']}** vs #12 **{playoff_13.loc[12, 'Team']}**")
        st.write(f"🏈 **Matchup C:** #6 **{playoff_13.loc[6, 'Team']}** vs #11 **{playoff_13.loc[11, 'Team']}**")
        st.write(f"🏈 **Matchup D:** #7 **{playoff_13.loc[7, 'Team']}** vs #10 **{playoff_13.loc[10, 'Team']}**")
        st.write(f"🏈 **Matchup E:** #8 **{playoff_13.loc[8, 'Team']}** vs #9 **{playoff_13.loc[9, 'Team']}**")