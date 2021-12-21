# %%
# import pymongo
from re import search
from pymongo import MongoClient
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pandas import DataFrame
import numpy as np
import altair as alt
# import streamlit_authenticator as stauth
st.set_page_config(layout="wide")
#%%
#removes hamburger menu
hide_menu_style = """
        <style>
        #MainMenu {visibility: hidden;}
        </style>
        """
st.markdown(hide_menu_style, unsafe_allow_html=True)

#accessing credentials in secrets file
myusr = st.secrets["myusr"]
mypwd = st.secrets["mypwd"]
client = MongoClient(f"mongodb+srv://{myusr}:{mypwd}@cluster0.vkduz.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")
#databases
db = client.get_database("test")
search_db = client.get_database("cuy_searches")
#collections
search_data = search_db.get_collection("test_searches")
crimedata = db.get_collection("crimedata")

#%%
st.title('Cuyahoga Sentencing Data (2009-2019)')
st.subheader("All Data")
sidebar_items = ['judge']

@st.cache
def get_data():
    data = db.crimedata.find({}, {'judge':1, "plea_orcs":1, "prior_cases":1, "race":1, "_id":0, "pris_yrs":1})
    df = DataFrame(list(data))
    #remove all white space in all column headers
    for col in df.columns:
        col = col.strip()
    #remove rows whee plea_orcs is empty
    df = df[(df['plea_orcs'] != '') & (df['plea_orcs'] != np.nan) & (df['plea_orcs'] != 'None')]
    df = df[(df['prior_cases'] != '') & (df['prior_cases'] != np.nan) & (df['prior_cases'] != 'None')]
    df = df[(df['race'] != '') & (df['race'] != np.nan) & (df['race'] != 'None')]
    print(df['pris_yrs'].iloc[:10])
    #sort df by judge
    df = df.sort_values(by=['judge'])
    return df

df = get_data()
#put the df in an expander
with st.expander(f'All Data for All Judges'):
    st.write(df)

# creates the sidebar dropdown for the judge only, look to simplify this before production
params = {}
for item in sidebar_items:
    name_of_lst = f'{item}_lst'
    lst_name = f'{item}_lst'
    lst_name = db.crimedata.distinct (item)
    lst_name = [x for x in lst_name if str(x) != 'nan' and x != ' ' and x != '']
    #add each item to params
    params[item] = st.sidebar.selectbox(item.title(), lst_name)

