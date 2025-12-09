import streamlit as st
import json
import requests
import datetime
import math
import os

# ==========================================
# 0. パスワード認証機能
# ==========================================
def check_password():
    """合言葉を知っている人だけ通す検問"""
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if st.session_state.auth:
        return

    st.title("🔒 ログイン")
    password = st.text_input("合言葉を入力してください", type="password")
    
    if password:
        # secrets.toml (またはCloudのSecrets) から正解を取得
        if "PASSWORD" in st.secrets and password == st.secrets["PASSWORD"]:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("パスワードが違います")
            
    # 認証未完了ならここでストップ
    if not st.session_state.auth:
        st.stop()

# ==========================================
# 1. モダンUI用カスタムCSS設定 (白×赤)
# ==========================================
CUSTOM_CSS = """
<style>
    /* フォント設定 */
    html, body, [class*="css"] {
        font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
    }
    
    /* タイトルスタイル */
    h1 {
        color: #262730;
        font-weight: 800 !important;
        border-bottom: 3px solid #D32F2F;
        padding-bottom: 15px;
        margin-bottom: 30px;
    }
    
    /* 区切り線 */
    hr {
        border-color: #D32F2F !important;
        opacity: 0.2;
        margin: 30px 0;
    }
    
    /* メトリクス数字 */
    [data-testid="stMetricValue"] {
        font-size: 32px !important;
        color: #D32F2F !important;
        font-family: monospace;
        font-weight: bold;
    }
    [data-testid="stMetricDelta"] {
        background-color: #ffebee;
        color: #D32F2F !important;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 12px;
    }
    
    /* サイドバー見出し */
    section[data-testid="stSidebar"] h2 {
        color: #D32F2F !important;
        font-size: 18px !important;
    }

    /* テーブルヘッダー */
    [data-testid="stDataFrameResizable"] thead th {
        color: #D32F2F;
        font-weight: bold;
        border-bottom: 2px solid #D32F2F !important;
    }
</style>
"""

# --- 設定 ---
JSON_FILE = "payment_data.json"
PRICE_USD = 20.00

# --- 関数群 ---
def load_data():
    default_data = {
        "history": {}, 
        "members": ["永野", "西村", "箸方", "下地", "稲毛"], 
        "contractor": "永野",
        "payment_link": ""
    }
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                data = json.load(f)
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                return data
        except:
            return default_data
    return default_data

