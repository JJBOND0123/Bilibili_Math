"""文本分类模型训练脚本：基于数据库中的视频标题/标签/简介，训练科目分类器。"""  # 执行逻辑

from __future__ import annotations  # 从其他模块导入依赖

import argparse  # 导入 argparse 模块
import re  # 导入 re 模块
from dataclasses import dataclass  # 从其他模块导入依赖
from datetime import datetime  # 从其他模块导入依赖
from pathlib import Path  # 从其他模块导入依赖
from typing import Iterable, Optional  # 从其他模块导入依赖

import jieba  # 导入 jieba 模块
import joblib  # 导入 joblib 模块
import pandas as pd  # 导入 pandas 模块
from sqlalchemy import create_engine  # 从其他模块导入依赖
from sklearn.feature_extraction.text import TfidfVectorizer  # 从其他模块导入依赖
from sklearn.metrics import classification_report  # 从其他模块导入依赖
from sklearn.model_selection import train_test_split  # 从其他模块导入依赖
from sklearn.naive_bayes import ComplementNB  # 从其他模块导入依赖
from sklearn.pipeline import make_pipeline  # 从其他模块导入依赖


def get_sqlalchemy_db_uri() -> str:  # 定义函数：get_sqlalchemy_db_uri
    """优先复用 config.py 里的 SQLALCHEMY_DATABASE_URI，避免脚本里写死 DB 凭据。"""  # 执行逻辑
    try:  # 开始捕获异常
        from config import Config  # 从其他模块导入依赖

        uri = getattr(Config, "SQLALCHEMY_DATABASE_URI", "") or ""  # 设置变量：uri
        return uri.strip()  # 返回结果
    except Exception:  # 异常分支处理
        return ""  # 返回结果


def get_training_data(engine) -> pd.DataFrame:  # 定义函数：get_training_data
    """
    从数据库读取训练数据。

    说明：subject 目前来自“关键词/模型分类”混合结果；想要高质量训练，建议用 --export-labels 导出后人工修正再用 --labels-csv 训练。
    """
    sql = """
    SELECT
      bvid,
      title,
      tags,
      tag_names,
      source_keyword,
      `desc`,
      phase,
      subject
    FROM videos
    WHERE subject IS NOT NULL AND subject != '' AND subject != '其他'
    """
    return pd.read_sql(sql, engine)  # 返回结果


def normalize_text(value: object) -> str:  # 定义函数：normalize_text
    if value is None:  # 条件判断
        return ""  # 返回结果
    if not isinstance(value, str):  # 条件判断
        value = str(value)  # 设置变量：value
    value = value.replace("\u3000", " ").replace("\xa0", " ")  # 设置变量：value
    return re.sub(r"\s+", " ", value).strip()  # 返回结果


def build_training_text(row: pd.Series) -> str:  # 定义函数：build_training_text
    """
    将多字段拼成一段文本，用于分类：title + tag_names + tags + desc + source_keyword。
    """
    parts = [  # 设置变量：parts
        normalize_text(row.get("title")),  # 调用函数：normalize_text
        normalize_text(row.get("tag_names")),  # 调用函数：normalize_text
        normalize_text(row.get("tags")),  # 调用函数：normalize_text
        normalize_text(row.get("desc")),  # 调用函数：normalize_text
        normalize_text(row.get("source_keyword")),  # 调用函数：normalize_text
    ]  # 结构结束/分隔
    return " ".join([p for p in parts if p])  # 返回结果


def clean_tokens(tokens: Iterable[str]) -> list[str]:  # 定义函数：clean_tokens
    cleaned: list[str] = []  # 变量赋值/配置
    for t in tokens:  # 循环遍历
        t = (t or "").strip()  # 设置变量：t
        if len(t) <= 1:  # 条件判断
            continue  # 流程控制
        if t.isdigit():  # 条件判断
            continue  # 流程控制
        cleaned.append(t)  # 执行逻辑
    return cleaned  # 返回结果


def cut_text(text: str) -> str:  # 定义函数：cut_text
    """
    jieba 分词 + 简单清洗，输出“空格分隔 token”。

    注意：后续 TF-IDF 会用 tokenizer=str.split，所以这里一定要用空格分隔。
    """
    text = normalize_text(text)  # 设置变量：text
    if not text:  # 条件判断
        return ""  # 返回结果
    tokens = clean_tokens(jieba.cut(text))  # 设置变量：tokens
    return " ".join(tokens)  # 返回结果


