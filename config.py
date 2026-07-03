from sqlalchemy import create_engine
from urllib.parse import quote_plus
import streamlit as st

# 仅读取Streamlit后台Secrets，无本地硬编码、无环境变量本地逻辑
sec = st.secrets["database"]

# 提取数据库参数
TIDB_HOST = sec["host"]
TIDB_PORT = sec["port"]
TIDB_USER = sec["user"]
TIDB_PWD_RAW = sec["pwd"]
TIDB_PWD_ENC = quote_plus(TIDB_PWD_RAW)
TIDB_DB = sec["db_name"]
CERT_CLOUD = sec["ca_path"]

# SQLAlchemy连接串，云端强制SSL证书校验
DB_URL = (
    f"mysql+pymysql://{TIDB_USER}:{TIDB_PWD_ENC}@{TIDB_HOST}:{TIDB_PORT}/{TIDB_DB}"
    f"?charset=utf8mb4&ssl_ca={CERT_CLOUD}"
)

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)

# pymysql原生连接参数（供etl脚本使用）
pymysql_conn = {
    "host": TIDB_HOST,
    "port": TIDB_PORT,
    "user": TIDB_USER,
    "password": TIDB_PWD_RAW,
    "database": TIDB_DB,
    "charset": "utf8mb4",
    "ssl": {"ca": CERT_CLOUD}
}




# ========= Excel中文表头 → 数据库英文字段映射（ETL清洗用） =========
EXCEL_TO_DB_MAP = {
    "组长": "team_leader",
    "运营": "operator_name",
    "店铺id": "shop_ids",
    "入职时间": "entry_date",
    "数据类型": "data_category"
}

# ========= 数据库英文字段 → 看板中文展示映射（Dashboard专用） =========
DB_TO_CN_MAP = {
    "dept_manager": "部门负责人",
    "team_leader": "组长",
    "operator_name": "运营姓名",
    "staff_status": "人员状态",
    "shop_ids": "店铺ID",
    "entry_date": "入职日期",
    "stat_date": "统计日期",
    "data_category": "数据分类",
    "daily_value": "当日数值",
    "tag_info": "备注标签",
    "total_gmv": "总卢布业绩",
    "total_order": "总订单量",
    "total_new_goods": "累计上品数",
    "total_optimize": "商品优化总数",
    "avg_price": "平均客单价",
    "anomaly_type": "异常类型",
    "anomaly_detail": "异常说明",
    "current_value": "实际数值",
    "standard_value": "标准阈值"
}

# ========= 看板页面中英文对应 =========
PAGE_MAP = {
    "overview": "总览大盘",
    "dept_compare": "部门对比",
    "oper_rank": "运营排名",
    "anomaly_warn": "异常预警",
    "trend_analysis": "趋势分析"
}

# ========= 全局业务常量 =========
# 原来错误写法（仅1号，无月份）
# COL_APR = [f"{d}号" for d in range(1, 31)]
# COL_MAY = [f"{d}号" for d in range(1, 32)]
# COL_JUN = [f"{d}号" for d in range(1, 31)]
# COL_JUL = [f"{d}号" for d in range(1, 32)]

# 修复后：匹配你的Excel 4.1号 / 5.2号 格式
COL_APR = [f"4.{d}号" for d in range(1, 31)]
COL_MAY = [f"5.{d}号" for d in range(1, 32)]
COL_JUN = [f"6.{d}号" for d in range(1, 31)]
COL_JUL = [f"7.{d}号" for d in range(1, 32)]
ALL_DATE_COLS = COL_APR + COL_MAY + COL_JUN + COL_JUL
ALL_DATE_COLS = COL_APR + COL_MAY + COL_JUN + COL_JUL

# 脏数据标记文本
DIRTY_VALS = ["", "#ERROR", "#DIV/0", "请假", "周天", "放假"]
# 每日上品最低考核阈值
GOODS_STANDARD = 30
# 原始Excel文件路径
EXCEL_FILE_PATH = "运营业绩+工作登记表.xlsx"