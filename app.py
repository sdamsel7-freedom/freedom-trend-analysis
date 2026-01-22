import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import io

# 1. 페이지 설정
st.set_page_config(page_title="프리덤 트렌드 분석 대시보드", layout="wide")
st.title("🏃‍♂️ Freedom Trend Analysis Dashboard")
st.markdown("### 19~44세 남녀 트렌드 분석 및 스케일 보정 도구")

# 2. 보안 설정 (Secrets)
try:
    CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except KeyError:
    st.error("오류: Streamlit Secrets에 API 키를 설정해주세요.")
    st.stop()

# 3. Naver API 호출 함수
def get_api_data(keyword_groups, gender):
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    body = {
        "startDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
        "timeUnit": "month",
        "keywordGroups": keyword_groups,
        "device": "",
        "ages": ["3", "4", "5", "6", "7"], # 19~44세
        "gender": gender
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        res_json = response.json()
        data_list = []
        for group in res_json['results']:
            for entry in group['data']:
                data_list.append({
                    'Date': entry['period'],
                    'Keyword_Group': group['title'],
                    'Ratio': entry['ratio'],
                    'Gender': 'Male' if gender == 'm' else 'Female'
                })
        return pd.DataFrame(data_list)
    return pd.DataFrame()

# 4. 사이드바 설정
with st.sidebar:
    st.header("📁 데이터 관리")
    uploaded_file = st.file_uploader("분석할 엑셀 파일을 업로드하세요", type=["xlsx"])

# 5. 메인 로직
if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    
    if 'GroupName' in df_input.columns:
        all_groups = []
        for _, row in df_input.iterrows():
            g_name = str(row['GroupName']).strip()
            kw_val = str(row['Keywords']).strip() if 'Keywords' in df_input.columns and pd.notnull(row['Keywords']) else ""
            keywords = [k.strip() for k in kw_val.split(',')] if kw_val and kw_val != "nan" else [g_name]
            all_groups.append({"groupName": g_name, "keywords": keywords})

        anchor_group = all_groups[0]
        anchor_name = anchor_group['groupName']
        other_groups = all_groups[1:]

        if st.sidebar.button("🚀 분석 시작 (Run Analysis)"):
            final_df = pd.DataFrame()
            reference_data = pd.DataFrame()
            progress = st.progress(0)
            
            # API 배치 처리 및 스케일 보정 로직 (기존과 동일)
            batch_size = 4
            for i in range(0, len(other_groups) if other_groups else 1, batch_size):
                chunk = other_groups[i:i+batch_size]
                current_batch = [anchor_group] + chunk
                batch_res = pd.concat([get_api_data(current_batch, 'm'), get_api_data(current_batch, 'f')], ignore_index=True)
                
                if i == 0:
                    reference_data = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                    final_df = batch_res
                else:
                    curr_anchor = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                    scale_merge = pd.merge(curr_anchor, reference_data, on=['Date', 'Gender'], suffixes=('_curr', '_ref'))
                    scale_merge['Factor'] = scale_merge['Ratio_ref'] / scale_merge['Ratio_curr']
                    batch_res = pd.merge(batch_res, scale_merge[['Date', 'Gender', 'Factor']], on=['Date', 'Gender'])
                    batch_res['Ratio'] = batch_res['Ratio'] * batch_res['Factor']
                    final_df = pd.concat([final_df, batch_res[batch_res['Keyword_Group'] != anchor_name]], ignore_index=True)
                progress.progress(min((i + batch_size) / (len(other_groups) + 1) if other_groups else 1.0, 1.0))

            st.session_state['analysis_result'] = final_df
            st.success("분석이 완료되었습니다!")

        # [핵심 추가] 분석 결과가 있을 때 키워드 선택 필터 표시
        if 'analysis_result' in st.session_state:
            res_df = st.session_state['analysis_result']
            
            st.divider()
            st.subheader("🎯 키워드 필터링")
            
            # 모든 키워드 리스트 추출
            available_keywords = res_df['Keyword_Group'].unique().tolist()
            
            # 멀티 선택 박스 (기본값은 전체 선택)
            selected_items = st.multiselect(
                "그래프에서 확인하고 싶은 키워드들을 고르세요:",
                options=available_keywords,
                default=available_keywords
            )
            
            if selected_items:
                # 선택된 키워드만 필터링
                filtered_df = res_df[res_df['Keyword_Group'].isin(selected_items)]
                
                # 결과 출력
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"📊 선택한 키워드별 트렌드 (기준: {anchor_name})")
                    chart_data = filtered_df.pivot_table(index='Date', columns='Keyword_Group', values='Ratio', aggfunc='mean')
                    st.line_chart(chart_data)
                
                with col2:
                    st.subheader("👥 성별 비중 (선택 키워드)")
                    gender_stats = filtered_df.groupby('Gender')['Ratio'].mean()
                    st.write(gender_stats)

                st.subheader("📋 상세 데이터 (선택 키워드)")
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.warning("하나 이상의 키워드를 선택해 주세요.")
    else:
        st.error("엑셀 파일에 'GroupName' 컬럼이 필요합니다.")
else:
    st.info("파일을 업로드하고 '분석 시작'을 눌러주세요.")
