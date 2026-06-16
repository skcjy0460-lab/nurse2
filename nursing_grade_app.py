import streamlit as st
import pandas as pd
from datetime import date
import calendar
import json
import anthropic
import google.generativeai as genai

# ──────────────────────────────────────────────
# 🔑 [필독] AI API 설정 (여기에 키를 입력하세요)
# ──────────────────────────────────────────────
# 다른 사람들과 공유할 때 미리 입력해두면 편리합니다.
DEFAULT_GEMINI_API_KEY = ""  # <-- 여기에 제미나이 API 키를 입력하세요
DEFAULT_ANTHROPIC_API_KEY = "" # <-- 여기에 클로드 API 키를 입력하세요

# ──────────────────────────────────────────────
# 페이지 기본 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="일반병동 간호관리료 등급 산정",
    page_icon="🏥",
    layout="wide",
)

# ──────────────────────────────────────────────
# CSS 스타일
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* ── 화면 스타일 ── */
    .main-title {
        font-size: 24px; font-weight: 800; color: #1a3a6b;
        border-bottom: 3px solid #1a3a6b; padding-bottom: 10px; margin-bottom: 16px;
        display: flex; align-items: baseline; gap: 12px;
    }
    .creator-badge {
        font-size: 13px; color: #888; font-weight: 500;
    }
    .section-title {
        font-size: 15px; font-weight: 700; color: #1a3a6b;
        background: #eef3fb; border-left: 5px solid #1a3a6b;
        padding: 7px 12px; margin: 14px 0 8px 0; border-radius: 0 6px 6px 0;
    }
    .result-card {
        background: #f0f7ff; border: 1.5px solid #aac8f0;
        border-radius: 10px; padding: 14px 20px; margin: 8px 0;
    }
    .grade-box {
        display: inline-block; font-size: 34px; font-weight: 900;
        padding: 12px 32px; border-radius: 12px; color: white; margin: 4px 0;
    }
    .grade-A { background: #5c1e91; }
    .grade-1 { background: #0d47a1; }
    .grade-2 { background: #1976d2; }
    .grade-3 { background: #2e7d32; }
    .grade-4 { background: #f57f17; }
    .grade-5 { background: #e65100; }
    .grade-6 { background: #b71c1c; }
    .kpi-label { font-size: 12px; color: #555; margin-bottom: 2px; }
    .kpi-value { font-size: 20px; font-weight: 700; color: #1a3a6b; }
    .kpi-unit  { font-size: 11px; color: #777; }
    .yellow-note {
        background: #fffde7; border: 1px solid #f9a825;
        border-radius: 6px; padding: 7px 12px; font-size: 12px; color: #5d4037;
        margin-bottom: 6px;
    }
    .footer {
        font-size: 13px; color: #555; text-align: center;
        margin-top: 30px; border-top: 1px solid #ddd; padding-top: 12px;
    }

    /* ── 인쇄 전용 스타일 ── */
    @media print {
        header, footer,
        [data-testid="stToolbar"],
        [data-testid="stSidebar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        .stButton > button,
        .stDownloadButton { display: none !important; }

        @page { size: A4 landscape; margin: 8mm; }
        html, body { margin: 0 !important; padding: 0 !important; }
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] { padding: 0 !important; }
        [data-testid="block-container"] {
            padding: 6px 10px !important;
            max-width: 100% !important;
            width: 100% !important;
        }
        * { font-size: 9px !important; line-height: 1.3 !important; }
        .main-title  { font-size: 13px !important; padding-bottom: 4px !important; margin-bottom: 6px !important; }
        .creator-badge { font-size: 10px !important; }
        .section-title { font-size: 10px !important; padding: 4px 8px !important; margin: 6px 0 4px 0 !important; }
        .kpi-value { font-size: 12px !important; }
        .kpi-label { font-size: 9px !important; }
        .result-card { padding: 6px 10px !important; margin: 4px 0 !important; }
        .grade-box { font-size: 18px !important; padding: 6px 16px !important; }
        .yellow-note { padding: 4px 8px !important; font-size: 9px !important; margin-bottom: 3px !important; }
        table, th, td { font-size: 9px !important; padding: 2px 4px !important; }
        [data-testid="column"] { break-inside: avoid; }
        .stMarkdown, .element-container { margin: 0 !important; padding: 0 !important; }
        hr { margin: 4px 0 !important; }
        .footer { margin-top: 10px !important; padding-top: 6px !important; font-size: 10px !important; }
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 유틸 함수
# ──────────────────────────────────────────────
QUARTER_RANGES = {
    "1분기 (12/15 ~ 3/14)": {"month_start": 12, "day_start": 15, "month_end": 3,  "day_end": 14},
    "2분기 (3/15 ~ 6/14)":  {"month_start": 3,  "day_start": 15, "month_end": 6,  "day_end": 14},
    "3분기 (6/15 ~ 9/14)":  {"month_start": 6,  "day_start": 15, "month_end": 9,  "day_end": 14},
    "4분기 (9/15 ~ 12/14)": {"month_start": 9,  "day_start": 15, "month_end": 12, "day_end": 14},
}

def get_quarter_dates(year, quarter_label):
    q = QUARTER_RANGES[quarter_label]
    if quarter_label.startswith("1"):
        start = date(year - 1, q["month_start"], q["day_start"])
        end   = date(year,     q["month_end"],   q["day_end"])
    else:
        start = date(year, q["month_start"], q["day_start"])
        end   = date(year, q["month_end"],   q["day_end"])
    return start, end, (end - start).days + 1

def calc_nurse_days(hire_date, status, q_start, q_end):
    if status == "퇴사":
        return 0
    total = (q_end - q_start).days + 1
    if hire_date <= q_start:
        return total
    elif hire_date <= q_end:
        return (q_end - hire_date).days + 1
    return 0

def calc_parttime_weight(weekly_hours):
    if weekly_hours >= 40: return 1.0
    elif weekly_hours >= 36: return 0.8
    elif weekly_hours >= 32: return 0.6
    else: return 0.4

def determine_grade(ratio):
    pct = ratio * 100
    if   pct < 2.0: return "A등급"
    elif pct < 2.5: return "1등급"
    elif pct < 3.0: return "2등급"
    elif pct < 3.5: return "3등급"
    elif pct < 4.0: return "4등급"
    elif pct < 6.0: return "5등급"
    else:           return "6등급"

def grade_css(grade):
    return "grade-" + grade.replace("등급", "")

def month_label(base, offset):
    m = ((base.month - 1 + offset) % 12) + 1
    y = base.year + ((base.month - 1 + offset) // 12)
    return f"{y}년 {m}월"

# ──────────────────────────────────────────────
# 세션 상태 초기화
# ──────────────────────────────────────────────
if "daytime_nurses" not in st.session_state:
    st.session_state.daytime_nurses = [{"hire_date": None, "status": "근무"}]

if "night_nurses" not in st.session_state:
    st.session_state.night_nurses = [{"hire_date": None, "status": "근무", "weekly_hours": 40}]

# ──────────────────────────────────────────────
# 헤더
# ──────────────────────────────────────────────
st.markdown(
    '<div class="main-title">'
    '🏥 일반병동 간호관리료 등급 산정 시스템'
    '<span class="creator-badge">ㅣ 제작: 주식회사 메디엄 조정윤</span>'
    '</div>',
    unsafe_allow_html=True
)

# ──────────────────────────────────────────────
# ① 기본 정보
# ──────────────────────────────────────────────
st.markdown('<div class="section-title">① 기본 정보</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    year = st.number_input("연도", min_value=2020, max_value=2040, value=2026, step=1)
with col2:
    quarter_label = st.selectbox("분기", list(QUARTER_RANGES.keys()), index=1)
with col3:
    beds = st.number_input("운영 병상 수", min_value=0, max_value=500, value=0, step=1, placeholder="병상 수 입력")

q_start, q_end, q_days = get_quarter_dates(year, quarter_label)
st.info(f"📅 분기 기간: **{q_start}** ~ **{q_end}**  |  총 **{q_days}일**")

# ──────────────────────────────────────────────
# ② 월별 재원환자수
# ──────────────────────────────────────────────
st.markdown('<div class="section-title">② 월별 재원환자수</div>', unsafe_allow_html=True)
st.markdown('<div class="yellow-note">🟡 <b>노란색 항목</b>: 일평균 재원환자 수는 자동 계산됩니다.</div>', unsafe_allow_html=True)

month_cols = st.columns(4)
total_patients = 0
pat_values = []
for i in range(3):
    lbl = month_label(q_start, i)
    with month_cols[i]:
        st.markdown(f"**{lbl}**")
        pat = st.number_input("재원환자수", min_value=0, max_value=5000, value=0, step=1, key=f"pat_{i}", label_visibility="collapsed", placeholder="환자수 입력")
        st.caption("월 재원환자수")
        total_patients += pat
        pat_values.append(pat)

with month_cols[3]:
    st.markdown("**일평균 재원환자 수** 🟡")
    avg_patients = total_patients / q_days if q_days > 0 else 0
    st.markdown(f'<div class="kpi-value">{avg_patients:.2f}</div><div class="kpi-unit">명/일 (자동계산)</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ③ 주간(일반) 간호사 인력
# ──────────────────────────────────────────────
st.markdown('<div class="section-title">③ 주간(일반) 간호사 인력</div>', unsafe_allow_html=True)
c1, c2, _ = st.columns([1, 1, 6])
with c1:
    if st.button("➕ 주간 간호사 추가"):
        st.session_state.daytime_nurses.append({"hire_date": None, "status": "근무"})
with c2:
    if st.button("➖ 마지막 행 삭제") and len(st.session_state.daytime_nurses) > 1:
        st.session_state.daytime_nurses.pop()

hc = st.columns([0.4, 2, 2, 2, 2])
hc[0].markdown("**#**"); hc[1].markdown("**입사일**"); hc[2].markdown("**상태**")
hc[3].markdown("**산정일수** 🟡"); hc[4].markdown("**환산인원** 🟡")

daytime_total = 0.0
for i, nurse in enumerate(st.session_state.daytime_nurses):
    cols = st.columns([0.4, 2, 2, 2, 2])
    cols[0].markdown(f"{i+1}")
    hire_val = nurse["hire_date"]
    hire = cols[1].date_input("입사일", value=hire_val, key=f"d_hire_{i}", label_visibility="collapsed")
    status = cols[2].selectbox("상태", ["근무", "퇴사"], index=0 if nurse["status"] == "근무" else 1, key=f"d_status_{i}", label_visibility="collapsed")
    if hire is not None:
        days_worked = calc_nurse_days(hire, status, q_start, q_end)
        weight = days_worked / q_days if (status != "퇴사" and q_days > 0) else 0.0
        cols[3].markdown(f'<div style="padding-top:8px;color:#1565c0;font-weight:600">{days_worked}일</div>', unsafe_allow_html=True)
        cols[4].markdown(f'<div style="padding-top:8px;color:#1565c0;font-weight:600">{weight:.2f}명</div>', unsafe_allow_html=True)
    else:
        weight = 0.0
        cols[3].markdown('<div style="padding-top:8px;color:#bbb">-</div>', unsafe_allow_html=True)
        cols[4].markdown('<div style="padding-top:8px;color:#bbb">-</div>', unsafe_allow_html=True)
    daytime_total += weight
    st.session_state.daytime_nurses[i] = {"hire_date": hire, "status": status}

st.markdown(f'<div class="result-card">📊 <b>주간 간호사 3개월 평균 (환산합계)</b>: <span class="kpi-value">{daytime_total:.2f}명</span></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ④ 야간전담 간호사 인력
# ──────────────────────────────────────────────
st.markdown('<div class="section-title">④ 야간전담 간호사 인력</div>', unsafe_allow_html=True)
st.markdown('<div class="yellow-note">🟡 단시간근무자 가중치 자동 적용: 주40h↑=1.0 / 주36~40h=0.8 / 주32~36h=0.6 / 주32h↓=0.4</div>', unsafe_allow_html=True)

c3, c4, _ = st.columns([1, 1, 6])
with c3:
    if st.button("➕ 야간 간호사 추가"):
        st.session_state.night_nurses.append({"hire_date": None, "status": "근무", "weekly_hours": 40})
with c4:
    if st.button("➖ 마지막 행 삭제 ", key="del_night") and len(st.session_state.night_nurses) > 1:
        st.session_state.night_nurses.pop()

nh = st.columns([0.4, 2, 2, 2, 2, 2])
nh[0].markdown("**#**"); nh[1].markdown("**입사일**"); nh[2].markdown("**상태**")
nh[3].markdown("**근무시간**"); nh[4].markdown("**산정일수** 🟡"); nh[5].markdown("**환산인원** 🟡")

night_total = 0.0
for i, nurse in enumerate(st.session_state.night_nurses):
    cols = st.columns([0.4, 2, 2, 2, 2, 2])
    cols[0].markdown(f"{i+1}")
    hire_val = nurse["hire_date"]
    hire = cols[1].date_input("입사일", value=hire_val, key=f"n_hire_{i}", label_visibility="collapsed")
    status_opts = ["근무", "단시간근무", "퇴사"]
    sidx = status_opts.index(nurse["status"]) if nurse["status"] in status_opts else 0
    status = cols[2].selectbox("상태", status_opts, index=sidx, key=f"n_status_{i}", label_visibility="collapsed")
    weekly_h = cols[3].number_input("근무시간(h)", min_value=0, max_value=60, value=int(nurse.get("weekly_hours", 40)), step=1, key=f"n_hours_{i}", label_visibility="collapsed")
    
    if hire is not None:
        days_worked = calc_nurse_days(hire, status, q_start, q_end)
        if status == "퇴사":
            weight = 0.0
            eff_display = "0일"
        elif status == "단시간근무":
            pw = calc_parttime_weight(weekly_h)
            weight = (days_worked / q_days) * pw if q_days > 0 else 0.0
            eff = days_worked * pw
            eff_display = f"{days_worked}일 × {pw} = {eff:.2f}일"
        else:
            weight = days_worked / q_days if q_days > 0 else 0.0
            eff_display = f"{days_worked}일"
        cols[4].markdown(f'<div style="padding-top:8px;color:#6a1b9a;font-weight:600;font-size:12px">{eff_display}</div>', unsafe_allow_html=True)
        cols[5].markdown(f'<div style="padding-top:8px;color:#6a1b9a;font-weight:600">{weight:.2f}명</div>', unsafe_allow_html=True)
    else:
        weight = 0.0
        cols[4].markdown('<div style="padding-top:8px;color:#bbb">-</div>', unsafe_allow_html=True)
        cols[5].markdown('<div style="padding-top:8px;color:#bbb">-</div>', unsafe_allow_html=True)
    night_total += weight
    st.session_state.night_nurses[i] = {"hire_date": hire, "status": status, "weekly_hours": weekly_h}

st.markdown(f'<div class="result-card">📊 <b>야간전담 간호사 3개월 평균 (환산합계)</b>: <span class="kpi-value" style="color:#6a1b9a">{night_total:.2f}명</span></div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ⑤ 등급 산정 결과 보고서
# ──────────────────────────────────────────────
st.markdown('<div class="section-title">⑤ 등급 산정 결과 보고서</div>', unsafe_allow_html=True)
st.markdown('<div class="yellow-note">🟡 아래 항목은 모두 자동 계산됩니다.</div>', unsafe_allow_html=True)

total_nurses  = daytime_total + night_total
night_ratio   = (night_total / total_nurses * 100) if total_nurses > 0 else 0
patient_ratio = (avg_patients / total_nurses) if total_nurses > 0 else 0
grade         = determine_grade(patient_ratio / 100)

k1, k2, k3, k4, k5, k6 = st.columns(6)
def kpi(col, label, value, unit=""):
    col.markdown(f'<div class="result-card" style="text-align:center"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-unit">{unit}</div></div>', unsafe_allow_html=True)

kpi(k1, "🏥 운영 병상 수", f"{beds}", "병상")
kpi(k2, "👥 일평균 재원환자 수", f"{avg_patients:.2f}", "명/일")
kpi(k3, "👩‍⚕️ 3개월 평균 간호사 수", f"{total_nurses:.2f}", "명")
kpi(k4, "🌙 야간전담 간호사 수", f"{night_total:.2f}", "명")
kpi(k5, "📊 야간전담 간호사 비율", f"{night_ratio:.2f}", "%")
kpi(k6, "📐 환자대비 간호사수", f"{patient_ratio:.2f}", "(환자/간호사)")

st.markdown("---")
st.markdown(f'<div style="text-align:center; margin:14px 0;"><div style="font-size:16px; color:#555; margin-bottom:6px;">산정 등급</div><span class="grade-box {grade_css(grade)}">{grade}</span><div style="font-size:13px; color:#777; margin-top:8px;">환자대비 간호사수: <b>{patient_ratio:.2f} ({patient_ratio:.2f}%)</b></div></div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("#### 📋 등급 기준표")
grade_list = ["A등급","1등급","2등급","3등급","4등급","5등급","6등급"]
grade_table = pd.DataFrame({
    "등급": grade_list,
    "환자대비 간호사수 기준": ["2.0 미만", "2.0 이상 ~ 2.5 미만", "2.5 이상 ~ 3.0 미만", "3.0 이상 ~ 3.5 미만", "3.5 이상 ~ 4.0 미만", "4.0 이상 ~ 6.0 미만", "6.0 이상"],
    "현재": ["✅" if g == grade else "" for g in grade_list],
})
st.table(grade_table.set_index("등급"))

with st.expander("🔍 상세 계산 내역 보기"):
    st.markdown(f"""
| 항목 | 계산식 | 결과 |
|------|--------|------|
| 분기 일수 | {q_start} ~ {q_end} | **{q_days}일** |
| 총 재원환자수 | {total_patients}명 (3개월 합계) | |
| 일평균 재원환자수 | {total_patients} ÷ {q_days}일 | **{avg_patients:.2f}명** |
| 일반병동 간호사수 [주간간호사 + 야간전담간호사] | 각 간호사 근무일수 ÷ {q_days}일 합계 | **{daytime_total:.2f}명** |
| 야간전담 간호사 환산 | 근무일수 ÷ {q_days}일 × 가중치 합계 | **{night_total:.2f}명** |
| 3개월 평균 전체 간호사 수 | 일반병동 간호사 + 야간전담 | **{total_nurses:.2f}명** |
| 야간전담 간호사 비율 | {night_total:.2f} ÷ {total_nurses:.2f} × 100 | **{night_ratio:.2f}%** |
| 환자대비 간호사수 | {avg_patients:.2f} ÷ {total_nurses:.2f} | **{patient_ratio:.2f} ({patient_ratio:.2f}%)** |
| **산정 등급** | | **{grade}** |
""")

# ──────────────────────────────────────────────
# ⑥ AI 등급 진단 컨설팅 보고서
# ──────────────────────────────────────────────
st.markdown('<div class="section-title">⑥ AI 등급 진단 및 컨설팅 보고서</div>', unsafe_allow_html=True)

# API 설정 영역
with st.expander("🔑 AI API 설정 (관리자용)", expanded=False):
    ai_provider = st.radio("사용할 AI 모델 선택", ["Gemini (추천)", "Anthropic (Claude)"], horizontal=True)
    if ai_provider == "Gemini (추천)":
        gemini_api_key = st.text_input("Gemini API Key 입력", value=DEFAULT_GEMINI_API_KEY, type="password", help="Google AI Studio에서 발급받은 API 키를 입력하세요.")
        st.markdown("[Gemini API 키 발급받기](https://aistudio.google.com/app/apikey)")
    else:
        anthropic_api_key = st.text_input("Anthropic API Key 입력", value=DEFAULT_ANTHROPIC_API_KEY, type="password", help="Anthropic Console에서 발급받은 API 키를 입력하세요.")
        st.markdown("[Anthropic API 키 발급받기](https://console.anthropic.com/)")

st.markdown(
    '<div class="yellow-note">🤖 현재 입력된 데이터를 바탕으로 AI가 등급 현황을 진단하고, '
    '등급 상향을 위한 구체적인 인력 충원 방안 및 경영 전략을 제안합니다.</div>',
    unsafe_allow_html=True
)

def next_grade_info(current_grade):
    order = ["A등급","1등급","2등급","3등급","4등급","5등급","6등급"]
    thresholds = {"A등급": (0, 2.0), "1등급": (2.0, 2.5), "2등급": (2.5, 3.0), "3등급": (3.0, 3.5), "4등급": (3.5, 4.0), "5등급": (4.0, 6.0), "6등급": (6.0, 999)}
    idx = order.index(current_grade)
    if idx == 0: return None, None, None
    prev_grade = order[idx - 1]
    _, upper = thresholds[prev_grade]
    return prev_grade, upper, thresholds[current_grade][0]

def nurses_needed_for_upgrade(avg_patients, total_nurses, current_grade, q_days):
    order = ["A등급","1등급","2등급","3등급","4등급","5등급","6등급"]
    thresholds_upper = [2.0, 2.5, 3.0, 3.5, 4.0, 6.0, 999]
    idx = order.index(current_grade)
    if idx == 0: return 0, "A등급"
    target_ratio = thresholds_upper[idx - 1] - 0.01
    needed_nurses = avg_patients / target_ratio
    additional = needed_nurses - total_nurses
    return max(0, additional), order[idx - 1]

next_g, next_upper, curr_lower = next_grade_info(grade)
add_nurses, upgrade_to = nurses_needed_for_upgrade(avg_patients, total_nurses, grade, q_days)

daytime_list = [{"입사일": str(n["hire_date"]) if n["hire_date"] else "미입력", "상태": n["status"], "근무일수": calc_nurse_days(n["hire_date"], n["status"], q_start, q_end) if n["hire_date"] else 0} for n in st.session_state.daytime_nurses]
night_list = [{"입사일": str(n["hire_date"]) if n["hire_date"] else "미입력", "상태": n["status"], "주간근무시간": n.get("weekly_hours", 40), "근무일수": calc_nurse_days(n["hire_date"], n["status"], q_start, q_end) if n["hire_date"] else 0} for n in st.session_state.night_nurses]

analysis_data = {
    "분기": quarter_label, "연도": year, "분기_시작일": str(q_start), "분기_종료일": str(q_end), "분기_일수": q_days, "운영_병상수": beds,
    "월별_재원환자수": {month_label(q_start, i): pat_values[i] for i in range(3)},
    "일평균_재원환자수": round(avg_patients, 2), "주간간호사_3개월평균": round(daytime_total, 2), "야간전담간호사_3개월평균": round(night_total, 2),
    "전체_간호사_3개월평균": round(total_nurses, 2), "야간전담_비율_퍼센트": round(night_ratio, 2), "환자대비_간호사수": round(patient_ratio, 2),
    "현재_등급": grade, "상위_목표등급": upgrade_to if upgrade_to else "현재 최고등급(A등급)", "등급_상향_추가필요_간호사수_환산": round(add_nurses, 2),
    "주간간호사_명단": daytime_list, "야간전담간호사_명단": night_list,
}

system_prompt = """당신은 대한민국 의료기관 경영 전문 컨설턴트입니다.
특히 간호관리료 차등제(병동 차등제) 등급 관리에 특화된 전문가로서, 병원 개원 및 경영 컨설팅 회사 '주식회사 메디엄'의 수석 컨설턴트입니다.

보고서 작성 지침:
1. 전문적이고 구체적인 수치 기반 분석을 제공하세요.
2. 현실적으로 실행 가능한 방안을 제시하세요.
3. 인력 충원 시 단시간 근무(야간전담) 가중치를 반드시 고려하세요.
4. 등급 상향에 필요한 정확한 간호사 수(전일제 환산)를 계산하여 제시하세요.
5. 마크다운 형식으로 가독성 높게 작성하세요.
6. 보고서는 반드시 아래 구조를 따르세요:

---
# 일반병동 간호관리료 등급 진단 컨설팅 보고서

## 1. 현황 요약
## 2. 핵심 지표 분석
## 3. 등급 상향 전략 (단계별 인력 충원 시나리오)
   ### 시나리오 A: 주간 간호사 충원
   ### 시나리오 B: 야간전담 간호사 충원
   ### 시나리오 C: 혼합 충원 (최적안)
## 4. 재정적 효과 분석 (등급 상향 시 수가 변화)
## 5. 리스크 및 주의사항
## 6. 종합 권고사항 및 실행 로드맵
---"""

user_prompt = f"""다음은 의료기관의 이번 분기 간호인력 현황 데이터입니다. 이 데이터를 바탕으로 전문 컨설팅 보고서를 작성해 주세요.

```json
{json.dumps(analysis_data, ensure_ascii=False, indent=2)}
```

특히 다음 사항을 반드시 포함해 주세요:
1. 현재 {grade} 등급에서 {upgrade_to if upgrade_to else 'A등급'}으로 상향하기 위해 필요한 정확한 간호사 수
2. 주간 전일제 간호사 충원 시나리오 (몇 명 추가 시 몇 등급 달성 가능한지)
3. 야간전담 간호사 추가 충원 시나리오 (주 40시간, 주 36시간, 주 32시간 각각의 경우)
4. 가장 비용 효율적인 충원 조합 추천
5. 현재 야간전담 간호사 비율({night_ratio:.2f}%)에 대한 평가 및 개선 방향
6. 분기 내 신규 입사자 온보딩 전략 (분기 초 vs 중간 입사 시 산정일수 차이 설명)

수치는 반드시 소수점 2자리까지 정확하게 계산하여 제시하고, 실제 병원 현장에서 바로 활용 가능한 수준의 구체적인 보고서를 작성해 주세요."""

if st.button("🤖 AI 컨설팅 보고서 생성", type="primary", use_container_width=True):
    if ai_provider == "Gemini (추천)" and not gemini_api_key:
        st.error("❌ Gemini API 키가 설정되지 않았습니다. 관리자에게 문의하거나 API 설정을 확인해 주세요.")
    elif ai_provider == "Anthropic (Claude)" and not anthropic_api_key:
        st.error("❌ Anthropic API 키가 설정되지 않았습니다. 관리자에게 문의하거나 API 설정을 확인해 주세요.")
    else:
        with st.spinner("AI가 데이터를 분석하고 컨설팅 보고서를 작성 중입니다..."):
            try:
                report_placeholder = st.empty()
                full_report = ""
                
                if ai_provider == "Gemini (추천)":
                    genai.configure(api_key=gemini_api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_prompt)
                    response = model.generate_content(user_prompt, stream=True)
                    for chunk in response:
                        full_report += chunk.text
                        report_placeholder.markdown(full_report)
                else:
                    client = anthropic.Anthropic(api_key=anthropic_api_key)
                    with client.messages.stream(
                        model="claude-3-5-sonnet-20240620",
                        max_tokens=4000,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}]
                    ) as stream:
                        for text in stream.text_stream:
                            full_report += text
                            report_placeholder.markdown(full_report)

                st.session_state["last_report"] = full_report
                st.success("✅ AI 컨설팅 보고서 생성 완료!")
            except Exception as e:
                st.error(f"❌ AI 분석 중 오류가 발생했습니다: {str(e)}")

elif "last_report" in st.session_state:
    st.markdown(st.session_state["last_report"])
    st.info("💡 데이터를 변경한 후 버튼을 다시 누르면 새 보고서가 생성됩니다.")

st.markdown("---")
st.markdown("#### 📊 등급 상향 간호사 충원 시뮬레이션 (자동 계산)")
sim_data = []
grade_order = ["A등급","1등급","2등급","3등급","4등급","5등급","6등급"]
thresholds_map = {"A등급": 2.0, "1등급": 2.5, "2등급": 3.0, "3등급": 3.5, "4등급": 4.0, "5등급": 6.0, "6등급": 999}
curr_idx = grade_order.index(grade)
for target_idx in range(0, curr_idx):
    tg = grade_order[target_idx]
    upper = thresholds_map[tg]
    target_ratio = upper - 0.01
    needed = avg_patients / target_ratio if target_ratio > 0 else 0
    additional = max(0, needed - total_nurses)
    additional_night_36h = additional / 0.8
    sim_data.append({"목표 등급": tg, "필요 총 간호사(환산)": f"{needed:.2f}명", "추가 필요(환산)": f"{additional:.2f}명", "전일제 주간 충원 시": f"{additional:.2f}명 추가", "주36h 야간전담 충원 시": f"{additional_night_36h:.2f}명 추가"})

if sim_data:
    st.dataframe(pd.DataFrame(sim_data), use_container_width=True, hide_index=True)
else:
    st.success("🎉 현재 최고 등급(A등급)입니다!")

st.markdown('<div class="footer">본 프로그램은 주식회사 메디엄에서 제공하며, 입력된 데이터는 별도로 저장되지 않습니다.</div>', unsafe_allow_html=True)
