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
        "ages": ["3", "4", "5", "6", "7"], # 19~44세 타겟팅
        "gender": gender
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        res_json = response.json()
        data_list = []
        for group in res_json['results']:
            if 'data' in group and group['data']:
                for entry in group['data']:
                    data_list.append({
                        'Date': entry['period'],
                        'Keyword_Group': group['title'],
                        'Ratio': entry['ratio'],
                        'Gender': 'Male' if gender == 'm' else 'Female'
                    })
        return pd.DataFrame(data_list)
    return pd.DataFrame()

# 4. 사이드바: 양식 다운로드 및 파일 업로드
with st.sidebar:
    st.header("📁 데이터 관리")
    
    # [다시 추가된 기능] 엑셀 양식 다운로드 버튼
    st.subheader("1. 양식 받기")
    try:
        with open("keywords_input.xlsx", "rb") as f:
            st.download_button(
                label="📥 분석 양식(Excel) 다운로드",
                data=f,
                file_name="keywords_input.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        st.caption("팀원들은 이 양식을 받아 작성 후 아래에 업로드하세요.")
    except FileNotFoundError:
        st.warning("저장소에 keywords_input.xlsx 파일이 없습니다.")

    st.divider()
    
    # 파일 업로드
    st.subheader("2. 데이터 분석")
    uploaded_file = st.file_uploader("수정하신 엑셀 파일을 업로드하세요", type=["xlsx"])

# 5. 메인 로직
if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    
    if 'GroupName' in df_input.columns:
        all_groups = []
        for _, row in df_input.iterrows():
            g_name = str(row['GroupName']).strip()
            # 빈 행이나 '*'로 시작하는 메모 행 건너뛰기
            if not g_name or g_name.startswith('*') or g_name == "nan":
                continue
            
            kw_val = str(row['Keywords']).strip() if 'Keywords' in df_input.columns and pd.notnull(row['Keywords']) else ""
            keywords = [k.strip() for k in kw_val.split(',')] if kw_val and kw_val != "nan" else [g_name]
            all_groups.append({"groupName": g_name, "keywords": keywords})

        if not all_groups:
            st.error("분석할 유효한 키워드가 없습니다.")
        else:
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
                    
                    if batch_res.empty: continue

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
                    st.success("분석이 완료되었습니다!")

        # 분석 결과 표시 및 필터/다운로드 섹션
        if 'analysis_result' in st.session_state:
            res_df = st.session_state['analysis_result']
            anchor_name = st.session_state['anchor_name']
            
            st.divider()
            st.subheader("🎯 결과 필터링 및 다운로드")
            
            available_keywords = res_df['Keyword_Group'].unique().tolist()
            selected_items = st.multiselect("화면에서 보고 싶은 키워드만 선택하세요:", options=available_keywords, default=available_keywords)
            
            if selected_items:
                filtered_df = res_df[res_df['Keyword_Group'].isin(selected_items)]
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"📊 검색 트렌드 (기준: {anchor_name})")
                    chart_data = filtered_df.pivot_table(index='Date', columns='Keyword_Group', values='Ratio', aggfunc='mean')
                    st.line_chart(chart_data)
                
                with col2:
                    st.subheader("👥 성별 비중 (평균)")
                    gender_stats = filtered_df.groupby('Gender')['Ratio'].mean()
                    st.write(gender_stats)

                # 분석 결과 다운로드 버튼
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    filtered_df.to_excel(writer, index=False, sheet_name='Analysis_Result')
                
                st.download_button(
                    label="📥 선택된 분석 결과 엑셀로 저장",
                    data=output.getvalue(),
                    file_name=f"freedom_trend_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.dataframe(filtered_df, use_container_width=True)
    else:
        st.error("엑셀 파일에 'GroupName' 컬럼이 필요합니다.")
else:
    st.info("왼쪽 사이드바에서 양식을 다운로드하여 작성한 뒤 업로드해 주세요.")