def save_data(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_rate():
    try:
        url = "https://api.frankfurter.app/latest?from=USD&to=JPY"
        res = requests.get(url, timeout=3)
        return res.json()["rates"]["JPY"]
    except:
        return 150.0 

# ==========================================
# アプリ本体
# ==========================================
st.set_page_config(page_title="ChatGPT Split", layout="wide")

# ★ここで検問実施
check_password()

# 通過したらCSS適用
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

data = load_data()
history = data["history"]
members = data["members"]
contractor = data["contractor"]

# --- サイドバー ---
with st.sidebar:
    st.header("設定・管理")
    
    st.subheader("契約者")
    new_contractor = st.selectbox("集金先（立て替え人）", members, index=members.index(contractor) if contractor in members else 0)
    if new_contractor != contractor:
        data["contractor"] = new_contractor
        save_data(data)
        st.rerun()

    st.subheader("送金先リンク")
    payment_link = st.text_input("PayPayリンクURL等", value=data.get("payment_link", ""))
    if payment_link != data.get("payment_link", ""):
        data["payment_link"] = payment_link
        save_data(data)
        st.rerun()
    
    st.divider()

    with st.expander("メンバー編集メニュー"):
        with st.form("add_mem", clear_on_submit=True):
            new_mem = st.text_input("名前を追加")
            if st.form_submit_button("追加実行", use_container_width=True) and new_mem:
                if new_mem not in members:
                    data["members"].append(new_mem)
                    save_data(data)
                    st.rerun()
        
        st.write("")
        del_mem = st.selectbox("削除する人を選択", ["-"] + members)
        if del_mem != "-" and st.button("削除実行", type="primary", use_container_width=True):
            data["members"].remove(del_mem)
            save_data(data)
            st.rerun()

    # 月削除機能
    with st.expander("月データの削除"):
        if history:
            sorted_months_rev = sorted(history.keys(), reverse=True)
            target_month = st.selectbox("削除する月を選択", sorted_months_rev)
            
            if st.button(f"{target_month} の列を削除", type="primary", use_container_width=True):
                del history[target_month]
                data["history"] = history
                save_data(data)
                st.toast(f"{target_month} を削除しました")
                st.rerun()
        else:
            st.write("削除できるデータがありません")

# --- メイン画面 ---
rate = get_rate()
total_yen = int(PRICE_USD * rate)
per_head = math.ceil((total_yen / len(members)) / 10) * 10 if members else 0

st.title(f"ChatGPT 集金所 ({contractor})")

# 1. 概要
col1, col2, col3 = st.columns(3)
col1.metric("現在のレート", f"1$ = {rate:.2f}円")
col2.metric("月額合計", f"{total_yen:,} 円")
col3.metric("1人あたりの支払額", f"{per_head:,} 円/月", delta="10円単位切り上げ")

st.divider()

# 2. 未払い額計算（未来月無視ロジック）
if not history:
    init_month = datetime.datetime.now().strftime("%Y-%m")
    history = {init_month: []}

debt_summary = {}
current_month_str = datetime.datetime.now().strftime("%Y-%m")

for m in members:
    debt_amount = 0
    if m == contractor:
        debt_summary[m] = 0
        continue
    for month, paid_members in history.items():
        if month <= current_month_str:
            if m not in paid_members:
                debt_amount += per_head
    debt_summary[m] = debt_amount

# 3. アクション
st.subheader("アクション & 連絡")

debtors = [f"{n}({a:,}円)" for n, a in debt_summary.items() if a > 0]
debtors_str = "、".join(debtors) if debtors else "なし"

copy_text = f"""【業務連絡】ChatGPT代集金
レート: {rate:.2f}円
支払額: {per_head:,}円/月

▼未払いの方（今月分まで）
{debtors_str}

送金お願いします。"""

col_text, col_btn = st.columns([3, 1])
with col_text:
    st.text_area("LINE連絡用テキスト (コピー用)", copy_text, height=120)
with col_btn:
    st.write("")
    st.write("")
    if data.get("payment_link"):
        st.link_button(f"送金する\n(アプリを開く)", data["payment_link"], use_container_width=True, type="primary")
    else:
        st.info("サイドバーから送金リンクを設定してください")

st.divider()

# 4. 管理表
header_col, btn_col = st.columns([3, 1])
with header_col:
    st.subheader("支払いチェック表")
with btn_col:
    if st.button("翌月枠を追加", use_container_width=True):
        last = sorted(history.keys())[-1]
        y, m = map(int, last.split('-'))
        if m==12: y+=1; m=1
        else: m+=1
        nxt = f"{y}-{m:02d}"
        if nxt not in history:
            history[nxt] = []
            data["history"] = history
            save_data(data)
            st.rerun()

months = sorted(history.keys())
table_data = []
for member in members:
    row = {"Name": member}
    debt = debt_summary.get(member, 0)
    row["滞納状況"] = f"未払い {debt:,} 円" if debt > 0 else "完了"
    
    for month in months:
        row[month] = member in history[month]
    table_data.append(row)

edited_df = st.data_editor(
    table_data,
    column_config={
        "Name": st.column_config.TextColumn("メンバー名", disabled=True),
        "滞納状況": st.column_config.TextColumn("未払い合計 (今月まで)", disabled=True, width="medium"),
    },
    hide_index=True,
    use_container_width=True
)

new_hist = {m: [] for m in months}
for row in edited_df:
    name = row["Name"]
    for month in months:
        if row[month]:
            new_hist[month].append(name)

if new_hist != history:
    data["history"] = new_hist
    save_data(data)
    st.rerun()
