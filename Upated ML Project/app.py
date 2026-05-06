import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from wind_utils import get_location_coords, get_wind_forecast, calculate_wind_power, extrapolate_wind_speed

st.set_page_config(page_title="Wind Energy Forecast", page_icon="🌬️", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for enhanced styling
st.markdown(
    """
    <style>
    .main {
        background-color: #0e1117;
    }
    .stButton>button {
        background-color: #2ca02c;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #227a22;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    .stMetricValue {
        font-size: 28px;
        font-weight: bold;
    }
    .stMetricLabel {
        font-size: 16px;
        color: #a9b7c6;
    }
    .wind-turbine {
        font-size: 48px;
        text-align: center;
        margin: 10px 0;
        animation: spin 15s linear infinite;
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌬️ Real-Time Wind Energy Forecasting Dashboard")
st.markdown(
    "<p style='color:#a9b7c6;'>Search any location by name or enter exact coordinates to see current wind conditions and estimated energy generation forecasts.</p>",
    unsafe_allow_html=True
)

# Indian wind farm presets
INDIAN_LOCATIONS = {
    "Custom (enter below)": (None, None),
    "Muppandal, Tamil Nadu": (9.3000, 77.8000),
    "Jaisalmer, Rajasthan": (26.9124, 70.9122),
    "Satara, Maharashtra": (17.6800, 74.0200),
    "Kanyakumari, Tamil Nadu": (8.0800, 77.5500),
    "Dwarka, Gujarat": (22.2400, 68.9700),
    "Coimbatore, Tamil Nadu": (11.0168, 76.9558),
    "Rajkot, Gujarat": (22.3039, 70.8022),
    "Bhuj, Gujarat": (23.2500, 69.6667),
    "Nagpur, Maharashtra": (21.1458, 79.0882),
    "Chennai, Tamil Nadu": (13.0827, 80.2707),
}

# Sidebar
with st.sidebar:
    st.header("Location Search")

    search_mode = st.radio("Search by", ["City Name", "Coordinates"], index=1)

    if search_mode == "City Name":
        location_input = st.text_input("Enter city or location", value="Muppandal")
        lat_input = None
        lon_input = None
        search_btn = st.button("Search by Name")
    else:
        st.markdown("**Quick Select — Indian Wind Farms**")
        preset = st.selectbox("Choose a location", list(INDIAN_LOCATIONS.keys()))
        preset_lat, preset_lon = INDIAN_LOCATIONS[preset]

        st.markdown("**Or enter custom coordinates**")
        lat_input = st.number_input("Latitude", value=preset_lat if preset_lat else 9.3000, format="%.4f")
        lon_input = st.number_input("Longitude", value=preset_lon if preset_lon else 77.8000, format="%.4f")
        location_input = None
        search_btn = st.button("Search by Coordinates")

    st.markdown("---")
    st.header("Turbine Settings")

    hub_height = st.slider("Hub Height (m)", min_value=50, max_value=150, value=100, step=10)

    TERRAIN_ALPHA = {
        "Open water / flat desert": 0.10,
        "Open grassland / farmland": 0.14,
        "Rough farmland / scattered trees": 0.20,
        "Forest / suburban / cities": 0.30,
    }
    terrain = st.selectbox("Terrain Type", list(TERRAIN_ALPHA.keys()), index=1)
    alpha = TERRAIN_ALPHA[terrain]
    st.caption(f"Wind shear exponent (α): {alpha}")

    st.markdown("---")
    st.markdown("**About**")
    st.markdown(
        "This dashboard fetches live weather data from the Open-Meteo API "
        "and estimates wind energy output using a standard 2MW turbine power curve."
    )

# Main logic
if search_btn or location_input or (lat_input is not None and lon_input is not None):
    try:
        with st.spinner("Fetching forecast data..."):
            if search_mode == "City Name" and location_input:
                lat, lon, loc_name = get_location_coords(location_input)
            else:
                lat, lon = lat_input, lon_input
                loc_name = f"{lat:.4f}, {lon:.4f}"
            df = get_wind_forecast(lat, lon)

            # Extrapolate 10m wind speed to hub height
            df["wind_speed_hub_ms"] = df["wind_speed_ms"].apply(
                lambda v: extrapolate_wind_speed(v, hub_height, alpha)
            )

            # Calculate power from hub-height wind speed
            df["power_kw"] = df["wind_speed_hub_ms"].apply(calculate_wind_power)
            df["power_mw"] = df["power_kw"] / 1000

            # Current conditions (first hour in forecast)
            current = df.iloc[0]

        # Location map with wind direction arrow
        st.subheader(f"Forecast for {loc_name}")
        
        # Create wind direction arrow overlay
        import numpy as np
        # Add a small arrow showing wind direction
        wind_direction_rad = np.radians(current['wind_direction'])
        arrow_length = 0.1  # degrees
        arrow_lat = lat + arrow_length * np.cos(wind_direction_rad)
        arrow_lon = lon + arrow_length * np.sin(wind_direction_rad)
        
        map_data = {
            "lat": [lat, arrow_lat],
            "lon": [lon, arrow_lon]
        }
        
        # Wind turbine icon
        st.markdown(
            f'<div class="wind-turbine">🌀</div>',
            unsafe_allow_html=True
        )
        
        st.map(map_data, zoom=6)
        


        # Metrics with turbine status
        col1, col2, col3, col4 = st.columns([2,2,2,3])
        
        # Turbine status indicator
        if current['power_kw'] > 0:
            turbine_status = "🟢 Operational"
            status_color = "#2ca02c"
        elif current['wind_speed_hub_ms'] < 3.0:
            turbine_status = "🟡 Below Cut-in"
            status_color = "#ff7f0e"
        else:
            turbine_status = "🔴 Shutdown"
            status_color = "#d62728"
        
        col1.metric(
            "Wind Speed @ 10m",
            f"{current['wind_speed_ms']:.1f} m/s",
            f"{current['wind_speed_kmh']:.1f} km/h"
        )
        col2.metric(
            f"Wind Speed @ {hub_height}m",
            f"{current['wind_speed_hub_ms']:.1f} m/s"
        )
        col3.metric("Wind Direction", f"{current['wind_direction']:.0f}°")
        col4.markdown(
            f"<div style='text-align: center;'><b>Est. Power Output</b><br><span style='font-size: 32px; color: {status_color};'>{current['power_kw']:.0f} kW</span><br><span style='font-size: 14px;'>{turbine_status}</span></div>",
            unsafe_allow_html=True
        )

        st.markdown("---")

        # Charts
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown(f"### 🌬️ 7-Day Wind Speed Forecast (@ {hub_height}m)")
            
            # Enhanced wind speed chart
            fig_wind = go.Figure()
            
            # Main line
            fig_wind.add_trace(go.Scatter(
                x=df['time'],
                y=df['wind_speed_hub_ms'],
                mode='lines+markers',
                name='Wind Speed',
                line=dict(color='#2ca02c', width=3),
                marker=dict(size=4, color='#2ca02c'),
                hovertemplate='<b>%{y:.1f} m/s</b><br>%{x|%H:%M %d %b}<extra></extra>'
            ))
            
            # Fill area
            fig_wind.add_trace(go.Scatter(
                x=df['time'].tolist() + df['time'][::-1].tolist(),
                y=df['wind_speed_hub_ms'].tolist() + [0] * len(df),
                fill='toself',
                fillcolor='rgba(44, 160, 44, 0.2)',
                line=dict(color='rgba(255,255,255,0)'),
                showlegend=False
            ))
            
            # Add cut-in line
            fig_wind.add_hline(y=3.0, line_dash="dash", line_color="#ff7f0e", annotation_text="Cut-in Speed (3 m/s)", annotation_position="right")
            
            fig_wind.update_layout(
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#a9b7c6'),
                margin=dict(l=20, r=20, t=40, b=20),
                height=400
            )
            
            st.plotly_chart(fig_wind, use_container_width=True)

        with col_chart2:
            st.markdown(f"### ⚡ Estimated Energy Generation (@ {hub_height}m)")
            
            # Enhanced power generation chart
            fig_power = go.Figure()
            
            # Main area
            fig_power.add_trace(go.Scatter(
                x=df['time'],
                y=df['power_mw'],
                mode='lines+markers',
                name='Power Output',
                line=dict(color='#2ca02c', width=3),
                marker=dict(size=4, color='#2ca02c'),
                fill='tozeroy',
                fillcolor='rgba(44, 160, 44, 0.2)',
                hovertemplate='<b>%{y:.2f} MW</b><br>%{x|%H:%M %d %b}<extra></extra>'
            ))
            
            # Add rated power line
            fig_power.add_hline(y=2.0, line_dash="dash", line_color="#1f77b4", annotation_text="Rated Power (2 MW)", annotation_position="right")
            
            fig_power.update_layout(
                template="plotly_dark",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#a9b7c6'),
                margin=dict(l=20, r=20, t=40, b=20),
                height=400
            )
            
            st.plotly_chart(fig_power, use_container_width=True)

        # Summary statistics
        st.markdown("---")
        st.markdown("### 📊 Summary Statistics (Next 7 Days)")

        total_mwh = df["power_mw"].sum()
        peak_idx = df["power_mw"].idxmax()
        peak_time = df.loc[peak_idx, "time"]
        peak_power = df.loc[peak_idx, "power_mw"]
        avg_wind = df["wind_speed_hub_ms"].mean()
        operating_hours = int((df["power_kw"] > 0).sum())
        capacity_factor = (total_mwh / (2.0 * 24 * 7)) * 100  # 2MW turbine × 168 hours
        
        # Create a grid for summary metrics
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total Est. Energy", f"{total_mwh:.1f} MWh", "over 7 days")
        s2.metric("Peak Generation", f"{peak_power:.2f} MW", f"at {peak_time.strftime('%H:%M')}")
        s3.metric("Avg Wind Speed", f"{avg_wind:.1f} m/s", f"@ {hub_height}m")
        s4.metric("Capacity Factor", f"{capacity_factor:.1f}%", "of rated power")

        # Raw data expander
        with st.expander("View Raw Hourly Data"):
            display_df = df[[
                "time",
                "wind_speed_ms",
                "wind_speed_hub_ms",
                "wind_direction",
                "temperature_c",
                "power_kw"
            ]].copy()
            display_df.columns = [
                "Time",
                "Wind Speed 10m (m/s)",
                f"Wind Speed {hub_height}m (m/s)",
                "Wind Direction (°)",
                "Temperature (°C)",
                "Power (kW)"
            ]
            st.dataframe(display_df, use_container_width=True)
        

        


    except ValueError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"An error occurred: {e}")
