"""データモデル定義"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


# ─── 財務データ ─────────────────────────────────────────


@dataclass
class Account:
    """金融口座"""

    name: str
    institution: str
    balance: float
    currency: str = "JPY"
    account_type: str = ""  # 銀行, 証券, ポイント, etc.
    last_updated: datetime | None = None


@dataclass
class FinanceSnapshot:
    """資産残高スナップショット"""

    accounts: list[Account] = field(default_factory=list)
    total_assets: float = 0.0
    fetched_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if self.accounts and self.total_assets == 0.0:
            self.total_assets = sum(a.balance for a in self.accounts)


# ─── 健康データ ─────────────────────────────────────────


@dataclass
class StepData:
    """歩数データ"""

    date: date
    steps: int
    distance_m: float = 0.0
    calories: float = 0.0


@dataclass
class SleepData:
    """睡眠データ"""

    date: date
    total_minutes: int = 0
    deep_sleep_minutes: int = 0
    light_sleep_minutes: int = 0
    rem_sleep_minutes: int = 0
    awake_minutes: int = 0

    @property
    def total_hours(self) -> float:
        return self.total_minutes / 60.0


@dataclass
class HeartRateData:
    """心拍数データ"""

    date: date
    resting_bpm: int = 0
    avg_bpm: int = 0
    max_bpm: int = 0
    min_bpm: int = 0


@dataclass
class WeightData:
    """体重データ"""

    date: date
    weight_kg: float = 0.0
    bmi: float = 0.0
    body_fat_pct: float = 0.0


@dataclass
class ExerciseRecord:
    """運動記録"""

    date: date
    exercise_type: str = ""
    duration_minutes: int = 0
    calories: float = 0.0


@dataclass
class HealthSnapshot:
    """ヘルスデータスナップショット"""

    steps: list[StepData] = field(default_factory=list)
    sleep: list[SleepData] = field(default_factory=list)
    heart_rate: list[HeartRateData] = field(default_factory=list)
    weight: list[WeightData] = field(default_factory=list)
    exercises: list[ExerciseRecord] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.now)

    @property
    def latest_steps(self) -> StepData | None:
        return self.steps[-1] if self.steps else None

    @property
    def latest_sleep(self) -> SleepData | None:
        return self.sleep[-1] if self.sleep else None

    @property
    def latest_heart_rate(self) -> HeartRateData | None:
        return self.heart_rate[-1] if self.heart_rate else None

    @property
    def latest_weight(self) -> WeightData | None:
        return self.weight[-1] if self.weight else None


# ─── 目標・差分 ──────────────────────────────────────────


@dataclass
class TargetDiff:
    """計画値との差分"""

    category: str  # "finance" or "health"
    metric_name: str
    current_value: float
    target_value: float
    unit: str = ""

    @property
    def diff(self) -> float:
        return self.current_value - self.target_value

    @property
    def diff_pct(self) -> float:
        if self.target_value == 0:
            return 0.0
        return (self.diff / self.target_value) * 100

    @property
    def is_on_track(self) -> bool:
        return self.current_value >= self.target_value


@dataclass
class DailyReport:
    """日次レポート"""

    date: date
    finance: FinanceSnapshot | None = None
    health: HealthSnapshot | None = None
    diffs: list[TargetDiff] = field(default_factory=list)
    advice: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
