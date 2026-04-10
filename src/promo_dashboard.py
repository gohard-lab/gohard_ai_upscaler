import streamlit as st
import pandas as pd
from supabase import create_client
import os
import shutil
from pathlib import Path
from datetime import datetime

# [설정] 미디어 루트 경로
MEDIA_ROOT = Path(r"D:\My_Work\MEDIA_ROOT")
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


# 🏁 필수 데이터 트래커 연동
try:
    from tracker_web import log_app_usage
except ImportError:
    # 로컬 테스트 중 트래커가 없을 때를 대비한 더미 함수
    def log_app_usage(app_name, action, details=None):
        pass

# 페이지 기본 설정
st.set_page_config(page_title="🚀 홍보 관제 시스템", layout="wide")

# 앱 접속 로그 남기기
log_app_usage("promotion_dashboard", "app_opened")

@st.cache_resource
def get_supabase():
    # st.secrets를 사용하여 secrets.toml의 정보 불러오기
    url = st.secrets["url"]
    key = st.secrets["key"]
    return create_client(url, key)

supabase = get_supabase()

st.title("🚀 통합 홍보 관제 대시보드 v3.0")

# 탭 구조 설계: 1.대시보드(조회) / 2.등록 / 3.설정
tab_dash, tab_entry, tab_settings = st.tabs(["📊 대시보드", "📝 새 홍보글 등록", "⚙️ 플랫폼 관리"])


