import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import csv

# Set Streamlit Page Configuration
st.set_page_config(page_title="NHIAA D1 Playoff Simulator", layout="wide")

st.title("🏈 NHIAA Division 1 Football Playoff & Tiebreaker Simulator")
st.markdown("Simulate remaining regular season game outcomes to dynamically compute standings, divisional rating points, tiebreakers, and 1–13 playoff seeding in real-time.")

# ---------------------------------------------------------
# 1. Team & Division Definitions
# ---------------------------------------------------------
DIVISIONS = {
    'East': ['Portsmouth-Oyster River', 'Winnacunnet', 'Manchester Memorial', 'Exeter', 'Spaulding', 'Dover', 'Timberlane'],
    'Central': ['Pinkerton', 'Windham', 'Londonderry', 'Concord', 'Manchester Central', 'Salem', 'Alvirne'],
    'West': ['Bishop Guertin', 'Bedford', 'Merrimack', 'Nashua North', 'Nashua South', 'Goffstown', 'Keene']
}

TEAM_TO_DIV = {team: div for div, teams in DIVISIONS.items() for team in teams}

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

EXCLUDED_OPPONENTS = [
    'Central Catholic', 'Bonny Eagle', 'South Portland', 'Thornton', 
    'Westerly', 'Dracut', 'Malden Catholic', 'Haverhill', 'Noble', 
    'Amesbury', 'Andover', 'BYE'
]

# ---------------------------------------------------------
# 2. CSV Parser
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
            
            if col0 and not col0.startswith('Week') and col0 not in ['East', 'Central', 'West']:
                current_team = normalize_name(col0)
            
            elif col0.startswith('Week'):
                opp_norm = normalize_name(row[2]) if len(row) > 2 else None
                is_div_flag = str(row[3]).strip() if len(row) > 3 else ''
                
                raw_res = str(row[4]).strip().upper() if len(row) > 4 else ''
                res = raw_res if raw_res in ['W', 'L'] else None
                
                if opp_norm and opp_norm not in EXCLUDED_OPPONENTS and current_team in TEAM_TO_DIV:
                    games.append({
                        'Team': current_team,
                        'Week': col0,
                        'Opponent': opp_norm,
                        'IsDiv': is_div_flag,
                        'Result': res
                    })
                    
    return pd.DataFrame(games)

# ---------------------------------------------------------
# 3. Sidebar: What-If Game Simulator & Reset Control
# ---------------------------------------------------------
st.sidebar.header("⚙️ Game Simulator Sandbox")

games_df = parse_schedule_csv()
unplayed_df = games_df[games_df['Result'].isna()].copy()

unique_fixtures = []
seen_fixtures = set()

for _, row in unplayed_df.iterrows():
    pair = tuple(sorted([row['Team'], row['Opponent']]))
    if pair not in seen_fixtures:
        seen_fixtures.add(pair)
        unique_fixtures.append((row['Week'], row['Team'], row['Opponent']))

if st.sidebar.button("🔄 Reset All Results", use_container_width=True):
    for week, team1, team2 in unique_fixtures:
        key = f"sim_{week}_{team1}_{team2}"
        if key in st.session_state:
            st.session_state[key] = "Actual/TBD"
    st.rerun()

simulated_outcomes = {}

if len(unique_fixtures) == 0:
    st.sidebar.success("🎉 All regular season games have been completed!")
else:
    st.sidebar.markdown("Pick winners for remaining unplayed games:")
    weeks = sorted(list(set(w for w, _, _ in unique_fixtures)))
    
    for week in weeks:
        st.sidebar.subheader(f"📅 {week}")
        week_fixtures = [f for f in unique_fixtures if f[0] == week]
        
        for w, team1, team2 in week_fixtures:
            key = f"sim_{w}_{team1}_{team2}"
            choice = st.sidebar.selectbox(
                f"{team1} vs {team2}",
                options=["Actual/TBD", f"{team1} Win", f"{team2} Win"],
                key=key
            )
            if choice == f"{team1} Win":
                simulated_outcomes[(team1, team2)] = team1
            elif choice == f"{team2} Win":
                simulated_outcomes[(team1, team2)] = team2
            else:
                simulated_outcomes[(team1, team2)] = None

