from __future__ import annotations

import math
import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _next_int(prev: int, *, drift: float, noise: float, low: int, high: int) -> int:
    """基于上一次值做带趋势的递推：value' = value * (1+drift) + noise。"""
    predicted = prev * (1 + drift) + random.uniform(-noise, noise)
    return int(round(_clamp(predicted, low, high)))


def _next_float(
    prev: float,
    *,
    drift: float,
    noise: float,
    low: float,
    high: float,
    digits: int = 2,
) -> float:
    predicted = prev * (1 + drift) + random.uniform(-noise, noise)
    return round(_clamp(predicted, low, high), digits)


def _format_hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _format_hms(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


EVENT_TEMPLATES = [
    ("shop", "用户下单成功，订单金额 ¥{n}"),
    ("shop", "热销商品加购 +{n}"),
    ("video", "短视频播放破 {n} 次"),
    ("video", "内容获赞 +{n}"),
    ("live", "直播间同时在线 {n} 人"),
    ("live", "收到礼物打赏 ¥{n}"),
]

RANK_POOL = [
    ("shop", "夏季凉感套装"),
    ("shop", "运动速干鞋"),
    ("shop", "轻薄防晒衣"),
    ("video", "开箱测评 #42"),
    ("video", "同城探店精选"),
    ("video", "居家好物合集"),
    ("live", "晚间好物专场"),
    ("live", "品牌闪购直播"),
    ("live", "周末亲子场"),
]

# 城市经纬度 + 所属省份（用于 ECharts 中国地图）
REGION_SEED = [
    {"name": "北京", "lng": 116.41, "lat": 39.90, "province": "北京", "module": "shop", "base": 8600},
    {"name": "上海", "lng": 121.47, "lat": 31.23, "province": "上海", "module": "shop", "base": 9200},
    {"name": "广州", "lng": 113.26, "lat": 23.13, "province": "广东", "module": "live", "base": 7400},
    {"name": "深圳", "lng": 114.06, "lat": 22.55, "province": "广东", "module": "video", "base": 8100},
    {"name": "杭州", "lng": 120.15, "lat": 30.28, "province": "浙江", "module": "shop", "base": 6800},
    {"name": "成都", "lng": 104.07, "lat": 30.67, "province": "四川", "module": "live", "base": 6200},
    {"name": "武汉", "lng": 114.31, "lat": 30.59, "province": "湖北", "module": "video", "base": 5400},
    {"name": "西安", "lng": 108.94, "lat": 34.34, "province": "陕西", "module": "shop", "base": 4800},
    {"name": "重庆", "lng": 106.55, "lat": 29.56, "province": "重庆", "module": "live", "base": 5100},
    {"name": "南京", "lng": 118.80, "lat": 32.06, "province": "江苏", "module": "video", "base": 4600},
    {"name": "郑州", "lng": 113.65, "lat": 34.76, "province": "河南", "module": "shop", "base": 3900},
    {"name": "长沙", "lng": 112.98, "lat": 28.21, "province": "湖南", "module": "live", "base": 4200},
]


class DashboardPredictor:
    """内存态预测器：每次请求基于上一次快照递推下一次数据。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._state: dict[str, Any] | None = None
        # 全局缓慢趋势，模拟业务起伏
        self._trend_phase = random.uniform(0, math.pi * 2)

    def next_snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._state is None:
                self._state = self._bootstrap()
                return deepcopy(self._state)

            # 兼容旧内存态（升级后缺 regions 字段）
            if "regions" not in self._state:
                self._state["regions"] = self._build_regions(None)

            self._trend_phase += random.uniform(0.08, 0.22)
            self._state = self._predict_from(self._state)
            return deepcopy(self._state)

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self._trend_phase = random.uniform(0, math.pi * 2)
            self._state = self._bootstrap()
            return deepcopy(self._state)

    def _wave(self) -> float:
        # -0.03 ~ +0.03 的缓变趋势
        return math.sin(self._trend_phase) * 0.03

    def _bootstrap(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        shop_visitors = random.randint(4200, 6800)
        live_viewers = random.randint(6500, 12000)

        traffic = []
        base_shop, base_video, base_live = 1800, 3200, 1400
        for i in range(23, -1, -1):
            t = now - timedelta(minutes=5 * i)
            wave = math.sin(i / 4) * 0.08
            traffic.append(
                {
                    "time": _format_hm(t),
                    "shop": int(base_shop * (1 + wave) + random.uniform(-120, 120)),
                    "video": int(base_video * (1 + wave * 1.2) + random.uniform(-180, 180)),
                    "live": int(base_live * (1 + wave * 0.9) + random.uniform(-100, 100)),
                }
            )

        snapshot = {
            "updatedAt": now.isoformat(),
            "overview": {
                "onlineUsers": random.randint(2200, 4200),
                "todayPV": random.randint(68000, 98000),
                "todayUV": random.randint(24000, 36000),
                "gmv": random.randint(126000, 186000),
            },
            "modules": {
                "shop": {
                    "gmv": random.randint(52000, 82000),
                    "orders": random.randint(320, 560),
                    "visitors": shop_visitors,
                    "conversionRate": round(random.uniform(2.4, 4.2), 2),
                    "cartUsers": random.randint(900, 1600),
                    "refundRate": round(random.uniform(0.8, 1.6), 2),
                },
                "video": {
                    "plays": random.randint(28000, 46000),
                    "likes": random.randint(6200, 12000),
                    "shares": random.randint(1400, 2800),
                    "comments": random.randint(2200, 4600),
                    "avgWatchSec": random.randint(28, 48),
                    "publishCount": random.randint(120, 220),
                },
                "live": {
                    "rooms": random.randint(28, 48),
                    "viewers": live_viewers,
                    "peakOnline": live_viewers + random.randint(800, 2600),
                    "gifts": random.randint(4800, 9200),
                    "durationMin": random.randint(860, 1400),
                    "interactionRate": round(random.uniform(14.0, 24.0), 1),
                },
            },
            "trafficTrend": traffic,
            "sourceShare": [
                {"name": "短视频引流", "value": 34},
                {"name": "直播带货", "value": 26},
                {"name": "商城直访", "value": 22},
                {"name": "搜索/分享", "value": 18},
            ],
            "topRank": self._build_rank(None),
            "realtimeEvents": self._build_events(None, count=10),
            "regions": self._build_regions(None),
        }
        return snapshot

    def _predict_from(self, prev: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        wave = self._wave()
        # 各业务线略有差异的漂移
        shop_drift = wave + random.uniform(-0.015, 0.02)
        video_drift = wave * 1.2 + random.uniform(-0.02, 0.025)
        live_drift = wave * 0.9 + random.uniform(-0.018, 0.022)

        prev_overview = prev["overview"]
        prev_shop = prev["modules"]["shop"]
        prev_video = prev["modules"]["video"]
        prev_live = prev["modules"]["live"]

        overview = {
            "onlineUsers": _next_int(
                prev_overview["onlineUsers"],
                drift=wave + random.uniform(-0.02, 0.02),
                noise=80,
                low=800,
                high=12000,
            ),
            "todayPV": _next_int(
                prev_overview["todayPV"],
                drift=abs(wave) * 0.4 + random.uniform(0.002, 0.012),
                noise=900,
                low=20000,
                high=320000,
            ),
            "todayUV": _next_int(
                prev_overview["todayUV"],
                drift=abs(wave) * 0.35 + random.uniform(0.002, 0.01),
                noise=350,
                low=8000,
                high=120000,
            ),
            "gmv": _next_int(
                prev_overview["gmv"],
                drift=shop_drift,
                noise=1800,
                low=30000,
                high=800000,
            ),
        }

        shop = {
            "gmv": _next_int(prev_shop["gmv"], drift=shop_drift, noise=1200, low=10000, high=300000),
            "orders": _next_int(prev_shop["orders"], drift=shop_drift, noise=18, low=50, high=3000),
            "visitors": _next_int(
                prev_shop["visitors"], drift=shop_drift, noise=120, low=800, high=20000
            ),
            "conversionRate": _next_float(
                prev_shop["conversionRate"],
                drift=random.uniform(-0.03, 0.03),
                noise=0.08,
                low=0.8,
                high=12.0,
            ),
            "cartUsers": _next_int(
                prev_shop["cartUsers"], drift=shop_drift, noise=40, low=100, high=8000
            ),
            "refundRate": _next_float(
                prev_shop["refundRate"],
                drift=random.uniform(-0.02, 0.02),
                noise=0.05,
                low=0.2,
                high=8.0,
            ),
        }

        video = {
            "plays": _next_int(
                prev_video["plays"], drift=video_drift, noise=900, low=5000, high=200000
            ),
            "likes": _next_int(
                prev_video["likes"], drift=video_drift, noise=220, low=500, high=80000
            ),
            "shares": _next_int(
                prev_video["shares"], drift=video_drift, noise=60, low=100, high=30000
            ),
            "comments": _next_int(
                prev_video["comments"], drift=video_drift, noise=80, low=200, high=40000
            ),
            "avgWatchSec": _next_int(
                prev_video["avgWatchSec"],
                drift=random.uniform(-0.02, 0.02),
                noise=1.5,
                low=8,
                high=120,
            ),
            "publishCount": _next_int(
                prev_video["publishCount"],
                drift=abs(video_drift) * 0.5 + random.uniform(0.0, 0.01),
                noise=4,
                low=20,
                high=1200,
            ),
        }

        live_viewers = _next_int(
            prev_live["viewers"], drift=live_drift, noise=280, low=500, high=80000
        )
        live = {
            "rooms": _next_int(prev_live["rooms"], drift=live_drift * 0.4, noise=1.2, low=5, high=200),
            "viewers": live_viewers,
            "peakOnline": max(
                live_viewers,
                _next_int(
                    prev_live["peakOnline"],
                    drift=live_drift,
                    noise=220,
                    low=live_viewers,
                    high=100000,
                ),
            ),
            "gifts": _next_int(prev_live["gifts"], drift=live_drift, noise=180, low=300, high=80000),
            "durationMin": _next_int(
                prev_live["durationMin"],
                drift=abs(live_drift) * 0.4 + random.uniform(0.0, 0.008),
                noise=12,
                low=60,
                high=8000,
            ),
            "interactionRate": _next_float(
                prev_live["interactionRate"],
                drift=random.uniform(-0.025, 0.025),
                noise=0.4,
                low=3.0,
                high=60.0,
                digits=1,
            ),
        }

        traffic = self._predict_traffic(prev["trafficTrend"], now, shop_drift, video_drift, live_drift)
        source_share = self._predict_share(prev["sourceShare"], video_drift, live_drift, shop_drift)
        top_rank = self._build_rank(prev.get("topRank"))
        events = self._build_events(prev.get("realtimeEvents"), count=10)
        regions = self._build_regions(prev.get("regions"), shop_drift, video_drift, live_drift)

        return {
            "updatedAt": now.isoformat(),
            "overview": overview,
            "modules": {"shop": shop, "video": video, "live": live},
            "trafficTrend": traffic,
            "sourceShare": source_share,
            "topRank": top_rank,
            "realtimeEvents": events,
            "regions": regions,
        }

    def _predict_traffic(
        self,
        prev_traffic: list[dict[str, Any]],
        now: datetime,
        shop_drift: float,
        video_drift: float,
        live_drift: float,
    ) -> list[dict[str, Any]]:
        last = prev_traffic[-1] if prev_traffic else {"shop": 1800, "video": 3200, "live": 1400}
        point = {
            "time": _format_hm(now),
            "shop": _next_int(last["shop"], drift=shop_drift, noise=90, low=200, high=12000),
            "video": _next_int(last["video"], drift=video_drift, noise=140, low=300, high=18000),
            "live": _next_int(last["live"], drift=live_drift, noise=80, low=100, high=12000),
        }
        traffic = list(prev_traffic[1:]) if len(prev_traffic) >= 24 else list(prev_traffic)
        traffic.append(point)
        while len(traffic) < 24:
            traffic.insert(0, deepcopy(traffic[0]))
        return traffic[-24:]

    def _predict_share(
        self,
        prev_share: list[dict[str, Any]],
        video_drift: float,
        live_drift: float,
        shop_drift: float,
    ) -> list[dict[str, Any]]:
        weights = {
            "短视频引流": 1 + video_drift * 2,
            "直播带货": 1 + live_drift * 2,
            "商城直访": 1 + shop_drift * 2,
            "搜索/分享": 1 + random.uniform(-0.02, 0.02),
        }
        raw: list[tuple[str, float]] = []
        for item in prev_share:
            name = item["name"]
            value = float(item["value"]) * weights.get(name, 1.0)
            value = _clamp(value + random.uniform(-1.2, 1.2), 5, 60)
            raw.append((name, value))

        total = sum(v for _, v in raw) or 1
        # 归一到 100
        normalized = [(name, v / total * 100) for name, v in raw]
        ints = [int(round(v)) for _, v in normalized]
        diff = 100 - sum(ints)
        ints[-1] += diff
        return [{"name": name, "value": max(1, ints[i])} for i, (name, _) in enumerate(normalized)]

    def _build_rank(self, prev_rank: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not prev_rank:
            items = []
            for module, name in random.sample(RANK_POOL, k=6):
                base = {
                    "shop": random.randint(1200, 4200),
                    "video": random.randint(18000, 62000),
                    "live": random.randint(2800, 12000),
                }[module]
                items.append({"module": module, "name": name, "value": base})
            return sorted(items, key=lambda x: x["value"], reverse=True)

        items = []
        for item in prev_rank:
            items.append(
                {
                    "module": item["module"],
                    "name": item["name"],
                    "value": _next_int(
                        item["value"],
                        drift=random.uniform(-0.03, 0.05),
                        noise=max(20, item["value"] * 0.02),
                        low=100,
                        high=200000,
                    ),
                }
            )

        # 偶尔替换一个条目，避免排行长期不变
        if random.random() < 0.25:
            module, name = random.choice(RANK_POOL)
            if all(x["name"] != name for x in items):
                replace_at = random.randrange(len(items))
                items[replace_at] = {
                    "module": module,
                    "name": name,
                    "value": max(200, int(items[replace_at]["value"] * random.uniform(0.7, 1.1))),
                }

        return sorted(items, key=lambda x: x["value"], reverse=True)

    def _build_regions(
        self,
        prev_regions: list[dict[str, Any]] | None,
        shop_drift: float = 0.0,
        video_drift: float = 0.0,
        live_drift: float = 0.0,
    ) -> list[dict[str, Any]]:
        drift_by_module = {"shop": shop_drift, "video": video_drift, "live": live_drift}
        seed_map = {item["name"]: item for item in REGION_SEED}

        # 旧内存态只有 x/y 时，直接按新种子重建
        if not prev_regions or any("lng" not in item for item in prev_regions):
            return [
                {
                    "name": item["name"],
                    "lng": item["lng"],
                    "lat": item["lat"],
                    "province": item["province"],
                    "module": item["module"],
                    "value": int(item["base"] * random.uniform(0.85, 1.15)),
                }
                for item in REGION_SEED
            ]

        regions: list[dict[str, Any]] = []
        for item in prev_regions:
            module = item.get("module", "shop")
            seed = seed_map.get(item["name"])
            regions.append(
                {
                    "name": item["name"],
                    "lng": seed["lng"] if seed else item["lng"],
                    "lat": seed["lat"] if seed else item["lat"],
                    "province": seed["province"] if seed else item.get("province", ""),
                    "module": module,
                    "value": _next_int(
                        int(item["value"]),
                        drift=drift_by_module.get(module, 0.0) + random.uniform(-0.02, 0.03),
                        noise=max(40, int(item["value"]) * 0.03),
                        low=500,
                        high=30000,
                    ),
                }
            )
        return sorted(regions, key=lambda x: x["value"], reverse=True)

    def _build_events(
        self,
        prev_events: list[dict[str, Any]] | None,
        *,
        count: int,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        module, template = random.choice(EVENT_TEMPLATES)
        n = random.randint(20, 9999)
        newest = {
            "id": f"{int(now.timestamp() * 1000)}-{random.randint(100, 999)}",
            "time": _format_hms(now),
            "module": module,
            "message": template.format(n=n),
        }

        old = list(prev_events or [])
        # 旧事件时间略微保留，新事件插到最前
        merged = [newest, *old]
        return merged[:count]


predictor = DashboardPredictor()