# 1. 경로 설정 (D드라이브)
MEDIA_ROOT = Path(r"D:\My_Work\MEDIA_ROOT")
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# 헬퍼 함수: 파일 저장
def save_uploaded_files(uploaded_files):
    saved_paths = []
    for uploaded_file in uploaded_files:
        # 파일명 중복 방지를 위해 타임스탬프 추가 (선택 사항)
        file_name = f"{datetime.now().strftime('%H%M%S')}_{uploaded_file.name}"
        target_path = MEDIA_ROOT / file_name
        
        with open(target_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(file_name) # DB에는 파일명만 저장
    return saved_paths

# [함수] 로컬 파일 삭제 전용
def delete_local_files(file_names):
    for name in file_names:
        file_path = MEDIA_ROOT / name
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as e:
                st.error(f"파일 삭제 실패 ({name}): {e}")
            


# ---------------------------------------------------------
# Tab 3: 플랫폼 관리 (마스터 데이터 + 인라인 편집)
# ---------------------------------------------------------
with tab_settings:
    st.header("플랫폼 마스터 코드 설정")
    
    with st.expander("➕ 새 플랫폼 추가하기", expanded=False):
        # (기존의 새 플랫폼 추가 폼 코드는 동일하게 유지하세요)
        with st.form("new_platform_form"):
            c1, c2, c3 = st.columns([1, 2, 2])
            new_code = c1.text_input("코드 (예: RDIT)")
            new_name = c2.text_input("명칭 (예: Reddit)")
            new_url = c3.text_input("사이트 주소 (http://...)")
            
            if st.form_submit_button("저장하기"):
                if new_code and new_name:
                    try:
                        supabase.table("platform_codes").insert({
                            "code": new_code.upper(), "name": new_name, "site_url": new_url
                        }).execute()
                        log_app_usage("promotion_dashboard", "platform_added", {"code": new_code.upper()})
                        st.success(f"{new_name} 플랫폼이 등록되었습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
                else:
                    st.warning("코드와 명칭은 필수입니다.")

    platforms_data = supabase.table("platform_codes").select("*").order("code", desc=False).execute().data
    if platforms_data:
        st.divider()
        st.subheader("등록된 플랫폼 관리")
        st.caption("💡 **팁:** '명칭'과 '사이트 주소' 셀을 더블 클릭하여 수정하거나, '삭제'를 체크하고 아래 버튼을 누르세요.")
        
        p_df = pd.DataFrame(platforms_data)
        
        # 편집용 데이터프레임 구성
        edit_p_df = pd.DataFrame({
            "삭제": [False] * len(p_df),
            "code": p_df['code'],
            "name": p_df['name'],
            "site_url": p_df['site_url']
        })
        
        # 대화형 데이터 에디터
        # 편집용 데이터프레임 구성 (exclude, note 컬럼 추가)
        edit_p_df = pd.DataFrame({
            "삭제": [False] * len(p_df),
            "code": p_df['code'],
            "name": p_df['name'],
            "site_url": p_df['site_url'],
            "exclude": p_df.get('exclude', False), # DB에 값이 없으면 False
            "note": p_df.get('note', '')           # DB에 값이 없으면 빈 문자열
        })
        
        # 대화형 데이터 에디터 (key 추가 필수)
        edited_p_df = st.data_editor(
            edit_p_df,
            column_config={
                "삭제": st.column_config.CheckboxColumn("🗑️ 삭제", width="small"),
                "code": st.column_config.TextColumn("코드", disabled=True), 
                "name": st.column_config.TextColumn("📝 명칭 (수정 가능)"),
                "site_url": st.column_config.TextColumn("📝 사이트 주소 (수정 가능)"),
                "exclude": st.column_config.CheckboxColumn("🚨 제외 (체크)"),
                "note": st.column_config.TextColumn("📝 비고")
            },
            use_container_width=True,
            hide_index=True,
            key="plat_editor"
        )
        
        if st.button("💾 플랫폼 변경사항 및 삭제 적용", type="primary", key="btn_plat_save"):
            # 에디터 세션 상태를 가장 안전하게 불러오는 방식
            editor_state = st.session_state.get("plat_editor", {})
            edited_rows = editor_state.get("edited_rows", {})
            
            del_count = 0
            up_count = 0
            has_error = False
            
            # 변경점 감지 실패 시 경고창 (Streamlit 특성 안내)
            if not edited_rows:
                st.warning("💡 변경된 내용이 감지되지 않았습니다. 텍스트 수정 후 반드시 **'엔터(Enter)'**를 치거나 **표 바깥쪽 빈 공간을 클릭**하여 입력을 완료한 뒤에 저장 버튼을 눌러주세요.")
            else:
                for idx_str, changes in edited_rows.items():
                    idx = int(idx_str) # 인덱스를 명확한 정수형으로 변환 (인덱스 오류 방어)
                    code = edit_p_df.iloc[idx]["code"]
                    
                    # 1. 삭제 체크 처리
                    if changes.get("삭제") == True:
                        try:
                            supabase.table("platform_codes").delete().eq("code", code).execute()
                            del_count += 1
                        except Exception as e:
                            st.error(f"🚨 '{code}' 삭제 실패: 이 플랫폼에 등록된 홍보글 이력이 남아있습니다.")
                            has_error = True
                            
                    # 2. 내용 수정 처리
                    else:
                        update_data = {}
                        # 딕셔너리에 들어온 정확한 키값만 매칭해서 DB로 전송
                        if "name" in changes: 
                            update_data["name"] = changes["name"]
                        if "site_url" in changes: 
                            update_data["site_url"] = changes["site_url"]
                        if "exclude" in changes: 
                            update_data["exclude"] = bool(changes["exclude"])
                        if "note" in changes: 
                            update_data["note"] = changes["note"]
                            
                        if update_data:
                            try:
                                supabase.table("platform_codes").update(update_data).eq("code", code).execute()
                                up_count += 1
                            except Exception as e:
                                st.error(f"🚨 '{code}' 수정 실패: {e}")
                                has_error = True
                                
                if (del_count > 0 or up_count > 0) and not has_error:
                    st.success(f"적용 완료! (삭제: {del_count}건, 수정: {up_count}건)")
                    st.rerun()

# ---------------------------------------------------------
# Tab 2: 새 홍보글 등록
# ---------------------------------------------------------
with tab_entry:
    st.header("새로운 서킷에 홍보글 런칭")
    
    # 💡 리셋 카운터 엔진 초기화
    if "reset_cnt" not in st.session_state:
        st.session_state.reset_cnt = 0
        
    def reset_inputs():
        st.session_state.reset_cnt += 1

    if platforms_data:
        # 1. 플랫폼 데이터 준비
        all_history = supabase.table("promotion_history").select("platform_code").execute().data
        counts = pd.DataFrame(all_history)['platform_code'].value_counts().to_dict() if all_history else {}
        platform_options = {p['code']: f"{p['name']} ({counts.get(p['code'], 0)}건)" for p in platforms_data}
        
        # 2. 플랫폼 선택 및 입력 UI 레이아웃
        col1, col2 = st.columns([1, 2])
        
        with col1:
            selected_code = st.selectbox(
                "🎯 플랫폼 선택", 
                options=list(platform_options.keys()), 
                format_func=lambda x: platform_options[x],
                on_change=reset_inputs 
            )
            
        with col2:
            # 💡 key에 리셋 카운터를 붙여서 저장 후 깨끗하게 비워지게 설정
            title = st.text_input("📝 홍보글 제목", key=f"promo_title_{st.session_state.reset_cnt}")
            url = st.text_input("🔗 게시글 URL (직접 링크)", key=f"promo_url_{st.session_state.reset_cnt}")

        st.divider()

        # 3. 미디어 에셋 등록 영역
        st.subheader("🖼️ 미디어 에셋 등록")
        uploaded_files = st.file_uploader(
            "이미지나 동영상을 선택하세요 (D:\\My_Work\\MEDIA_ROOT 에 저장됩니다)", 
            accept_multiple_files=True,
            key=f"file_uploader_{st.session_state.reset_cnt}"
        )

        st.divider()

        # 4. 통합 등록 버튼
        if st.button("🚀 홍보 기록 및 에셋 저장", type="primary", use_container_width=True):
            if title and url:
                try:
                    # A. 파일 저장 처리
                    asset_list = []
                    if uploaded_files:
                        asset_list = save_uploaded_files(uploaded_files)
                    
                    # B. Supabase 데이터 결합 (텍스트 + 미디어 경로)
                    new_promo_data = {
                        "platform_code": selected_code,
                        "title": title,
                        "url": url,
                        "media_assets": asset_list,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    # C. DB Insert 실행
                    supabase.table("promotion_history").insert(new_promo_data).execute()
                    
                    # D. 트래커 연동 [cite: 2026-03-20]
                    log_app_usage("promotion_dashboard", "post_and_media_registered", 
                                   details={"platform": selected_code, "assets_count": len(asset_list)})
                    
                    st.success(f"✅ '{title}' 기록 성공! 에셋 {len(asset_list)}개가 안전하게 저장되었습니다.")
                    
                    # E. UI 리셋 및 화면 갱신
                    st.session_state.reset_cnt += 1 
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"🚨 등록 중 오류 발생: {e}")
            else:
                st.warning("⚠️ 제목과 URL은 필수 입력 항목입니다.")
                
    else:
        st.info("먼저 '⚙️ 플랫폼 관리' 탭에서 플랫폼을 하나 이상 등록해 주세요.")


# ---------------------------------------------------------
# Tab 1: 대시보드 (핵심 통계 및 리스트 + 필터링 + 인라인 편집)
# ---------------------------------------------------------
with tab_dash:
    # 0. 선택 상태 관리를 위한 세션 상태 초기화
    if "selected_row_id" not in st.session_state:
        st.session_state.selected_row_id = None

    # 1. 데이터 불러오기
    history_data = supabase.table("promotion_history").select("*, platform_codes(name, exclude, note)").order("platform_code", desc=False).order("created_at", desc=True).execute().data
    
    if history_data:
        df = pd.DataFrame(history_data)
        df['platform_name'] = df['platform_codes'].apply(lambda x: x['name'] if pd.notnull(x) else 'Unknown')
        df['exclude'] = df['platform_codes'].apply(lambda x: x.get('exclude', False) if pd.notnull(x) else False)
        df['note'] = df['platform_codes'].apply(lambda x: x.get('note', '') if pd.notnull(x) else '')
        
        # 상단 요약 통계
        col1, col2, col3 = st.columns(3)
        col1.metric("총 홍보글 수", f"{len(df)} 건")
        top_platform = df['platform_name'].value_counts().idxmax()
        col2.metric("가장 많이 올린 곳", top_platform)
        col3.metric("최근 활동일", pd.to_datetime(df['created_at'].max()).strftime('%Y-%m-%d'))
        
        st.divider()
        
        # 플랫폼 필터링
        platform_list = ["전체 보기"] + sorted(df['platform_name'].unique().tolist())
        selected_filter = st.selectbox("🔍 플랫폼 필터링", options=platform_list)
        
        display_df = df[df['platform_name'] == selected_filter].reset_index(drop=True) if selected_filter != "전체 보기" else df.reset_index(drop=True)

        # 2. 메인 데이터 에디터 구성
        # 🎯 선택 컬럼의 초기값을 세션 상태의 selected_row_id와 비교하여 설정
        final_df = pd.DataFrame({
            "선택": display_df['id'] == st.session_state.selected_row_id, 
            "삭제": [False] * len(display_df),
            "id": display_df['id'],
            "플랫폼": display_df['platform_name'],
            "제목": display_df['title'],
            "URL": display_df['url'],
            "작성일시": pd.to_datetime(display_df['created_at']).dt.strftime('%Y-%m-%d %H:%M'),
            "제외": display_df['exclude'],
            "비고": display_df['note']
        })
        
        def highlight_excluded_rows(row):
            return ['background-color: #ffe6e6' if row['제외'] else ''] * len(row)

        st.caption("💡 **'선택'**은 한 번에 하나만 가능합니다 (라디오 버튼 방식).")
        
        edited_df = st.data_editor(
            final_df.style.apply(highlight_excluded_rows, axis=1),
            column_config={
                "선택": st.column_config.CheckboxColumn("🔘 선택", width="small"),
                "삭제": st.column_config.CheckboxColumn("🗑️ 삭제", width="small"),
                "id": None, 
                "제목": st.column_config.TextColumn("📝 제목 (수정 가능)", width="large"),
                "URL": st.column_config.LinkColumn("바로가기", display_text="🔗 열기"),
                "제외": st.column_config.CheckboxColumn("🚨 제외 상태"),
                "비고": st.column_config.TextColumn("📝 비고")
            },
            disabled=["플랫폼", "URL", "작성일시", "제외", "비고"], 
            use_container_width=True, 
            hide_index=True,
            key=f"dash_editor_{selected_filter}"
        )

        # 🎯 [핵심] 라디오 버튼 로직: 새로 체크된 행 찾기
        newly_checked_ids = edited_df[edited_df["선택"] == True]["id"].tolist()
        
        # 로직 A: 사용자가 새로운 항목을 체크한 경우
        for cid in newly_checked_ids:
            if cid != st.session_state.selected_row_id:
                st.session_state.selected_row_id = cid
                st.rerun() # 즉시 화면 갱신하여 다른 체크 해제

        # 로직 B: 사용자가 기존에 선택된 항목을 해제한 경우
        if not newly_checked_ids and st.session_state.selected_row_id is not None:
            st.session_state.selected_row_id = None
            st.rerun()

        # 3. 🖼️ 미디어 에셋 매니저 출력 (현재 선택된 ID 기반)
        st.divider()

        if st.session_state.selected_row_id is not None:
            # display_df에서 현재 선택된 ID에 해당하는 데이터 추출
            selected_row_data = display_df[display_df['id'] == st.session_state.selected_row_id].iloc[0]
            row_id = selected_row_data['id']
            current_assets = selected_row_data.get("media_assets", []) or []

            st.subheader(f"📂 미디어 관리: {selected_row_data['title']}")
            
            with st.container(border=True):
                # 1. 컬럼 간격을 강제로 줄이는 CSS (코드 상단에 한 번만 넣으세요)
                st.markdown("""
                    <style>
                    /* 컬럼 사이의 간격(Gap)을 0으로 만들고 왼쪽으로 정렬 */
                    [data-testid="column"] {
                        width: fit-content !important;
                        flex: unset !important;
                        min-width: unset !important;
                    }
                    /* 파일명 컬럼은 공간을 다 쓰고, 버튼 컬럼은 자기 크기만큼만 차지하게 설정 */
                    [data-testid="column"]:nth-child(1) {
                        flex: 1 1 auto !important;
                    }
                    [data-testid="column"]:nth-child(2) {
                        flex: 0 0 auto !important;
                        margin-left: -10px !important; /* 여기서 간격을 미세하게 조절하세요 */
                    }
                    </style>
                    """, unsafe_allow_html=True)

                if current_assets:
                    st.write(f"📌 **현재 등록된 파일 ({len(current_assets)}개)**")
                    st.caption("삭제할 파일을 왼쪽에서 체크한 후 하단의 삭제 버튼을 누르세요.")

                    # 삭제 대상으로 선택된 파일들을 담을 리스트
                    selected_for_deletion = []

                    # 파일 목록을 루프 돌며 행(Row) 생성
                    for i, asset in enumerate(current_assets):
                        # 1. 각 행을 테두리가 있는 컨테이너로 감싸서 범위를 확인합니다.
                        with st.container(border=True):
                            # 🎯 컬럼을 2개로 줄였습니다. [8.5 : 1.5] 비율
                            c1, c2 = st.columns([9, 1], gap="small", vertical_alignment="center")

                            with c1:
                                # 1. 체크박스의 'label'에 파일명을 바로 넣습니다. 
                                # 이렇게 하면 별도의 텍스트 컬럼이 필요 없어서 간격이 완벽하게 붙습니다.
                                if st.checkbox(asset, key=f"chk_{row_id}_{i}"):
                                    selected_for_deletion.append(asset)

                            with c2:
                                # 2. 보기 버튼만 오른쪽 끝에 배치
                                if st.button("👁️ 열기", key=f"v_{row_id}_{i}", use_container_width=True):
                                    full_path = MEDIA_ROOT / asset
                                    if full_path.exists():
                                        os.startfile(str(full_path))
                                    else:
                                        st.error("파일 없음")

                    # 체크된 파일이 하나라도 있을 때만 삭제 실행 버튼 표시
                    if selected_for_deletion:
                        st.markdown("---")
                        st.warning(f"⚠️ **선택된 {len(selected_for_deletion)}개의 파일을 삭제하시겠습니까?**")
                        
                        # 버튼을 누르면 로컬 파일과 DB 정보를 동시에 삭제
                        if st.button(f"🗑️ 선택한 {len(selected_for_deletion)}개 파일 삭제 실행", 
                                    key=f"del_exe_{row_id}", type="secondary", use_container_width=True):
                            # 1. 로컬 저장소(D드라이브)에서 실제 파일 삭제
                            delete_local_files(selected_for_deletion)
                            
                            # 2. DB 업데이트: 전체 에셋 목록에서 선택된 파일들만 제외
                            new_assets = [a for a in current_assets if a not in selected_for_deletion]
                            supabase.table("promotion_history").update({"media_assets": new_assets}).eq("id", row_id).execute()
                            
                            # 트래커 기록
                            log_app_usage("promotion_dashboard", "assets_bulk_deleted", details={"count": len(selected_for_deletion)})
                            
                            st.success("선택한 파일이 삭제되었습니다.")
                            st.rerun()
                else:
                    st.info("이 항목에는 첨부된 미디어 파일이 없습니다.")

                st.markdown("---")
                st.write("➕ **새 파일 추가**")
                new_uploads = st.file_uploader("파일 업로드", accept_multiple_files=True, key=f"add_{row_id}")
                
                if new_uploads:
                    if st.button("📤 업로드 및 저장", key=f"save_{row_id}", type="primary"):
                        added_names = save_uploaded_files(new_uploads)
                        updated_assets = current_assets + added_names
                        supabase.table("promotion_history").update({"media_assets": updated_assets}).eq("id", row_id).execute()
                        st.success(f"{len(added_names)}개 추가 완료!")
                        st.rerun()
        else:
            st.info("⬆️ 위 표에서 미디어를 관리할 행의 **'선택'** 칸을 체크해 주세요.")

        # 4. 저장 및 삭제 처리
        st.divider()
        col_btn, col_opt = st.columns([0.6, 0.4])
        with col_opt:
            confirm_local_del = st.checkbox("🗑️ 체크된 행 삭제 시 D드라이브 파일도 삭제", value=False)

        if col_btn.button("💾 체크된 항목 삭제 및 수정사항 저장", type="primary", use_container_width=True):
            del_count = 0
            up_count = 0
            
            to_delete = edited_df[edited_df["삭제"] == True]
            for _, del_row in to_delete.iterrows():
                d_id = int(del_row["id"])
                if confirm_local_del:
                    target_assets = display_df[display_df['id'] == d_id]['media_assets'].values
                    if target_assets and target_assets[0]:
                        delete_local_files(target_assets[0])
                supabase.table("promotion_history").delete().eq("id", d_id).execute()
                
                # 만약 현재 선택해서 관리 중인 행을 삭제했다면 세션 초기화
                if d_id == st.session_state.selected_row_id:
                    st.session_state.selected_row_id = None
                    
                del_count += 1
            
            remain_edited = edited_df[edited_df["삭제"] == False]
            remain_orig = final_df[final_df["삭제"] == False]
            for idx in remain_edited.index:
                if remain_orig.loc[idx, "제목"] != remain_edited.loc[idx, "제목"]:
                    new_title = remain_edited.loc[idx, "제목"]
                    row_id = int(remain_edited.loc[idx, "id"])
                    supabase.table("promotion_history").update({"title": new_title}).eq("id", row_id).execute()
                    up_count += 1
            
            if del_count > 0 or up_count > 0:
                st.success(f"적용 완료! (삭제: {del_count}건, 제목 수정: {up_count}건)")
                st.rerun()
    else:
        st.info("등록된 홍보 기록이 없습니다.")