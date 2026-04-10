import uuid
import streamlit as st
import requests
import os
import sys
from supabase import create_client, Client
from streamlit_javascript import st_javascript
from datetime import datetime, timezone
from google.colab import userdata


def get_supabase_client():
    try:
        url = userdata.get('SUPABASE_URL')
        key = userdata.get('SUPABASE_KEY')
        
        if not url or not key:
            print("🚨 데이터베이스 URL 또는 Key가 비어있습니다!")
            return None
            
        return create_client(url, key)
    except Exception as e:
        print(f"🚨 연결 실패: {e}")
        return None


def get_real_client_ip():
    if "cached_ip" in st.session_state:
        return st.session_state.cached_ip

    try:
        js_code = "await fetch('https://api.ipify.org?format=json').then(r => r.json()).then(d => d.ip)"
        client_ip = st_javascript(js_code, key="ip_tracker_js")
        
        if client_ip == 0 or not client_ip:
            return None 
        
        st.session_state.cached_ip = client_ip
        return client_ip
    except:
        return "Unknown"


def get_or_create_session_id():
    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = uuid.uuid4().hex
    return st.session_state['session_id']


def log_app_usage(app_name="unknown_app", action="page_view", details=None):
    real_ip = get_real_client_ip()
    
    if not real_ip:
        return False

    try:
        client = get_supabase_client()
        if not client:
            return False

        loc_data = {}
        if real_ip not in ["Unknown"]:
            try:
                res = requests.get(f"http://ip-api.com/json/{real_ip}?fields=status,country,regionName,city,lat,lon", timeout=1)
                loc_data = res.json() if res.status_code == 200 else {}
            except: pass

        current_session = get_or_create_session_id()
        user_agent = st.context.headers.get("User-Agent", "Unknown") if hasattr(st, "context") else "Unknown"
        utc_time = datetime.now(timezone.utc).isoformat()

        log_data = {
            "session_id": current_session,
            "app_name": app_name,
            "action": action,
            "timestamp": utc_time,
            "country": loc_data.get('country', "Unknown"),
            "region": loc_data.get('regionName', "Unknown"),
            "city": loc_data.get('city', "Unknown"),
            "lat": loc_data.get('lat', 0.0),
            "lon": loc_data.get('lon', 0.0),
            "ip_address": real_ip,
            "details": details if details else {},
            "user_agent": user_agent
        }

        # 스마트 봇 차단 로직
        if user_agent and any(keyword in user_agent.lower() for keyword in ["bot", "uptime", "cron"]):
            return False
            
        if user_agent == "Unknown" and real_ip == "Unknown":
            return False
        
        # 🎯 [수정 완료] returning='minimal' 제거
        client.table('usage_logs').insert(log_data).execute()
        return True
    except Exception as e:
        print(f"🚨 트래커 에러: {e}")
        return False
