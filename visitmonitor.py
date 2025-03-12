import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# Set page config
st.set_page_config(
    page_title="Dealer Visit Monitor",
    page_icon="📊",
    layout="wide"
)


# Function to load and prepare data
@st.cache_data(ttl=600)
def load_data():
    try:
        # Set up Google Sheets API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        # Try using service account file first
        try:
            credentials = Credentials.from_service_account_file('sheet_access.json', scopes=scopes)
        except:
            # If file not found, try using secrets
            credentials_dict = st.secrets["gcp_service_account"]
            credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)

        gc = gspread.authorize(credentials)

        # Open the spreadsheet
        spreadsheet = gc.open('visit form - data')

        # Get the responses worksheet
        responses_sheet = spreadsheet.worksheet('responses')

        # Get all records
        data = responses_sheet.get_all_records()

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Rename columns to remove spaces and match expected names
        df = df.rename(columns={
            'buy now': 'buy_now',
            'dealer code': 'dealer_code',
            'Hatla2ee link': 'hatla2ee_link',
            'dubizzle link': 'dubizzle_link',
            'showroom capacity': 'showroom_capacity'
        })

        # Convert datetime column
        df['submitted_datetime'] = pd.to_datetime(df['submitted_datetime'])

        # Convert Yes/No columns to boolean
        for col in ['showroom', 'swift', 'lending', 'buy_now']:
            df[col] = df[col].map({'Yes': True, 'No': False})

        # Split issues into list
        df['issues_list'] = df['issues'].str.split(', ')

        return df

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.error("Available columns: " + ", ".join(df.columns if 'df' in locals() else ["No DataFrame available"]))
        return pd.DataFrame()  # Return empty DataFrame on error


def main():
    st.title("Dealer Visit Analytics Dashboard")

    # Load data
    df = load_data()

    # Sidebar filters
    st.sidebar.header("Filters")

    # Date range filter
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(df['submitted_datetime'].min().date(), df['submitted_datetime'].max().date())
    )

    # Dealer filter
    selected_dealers = st.sidebar.multiselect(
        "Select Dealers",
        options=sorted(df['dealer'].unique())
    )

    # Apply filters
    mask = (df['submitted_datetime'].dt.date >= date_range[0]) & \
           (df['submitted_datetime'].dt.date <= date_range[1])
    if selected_dealers:
        mask = mask & (df['dealer'].isin(selected_dealers))

    filtered_df = df[mask]

    # Add Summary Statistics Section
    st.header("Summary Statistics")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Total Visits",
            value=len(filtered_df)
        )

    with col2:
        st.metric(
            label="Unique Dealers Visited",
            value=filtered_df['dealer'].nunique()
        )



    # Add Dealer Visit Summary
    st.subheader("Dealer Visit Summary")
    dealer_summary = filtered_df.groupby('dealer').agg({
        'submitted_datetime': 'count',
        'dealer_code': 'first'
    }).reset_index()

    dealer_summary.columns = ['Dealer Name', 'Number of Visits', 'Dealer Code']
    dealer_summary = dealer_summary.sort_values('Number of Visits', ascending=False)

    st.dataframe(
        dealer_summary,
        column_config={
            "Dealer Name": st.column_config.TextColumn(width="medium"),
            "Number of Visits": st.column_config.NumberColumn(width="small"),
            "Dealer Code": st.column_config.TextColumn(width="small")
        }
    )

    # Dashboard layout
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Issues Overview")
        # Create issues chart
        issues_data = []
        for issues in filtered_df['issues_list'].dropna():
            issues_data.extend(issues)

        issues_counts = pd.Series(issues_data).value_counts()

        fig = px.bar(
            x=issues_counts.index,
            y=issues_counts.values,
            title="Most Common Issues"
        )
        st.plotly_chart(fig)

    with col2:
        st.subheader("Visit Metrics")
        metrics_df = pd.DataFrame({
            'Metric': ['Showroom', 'Swift', 'Lending', 'Buy Now'],
            'Yes': [
                filtered_df['showroom'].mean() * 100,
                filtered_df['swift'].mean() * 100,
                filtered_df['lending'].mean() * 100,
                filtered_df['buy_now'].mean() * 100
            ]
        })

        fig = px.bar(
            metrics_df,
            x='Metric',
            y='Yes',
            title="Percentage of 'Yes' Responses",
            labels={'Yes': 'Percentage (%)'}
        )
        st.plotly_chart(fig)

    # Detailed data view
    st.subheader("Visit Details")
    st.dataframe(
        filtered_df[[
            'submitted_datetime', 'dealer', 'dealer_code',
            'purpose', 'problems', 'positives', 'requests'
        ]].sort_values('submitted_datetime', ascending=False)
    )


if __name__ == "__main__":
    main()