# ---------------------------------------------------------
# 4. Calculation Engine
# ---------------------------------------------------------
teams_list = list(TEAM_TO_DIV.keys())

all_victories = {t: [] for t in teams_list}
div_victories = {t: [] for t in teams_list}

standings_data = {
    t: {
        'Division': TEAM_TO_DIV[t], 
        'W': 0, 'L': 0, 'GP': 0, 
        'Div_W': 0, 'Div_L': 0, 'Div_GP': 0,
        'H2H_Wins': {other: 0 for other in teams_list}
    }
    for t in teams_list
}

played_games = games_df[games_df['Result'].isin(['W', 'L'])]

for _, row in played_games.iterrows():
    t = row['Team']
    opp = row['Opponent']
    is_div = TEAM_TO_DIV.get(t) == TEAM_TO_DIV.get(opp)
    
    if t in standings_data:
        standings_data[t]['GP'] += 1
        if is_div:
            standings_data[t]['Div_GP'] += 1
            
        if row['Result'] == 'W':
            standings_data[t]['W'] += 1
            standings_data[t]['H2H_Wins'][opp] += 1
            all_victories[t].append(opp)
            if is_div:
                standings_data[t]['Div_W'] += 1
                div_victories[t].append(opp)
        elif row['Result'] == 'L':
            standings_data[t]['L'] += 1
            if is_div:
                standings_data[t]['Div_L'] += 1

for (t1, t2), winner in simulated_outcomes.items():
    if winner is not None:
        loser = t2 if winner == t1 else t1
        is_div = TEAM_TO_DIV.get(winner) == TEAM_TO_DIV.get(loser)
        
        if winner in standings_data:
            standings_data[winner]['GP'] += 1
            standings_data[winner]['W'] += 1
            standings_data[winner]['H2H_Wins'][loser] += 1
            all_victories[winner].append(loser)
            if is_div:
                standings_data[winner]['Div_GP'] += 1
                standings_data[winner]['Div_W'] += 1
                div_victories[winner].append(loser)
                
        if loser in standings_data:
            standings_data[loser]['GP'] += 1
            standings_data[loser]['L'] += 1
            if is_div:
                standings_data[loser]['Div_GP'] += 1
                standings_data[loser]['Div_L'] += 1

win_counts = {t: standings_data[t]['W'] for t in teams_list}
overall_points = {}
div_points = {}

for t in teams_list:
    tot_pts = sum(10.0 + (2.0 * win_counts.get(opp, 0)) for opp in all_victories[t])
    overall_points[t] = tot_pts
    
    d_pts = sum(10.0 + (2.0 * win_counts.get(opp, 0)) for opp in div_victories[t])
    div_points[t] = d_pts

df_stand = pd.DataFrame.from_dict(standings_data, orient='index').reset_index()
df_stand.rename(columns={'index': 'Team'}, inplace=True)

df_stand['Points'] = df_stand['Team'].map(overall_points)
df_stand['Div_Points'] = df_stand['Team'].map(div_points)

df_stand['Rating'] = (df_stand['Points'] / df_stand['GP'].replace(0, 1)).round(4)
df_stand['Div_Rating'] = (df_stand['Div_Points'] / df_stand['Div_GP'].replace(0, 1)).round(4)
df_stand['Div_WinPct'] = (df_stand['Div_W'] / df_stand['Div_GP'].replace(0, 1)).round(4)
df_stand['Overall_WinPct'] = (df_stand['W'] / df_stand['GP'].replace(0, 1)).round(4)

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
    (df_stand['Div_Rating'] * 0.001) + 
    (df_stand['Overall_WinPct'] * 0.0001)
)

df_stand = df_stand.sort_values(by='Adjusted_Rating', ascending=False).reset_index(drop=True)

# ---------------------------------------------------------
# 5. Division Leaders & Playoff Seeding
# ---------------------------------------------------------
div_leaders = []
for div_name in ['East', 'Central', 'West']:
    top_team = df_stand[df_stand['Division'] == div_name].iloc[0]['Team']
    div_leaders.append(top_team)

df_stand['Is_Div_Leader'] = df_stand['Team'].isin(div_leaders)