def load_labels_csv(path: str) -> pd.DataFrame:  # 定义函数：load_labels_csv
    """
    加载人工标注 CSV（推荐）。
    必须包含：bvid, subject_label
    """
    df = pd.read_csv(path)  # 设置变量：df
    if "bvid" not in df.columns or "subject_label" not in df.columns:  # 条件判断
        raise ValueError("labels csv 必须包含列：bvid, subject_label")  # 抛出异常
    df["bvid"] = df["bvid"].astype(str)  # 变量赋值/配置
    df["subject_label"] = df["subject_label"].astype(str).map(lambda s: normalize_text(s))  # 变量赋值/配置
    return df[["bvid", "subject_label"]]  # 返回结果


def export_label_template(df: pd.DataFrame, out_path: str, *, sample_size: int = 500) -> str:  # 定义函数：export_label_template
    """
    导出一份“待人工修正”的 CSV，方便 Excel/表格工具编辑 subject_label。
    """
    out = df.copy()  # 设置变量：out
    out["subject_label"] = out["subject"].astype(str)  # 变量赋值/配置
    cols = ["bvid", "phase", "subject", "subject_label", "title", "tag_names", "tags", "source_keyword", "desc"]  # 设置变量：cols
    out = out[cols]  # 设置变量：out
    if sample_size and sample_size > 0:  # 条件判断
        out = out.sample(n=min(sample_size, len(out)), random_state=42)  # 设置变量：out
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)  # 变量赋值/配置
    out.to_csv(out_path, index=False, encoding="utf-8-sig")  # 变量赋值/配置
    return out_path  # 返回结果


@dataclass(frozen=True)  # 装饰器：为下方函数增加行为
class TrainOptions:  # 定义类：TrainOptions
    min_rows: int = 200  # 变量赋值/配置
    min_class_count: int = 10  # 变量赋值/配置
    test_size: float = 0.2  # 变量赋值/配置
    seed: int = 42  # 变量赋值/配置
    ngram_max: int = 2  # 变量赋值/配置


def train_model(df: pd.DataFrame, opts: TrainOptions):  # 定义函数：train_model
    if df.empty:  # 条件判断
        raise ValueError("训练数据为空")  # 抛出异常

    if len(df) < opts.min_rows:  # 条件判断
        raise ValueError(f"数据量太少（{len(df)} 条），建议至少 {opts.min_rows} 条再训练。")  # 抛出异常

    print("2. 构造训练文本并分词...")  # 调用函数：print
    df = df.copy()  # 设置变量：df
    df["text"] = df.apply(build_training_text, axis=1)  # 变量赋值/配置
    df["cut_text"] = df["text"].map(cut_text)  # 变量赋值/配置

    # 过滤样本极少的类别，避免模型偏斜
    subject_counts = df["subject"].value_counts()  # 设置变量：subject_counts
    print("类别分布情况:\n", subject_counts)  # 调用函数：print
    valid_subjects = subject_counts[subject_counts >= opts.min_class_count].index  # 执行逻辑
    df = df[df["subject"].isin(valid_subjects)]  # 设置变量：df
    print(f"过滤后剩余用于训练的数据量: {len(df)}")  # 调用函数：print
    if df.empty:  # 条件判断
        raise ValueError("过滤后无可训练数据：请降低 min_class_count 或先补充/修正标注。")  # 抛出异常

    X = df["cut_text"]  # 设置变量：X
    y = df["subject"]  # 设置变量：y
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=opts.test_size, random_state=opts.seed, stratify=y)  # 变量赋值/配置

    print("3. 开始训练模型...")  # 调用函数：print
    vectorizer = TfidfVectorizer(  # 设置变量：vectorizer
        tokenizer=str.split,  # 设置变量：tokenizer
        token_pattern=None,  # 设置变量：token_pattern
        ngram_range=(1, max(1, int(opts.ngram_max))),  # 设置变量：ngram_range
    )  # 结构结束/分隔
    model = make_pipeline(vectorizer, ComplementNB())  # 设置变量：model
    model.fit(X_train, y_train)  # 执行逻辑

    print("4. 评估结果:")  # 调用函数：print
    y_pred = model.predict(X_test)  # 设置变量：y_pred
    print(classification_report(y_test, y_pred, zero_division=0))  # 变量赋值/配置
    return model  # 返回结果


