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
    st.error("오류: Streamlit Secrets 설정을 확인해주세요.")
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
        "ages": ["3", "4", "5", "6", "7"], # 19~44세 타겟
        "gender": gender
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(body), timeout=15)
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
    except Exception as e:
        st.sidebar.error(f"Error: {e}")
    return pd.DataFrame()

# 4. 사이드바 구성
with st.sidebar:
    st.header("📁 데이터 관리")
    try:
        with open("keywords_input.xlsx", "rb") as f:
            st.download_button("📥 분석 양식(Excel) 받기", f, file_name="keywords_input.xlsx")
    except:
        pass
    st.divider()
    uploaded_file = st.file_uploader("수정하신 엑셀 파일을 업로드하세요", type=["xlsx"])

# 5. 메인 분석 로직
if uploaded_file:
    df_input = pd.read_excel(uploaded_file)
    name_col = next((c for c in df_input.columns if c.lower() in ['groupname', '그룹명', '항목']), None)
    kw_col = next((c for c in df_input.columns if c.lower() in ['keywords', '키워드', '연관검색어']), None)

    if name_col:
        all_groups = []
        for _, row in df_input.iterrows():
            g_name = str(row[name_col]).strip()
            if not g_name or g_name.startswith('*') or g_name == "nan": continue
            
            # [핵심 로직 변경] GroupName을 기본 검색어로 포함
            keyword_list = [g_name]
            
            # Keywords 컬럼에 추가 검색어가 있다면 리스트에 더해줌
            raw_kws = str(row[kw_col]).strip() if kw_col and pd.notnull(row[kw_col]) else ""
            if raw_kws and raw_kws.lower() != "nan":
                extra_kws = [k.strip() for k in raw_kws.split(',') if k.strip()]
                keyword_list.extend(extra_kws)
            
            # 중복 단어 제거 (순서 유지)
            final_keywords = list(dict.fromkeys(keyword_list))
            all_groups.append({"groupName": g_name, "keywords": final_keywords})

        if all_groups:
            anchor_group = all_groups[0]
            anchor_name = anchor_group['groupName']
            other_groups = all_groups[1:]

            if st.sidebar.button("🚀 분석 시작 (Run Analysis)"):
                final_df = pd.DataFrame()
                reference_data = pd.DataFrame()
                status = st.empty()
                progress = st.progress(0)
                
                batch_size = 4
                for i in range(0, len(other_groups) if other_groups else 1, batch_size):
                    chunk = other_groups[i:i+batch_size]
                    current_batch = [anchor_group] + chunk
                    status.text(f"⏳ 분석 중: {anchor_name} + {', '.join([c['groupName'] for c in chunk])}")
                    
                    batch_res = pd.concat([get_api_data(current_batch, 'm'), get_api_data(current_batch, 'f')], ignore_index=True)
                    if batch_res.empty: continue

                    if i == 0 or reference_data.empty:
                        reference_data = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                        final_df = batch_res
                    else:
                        curr_anchor = batch_res[batch_res['Keyword_Group'] == anchor_name].copy()
                        if not curr_anchor.empty and not reference_data.empty:
                            scale_merge = pd.merge(curr_anchor, reference_data, on=['Date', 'Gender'], suffixes=('_curr', '_ref'))
                            if not scale_merge.empty:
                                scale_merge['Factor'] = scale_merge['Ratio_ref'] / scale_merge['Ratio_curr']
                                batch_res = pd.merge(batch_res, scale_merge[['Date', 'Gender', 'Factor']], on=['Date', 'Gender'])
                                batch_res['Ratio'] = batch_res['Ratio'] * batch_res['Factor']
                                final_df = pd.concat([final_df, batch_res[batch_res['Keyword_Group'] != anchor_name]], ignore_index=True)
                    progress.progress(min((i + batch_size) / (len(other_groups) + 1) if other_groups else 1.0, 1.0))

                status.empty()
                if not final_df.empty:
                    st.session_state['analysis_result'] = final_df
                    st.session_state['anchor_name'] = anchor_name
                    st.success("✅ 분석 완료!")

        # 6. 결과 출력
        if st.session_state.get('analysis_result') is not None:
            res_df = st.session_state['analysis_result']
            anchor_name = st.session_state['anchor_name']
            st.divider()
            available = res_df['Keyword_Group'].unique().tolist()
            selected = st.multiselect("📈 표시할 항목 선택:", options=available, default=available)
            if selected:
                f_df = res_df[res_df['Keyword_Group'].isin(selected)]
                chart_data = f_df.pivot_table(index='Date', columns='Keyword_Group', values='Ratio', aggfunc='mean')
                st.line_chart(chart_data)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    f_df.to_excel(writer, index=False, sheet_name='Result')
                st.download_button("📥 결과 엑셀 저장", output.getvalue(), file_name=f"freedom_trend_{datetime.now().strftime('%Y%m%d')}.xlsx")
                st.dataframe(f_df, use_container_width=True)
