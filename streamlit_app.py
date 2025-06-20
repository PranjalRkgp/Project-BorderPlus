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
import re

icon=Image.open('BorderPlus_icon.png')
# Set page config with light theme
st.set_page_config(
    page_title="Competitor Insights Dashboard",
    page_icon=icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# [Previous CSS and authentication code remains the same...]

def get_available_weeks(service, folder_id):
    query = f"'{folder_id}' in parents"
    results = service.files().list(q=query, fields="files(name)").execute()
    items = results.get('files', [])
    
    weeks = []
    month_order = ['january', 'february', 'march', 'april', 'may', 'june', 
                  'july', 'august', 'september', 'october', 'november', 'december']
    
    for item in items:
        if 'week' in item['name'].lower():
            try:
                # Extract week number, month name, and year suffix using regex
                match = re.match(r'week(\d+)([a-z]+)(\'?\d*)', item['name'].lower())
                if match:
                    week_num = int(match.group(1))
                    month_name = match.group(2)
                    year_suffix = match.group(3) if match.group(3) else ''
                    
                    if month_name in month_order:
                        month_num = month_order.index(month_name) + 1
                        weeks.append({
                            'file_name': item['name'].split('.')[0],  # Store full filename without extension
                            'identifier': f'week{week_num}{month_name}{year_suffix}',
                            'sort_key': (month_num, week_num),
                            'display_name': f"Week {week_num} {month_name.capitalize()}{year_suffix}"
                        })
            except Exception as e:
                print(f"Error processing file {item['name']}: {str(e)}")
                continue
    
    # Sort by month number, then by week number (oldest to newest)
    weeks.sort(key=lambda x: x['sort_key'])
    
    # Return both identifiers and display names
    return {
        'file_names': [w['file_name'] for w in weeks],
        'display_names': [w['display_name'] for w in weeks]
    }

def find_file_with_fallback(service, base_name, parent_id, extensions=['.html', '.xlsx', '.csv']):
    """Try to find file with different naming patterns and extensions"""
    patterns_to_try = [
        base_name,
        f"{base_name.split('_')[0]}_{base_name.split('_')[1].replace("'", "")}"  # Try without year suffix
    ]
    
    for pattern in patterns_to_try:
        for ext in extensions:
            try:
                full_name = f"{pattern}{ext}"
                return find_file(service, full_name, parent_id)
            except:
                continue
    
    raise Exception(f"Could not find any matching file for base name: {base_name}")

# [Previous helper functions remain the same...]

def show_all_at_once_view(service, allatonce_folder_id, selected_week_file):
    st.title("Industry Report - All at Once View")
    display_name = selected_week_file.replace('week', 'Week ').title()
    st.subheader(f"You are viewing the complete industry report for {display_name}")
    
    try:
        base_name = f"industry_report_{selected_week_file}"
        html_file_id = find_file_with_fallback(service, base_name, allatonce_folder_id, ['.html'])
        html_file = download_file(service, html_file_id)
        html_content = read_html_content(html_file)
        
        st.markdown(f"""
        <div class="custom-container">
            {html_content}
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Could not load industry report: {str(e)}")

def show_dashboard_view(service, folder_ids, selected_week_file, selected_company, summary_df):
    display_name = selected_week_file.replace('week', 'Week ').title()
    st.title(f"{selected_company} Insights Dashboard")
    st.subheader(f"You are viewing {display_name} data")
    
    try:
        base_name = f"raw_info_{selected_week_file}"
        raw_file_id = find_file_with_fallback(service, base_name, folder_ids['raw_info_sources'], ['.xlsx'])
        raw_file = download_file(service, raw_file_id)
        raw_df = read_excel_content(raw_file)
    except Exception as e:
        st.error(f"Could not load raw data: {str(e)}")
        return
    
    # [Rest of the dashboard view code remains the same...]

def main():
    # Initialize session state variables
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
        available_week_files = weeks_data['file_names']
        week_display_names = weeks_data['display_names']
        
        # Default to latest week (last in sorted list)
        default_week_index = len(available_week_files) - 1 if available_week_files else 0
    except Exception as e:
        st.error(f"Could not retrieve available weeks: {str(e)}")
        return
    
    with st.sidebar:
        image = Image.open('BorderPlus_logo.png')
        st.image(image)
        st.header("Competitor Analysis Controls")
        
        # Week selection with formatted display names
        selected_week_file = st.selectbox(
            "Select Week",
            options=available_week_files,
            format_func=lambda x: week_display_names[available_week_files.index(x)],
            index=default_week_index
        )
        
        # Load summary data for the selected week
        try:
            base_name = f"summary_{selected_week_file}"
            summary_file_id = find_file_with_fallback(service, base_name, folder_ids['summary_sources'], ['.csv'])
            summary_file = download_file(service, summary_file_id)
            summary_df = read_csv_content(summary_file)
            companies = summary_df['Company'].unique().tolist()
            companies = ["View All at Once"] + companies
        except Exception as e:
            st.error(f"Could not load summary data: {str(e)}")
            return
        
        # [Rest of the main function remains the same...]

if __name__ == "__main__":
    main()