def main(argv: Optional[list[str]] = None) -> int:  # 定义函数：main
    parser = argparse.ArgumentParser(description="训练 subject_classifier.pkl（TF-IDF + ComplementNB）")  # 设置变量：parser
    parser.add_argument("--output", default="subject_classifier.pkl", help="模型输出路径（默认：subject_classifier.pkl）")  # 变量赋值/配置
    parser.add_argument("--no-save", action="store_true", help="只训练与评估，不保存模型文件")  # 变量赋值/配置
    parser.add_argument("--labels-csv", default="", help="人工标注 CSV（包含 bvid, subject_label），提供则优先使用")  # 变量赋值/配置
    parser.add_argument("--export-labels", default="", help="导出待标注 CSV（包含 subject_label 列）")  # 变量赋值/配置
    parser.add_argument("--export-sample-size", type=int, default=500, help="导出待标注样本数（默认 500，0 表示全量）")  # 变量赋值/配置
    parser.add_argument("--min-rows", type=int, default=200, help="最小训练样本数（默认 200）")  # 变量赋值/配置
    parser.add_argument("--min-class-count", type=int, default=10, help="每类最小样本数（默认 10）")  # 变量赋值/配置
    parser.add_argument("--test-size", type=float, default=0.2, help="测试集比例（默认 0.2）")  # 变量赋值/配置
    parser.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")  # 变量赋值/配置
    parser.add_argument("--ngram-max", type=int, default=2, help="最大 ngram（默认 2）")  # 变量赋值/配置
    args = parser.parse_args(argv)  # 设置变量：args

    db_uri = get_sqlalchemy_db_uri()  # 设置变量：db_uri
    if not db_uri:  # 条件判断
        print("[WARN] 未能从 config.py 读取 SQLALCHEMY_DATABASE_URI，请先配置数据库连接。")  # 调用函数：print
        return 1  # 返回结果

    print("1. 正在加载数据...")  # 调用函数：print
    try:  # 开始捕获异常
        engine = create_engine(db_uri)  # 设置变量：engine
        df = get_training_data(engine)  # 设置变量：df
    except Exception as e:  # 异常分支处理
        print(f"[WARN] 数据库连接失败: {e}")  # 调用函数：print
        return 1  # 返回结果

    if args.export_labels:  # 条件判断
        out_path = export_label_template(df, args.export_labels, sample_size=args.export_sample_size)  # 设置变量：out_path
        print(f"[OK] 已导出待标注 CSV：{out_path}")  # 调用函数：print
        return 0  # 返回结果

    if args.labels_csv:  # 条件判断
        try:  # 开始捕获异常
            labels = load_labels_csv(args.labels_csv)  # 设置变量：labels
        except Exception as e:  # 异常分支处理
            print(f"[WARN] labels csv 加载失败: {e}")  # 调用函数：print
            return 1  # 返回结果

        df["bvid"] = df["bvid"].astype(str)  # 变量赋值/配置
        df = df.merge(labels, on="bvid", how="inner")  # 设置变量：df
        df["subject"] = df["subject_label"]  # 变量赋值/配置
        df = df.drop(columns=["subject_label"])  # 设置变量：df
        print(f"使用人工标注数据训练：{len(df)} 条")  # 调用函数：print

    opts = TrainOptions(  # 设置变量：opts
        min_rows=args.min_rows,  # 设置变量：min_rows
        min_class_count=args.min_class_count,  # 设置变量：min_class_count
        test_size=args.test_size,  # 设置变量：test_size
        seed=args.seed,  # 设置变量：seed
        ngram_max=args.ngram_max,  # 设置变量：ngram_max
    )  # 结构结束/分隔

    try:  # 开始捕获异常
        model = train_model(df, opts)  # 设置变量：model
    except Exception as e:  # 异常分支处理
        print(f"[WARN] 训练失败: {e}")  # 调用函数：print
        return 1  # 返回结果

    if not args.no_save:  # 条件判断
        out = Path(args.output)  # 设置变量：out
        joblib.dump(model, out.as_posix())  # 执行逻辑
        print(f"[OK] 模型已保存：{out}")  # 调用函数：print

    test_title = "张宇带你刷线代矩阵的本质"  # 设置变量：test_title
    processed = cut_text(test_title)  # 设置变量：processed
    try:  # 开始捕获异常
        prediction = model.predict([processed])[0]  # 设置变量：prediction
        print(f"\n测试预测: '{test_title}' -> 【{prediction}】")  # 调用函数：print
    except Exception as e:  # 异常分支处理
        print(f"[WARN] 测试预测失败: {e}")  # 调用函数：print

    print(f"\n完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")  # 调用函数：print
    return 0  # 返回结果


if __name__ == "__main__":  # 条件判断
    raise SystemExit(main())  # 抛出异常