leaders_df = df_stand[df_stand['Is_Div_Leader']].sort_values(by='Adjusted_Rating', ascending=False)
remaining_df = df_stand[~df_stand['Is_Div_Leader']].sort_values(by='Adjusted_Rating', ascending=False)

seeding_df = pd.concat([leaders_df, remaining_df]).reset_index(drop=True)
seeding_df['Seed'] = seeding_df.index + 1

# ---------------------------------------------------------
# 6. Streamlit User Interface
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📊 Standings & Seeding", "🏆 Bracket Matchups"])

display_cols = ['Seed', 'Team', 'Division', 'W', 'L', 'GP', 'Points', 'Rating', 'Div_W', 'Div_L', 'Div_Rating']

with tab1:
    st.subheader("Official Projected Seeding (Top 13 Qualify)")
    st.dataframe(
        seeding_df[display_cols].head(13),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("Conference Division Standings")
    
    div_tab1, div_tab2, div_tab3 = st.tabs(["East Division", "Central Division", "West Division"])
    
    with div_tab1:
        east_df = df_stand[df_stand['Division'] == 'East'].sort_values(by='Adjusted_Rating', ascending=False)
        st.dataframe(
            east_df[['Team', 'W', 'L', 'GP', 'Points', 'Rating', 'Div_W', 'Div_L', 'Div_Rating']],
            use_container_width=True,
            hide_index=True
        )
        
    with div_tab2:
        central_df = df_stand[df_stand['Division'] == 'Central'].sort_values(by='Adjusted_Rating', ascending=False)
        st.dataframe(
            central_df[['Team', 'W', 'L', 'GP', 'Points', 'Rating', 'Div_W', 'Div_L', 'Div_Rating']],
            use_container_width=True,
            hide_index=True
        )
        
    with div_tab3:
        west_df = df_stand[df_stand['Division'] == 'West'].sort_values(by='Adjusted_Rating', ascending=False)
        st.dataframe(
            west_df[['Team', 'W', 'L', 'GP', 'Points', 'Rating', 'Div_W', 'Div_L', 'Div_Rating']],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")
    st.subheader("Full Division 1 Standings")
    st.dataframe(
        df_stand[['Team', 'Division', 'W', 'L', 'GP', 'Points', 'Rating', 'Div_W', 'Div_L', 'Div_Rating']],
        use_container_width=True,
        hide_index=True
    )

with tab2:
    st.subheader("NHIAA Division 1 Playoff Bracket Preview")
    playoff_13 = seeding_df.head(13).set_index('Seed')

    # Generate Graphical HTML Bracket
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
        st.info(f"**#1 Seed ({playoff_13.loc[1, 'Division']} Winner):** {playoff_13.loc[1, 'Team']} ({playoff_13.loc[1, 'Rating']} Rating)")
        st.info(f"**#2 Seed ({playoff_13.loc[2, 'Division']} Winner):** {playoff_13.loc[2, 'Team']} ({playoff_13.loc[2, 'Rating']} Rating)")
        st.info(f"**#3 Seed ({playoff_13.loc[3, 'Division']} Winner):** {playoff_13.loc[3, 'Team']} ({playoff_13.loc[3, 'Rating']} Rating)")

    with col_b:
        st.markdown("### ⚔️ Opening Round Matchups")
        st.write(f"🏈 **Matchup A:** #4 **{playoff_13.loc[4, 'Team']}** vs #13 **{playoff_13.loc[13, 'Team']}**")
        st.write(f"🏈 **Matchup B:** #5 **{playoff_13.loc[5, 'Team']}** vs #12 **{playoff_13.loc[12, 'Team']}**")
        st.write(f"🏈 **Matchup C:** #6 **{playoff_13.loc[6, 'Team']}** vs #11 **{playoff_13.loc[11, 'Team']}**")
        st.write(f"🏈 **Matchup D:** #7 **{playoff_13.loc[7, 'Team']}** vs #10 **{playoff_13.loc[10, 'Team']}**")
        st.write(f"🏈 **Matchup E:** #8 **{playoff_13.loc[8, 'Team']}** vs #9 **{playoff_13.loc[9, 'Team']}**")