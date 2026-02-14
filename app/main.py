"""Morning Advisor メインエントリポイント

毎朝、マネーフォワードとHuawei Healthからデータを取得し、
計画値との差分をClaude AIが分析してアドバイスを生成します。

使い方:
  # 1回実行
  python -m app.main

  # スケジューラーモード (毎朝自動実行)
  python -m app.main --schedule

  # 設定ファイル指定
  python -m app.main --config /path/to/config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

import schedule
from rich.console import Console

from app.analysis.diff_engine import analyze_all
from app.advisor.llm_advisor import build_report, generate_advice
from app.config import AppConfig, load_config
from app.display import print_report
from app.fetchers.huawei_health import fetch_health_data
from app.fetchers.moneyforward import fetch_finance_data

console = Console()
logger = logging.getLogger("morning_advisor")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def run_once(config: AppConfig) -> None:
    """1回のデータ取得・分析・アドバイス生成を実行"""
    console.print("[bold blue]Morning Advisor を実行中...[/bold blue]")
    console.print()

    # 1. データ取得 (並行実行)
    console.print("[dim]データを取得中...[/dim]")
    finance_data, health_data = await asyncio.gather(
        fetch_finance_data(config.moneyforward),
        fetch_health_data(config.huawei_health),
        return_exceptions=True,
    )

    # エラーハンドリング
    if isinstance(finance_data, Exception):
        logger.error("財務データ取得エラー: %s", finance_data)
        finance_data = None
    if isinstance(health_data, Exception):
        logger.error("健康データ取得エラー: %s", health_data)
        health_data = None

    if finance_data is None and health_data is None:
        console.print("[bold red]データを取得できませんでした。設定を確認してください。[/bold red]")
        return

    # 2. 差分分析
    console.print("[dim]差分を分析中...[/dim]")
    diffs = analyze_all(finance_data, health_data, config.targets)

    # 3. アドバイス生成
    console.print("[dim]アドバイスを生成中...[/dim]")
    advice = await generate_advice(
        config.anthropic,
        finance_data,
        health_data,
        diffs,
    )

    # 4. レポート表示
    report = build_report(finance_data, health_data, diffs, advice)
    print_report(report)


def run_scheduled(config: AppConfig) -> None:
    """スケジューラーモードで実行"""
    run_time = config.schedule.run_time
    console.print(
        f"[bold green]スケジューラーモード: 毎日 {run_time} に実行します[/bold green]"
    )
    console.print("[dim]Ctrl+C で停止[/dim]")

    def job() -> None:
        asyncio.run(run_once(config))

    schedule.every().day.at(run_time).do(job)

    # 起動確認のため初回実行
    console.print("[dim]初回実行を開始します...[/dim]")
    job()

    # スケジューラーループ
    while True:
        schedule.run_pending()
        time.sleep(60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Morning Advisor - 財務・健康データの朝アドバイザー"
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="設定ファイルのパス (デフォルト: config.yaml)",
    )
    parser.add_argument(
        "--schedule", "-s",
        action="store_true",
        help="スケジューラーモードで実行 (毎朝自動実行)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細ログを出力",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        config = load_config(args.config)
    except Exception as e:
        console.print(f"[bold red]設定ファイルの読み込みに失敗: {e}[/bold red]")
        sys.exit(1)

    if args.schedule:
        try:
            run_scheduled(config)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]スケジューラーを停止しました[/bold yellow]")
    else:
        asyncio.run(run_once(config))


if __name__ == "__main__":
    main()
