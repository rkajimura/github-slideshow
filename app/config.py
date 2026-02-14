"""設定管理"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ScheduleConfig:
    run_time: str = "07:00"
    timezone: str = "Asia/Tokyo"


@dataclass
class MoneyForwardConfig:
    email: str = ""
    password: str = ""
    account_groups: list[str] = field(default_factory=list)


@dataclass
class HuaweiHealthConfig:
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""


@dataclass
class AnthropicConfig:
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"


@dataclass
class FinanceTargets:
    monthly_savings_target: float = 100000
    yearly_asset_target: float = 5000000
    emergency_fund_minimum: float = 1000000


@dataclass
class HealthTargets:
    daily_steps: int = 8000
    daily_sleep_hours: float = 7.5
    resting_heart_rate_max: int = 75
    target_weight: float = 70.0
    weekly_exercise_count: int = 3


@dataclass
class Targets:
    finance: FinanceTargets = field(default_factory=FinanceTargets)
    health: HealthTargets = field(default_factory=HealthTargets)


@dataclass
class AppConfig:
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    moneyforward: MoneyForwardConfig = field(default_factory=MoneyForwardConfig)
    huawei_health: HuaweiHealthConfig = field(default_factory=HuaweiHealthConfig)
    anthropic: AnthropicConfig = field(default_factory=AnthropicConfig)
    targets: Targets = field(default_factory=Targets)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """設定ファイルを読み込み、環境変数でオーバーライドする"""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"

    config_path = Path(config_path)
    raw: dict = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    config = AppConfig()

    # Schedule
    sched = raw.get("schedule", {})
    config.schedule.run_time = sched.get("run_time", config.schedule.run_time)
    config.schedule.timezone = sched.get("timezone", config.schedule.timezone)

    # MoneyForward (環境変数優先)
    mf = raw.get("moneyforward", {})
    config.moneyforward.email = os.environ.get("MF_EMAIL", mf.get("email", ""))
    config.moneyforward.password = os.environ.get("MF_PASSWORD", mf.get("password", ""))
    config.moneyforward.account_groups = mf.get("account_groups", [])

    # Huawei Health (環境変数優先)
    hw = raw.get("huawei_health", {})
    config.huawei_health.client_id = os.environ.get(
        "HUAWEI_CLIENT_ID", hw.get("client_id", "")
    )
    config.huawei_health.client_secret = os.environ.get(
        "HUAWEI_CLIENT_SECRET", hw.get("client_secret", "")
    )
    config.huawei_health.refresh_token = os.environ.get(
        "HUAWEI_REFRESH_TOKEN", hw.get("refresh_token", "")
    )

    # Anthropic (環境変数優先)
    ant = raw.get("anthropic", {})
    config.anthropic.api_key = os.environ.get("ANTHROPIC_API_KEY", ant.get("api_key", ""))
    config.anthropic.model = ant.get("model", config.anthropic.model)

    # Targets
    targets = raw.get("targets", {})
    ft = targets.get("finance", {})
    config.targets.finance.monthly_savings_target = ft.get(
        "monthly_savings_target", config.targets.finance.monthly_savings_target
    )
    config.targets.finance.yearly_asset_target = ft.get(
        "yearly_asset_target", config.targets.finance.yearly_asset_target
    )
    config.targets.finance.emergency_fund_minimum = ft.get(
        "emergency_fund_minimum", config.targets.finance.emergency_fund_minimum
    )

    ht = targets.get("health", {})
    config.targets.health.daily_steps = ht.get(
        "daily_steps", config.targets.health.daily_steps
    )
    config.targets.health.daily_sleep_hours = ht.get(
        "daily_sleep_hours", config.targets.health.daily_sleep_hours
    )
    config.targets.health.resting_heart_rate_max = ht.get(
        "resting_heart_rate_max", config.targets.health.resting_heart_rate_max
    )
    config.targets.health.target_weight = ht.get(
        "target_weight", config.targets.health.target_weight
    )
    config.targets.health.weekly_exercise_count = ht.get(
        "weekly_exercise_count", config.targets.health.weekly_exercise_count
    )

    return config
