"""計画値との差分を分析するエンジン"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.config import Targets
from app.models import FinanceSnapshot, HealthSnapshot, TargetDiff

logger = logging.getLogger(__name__)


def analyze_finance_diff(
    snapshot: FinanceSnapshot, targets: Targets
) -> list[TargetDiff]:
    """財務データと目標値の差分を算出"""
    diffs: list[TargetDiff] = []
    ft = targets.finance

    # 総資産 vs 年間目標
    # 年初からの進捗で按分した目標値と比較
    today = date.today()
    days_in_year = 366 if _is_leap_year(today.year) else 365
    day_of_year = today.timetuple().tm_yday
    prorated_target = ft.yearly_asset_target * (day_of_year / days_in_year)

    diffs.append(
        TargetDiff(
            category="finance",
            metric_name="総資産 (年間目標按分)",
            current_value=snapshot.total_assets,
            target_value=prorated_target,
            unit="円",
        )
    )

    # 総資産 vs 年末目標
    diffs.append(
        TargetDiff(
            category="finance",
            metric_name="総資産 (年末目標)",
            current_value=snapshot.total_assets,
            target_value=ft.yearly_asset_target,
            unit="円",
        )
    )

    # 緊急資金ライン
    # 銀行口座の合計を緊急資金とみなす
    bank_total = sum(
        a.balance for a in snapshot.accounts
        if "銀行" in a.account_type or "bank" in a.account_type.lower()
    )
    if bank_total == 0:
        bank_total = snapshot.total_assets  # 口座タイプ不明の場合は全体を使用

    diffs.append(
        TargetDiff(
            category="finance",
            metric_name="緊急資金",
            current_value=bank_total,
            target_value=ft.emergency_fund_minimum,
            unit="円",
        )
    )

    return diffs


def analyze_health_diff(
    snapshot: HealthSnapshot, targets: Targets
) -> list[TargetDiff]:
    """健康データと目標値の差分を算出"""
    diffs: list[TargetDiff] = []
    ht = targets.health

    # 歩数 (直近1日)
    if snapshot.latest_steps:
        diffs.append(
            TargetDiff(
                category="health",
                metric_name="歩数 (昨日)",
                current_value=snapshot.latest_steps.steps,
                target_value=ht.daily_steps,
                unit="歩",
            )
        )

    # 歩数 (直近7日平均)
    if snapshot.steps:
        avg_steps = sum(s.steps for s in snapshot.steps) / len(snapshot.steps)
        diffs.append(
            TargetDiff(
                category="health",
                metric_name="歩数 (7日平均)",
                current_value=avg_steps,
                target_value=ht.daily_steps,
                unit="歩",
            )
        )

    # 睡眠時間 (直近1日)
    if snapshot.latest_sleep:
        diffs.append(
            TargetDiff(
                category="health",
                metric_name="睡眠時間 (昨夜)",
                current_value=snapshot.latest_sleep.total_hours,
                target_value=ht.daily_sleep_hours,
                unit="時間",
            )
        )

    # 睡眠時間 (7日平均)
    if snapshot.sleep:
        avg_sleep = sum(s.total_hours for s in snapshot.sleep) / len(snapshot.sleep)
        diffs.append(
            TargetDiff(
                category="health",
                metric_name="睡眠時間 (7日平均)",
                current_value=avg_sleep,
                target_value=ht.daily_sleep_hours,
                unit="時間",
            )
        )

    # 安静時心拍数
    if snapshot.latest_heart_rate:
        # 心拍数は低い方が良いので、target_valueが上限
        diffs.append(
            TargetDiff(
                category="health",
                metric_name="安静時心拍数",
                current_value=snapshot.latest_heart_rate.resting_bpm,
                target_value=ht.resting_heart_rate_max,
                unit="bpm",
            )
        )

    # 体重
    if snapshot.latest_weight:
        diffs.append(
            TargetDiff(
                category="health",
                metric_name="体重",
                current_value=snapshot.latest_weight.weight_kg,
                target_value=ht.target_weight,
                unit="kg",
            )
        )

    # 週の運動回数
    if snapshot.exercises is not None:
        week_ago = date.today() - timedelta(days=7)
        weekly_count = sum(
            1 for e in snapshot.exercises if e.date >= week_ago
        )
        diffs.append(
            TargetDiff(
                category="health",
                metric_name="週間運動回数",
                current_value=weekly_count,
                target_value=ht.weekly_exercise_count,
                unit="回",
            )
        )

    return diffs


def analyze_all(
    finance: FinanceSnapshot | None,
    health: HealthSnapshot | None,
    targets: Targets,
) -> list[TargetDiff]:
    """全データの差分を一括分析"""
    diffs: list[TargetDiff] = []

    if finance and finance.accounts:
        diffs.extend(analyze_finance_diff(finance, targets))

    if health:
        diffs.extend(analyze_health_diff(health, targets))

    logger.info("差分分析完了: %d項目", len(diffs))
    return diffs


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
