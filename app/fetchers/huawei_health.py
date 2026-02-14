"""Huawei Health Kit API からヘルスデータを取得するモジュール

Huawei Health Kit REST API を使用して以下のデータを取得します:
- 歩数 / 距離 / カロリー
- 睡眠データ
- 心拍数
- 体重・体組成
- 運動記録

API ドキュメント:
https://developer.huawei.com/consumer/en/doc/HMSCore-References/server-api-overview-0000001138020895
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx

from app.config import HuaweiHealthConfig
from app.models import (
    ExerciseRecord,
    HeartRateData,
    HealthSnapshot,
    SleepData,
    StepData,
    WeightData,
)

logger = logging.getLogger(__name__)

HUAWEI_TOKEN_URL = "https://oauth-login.cloud.huawei.com/oauth2/v3/token"
HUAWEI_API_BASE = "https://health-api.cloud.huawei.com/healthkit/v1"

# Huawei Health Kit データタイプID
DATA_TYPE_STEP = "com.huawei.continuous.steps.delta"
DATA_TYPE_DISTANCE = "com.huawei.continuous.distance.delta"
DATA_TYPE_CALORIES = "com.huawei.continuous.calories.burnt"
DATA_TYPE_SLEEP = "com.huawei.continuous.sleep"
DATA_TYPE_HEART_RATE = "com.huawei.instantaneous.heart_rate"
DATA_TYPE_WEIGHT = "com.huawei.instantaneous.body.weight"
DATA_TYPE_BODY_FAT = "com.huawei.instantaneous.body_fat_rate"
DATA_TYPE_EXERCISE = "com.huawei.activity.record"


class HuaweiHealthClient:
    """Huawei Health Kit APIクライアント"""

    def __init__(self, config: HuaweiHealthConfig) -> None:
        self.config = config
        self._access_token: str = ""
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def authenticate(self) -> bool:
        """OAuth2 refresh_token を使ってアクセストークンを取得"""
        client = await self._get_client()
        try:
            resp = await client.post(
                HUAWEI_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "refresh_token": self.config.refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            logger.info("Huawei Health 認証に成功しました")
            return True
        except (httpx.HTTPError, KeyError) as e:
            logger.error("Huawei Health 認証に失敗: %s", e)
            return False

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _time_range(self, days_back: int = 7) -> tuple[int, int]:
        """ミリ秒エポック時間で期間を返す"""
        end = datetime.now()
        start = end - timedelta(days=days_back)
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    async def _fetch_data(
        self, data_type: str, days_back: int = 7
    ) -> list[dict]:
        """指定データタイプのデータを取得"""
        client = await self._get_client()
        start_ms, end_ms = self._time_range(days_back)

        try:
            resp = await client.post(
                f"{HUAWEI_API_BASE}/{self.config.client_id}/data",
                headers=self._auth_headers(),
                json={
                    "dataType": data_type,
                    "startTime": start_ms,
                    "endTime": end_ms,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("data", [])
        except httpx.HTTPError as e:
            logger.error("データ取得エラー (type=%s): %s", data_type, e)
            return []

    async def fetch_steps(self, days_back: int = 7) -> list[StepData]:
        """歩数データを取得"""
        raw = await self._fetch_data(DATA_TYPE_STEP, days_back)
        steps: list[StepData] = []

        # 日別に集約
        daily: dict[date, dict] = {}
        for record in raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            if d not in daily:
                daily[d] = {"steps": 0, "distance": 0.0, "calories": 0.0}
            daily[d]["steps"] += int(record.get("value", 0))

        # 距離データも取得して統合
        dist_raw = await self._fetch_data(DATA_TYPE_DISTANCE, days_back)
        for record in dist_raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            if d in daily:
                daily[d]["distance"] += float(record.get("value", 0))

        # カロリーデータも統合
        cal_raw = await self._fetch_data(DATA_TYPE_CALORIES, days_back)
        for record in cal_raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            if d in daily:
                daily[d]["calories"] += float(record.get("value", 0))

        for d in sorted(daily.keys()):
            steps.append(
                StepData(
                    date=d,
                    steps=daily[d]["steps"],
                    distance_m=daily[d]["distance"],
                    calories=daily[d]["calories"],
                )
            )

        logger.info("歩数データ取得: %d日分", len(steps))
        return steps

    async def fetch_sleep(self, days_back: int = 7) -> list[SleepData]:
        """睡眠データを取得"""
        raw = await self._fetch_data(DATA_TYPE_SLEEP, days_back)
        sleep_list: list[SleepData] = []

        for record in raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            duration = record.get("duration", 0)
            details = record.get("details", {})

            sleep_list.append(
                SleepData(
                    date=d,
                    total_minutes=duration // 60000,
                    deep_sleep_minutes=details.get("deepSleep", 0) // 60000,
                    light_sleep_minutes=details.get("lightSleep", 0) // 60000,
                    rem_sleep_minutes=details.get("remSleep", 0) // 60000,
                    awake_minutes=details.get("awake", 0) // 60000,
                )
            )

        logger.info("睡眠データ取得: %d日分", len(sleep_list))
        return sleep_list

    async def fetch_heart_rate(self, days_back: int = 7) -> list[HeartRateData]:
        """心拍数データを取得"""
        raw = await self._fetch_data(DATA_TYPE_HEART_RATE, days_back)

        # 日別に集約
        daily: dict[date, list[int]] = {}
        for record in raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            bpm = int(record.get("value", 0))
            if bpm > 0:
                daily.setdefault(d, []).append(bpm)

        hr_list: list[HeartRateData] = []
        for d in sorted(daily.keys()):
            values = daily[d]
            hr_list.append(
                HeartRateData(
                    date=d,
                    resting_bpm=min(values),
                    avg_bpm=sum(values) // len(values),
                    max_bpm=max(values),
                    min_bpm=min(values),
                )
            )

        logger.info("心拍数データ取得: %d日分", len(hr_list))
        return hr_list

    async def fetch_weight(self, days_back: int = 30) -> list[WeightData]:
        """体重データを取得"""
        raw = await self._fetch_data(DATA_TYPE_WEIGHT, days_back)

        weight_list: list[WeightData] = []
        for record in raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            weight = float(record.get("value", 0))
            if weight > 0:
                weight_list.append(
                    WeightData(
                        date=d,
                        weight_kg=weight,
                    )
                )

        # 体脂肪率も取得
        fat_raw = await self._fetch_data(DATA_TYPE_BODY_FAT, days_back)
        fat_by_date: dict[date, float] = {}
        for record in fat_raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            fat_by_date[d] = float(record.get("value", 0))

        for w in weight_list:
            if w.date in fat_by_date:
                w.body_fat_pct = fat_by_date[w.date]
            if w.weight_kg > 0:
                # BMI = 体重(kg) / 身長(m)^2  (身長はデフォルト170cm)
                w.bmi = w.weight_kg / (1.70**2)

        logger.info("体重データ取得: %d件", len(weight_list))
        return weight_list

    async def fetch_exercises(self, days_back: int = 7) -> list[ExerciseRecord]:
        """運動記録を取得"""
        raw = await self._fetch_data(DATA_TYPE_EXERCISE, days_back)

        exercises: list[ExerciseRecord] = []
        for record in raw:
            ts = record.get("startTime", 0)
            d = datetime.fromtimestamp(ts / 1000).date()
            exercises.append(
                ExerciseRecord(
                    date=d,
                    exercise_type=record.get("activityType", "unknown"),
                    duration_minutes=record.get("duration", 0) // 60000,
                    calories=float(record.get("calories", 0)),
                )
            )

        logger.info("運動記録取得: %d件", len(exercises))
        return exercises

    async def fetch_all(self, days_back: int = 7) -> HealthSnapshot:
        """全ヘルスデータを一括取得"""
        steps = await self.fetch_steps(days_back)
        sleep = await self.fetch_sleep(days_back)
        heart_rate = await self.fetch_heart_rate(days_back)
        weight = await self.fetch_weight(days_back=30)  # 体重は30日分
        exercises = await self.fetch_exercises(days_back)

        return HealthSnapshot(
            steps=steps,
            sleep=sleep,
            heart_rate=heart_rate,
            weight=weight,
            exercises=exercises,
            fetched_at=datetime.now(),
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


async def fetch_health_data(config: HuaweiHealthConfig) -> HealthSnapshot:
    """Huawei Healthから全ヘルスデータを取得するヘルパー関数"""
    client = HuaweiHealthClient(config)
    try:
        authenticated = await client.authenticate()
        if not authenticated:
            logger.error("Huawei Health の認証に失敗しました")
            return HealthSnapshot(fetched_at=datetime.now())
        return await client.fetch_all()
    finally:
        await client.close()
