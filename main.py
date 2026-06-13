import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap
import math

st.set_page_config(layout="wide")
st.title("精神医療戦略マップ（商圏分析付き）")

# -------------------------
# 距離
# -------------------------
def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lat2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# -------------------------
# CSV
# -------------------------
def load_csv_safe(path):
    for enc in ["utf-8-sig","utf-8","cp932","shift_jis"]:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = df.columns.str.strip()
            return df
        except:
            continue
    st.error(f"{path} 読み込み失敗")
    return pd.DataFrame()

df = load_csv_safe("data/population_real.csv")
hosp = load_csv_safe("data/psychiatric_hospitals.csv")

# 救急・児童補完
if "救急" not in hosp.columns:
    hosp["救急"] = 0
if "児童" not in hosp.columns:
    hosp["児童"] = 0

# 数値化
for col in ["人口","児童人口","現役人口","高齢人口","緯度","経度"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

for col in ["緯度","経度","ベッド数","救急","児童"]:
    hosp[col] = pd.to_numeric(hosp[col], errors="coerce")

# 割合
df["児童割合"] = df["児童人口"] / df["人口"]
df["現役割合"] = df["現役人口"] / df["人口"]
df["高齢割合"] = df["高齢人口"] / df["人口"]

# -------------------------
# スライダー
# -------------------------
st.sidebar.header("需要設定")

child_w = st.sidebar.slider("児童",0.0,2.0,1.0)
work_w = st.sidebar.slider("現役",0.0,2.0,1.0)
old_w = st.sidebar.slider("高齢",0.0,2.0,0.5)

# -------------------------
# 商圏設定（NEW）
# -------------------------
st.sidebar.header("商圏設定")

show_own_area = st.sidebar.checkbox("自院商圏を表示", True)
show_comp_area = st.sidebar.checkbox("競合商圏を表示", False)

radius_km = st.sidebar.slider("商圏半径（km）", 1, 30, 10)

# -------------------------
# フィルター
# -------------------------
st.sidebar.header("施設フィルター")

exclude_clinic = st.sidebar.checkbox("クリニック除外", True)
emergency_only = st.sidebar.checkbox("精神科救急のみ")
child_only = st.sidebar.checkbox("児童思春期のみ")

hosp_filtered = hosp.copy()

if exclude_clinic:
    hosp_filtered = hosp_filtered[hosp_filtered["種別"] != "クリニック"]

if emergency_only:
    hosp_filtered = hosp_filtered[hosp_filtered["救急"] == 1]

if child_only:
    hosp_filtered = hosp_filtered[hosp_filtered["児童"] == 1]

# -------------------------
# 需要スコア
# -------------------------
df["需要スコア"] = (
    df["児童割合"]*100*child_w +
    df["現役割合"]*100*work_w +
    df["高齢割合"]*100*old_w
)

# -------------------------
# 競合強度
# -------------------------
def comp(row):
    s = 0
    for _,h in hosp_filtered.iterrows():
        if pd.isna(h["緯度"]): continue
        d = distance_km(row["緯度"],row["経度"],h["緯度"],h["経度"])
        w = 1 if h["種別"]=="精神科" else 0.3
        s += (h["ベッド数"]*w)/(d+1)
    return s

df["競合強度"] = df.apply(comp,axis=1)

# 勝てる
df["勝てる"] = df["需要スコア"] / df["競合強度"]

# -------------------------
# 地図
# -------------------------
own = hosp[hosp["種別"]=="自院"].iloc[0]

m = folium.Map(location=[own["緯度"],own["経度"]],zoom_start=10)

# ヒート
HeatMap([[r["緯度"],r["経度"],r["競合強度"]] for _,r in df.iterrows()]).add_to(m)

# -------------------------
# ★ 商圏表示（ここが追加）
# -------------------------

# 自院
if show_own_area:
    folium.Circle(
        location=[own["緯度"], own["経度"]],
        radius=radius_km * 1000,
        color="red",
        fill=True,
        fill_opacity=0.1,
        popup="自院商圏"
    ).add_to(m)

# 競合
if show_comp_area:
    for _,r in hosp_filtered.iterrows():
        if r["種別"] == "自院":
            continue

        folium.Circle(
            location=[r["緯度"], r["経度"]],
            radius=radius_km * 1000,
            color="purple",
            fill=True,
            fill_opacity=0.05,
            popup=r["名称"]
        ).add_to(m)

# -------------------------
# 市町村
# -------------------------
for _,r in df.iterrows():
    if pd.isna(r["緯度"]): continue

    color = "green" if r["勝てる"]>1.5 else "orange" if r["勝てる"]>1 else "red"

    folium.CircleMarker(
        location=[r["緯度"],r["経度"]],
        radius=6,
        color=color,
        fill=True,
        popup=f"{r['市町村']} 勝:{round(r['勝てる'],2)}"
    ).add_to(m)

# 病院
for _,r in hosp_filtered.iterrows():
    col = "red" if r["種別"]=="自院" else "purple"

    folium.Marker(
        location=[r["緯度"],r["経度"]],
        popup=r["名称"],
        icon=folium.Icon(color=col)
    ).add_to(m)

st.components.v1.html(m.get_root().render(),height=700)