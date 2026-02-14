"""ターミナル表示モジュール (Rich使用)"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.models import DailyReport, TargetDiff

console = Console()


def print_report(report: DailyReport) -> None:
    """日次レポートをターミナルに表示"""
    console.print()
    console.rule(f"[bold blue]Morning Advisor - {report.date}[/bold blue]")
    console.print()

    # 財務セクション
    if report.finance and report.finance.accounts:
        _print_finance(report)

    # 健康セクション
    if report.health:
        _print_health(report)

    # 差分テーブル
    if report.diffs:
        _print_diffs(report.diffs)

    # アドバイス
    if report.advice:
        console.print()
        console.print(
            Panel(
                report.advice,
                title="[bold yellow]Today's Advice[/bold yellow]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    console.print()


def _print_finance(report: DailyReport) -> None:
    finance = report.finance
    assert finance is not None

    table = Table(title="資産残高 (マネーフォワード)", show_header=True)
    table.add_column("口座名", style="cyan")
    table.add_column("金融機関", style="dim")
    table.add_column("種別", style="dim")
    table.add_column("残高", justify="right", style="green")

    for acc in finance.accounts:
        table.add_row(
            acc.name,
            acc.institution,
            acc.account_type,
            f"¥{acc.balance:,.0f}",
        )

    table.add_section()
    table.add_row("", "", "[bold]合計[/bold]", f"[bold]¥{finance.total_assets:,.0f}[/bold]")
    console.print(table)


def _print_health(report: DailyReport) -> None:
    health = report.health
    assert health is not None

    table = Table(title="ヘルスデータ (Huawei Health)", show_header=True)
    table.add_column("指標", style="cyan")
    table.add_column("値", justify="right", style="green")

    if health.latest_steps:
        table.add_row("歩数 (昨日)", f"{health.latest_steps.steps:,} 歩")
    if health.steps:
        avg = sum(s.steps for s in health.steps) / len(health.steps)
        table.add_row("歩数 (7日平均)", f"{avg:,.0f} 歩")
    if health.latest_sleep:
        table.add_row("睡眠 (昨夜)", f"{health.latest_sleep.total_hours:.1f} 時間")
    if health.latest_heart_rate:
        hr = health.latest_heart_rate
        table.add_row("安静時心拍数", f"{hr.resting_bpm} bpm")
    if health.latest_weight:
        table.add_row("体重", f"{health.latest_weight.weight_kg:.1f} kg")
    if health.exercises is not None:
        table.add_row("今週の運動", f"{len(health.exercises)} 回")

    console.print(table)


def _print_diffs(diffs: list[TargetDiff]) -> None:
    table = Table(title="計画値との差分", show_header=True)
    table.add_column("項目", style="cyan")
    table.add_column("現在値", justify="right")
    table.add_column("目標値", justify="right")
    table.add_column("差分", justify="right")
    table.add_column("状態", justify="center")

    for d in diffs:
        diff_style = "green" if d.is_on_track else "red"
        status = Text("達成", style="bold green") if d.is_on_track else Text("未達", style="bold red")

        table.add_row(
            d.metric_name,
            f"{d.current_value:,.1f} {d.unit}",
            f"{d.target_value:,.1f} {d.unit}",
            Text(f"{d.diff:+,.1f} {d.unit} ({d.diff_pct:+.1f}%)", style=diff_style),
            status,
        )

    console.print(table)