def df_update(df):
    selection = df[df['judge'] == params['judge']]  #data for selected Judge
    overall = df[df['judge'] != params['judge']] #data for all judges except the selected judge
    plea_orcs = sorted(selection['plea_orcs'].unique())
    plea_orcs = ['All'] + plea_orcs
    params['Plea'] = st.sidebar.selectbox('Plea'.title(), plea_orcs)
    if params['Plea'] != 'All':
        selection = selection[selection['plea_orcs'] == params['Plea']]
        overall = overall[overall['plea_orcs'] == params['Plea']]
    #unique prior cases for dropdown list
    priors = sorted(selection['prior_cases'].unique())
    priors = ['All'] + priors
    params['Prior Cases (greater than or equal to selection)'] = st.sidebar.selectbox('Prior Cases (greater than or equal to selection)'.title(), priors)
    if params['Prior Cases (greater than or equal to selection)'] != 'All':
        selection = selection[selection['prior_cases'] == params['Prior Cases (greater than or equal to selection)']]
        overall = overall[overall['prior_cases'] >= params['Prior Cases (greater than or equal to selection)']]
    #unique races for dropdown list
    race_lst = selection['race'].unique() #list of race values in data from above selections
    race_lst = [str(x) for x in race_lst]
    race_lst = sorted(race_lst)
    race_lst = ['All'] + race_lst
    params["Defendant's Race"] = st.sidebar.selectbox("Defendant's Race".title(), race_lst)
    if params["Defendant's Race"] != 'All':
        selection = selection['race'] == params["Defendant's Race"]
        overall = overall['race'] == params["Defendant's Race"]
    # total_cases = overall.shape[0]
    total_cases_selected = selection.shape[0]
    #create row of two columns
    judge_total = f'{total_cases_selected} cases'

    avg_overall_sent = round(overall['pris_yrs'].mean(),2)
    avg_sentence_judge = round(selection['pris_yrs'].mean(),2)

    race_g = selection.groupby('race')['pris_yrs'].mean().reset_index()
    race_g['pris_yrs'] = round(race_g['pris_yrs'],2)
    race_g.columns = ['Race', 'Average Prison Sentence (years)']
    race_g['Average Prison Sentence (years)'] = round(race_g['Average Prison Sentence (years)'],2)

    conditions = [
        (race_g['Average Prison Sentence (years)'] > avg_overall_sent),
        (race_g['Average Prison Sentence (years)'] < avg_overall_sent),
        (race_g['Average Prison Sentence (years)'] == avg_overall_sent),
    ]
    values = ['Above', 'Below', 'Equal']
    race_g['Compared to Average'] = np.select(conditions, values)
    #avg sentence by race - selected judge
    g = selection.groupby(['prior_cases', 'race'])['pris_yrs'].mean().reset_index()
    g.columns = ['Prior Cases', 'Race', 'Prison Years']
    g['Compared to Average'] = np.where(g['Prison Years'] > avg_sentence_judge, 'Above', 'Below')

    #modifications to the overall dataframe
    overall = overall[['prior_cases', 'race', 'judge', 'pris_yrs']]
    #sort by Judge
    overall.sort_values(by=['judge', 'prior_cases'], inplace=True)

    total_cases = overall.shape[0]
    all_total = f'{total_cases} cases'

    #grouping for a new dataframe to show the average by judge and by race and their prior cases.
    g_all = overall.groupby(['judge', 'race'])['pris_yrs'].mean().reset_index()
    #grouping data to use for the graph of all judges by race
    g_all_avg = overall.groupby('race')['pris_yrs'].mean().reset_index()
    g_all_avg['pris_yrs'] = g_all_avg['pris_yrs'].round(2)
    #avg sentence by race - all judges
    g_all.columns = ['Judge', 'Race', 'Average Prison Sentence (years)']
    g_all['Average Prison Sentence (years)'] = round(g_all['Average Prison Sentence (years)'],2)
    g_all['Compared to Average'] = np.where(g_all['Average Prison Sentence (years)'] > avg_sentence_judge, 'Above', 'Below')

    #add search terms to another database/collection
    from datetime import datetime
    if params['judge'] != 'AMBROSE_D' or params['Plea'] != 'All' or params['Prior Cases (greater than or equal to selection)'] != 'All':
        search_db.search_data.insert_one(
        {"judge": params['judge'], "plea_orc":params['Plea'] , "prior_cases": params['Prior Cases (greater than or equal to selection)'], "date": datetime.now()}
)
    return selection, judge_total, all_total, avg_sentence_judge, avg_overall_sent,g, race_g, g_all, overall, g_all_avg

selection, judge_total, all_total, avg_sent, avg_overall_sent, g, race_g, g_all, overall, g_all_avg = df_update(df)

st.subheader(f'Plea to: Ohio Revised Code §{params["Plea"]}')

col1, col2 = st.columns(2)
col1.metric(params['judge'], judge_total)
col2.metric("All Other Judges", all_total)
col1.markdown(f'Average Sentence is {avg_sent} years')
col2.markdown(f'Average Sentence is {avg_overall_sent} years')



#into columns here

col1, col2 = st.columns(2)

col1.subheader(f'Judge {params["judge"]} Cases:')
select_bar = alt.Chart(race_g, title='Average Sentence by Race').mark_bar().encode(y='Race', x='Average Prison Sentence (years)')
text = select_bar.mark_text(color='white').encode(text = 'Average Prison Sentence (years)')
col1.altair_chart(select_bar+text)
# col1.markdown("""---""")

col2.subheader(f'All Other Judges')
all_bar = alt.Chart(g_all_avg, title='Average Sentence by Race').mark_bar().encode(y='race', x='pris_yrs')
all_text = all_bar.mark_text(color='white').encode(text = 'pris_yrs')
col2.altair_chart(all_bar+all_text)
# col2.markdown("""---""")

with st.expander(F'All {params["judge"]} Data for {params["Plea"]}'):
    st.write(race_g)
with st.expander(F'All Other Judge Data for {params["Plea"]}'):
    st.write(g_all)
