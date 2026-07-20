# dashboard.py Ozon运营数据分析看板
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

# 导入配置
from config import DB_URL, DB_TO_CN_MAP, PAGE_MAP

# 全局唯一引擎，只初始化一次
GLOBAL_ENGINE = create_engine(DB_URL)

# 通用查询函数：关闭自动列映射，使用原始英文列名，规避映射字典缺失key
def run_sql_query(sql, params=None):
    with GLOBAL_ENGINE.connect() as conn:
        df = pd.read_sql(sql, conn, params=params)
    # 打印列名，方便你查看真实字段
    print("数据集所有列：", df.columns.tolist())
    return df

# 页面全局基础配置
st.set_page_config(page_title="Ozon跨境运营数据分析仪表盘", layout="wide", page_icon="📊")
# 自定义CSS样式
# 自定义CSS样式
# 自定义全局CSS
# 自定义全局CSS
st.markdown("""
<style>
.metric-card{background:#f6f8fa;padding:16px;border-radius:10px;margin-bottom:10px}
.warn-box{background:#ffe8e8;padding:12px;border-radius:8px;margin:10px 0}

/* 只隐藏【输入框内的选中标签】，完全不操作下拉弹窗listbox */
div[data-testid="stMultiSelect"] > div:first-of-type > div[class*="tag"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)
# 侧边筛选面板
with st.sidebar:
    st.title("筛选控制面板")
    page_cn_list = list(PAGE_MAP.values())
    page_selected_cn = st.radio("选择功能页面", page_cn_list)
    # 反向匹配页面标识
    page_flag = [k for k, v in PAGE_MAP.items() if v == page_selected_cn][0]

    # 获取所有部门下拉选项
    dept_df = run_sql_query("SELECT DISTINCT dept_manager FROM ozon_daily_oper")
    dept_all_list = dept_df["dept_manager"].tolist()
    select_dept = st.multiselect("选择部门", dept_all_list, default=dept_all_list)
    # # 日期区间筛选
    # date_range = st.date_input("日期筛选区间", value=(pd.to_datetime("2026-04-01"), pd.to_datetime("2026-07-31")))
    # start_dt = pd.to_datetime(date_range[0])
    # end_dt = pd.to_datetime(date_range[1])
    # 自动计算最近7天
    today = pd.Timestamp.now().normalize()
    start_dt = today - pd.Timedelta(days=6)
    end_dt = today

    # 日期选择框默认绑定最近一周
    date_range = st.date_input("日期筛选区间", value=(start_dt, end_dt))
    # 同步更新变量
    start_dt = pd.to_datetime(date_range[0])
    end_dt = pd.to_datetime(date_range[1])

# 统一基础子查询：只过滤部门、日期，不带分类LIKE
dept_placeholder = ",".join(["%s"] * len(select_dept))
base_sub_sql = f"""
SELECT dept_manager, team_leader, operator_name, stat_date, daily_value, data_category
FROM ozon_daily_oper
WHERE dept_manager IN ({dept_placeholder}) AND stat_date BETWEEN %s AND %s
"""
base_sub_params = tuple(select_dept) + (start_dt, end_dt)
# 预查询基础数据集，使用原始英文列名
base_df = run_sql_query(base_sub_sql, params=base_sub_params)
# 统一转为datetime，防止日期计算报错
base_df["stat_date"] = pd.to_datetime(base_df["stat_date"])
# 在 base_df 加载后，直接运行调试代码确认总和
debug_df = base_df[
    (base_df["operator_name"] == "王学良") &
    (base_df["data_category"].str.contains("业绩", na=False))
]
print("王学良 本周业绩明细：")
print(debug_df[["stat_date", "daily_value"]])
print("正确总业绩 =", debug_df["daily_value"].sum())

# ========== 页面1：总览大盘 ==========
if page_flag == "overview":
    st.header("📊 Ozon跨境运营全局大盘")

    # 打印当前选中区间
    st.write(f"【当前筛选区间】{start_dt.date()} ~ {end_dt.date()}")

    # 计算上期区间：和当前区间天数一致，往前平移
    days_diff = (end_dt - start_dt).days
    prev_end_dt = start_dt - pd.Timedelta(days=1)
    prev_start_dt = prev_end_dt - pd.Timedelta(days=days_diff)

    # 打印环比上期区间
    st.write(f"【环比对比上期区间】{prev_start_dt.date()} ~ {prev_end_dt.date()}")

    # 本期数据：从全局base_df过滤
    curr_df = base_df[(base_df["stat_date"] >= start_dt) & (base_df["stat_date"] <= end_dt)]



    # 【修复核心】单独SQL读取上期完整数据（带相同部门筛选）
    dept_placeholder = ",".join(["%s"] * len(select_dept))
    prev_sql = f"""
    SELECT dept_manager, stat_date, daily_value, data_category
    FROM ozon_daily_oper
    WHERE dept_manager IN ({dept_placeholder}) AND stat_date BETWEEN %s AND %s
    """
    prev_params = tuple(select_dept) + (prev_start_dt, prev_end_dt)
    prev_df = run_sql_query(prev_sql, params=prev_params)
    prev_df["stat_date"] = pd.to_datetime(prev_df["stat_date"])

    # 指标求和函数
    def calc_metric(df, keyword):
        return df[df["data_category"].str.contains(keyword)]["daily_value"].sum()

    # 本期指标
    gmv_curr = calc_metric(curr_df, "业绩")
    order_curr = calc_metric(curr_df, "订单")
    goods_curr = calc_metric(curr_df, "上品")
    opt_curr = calc_metric(curr_df, "优化")

    # 上期指标
    gmv_prev = calc_metric(prev_df, "业绩")
    order_prev = calc_metric(prev_df, "订单")
    goods_prev = calc_metric(prev_df, "上品")
    opt_prev = calc_metric(prev_df, "优化")

    # # 打印数值调试，直观看到上期是否为0
    # st.write(f"本期业绩：{gmv_curr:,.0f} | 上期业绩：{gmv_prev:,.0f}")

    # 环比计算，上期0时提示无上期数据
    def get_delta_pct(curr, prev):
        if prev == 0:
            return "上期无数据"
        pct = (curr - prev) / prev * 100
        return f"{pct:.1f}%"

    gmv_delta = get_delta_pct(gmv_curr, gmv_prev)
    order_delta = get_delta_pct(order_curr, order_prev)
    goods_delta = get_delta_pct(goods_curr, goods_prev)
    opt_delta = get_delta_pct(opt_curr, opt_prev)

    # 四栏指标卡片，完整传入delta环比参数
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric(
            label="总卢布业绩",
            value=f"{gmv_curr:,.0f}",
            delta=gmv_delta,
            delta_color="normal"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric(
            label="总订单量",
            value=f"{order_curr:,.0f}",
            delta=order_delta,
            delta_color="normal"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric(
            label="累计上品数",
            value=f"{goods_curr:,.0f}",
            delta=goods_delta,
            delta_color="normal"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with col4:
        st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
        st.metric(
            label="商品优化总数",
            value=f"{opt_curr:,.0f}",
            delta=opt_delta,
            delta_color="normal"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # 部门业绩占比饼图
    gmv_df = base_df[base_df["data_category"].str.contains("业绩")]
    pie_data = gmv_df.groupby("dept_manager")["daily_value"].sum().reset_index()
    pie_data.columns = ["部门负责人", "总卢布业绩"]
    fig_pie = px.pie(pie_data, values="总卢布业绩", names="部门负责人", title="各部门业绩占比分布")
    st.plotly_chart(fig_pie, use_container_width=True)

    # # 每日业绩趋势折线图
    # day_gmv_df = base_df[base_df["data_category"].str.contains("业绩")]
    # trend_day_data = day_gmv_df.groupby("stat_date")["daily_value"].sum().reset_index()
    # trend_day_data.columns = ["统计日期", "总卢布业绩"]
    # fig_line = px.line(trend_day_data, x="统计日期", y="总卢布业绩", title="每日业绩趋势图")
    # st.plotly_chart(fig_line, use_container_width=True)

    # 每日业绩趋势折线图
    # 本期每日业绩
    day_gmv_curr = base_df[base_df["data_category"].str.contains("业绩")]
    trend_curr = day_gmv_curr.groupby("stat_date")["daily_value"].sum().reset_index()
    trend_curr.columns = ["统计日期", "本期业绩"]

    # 上期每日业绩（复用前面已查询好的prev_df）
    day_gmv_prev = prev_df[prev_df["data_category"].str.contains("业绩")]
    trend_prev = day_gmv_prev.groupby("stat_date")["daily_value"].sum().reset_index()
    trend_prev.columns = ["统计日期", "上期业绩"]

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=trend_curr["统计日期"],
        y=trend_curr["本期业绩"],
        name="本期业绩",
        mode="lines+markers"
    ))
    fig_line.add_trace(go.Scatter(
        x=trend_prev["统计日期"],
        y=trend_prev["上期业绩"],
        name="上期同期业绩",
        mode="lines+markers",
        line_dash="dash"
    ))
    fig_line.update_layout(
        title="每日业绩趋势对比",
        xaxis_title="统计日期",
        yaxis_title="总卢布业绩"
    )
    st.plotly_chart(fig_line, use_container_width=True)

# ========== 页面2：部门对比 ==========
elif page_flag == "dept_compare":
    st.header("🏢 各部门业绩对比分析")
    def calc_cat_sum(df, cat_key):
        return df[df["data_category"].str.contains(cat_key)].groupby("dept_manager")["daily_value"].sum()

    gmv_dept = calc_cat_sum(base_df, "业绩")
    order_dept = calc_cat_sum(base_df, "订单")
    goods_dept = calc_cat_sum(base_df, "上品")
    opt_dept = calc_cat_sum(base_df, "优化")

    compare_df = pd.concat([gmv_dept, order_dept, goods_dept, opt_dept], axis=1).fillna(0)
    # 底层列名先定义英文
    compare_df.columns = ["total_gmv", "total_order", "total_new_goods", "total_optimize"]
    compare_df = compare_df.reset_index()
    compare_df.columns = ["部门负责人", "total_gmv", "total_order", "total_new_goods", "total_optimize"]

    # 1. 按业绩total_gmv降序排序
    compare_df = compare_df.sort_values("total_gmv", ascending=False).reset_index(drop=True)

    # 2. 定义前三名浅底色
    def highlight_top3(row):
        bg = ""
        if row.name == 0:
            bg = "background-color:#fff2cc" # 浅黄
        elif row.name == 1:
            bg = "background-color:#e6f7ff" # 浅蓝
        elif row.name == 2:
            bg = "background-color:#f0fff4" # 浅绿
        return [bg]*len(row)


    # 3. 重命名表头为中文，差异化格式化数字
    styled_df = compare_df.rename(columns={
        "total_gmv": "总卢布业绩",
        "total_order": "总订单量",
        "total_new_goods": "累计上品数",
        "total_optimize": "商品优化总数"
    }).style.apply(highlight_top3, axis=1) \
        .format("{:.2f}", subset=["总卢布业绩"]) \
        .format("{:.0f}", subset=["总订单量", "累计上品数", "商品优化总数"])

    st.dataframe(styled_df, use_container_width=True)

    fig_bar_dept = px.bar(compare_df, x="部门负责人", y="total_gmv", color="部门负责人", title="部门总业绩柱状对比")
    st.plotly_chart(fig_bar_dept, use_container_width=True)

    # ===================== 新增：七部门每日业绩趋势图 =====================
    st.subheader("各部门每日业绩变化趋势")
    # 筛选业绩数据
    dept_daily = base_df[base_df["data_category"].str.contains("业绩")].copy()
    # 按 日期+部门 聚合每日业绩
    dept_trend = dept_daily.groupby(["stat_date", "dept_manager"])["daily_value"].sum().reset_index()
    # 重命名列，统一用中文列名
    dept_trend.columns = ["统计日期", "部门负责人", "当日业绩"]

    # 创建多线画布
    fig_multi_dept = go.Figure()
    # 遍历每个部门，单独添加一条线（改用新列名"部门负责人"）
    for dept_name in dept_trend["部门负责人"].unique():
        single_dept = dept_trend[dept_trend["部门负责人"] == dept_name]
        fig_multi_dept.add_trace(go.Scatter(
            x=single_dept["统计日期"],
            y=single_dept["当日业绩"],
            name=dept_name,
            mode="lines+markers"
        ))
    fig_multi_dept.update_layout(
        title="全部门每日业绩走势对比",
        xaxis_title="统计日期",
        yaxis_title="当日总卢布业绩",
        legend_title="部门"
    )
    st.plotly_chart(fig_multi_dept, use_container_width=True)

# ========== 页面3：运营人员绩效排名 ==========
# elif page_flag == "oper_rank":
#     st.header("👤 运营人员绩效排名")
#     def get_person_sum(df, cat):
#         cat_df = df[df["data_category"].str.contains(cat)]
#         return cat_df.groupby(["dept_manager", "team_leader", "operator_name"])["daily_value"].sum()
#
#     gmv_person = get_person_sum(base_df, "业绩")
#     order_person = get_person_sum(base_df, "订单")
#     goods_person = get_person_sum(base_df, "上品")
#
#     rank_df = pd.concat([gmv_person, order_person, goods_person], axis=1).fillna(0)
#     rank_df.columns = ["total_gmv", "total_order", "total_new_goods"]
#     rank_df = rank_df.reset_index().sort_values("total_gmv", ascending=False)
#     rank_df.columns = ["部门负责人", "team_leader", "运营姓名", "total_gmv", "total_order", "total_new_goods"]
#
#     st.dataframe(rank_df, use_container_width=True)
#     # TOP20运营柱状图
#     fig_rank_top20 = px.bar(rank_df.head(20), x="运营姓名", y="total_gmv", color="部门负责人", title="TOP20运营业绩榜单")
#     st.plotly_chart(fig_rank_top20, use_container_width=True)


# ========== 页面3：运营人员绩效排名 ==========
elif page_flag == "oper_rank":
    st.header("👤 运营人员绩效排名")
    if "select_dept_val" not in st.session_state:
        st.session_state.select_dept_val = ""
    if "select_oper_val" not in st.session_state:
        st.session_state.select_oper_val = ""

    def get_person_sum(df, cat):
        cat_df = df[df["data_category"].str.contains(cat, na=False)]
        return cat_df.groupby(["dept_manager", "operator_name"])["daily_value"].sum()

    gmv_person_all = get_person_sum(base_df, "业绩")
    order_person_all = get_person_sum(base_df, "订单")
    goods_person_all = get_person_sum(base_df, "上品")
    # 新增：读取商品优化聚合数据
    opt_person_all = get_person_sum(base_df, "优化")

    # 对齐索引，保证全部运营行合并正确
    all_index = gmv_person_all.index.union(order_person_all.index).union(goods_person_all.index).union(opt_person_all.index)
    gmv_person_all = gmv_person_all.reindex(all_index, fill_value=0)
    order_person_all = order_person_all.reindex(all_index, fill_value=0)
    goods_person_all = goods_person_all.reindex(all_index, fill_value=0)
    opt_person_all = opt_person_all.reindex(all_index, fill_value=0)

    # 拼接时加入优化列
    rank_df_all = pd.concat([gmv_person_all, order_person_all, goods_person_all, opt_person_all], axis=1).fillna(0)
    rank_df_all.columns = ["total_gmv", "total_order", "total_new_goods", "total_optimize"]
    rank_df_all = rank_df_all.reset_index().sort_values("total_gmv", ascending=False)
    rank_df_all.columns = ["部门负责人", "运营姓名", "total_gmv", "total_order", "total_new_goods", "total_optimize"]

    col_dept, col_oper = st.columns(2)

    with col_dept:
        btn_all, btn_clear = st.columns(2)
        with btn_all:
            if st.button("全部部门", key="dept_all"):
                st.session_state.select_dept_val = ""
                st.session_state.select_oper_val = ""
        with btn_clear:
            if st.button("清空部门", key="dept_clear"):
                st.session_state.select_dept_val = ""
                st.session_state.select_oper_val = ""

        dept_total_gmv = base_df[base_df["data_category"].str.contains("业绩")].groupby("dept_manager")["daily_value"].sum().reset_index()
        dept_total_gmv = dept_total_gmv.sort_values("daily_value", ascending=False)
        dept_options = [""] + [f"{row['dept_manager']} ({row['daily_value']:.2f})" for _, row in dept_total_gmv.iterrows()]
        choose_dept = st.selectbox(
            label="下拉选择部门",
            options=dept_options,
            index=dept_options.index(st.session_state.select_dept_val),
            key="dept_sel"
        )
        st.session_state.select_dept_val = choose_dept

    with col_oper:
        btn_all_o, btn_clear_o = st.columns(2)
        with btn_all_o:
            if st.button("全部人员", key="oper_all"):
                st.session_state.select_oper_val = ""
        with btn_clear_o:
            if st.button("清空人员", key="oper_clear"):
                st.session_state.select_oper_val = ""

        if st.session_state.select_dept_val == "":
            oper_filter_df = base_df
        else:
            d_name = st.session_state.select_dept_val.split(" (")[0]
            oper_filter_df = base_df[base_df["dept_manager"] == d_name]
        oper_total_gmv = oper_filter_df[oper_filter_df["data_category"].str.contains("业绩")].groupby("operator_name")["daily_value"].sum().reset_index()
        oper_total_gmv = oper_total_gmv.sort_values("daily_value", ascending=False)
        oper_options = [""] + [f"{row['operator_name']} ({row['daily_value']:.2f})" for _, row in oper_total_gmv.iterrows()]
        choose_oper = st.selectbox(
            label="下拉选择运营",
            options=oper_options,
            index=oper_options.index(st.session_state.select_oper_val),
            key="oper_sel"
        )
        st.session_state.select_oper_val = choose_oper

    filter_rank_df = rank_df_all.copy()
    if st.session_state.select_dept_val != "":
        dn = st.session_state.select_dept_val.split(" (")[0]
        filter_rank_df = filter_rank_df[filter_rank_df["部门负责人"] == dn]
    if st.session_state.select_oper_val != "":
        on = st.session_state.select_oper_val.split(" (")[0]
        filter_rank_df = filter_rank_df[filter_rank_df["运营姓名"] == on]

    # 新增商品优化总数中文表头、数字格式化
    styled_table = filter_rank_df.rename(columns={
        "total_gmv": "总卢布业绩",
        "total_order": "总订单量",
        "total_new_goods": "累计上品数",
        "total_optimize": "商品优化总数"
    }).style.format("{:.2f}", subset=["总卢布业绩"]).format("{:.0f}", subset=["总订单量","累计上品数","商品优化总数"])
    st.dataframe(styled_table, use_container_width=True)

    # TOP20柱状图不受筛选影响
    fig_rank_top20 = px.bar(rank_df_all.head(20), x="运营姓名", y="total_gmv", color="部门负责人", title="TOP20运营业绩榜单")
    st.plotly_chart(fig_rank_top20, use_container_width=True)
# ========== 页面4：异常预警面板（核心业务需求） ==========
elif page_flag == "anomaly_warn":
    st.header("⚠️ 运营异常监控面板")
    sql_anomaly_data = "SELECT * FROM ozon_anomaly_record WHERE stat_date BETWEEN %s AND %s"
    anomaly_params = (start_dt, end_dt)
    df_anomaly = run_sql_query(sql_anomaly_data, params=anomaly_params)
    if len(df_anomaly) == 0:
        st.success("✅ 当前筛选区间无任何运营异常！")
    else:
        st.markdown(f"<div class='warn-box'>异常数据总条数：{len(df_anomaly)} 条</div>", unsafe_allow_html=True)
        st.dataframe(df_anomaly, use_container_width=True)
        # 异常类型占比饼图
        anomaly_group = df_anomaly.groupby("anomaly_type")["id"].count().reset_index(name="数量")
        anomaly_group.columns = ["异常类型", "数量"]
        fig_anomaly_pie = px.pie(anomaly_group, values="数量", names="异常类型", title="各类异常占比分布")
        st.plotly_chart(fig_anomaly_pie, use_container_width=True)
        # 导出异常明细CSV
        csv_export = df_anomaly.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("导出异常明细CSV文件", data=csv_export, file_name="运营异常明细.csv")

# ========== 页面5：多指标时序趋势分析 ==========
elif page_flag == "trend_analysis":
    st.header("📈 多指标时序趋势分析")
    gmv_trend = base_df[base_df["data_category"].str.contains("业绩")].groupby("stat_date")["daily_value"].sum()
    order_trend = base_df[base_df["data_category"].str.contains("订单")].groupby("stat_date")["daily_value"].sum()
    goods_trend = base_df[base_df["data_category"].str.contains("上品")].groupby("stat_date")["daily_value"].sum()

    trend_df = pd.concat([gmv_trend, order_trend, goods_trend], axis=1).fillna(0)
    trend_df.columns = ["总卢布业绩", "总订单量", "累计上品数"]
    trend_df = trend_df.reset_index()
    trend_df.rename(columns={"stat_date": "统计日期"}, inplace=True)

    fig_multi_line = go.Figure()
    fig_multi_line.add_trace(go.Scatter(x=trend_df["统计日期"], y=trend_df["总卢布业绩"], name="总业绩"))
    fig_multi_line.add_trace(go.Scatter(x=trend_df["统计日期"], y=trend_df["总订单量"], name="订单"))
    fig_multi_line.add_trace(go.Scatter(x=trend_df["统计日期"], y=trend_df["累计上品数"], name="上品"))
    fig_multi_line.update_layout(title="业绩/订单/上品 多维度趋势曲线")
    st.plotly_chart(fig_multi_line, use_container_width=True)
