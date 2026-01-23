import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import io

# 1. 페이지 설정
st.set_page_config(page_title="프리덤 트렌드 분석 대시보드", layout="wide")
st.title("🏃‍♂️ Freedom Trend Analysis Dashboard")

# 2. 보안 설정 (Secrets)
try:
    CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except KeyError:
    st.error("오류: Streamlit Secrets에 API 키를 설정해주세요.")
    st.stop()

# 3. Naver API 호출 함수 (에러 메시지 출력 기능 추가)
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
        "ages": ["3", "4", "5", "6", "7"],
        "gender": gender
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        res_json = response.json()
        data_list = []
        for group in res_json['results']:
            # 데이터가 있는 경우만 처리
            if 'data' in group and group['data']:
                for entry in group['data']:
                    data_list.append({
                        'Date': entry['period'],
                        'Keyword_Group': group['title'],
                        'Ratio': entry['ratio'],
                        'Gender': 'Male' if gender == 'm' else 'Female'
                    })
        return pd.DataFrame(data_list)
    else:
        # API 실패 시 사용자에게 이유를 알려줍니다.
        st.sidebar.error(f"API 호출 실패 ({response.status_code}): {response.text}")
        return pd.DataFrame()

# 4. 사이드바
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
            # [추가] 빈 행이거나 '*'로 시작하는 메모 행은 건너뜁니다.
            if not g_name or g_name.startswith('*') or g_name == "nan":
                continue
                
            kw_val = str(row['Keywords']).strip() if 'Keywords' in df_input.columns and pd.notnull(row['Keywords']) else ""
            keywords = [k.strip() for k in kw_val.split(',')] if kw_val and kw_val != "nan" else [g_name]
            all_groups.append({"groupName": g_name, "keywords": keywords})

        if not all_groups:
            st.error("분석할 유효한 키워드가 없습니다.")
            st.stop()

        anchor_group = all_groups[0]
        anchor_name = anchor_group['groupName']
        other_groups = all_groups[1:]

        if st.sidebar.button("🚀 분석 시작 (Run Analysis)"):
            final_df = pd.DataFrame()
            reference_data = pd.DataFrame()
            progress = st.progress(0)
            
            batch_size = 4
            for i in range(0, len(other_groups) if other_groups else 1, batch_size):
                chunk = other_groups[i:i+batch_size]
                current_batch = [anchor_group] + chunk
                batch_res = pd.concat([get_api_data(current_batch, 'm'), get_api_data(current_batch, 'f')], ignore_index=True)
                
                # [핵심 수정] 가져온 데이터가 비어있는지 확인하는 안전장치
                if batch_res.empty:
                    st.warning(f"{current_batch} 그룹에 대한 데이터가 없어 건너뜁니다.")
                    continue

                if i == 0 or reference_data.empty:
                    reference_data = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                    final_df = batch_res
                else:
                    curr_anchor = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                    if not curr_anchor.empty:
                        scale_merge = pd.merge(curr_anchor, reference_data, on=['Date', 'Gender'], suffixes=('_curr', '_ref'))
                        if not scale_merge.empty:
                            scale_merge['Factor'] = scale_merge['Ratio_ref'] / scale_merge['Ratio_curr']
                            batch_res = pd.merge(batch_res, scale_merge[['Date', 'Gender', 'Factor']], on=['Date', 'Gender'])
                            batch_res['Ratio'] = batch_res['Ratio'] * batch_res['Factor']
                            final_df = pd.concat([final_df, batch_res[batch_res['Keyword_Group'] != anchor_name]], ignore_index=True)
                
                progress.progress(min((i + batch_size) / (len(other_groups) + 1) if other_groups else 1.0, 1.0))

            if not final_df.empty:
                st.session_state['analysis_result'] = final_df
                st.session_state['anchor_name'] = anchor_name
                st.success("분석 완료!")
            else:
                st.error("네이버에서 검색 데이터를 가져오지 못했습니다. 키워드나 API 상태를 확인해주세요.")

        # 분석 결과 표시 섹션 (기존과 동일)
        if 'analysis_result' in st.session_state:
            res_df = st.session_state['analysis_result']
            # ... (중략: 필터 및 그래프 출력 코드는 이전과 동일하게 유지)
