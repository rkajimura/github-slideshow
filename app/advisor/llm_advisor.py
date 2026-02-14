"""Claude API を使ったアドバイス生成モジュール"""

from __future__ import annotations

import logging

import anthropic

from app.config import AnthropicConfig
from app.models import DailyReport, FinanceSnapshot, HealthSnapshot, TargetDiff

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたは個人の財務と健康の両方を統合的にアドバイスする専門家です。
毎朝、ユーザーのマネーフォワード（資産残高）とHuawei Health（歩数・睡眠・心拍数・体重・運動）の
データを受け取り、計画値との差分に基づいて実用的なアドバイスを提供します。

## アドバイスのルール
- 日本語で回答してください
- 簡潔かつ具体的に（全体で300文字以内）
- 良い点は1つ、改善点は最大2つに絞る
- 今日すぐ実行できるアクションを1つ提案する
- 数値は具体的に示す（「歩数が不足」ではなく「歩数が目標比 -2,000歩」）
- 励ましすぎず、事実ベースで
- 財務と健康の関連性があれば指摘する（例: 運動不足→医療費リスク）
"""


def _build_data_summary(
    finance: FinanceSnapshot | None,
    health: HealthSnapshot | None,
    diffs: list[TargetDiff],
) -> str:
    """LLMに渡すデータサマリーを構築"""
    lines: list[str] = []

    # 財務データ
    if finance and finance.accounts:
        lines.append("## 財務データ (マネーフォワード)")
        lines.append(f"総資産: ¥{finance.total_assets:,.0f}")
        for acc in finance.accounts:
            lines.append(f"  - {acc.name} ({acc.institution}): ¥{acc.balance:,.0f}")
        lines.append("")

    # 健康データ
    if health:
        lines.append("## 健康データ (Huawei Health)")
        if health.latest_steps:
            s = health.latest_steps
            lines.append(f"歩数 (昨日): {s.steps:,}歩 / 距離: {s.distance_m:.0f}m")
        if health.steps:
            avg = sum(s.steps for s in health.steps) / len(health.steps)
            lines.append(f"歩数 (7日平均): {avg:,.0f}歩")
        if health.latest_sleep:
            sl = health.latest_sleep
            lines.append(
                f"睡眠 (昨夜): {sl.total_hours:.1f}時間 "
                f"(深い: {sl.deep_sleep_minutes}分, 浅い: {sl.light_sleep_minutes}分, "
                f"REM: {sl.rem_sleep_minutes}分)"
            )
        if health.latest_heart_rate:
            hr = health.latest_heart_rate
            lines.append(
                f"心拍数: 安静時 {hr.resting_bpm}bpm / 平均 {hr.avg_bpm}bpm / "
                f"最大 {hr.max_bpm}bpm"
            )
        if health.latest_weight:
            w = health.latest_weight
            lines.append(f"体重: {w.weight_kg:.1f}kg / BMI: {w.bmi:.1f}")
            if w.body_fat_pct > 0:
                lines.append(f"体脂肪率: {w.body_fat_pct:.1f}%")
        if health.exercises:
            lines.append(f"今週の運動: {len(health.exercises)}回")
            for ex in health.exercises[-3:]:
                lines.append(
                    f"  - {ex.date}: {ex.exercise_type} ({ex.duration_minutes}分)"
                )
        lines.append("")

    # 差分データ
    if diffs:
        lines.append("## 計画値との差分")
        for d in diffs:
            status = "達成" if d.is_on_track else "未達"
            lines.append(
                f"- {d.metric_name}: 現在 {d.current_value:,.1f}{d.unit} / "
                f"目標 {d.target_value:,.1f}{d.unit} "
                f"(差分: {d.diff:+,.1f}{d.unit}, {d.diff_pct:+.1f}%) [{status}]"
            )

    return "\n".join(lines)


async def generate_advice(
    config: AnthropicConfig,
    finance: FinanceSnapshot | None,
    health: HealthSnapshot | None,
    diffs: list[TargetDiff],
) -> str:
    """Claude APIでアドバイスを生成"""
    data_summary = _build_data_summary(finance, health, diffs)

    user_message = f"""\
以下は今朝のデータです。計画値との差分を踏まえて、今日の朝のアドバイスをお願いします。

{data_summary}
"""

    try:
        client = anthropic.AsyncAnthropic(api_key=config.api_key)
        message = await client.messages.create(
            model=config.model,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        advice = message.content[0].text
        logger.info("アドバイス生成完了 (%d文字)", len(advice))
        return advice

    except anthropic.APIError as e:
        logger.error("Claude API エラー: %s", e)
        return "アドバイスの生成に失敗しました。API設定を確認してください。"


def build_report(
    finance: FinanceSnapshot | None,
    health: HealthSnapshot | None,
    diffs: list[TargetDiff],
    advice: str,
) -> DailyReport:
    """日次レポートを組み立てる"""
    from datetime import date

    return DailyReport(
        date=date.today(),
        finance=finance,
        health=health,
        diffs=diffs,
        advice=advice,
    )
