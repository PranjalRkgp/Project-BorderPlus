import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request
import pandas as pd
import io
from datetime import datetime
import json
from pathlib import Path
from PIL import Image

icon = Image.open('BorderPlus_icon.png')
# Set page config with light theme
st.set_page_config(
    page_title="Competitor Insights Dashboard",
    page_icon=icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom CSS for light blue and white theme
def add_custom_css():
    st.markdown("""
    <style>
        html, body, .stApp {
            background-color: #F0F6FF !important;
            color: #1A1A1A !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        /* Headers */
        h1, h2, h3, h4, h5, h6 {
            color: #165BAA !important;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #E6F0FF !important;
            border-right: 1px solid #CCE0FF;
        }

        .stSidebar label, .stSidebar h3, .stSidebar h2 {
            color: #165BAA !important;
            font-weight: 600;
        }

        /* Generic labels and small headers */
        .css-1lcbmhc, .css-1v0mbdj, .stText, label {
            color: #165BAA !important;
            font-size: 16px !important;
        }

        /* Buttons */
        .stButton>button {
            background-color: #0B5ED7 !important;
            color: #FFFFFF !important;
            border-radius: 8px;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            border: none;
        }

        .stButton>button:hover {
            background-color: #084BC1 !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab"] {
            background-color: #D0E1FF !important;
            color: #165BAA !important;
            font-weight: 500;
            border-radius: 10px 10px 0 0;
            padding: 10px 18px;
            border: 1px solid #A6C8FF;
            border-bottom: none;
        }

        .stTabs [aria-selected="true"] {
            background-color: #0B5ED7 !important;
            color: #FFFFFF !important;
        }

        /* Info Cards */
        .custom-container, .info-card {
            background-color: #FFFFFF;
            border: 1px solid #A6C8FF;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }

        .info-card, .info-card * {
            color: #1A1A1A !important;
        }

        .info-card .header {
            color: #0B5ED7 !important;
            font-weight: 600;
        }

        /* Dropdown Selectbox */
        .stSelectbox>div>div {
            background-color: #FFFFFF !important;
            color: #1A1A1A !important;
            border: 1px solid #CCE0FF !important;
            border-radius: 6px;
        }

        .stSelectbox ul {
            background-color: #FFFFFF !important;
            color: #1A1A1A !important;
        }

        /* Tables */
        th {
            background-color: #165BAA !important;
            color: white !important;
        }

        tr:nth-child(even) {
            background-color: #F7FAFF !important;
        }

        tr:nth-child(odd) {
            background-color: #FFFFFF !important;
        }

        /* Inputs */
        input, textarea {
            background-color: #FFFFFF !important;
            border: 1px solid #CCE0FF !important;
            color: #1A1A1A !important;
        }

        /* Alerts */
        .stAlert {
            background-color: #6ca3f5 !important;
            border-left: 4px solid #0B5ED7 !important;
            color: #1A1A1A !important;
        }

        /* Links */
        a {
            color: #0B5ED7 !important;
        }

        a:hover {
            color: #084BC1 !important;
            text-decoration: underline;
        }
        
        /* Disabled elements */
        .disabled {
            opacity: 0.6;
            pointer-events: none;
        }

        /* New styles for logo positioning */
        .logo-container {
            margin-top: 0rem !important;
            margin-bottom: 0rem !important;
            padding-top: 0 !important;
        }
        
        .stApp {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        
        /* Remove extra padding from main content */
        .main .block-container {
            padding-top: 0 !important;
        }

        /* Remove all padding/margin at the top */
        .stApp > div:first-child {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }
        
        /* Target the logo container specifically */
        div[data-testid="column"]:has(img[src*="BorderPlus_logo.png"]) {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }        
    </style>
    """, unsafe_allow_html=True)

add_custom_css()

# Authentication with token caching
def authenticate():
    try:
        creds = Credentials(
            token=None,
            refresh_token=st.secrets["google"]["refresh_token"],
            client_id=st.secrets["google"]["client_id"],
            client_secret=st.secrets["google"]["client_secret"],
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        creds.refresh(Request())
        return creds
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

# Helper functions
def find_file(service, name, parent_id=None, mime_type=None):
    query = f"name = '{name}'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    if mime_type:
        query += f" and mimeType = '{mime_type}'"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    files = results.get('files', [])
    if not files:
        raise Exception(f"'{name}' not found.")
    return files[0]['id']

def get_available_weeks(service, folder_id):
    query = f"'{folder_id}' in parents"
    results = service.files().list(q=query, fields="files(name)").execute()
    items = results.get('files', [])
    
    weeks = []
    month_order = ['january', 'february', 'march', 'april', 'may', 'june', 
                  'july', 'august', 'september', 'october', 'november', 'december']
    
    for item in items:
        if item['name'].lower().startswith('week'):
            try:
                # Remove file extensions and get base name
                filename = item['name'].lower()
                for ext in ['.html', '.xlsx', '.csv']:
                    filename = filename.replace(ext, '')
                
                # Extract week number, month, and year
                parts = filename.split('week')
                if len(parts) < 2:
                    continue
                
                rest = parts[1]  # e.g., "2june'25"
                
                # Extract week number
                week_num_str = ''
                i = 0
                while i < len(rest) and rest[i].isdigit():
                    week_num_str += rest[i]
                    i += 1
                
                if not week_num_str:
                    continue
                
                week_num = int(week_num_str)
                remaining = rest[i:]  # e.g., "june'25"
                
                # Extract month and year
                month_part = ''
                year_part = '25'  # default
                
                if "'" in remaining:
                    month_part = remaining.split("'")[0]
                    year_part = remaining.split("'")[1] if len(remaining.split("'")) > 1 else '25'
                else:
                    month_part = remaining
                
                month_name = month_part.lower()
                if month_name not in month_order:
                    continue
                
                month_num = month_order.index(month_name) + 1
                year_num = 2000 + int(year_part) if len(year_part) == 2 else int(year_part)
                
                weeks.append({
                    'identifier': f'week{week_num}{month_name}\'{year_part[-2:]}',  # week2june'25
                    'sort_key': (year_num, month_num, week_num),
                    'display_name': f"Week {week_num} {month_name.capitalize()}'{year_part[-2:]}"  # Week 2 June'25
                })
            except Exception as e:
                print(f"Error processing file {item['name']}: {str(e)}")
                continue
    
    # Sort by year, month, then week
    weeks.sort(key=lambda x: x['sort_key'])
    
    return {
        'identifiers': [w['identifier'] for w in weeks],
        'display_names': [w['display_name'] for w in weeks]
    }

def download_file(service, file_id):
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh

def read_html_content(file_content):
    content = file_content.read().decode('utf-8')
    content = content.replace('<body>', '<body style="background-color: white; color: #333;">')
    return content

def read_excel_content(file_content):
    return pd.read_excel(file_content)

def read_csv_content(file_content):
    return pd.read_csv(file_content)

# View functions
def show_all_at_once_view(service, allatonce_folder_id, selected_week):
    st.title("Industry Report - All at Once View")
    display_week = selected_week.replace('week', 'Week ').replace("'", "'").title()
    st.subheader(f"You are viewing the complete industry report for {display_week}")
    
    try:
        html_file_id = find_file(service, f"industry_report_{selected_week}.html", parent_id=allatonce_folder_id)
        html_file = download_file(service, html_file_id)
        html_content = read_html_content(html_file)
        
        st.markdown(f"""
        <div class="custom-container">
            {html_content}
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Could not load industry report: {str(e)}")

def show_dashboard_view(service, folder_ids, selected_week, selected_company, summary_df):
    display_week = selected_week.replace('week', 'Week ').replace("'", "'").title()
    st.title(f"{selected_company} Insights Dashboard")
    st.subheader(f"You are viewing {display_week} data")
    
    try:
        raw_file_id = find_file(service, f"raw_info_{selected_week}.xlsx", parent_id=folder_ids['raw_info_sources'])
        raw_file = download_file(service, raw_file_id)
        raw_df = read_excel_content(raw_file)
    except Exception as e:
        st.error(f"Could not load raw data: {str(e)}")
        return
    
    company_summary = summary_df[summary_df['Company'] == selected_company].iloc[0]
    company_raw_data = raw_df[raw_df['Company'] == selected_company]
    
    tab_names = [
        "Summary",
        "New Market",
        "New Product",
        "Pricing Changes",
        "Funding",
        "MOUs",
        "Hiring",
        "Leadership Changes",
        "Events",
        "Partnerships"
    ]
    
    tabs = st.tabs(tab_names)
    
    with tabs[0]:  # Summary tab
        st.subheader(f"Summary for {selected_company}")
        if pd.notna(company_summary['Summary']):
            st.markdown(f"""
            <div class="info-card">
                <div class="content">
                    {company_summary['Summary']}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No summary available for this company.")
            
        if pd.notna(company_summary['References']):
            st.markdown("**References:**")
            references = company_summary['References'].split(';')
            for ref in references:
                ref = ref.strip()
                if ref:
                    st.markdown(f"- [{ref}]({ref})")
    
    tab_fields = {
        "New Market": "new_market",
        "New Product": "new_product",
        "Pricing Changes": "pricing_changes",
        "Funding": "funding",
        "MOUs": "mous",
        "Hiring": "hiring",
        "Leadership Changes": "leadership_changes",
        "Events": "events",
        "Partnerships": "partnerships"
    }
    
    for tab_name, field in tab_fields.items():
        with tabs[tab_names.index(tab_name)]:
            st.subheader(tab_name)
            
            relevant_data = company_raw_data[
                (company_raw_data[field].astype(str).str.lower().ne('none')) & 
                (company_raw_data[field].astype(str).str.lower().ne('nan')) & 
                (company_raw_data[field].astype(str).str.lower().ne(''))
            ]
            
            if relevant_data.empty:
                st.info(f"No {tab_name.lower()} information available for this week.")
            else:
                relevant_data = relevant_data.reset_index(drop=True)
                
                for idx, row in relevant_data.iterrows():
                    button_key = f"see_more_{tab_name.lower()}_{idx}"
                    
                    with st.container():
                        st.markdown(f"""
                            <div class="info-card">
                                <div class="content">
                                    <strong>{row[field]}</strong>
                                </div>
                                <div>Source: {row['Source']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"See More Details", key=button_key):
                            with st.expander("Full Details", expanded=True):
                                st.markdown(f"**URL:** [{row['URL']}]({row['URL']})")
                                st.markdown(f"**Date:** {row['Date']}")
                                st.markdown("**Original Information:**")
                                st.markdown(f"""
                                <div class="custom-container">
                                    {row['Information']}
                                </div>
                                """, unsafe_allow_html=True)

def main():
    if 'show_details' not in st.session_state:
        st.session_state.show_details = False
    
    try:
        creds = authenticate()
        service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return
    
    try:
        parent_folder_id = find_file(service, "Competitor Reporting", mime_type="application/vnd.google-apps.folder")
        folder_ids = {
            'allatonce': find_file(service, "allatonce", parent_id=parent_folder_id, mime_type="application/vnd.google-apps.folder"),
            'raw_info_sources': find_file(service, "raw_info_sources", parent_id=parent_folder_id, mime_type="application/vnd.google-apps.folder"),
            'summary_sources': find_file(service, "summary_sources", parent_id=parent_folder_id, mime_type="application/vnd.google-apps.folder")
        }
    except Exception as e:
        st.error(str(e))
        return
    
    try:
        weeks_data = get_available_weeks(service, folder_ids['allatonce'])
        available_weeks = weeks_data['identifiers']
        week_display_names = weeks_data['display_names']
        
        default_week_index = len(available_weeks) - 1 if available_weeks else 0
    except Exception as e:
        st.error(f"Could not retrieve available weeks: {str(e)}")
        return
    
    with st.sidebar:
        image = Image.open('BorderPlus_logo.png')
        st.image(image)
        st.header("Competitor Analysis Controls")
        
        selected_week = st.selectbox(
            "Select Week",
            options=available_weeks,
            format_func=lambda x: week_display_names[available_weeks.index(x)],
            index=default_week_index
        )
        
        try:
            summary_file_id = find_file(service, f"summary_{selected_week}.csv", parent_id=folder_ids['summary_sources'])
            summary_file = download_file(service, summary_file_id)
            summary_df = read_csv_content(summary_file)
            companies = summary_df['Company'].unique().tolist()
            companies = ["View All at Once"] + companies
        except Exception as e:
            st.error(f"Could not load summary data: {str(e)}")
            return
        
        selected_company = st.selectbox(
            "Select Company", 
            options=companies,
            index=0
        )
        
        if st.button("Show Details"):
            if selected_company == "View All at Once":
                st.session_state.show_details = False
            else:
                st.session_state.show_details = True
            st.rerun()
    
    if selected_company == "View All at Once" or not st.session_state.show_details:
        show_all_at_once_view(service, folder_ids['allatonce'], selected_week)
    else:
        show_dashboard_view(service, folder_ids, selected_week, selected_company, summary_df)
        
if __name__ == "__main__":
    main()
