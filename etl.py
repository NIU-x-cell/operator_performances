# etl.py 数据清洗、行转列、MySQL入库、异常检测
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import pymysql
from datetime import datetime
import warnings
import re

from sqlalchemy.engine import url

warnings.filterwarnings("ignore")

# 导入独立配置文件所有常量
from config import (
    pymysql_conn, DB_URL, EXCEL_TO_DB_MAP, ALL_DATE_COLS,
    DIRTY_VALS, GOODS_STANDARD, EXCEL_FILE_PATH
)

# 初始化数据库连接
engine = create_engine(DB_URL)
conn = pymysql.connect(**pymysql_conn)
cursor = conn.cursor()


def clean_val(x):
    """清洗脏值：空值、报错文本、请假周天统一转为0"""
    if pd.isna(x) or str(x).strip() in DIRTY_VALS:
        return 0
    try:
        return float(str(x).strip())
    except Exception:
        return 0


def trans_date_text(date_str):
    """统一兼容 6.1 / 6.1号 / 6,01 多种格式转2026-mm-dd"""
    # 提取数字 m.d 部分，兼容逗号、点、末尾“号”
    num_part = re.sub(r"[^0-9,.]", "", date_str)
    num_part = num_part.replace(",", ".")
    month_part, day_part = num_part.split(".")
    month = int(month_part)
    day_num = int(day_part)
    return f"2026-{month:02d}-{day_num:02d}"


def process_excel(file_path):
    excel_file = pd.ExcelFile(file_path)
    print("读取到的所有sheet名称：", excel_file.sheet_names)
    all_rows = []  # 全局存储所有sheet明细，循环全程不重置
    for sheet in excel_file.sheet_names:
        df_raw = pd.read_excel(file_path, sheet)
        df_raw.columns = df_raw.columns.str.strip()
        print(f"\n==== 当前sheet：{sheet} ====")
        print("当前sheet所有列名：", list(df_raw.columns))

        # 中英文字段映射
        rename_dict = {}
        for cn_name, en_name in EXCEL_TO_DB_MAP.items():
            if cn_name in df_raw.columns:
                rename_dict[cn_name] = en_name
        df_raw = df_raw.rename(columns=rename_dict)
        df_raw["dept_manager"] = sheet

        base_cols = ["dept_manager", "team_leader", "operator_name", "shop_ids", "entry_date", "data_category"]
        exist_base_cols = [col for col in base_cols if col in df_raw.columns]
        print("有效基础列：", exist_base_cols)
        if len(exist_base_cols) == 0:
            print(f"【警告】{sheet} 无任何基础字段，跳过该sheet")
            continue
        df_base = df_raw[exist_base_cols].copy()

        # 修复1：不再用ALL_DATE_COLS反向匹配，直接读取Excel全部列，正则识别日期列（兼容带号/不带号/逗号）
        all_excel_cols = list(df_raw.columns)
        match_date_cols = []
        for col in all_excel_cols:
            if re.match(r"^\d+[,.]\d+.*", str(col)):
                match_date_cols.append(col)
        print("当前sheet匹配到的日期列：", match_date_cols)

        # 遍历Excel识别出的日期列，行转列
        for date_col in match_date_cols:
            temp_df = df_base.copy()
            temp_df["stat_date_str"] = date_col
            temp_df["daily_value"] = df_raw[date_col].apply(clean_val)
            tag_text = df_raw[date_col].apply(lambda x: str(x) if str(x) in DIRTY_VALS else "")
            temp_df["tag_info"] = tag_text
            temp_df["staff_status"] = temp_df["operator_name"].apply(lambda x: "离职" if "离职" in str(x) else "在职")
            all_rows.append(temp_df)

        print("当前sheet新增待合并数据条数：", len(all_rows))

    # 修复2：sheet循环全部结束后，再一次性合并全量数据（移到for sheet循环外部）
    if len(all_rows) == 0:
        raise Exception("未读取到任何有效数据，请检查Excel列名、日期格式是否匹配")
    df_all = pd.concat(all_rows, ignore_index=True)
    print(f"\n全部sheet读取完成，总待入库行数：{len(df_all)}")

    # 统一转换日期
    df_all["stat_date"] = pd.to_datetime(df_all["stat_date_str"].apply(trans_date_text))
    df_all.drop(columns=["stat_date_str"], inplace=True)
    return df_all


def create_anomaly_record(df):
    """检测上品不足异常，写入ozon_anomaly_record异常表"""
    anomaly_data = []
    goods_data = df[df["data_category"].str.contains("上品")]
    low_goods_df = goods_data[goods_data["daily_value"] < GOODS_STANDARD]
    for _, row in low_goods_df.iterrows():
        anomaly_data.append({
            "dept_manager": row["dept_manager"],
            "team_leader": row["team_leader"],
            "operator_name": row["operator_name"],
            "stat_date": row["stat_date"],
            "anomaly_type": f"日上品不足{GOODS_STANDARD}个",
            "anomaly_detail": f"当日上品数量未达到最低考核标准{GOODS_STANDARD}个",
            "current_value": row["daily_value"],
            "standard_value": GOODS_STANDARD
        })
    anomaly_df = pd.DataFrame(anomaly_data)
    if len(anomaly_df) > 0:
        anomaly_df.to_sql(name="ozon_anomaly_record", con=engine, if_exists="append", index=False)
    print(f"本次共检测到异常数据 {len(anomaly_df)} 条，已入库")
    return anomaly_df


# 程序入口
if __name__ == "__main__":
    # 1.清洗Excel
    df_clean_data = process_excel(EXCEL_FILE_PATH)
    # 2.写入运营明细表
    df_clean_data.to_sql(name="ozon_daily_oper", con=engine, if_exists="replace", index=False)
    print(f"明细数据入库完成，总数据行数：{len(df_clean_data)}")
    # 3.生成异常记录
    create_anomaly_record(df_clean_data)
    # 关闭连接
    cursor.close()
    conn.close()