from __future__ import annotations

import math
import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from threading import Lock

CST = timezone(timedelta(hours=8))


def _now() -> datetime:
    return datetime.now(CST)


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


TRAFFIC_KEYS = (
    "order",
    "video",
    "exam",
    "production",
    "offline",
    "supervise",
    "live",
)

EVENT_TEMPLATES = [
    ("order", "学员完成报名，订单金额 ¥{n}"),
    ("order", "课时包续费成功 +{n}"),
    ("video", "学习视频完课 +{n}"),
    ("video", "课程播放 {n} 次"),
    ("exam", "试卷提交 {n} 份"),
    ("exam", "章节测验完成 {n} 人"),
    ("production", "产生式掌握 +{n}"),
    ("production", "产生式练习完成 {n} 组"),
    ("offline", "线下辅导签到 {n} 人"),
    ("offline", "面授班到课 {n} 人"),
    ("supervise", "督导连线 {n} 人次"),
    ("supervise", "在线答疑处理 {n} 条"),
    ("live", "直播课在课 {n} 人"),
    ("live", "直播课互动 +{n}"),
]

RANK_POOL = [
    ("order", "春季提分课套餐"),
    ("order", "一对一课时包"),
    ("order", "期末冲刺班"),
    ("video", "函数极限精讲"),
    ("video", "英语听力训练"),
    ("video", "电路基础入门"),
    ("exam", "期中模拟卷 A"),
    ("exam", "章节测验 03"),
    ("exam", "高考真题精选"),
    ("production", "导数应用规则"),
    ("production", "完形填空策略"),
    ("production", "受力分析产生式"),
    ("offline", "北京海淀晚辅导"),
    ("offline", "天津南开面授班"),
    ("offline", "石家庄周末班"),
    ("supervise", "晚间在线督导"),
    ("supervise", "作业批改连线"),
    ("supervise", "答疑值班"),
    ("live", "高三数学直播课"),
    ("live", "英语写作直播"),
    ("live", "物理实验直播"),
]

# 公司日活约千人，主要分布在北京 / 深圳 / 天津 / 河北
REGION_SEED = [
    {"name": "北京", "lng": 116.41, "lat": 39.90, "province": "北京", "module": "order", "base": 280},
    {"name": "深圳", "lng": 114.06, "lat": 22.55, "province": "广东", "module": "video", "base": 230},
    {"name": "天津", "lng": 117.20, "lat": 39.13, "province": "天津", "module": "live", "base": 190},
    {"name": "石家庄", "lng": 114.51, "lat": 38.04, "province": "河北", "module": "offline", "base": 150},
    {"name": "保定", "lng": 115.46, "lat": 38.87, "province": "河北", "module": "exam", "base": 110},
    {"name": "廊坊", "lng": 116.70, "lat": 39.52, "province": "河北", "module": "supervise", "base": 95},
    {"name": "唐山", "lng": 118.18, "lat": 39.63, "province": "河北", "module": "production", "base": 85},
    {"name": "邯郸", "lng": 114.49, "lat": 36.61, "province": "河北", "module": "offline", "base": 70},
    {"name": "沧州", "lng": 116.84, "lat": 38.30, "province": "河北", "module": "exam", "base": 62},
    {"name": "秦皇岛", "lng": 119.60, "lat": 39.94, "province": "河北", "module": "live", "base": 48},
]

RANK_BASE = {
    "order": (12, 86),
    "video": (40, 320),
    "exam": (18, 160),
    "production": (16, 140),
    "offline": (10, 90),
    "supervise": (8, 70),
    "live": (14, 110),
}


class DashboardPredictor:
    """内存态预测器：每次请求基于上一次快照递推下一次数据。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._state: dict[str, Any] | None = None
        self._trend_phase = random.uniform(0, math.pi * 2)

    def next_snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._state is None or not self._is_current_schema(self._state):
                self._state = self._bootstrap()
                return deepcopy(self._state)

            self._trend_phase += random.uniform(0.08, 0.22)
            self._state = self._predict_from(self._state)
            return deepcopy(self._state)

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self._trend_phase = random.uniform(0, math.pi * 2)
            self._state = self._bootstrap()
            return deepcopy(self._state)

    def _is_current_schema(self, state: dict[str, Any]) -> bool:
        modules = state.get("modules") or {}
        if not all(key in modules for key in TRAFFIC_KEYS):
            return False
        gmv = int((state.get("overview") or {}).get("gmv") or 0)
        return gmv >= 200000

    def _wave(self) -> float:
        return math.sin(self._trend_phase) * 0.03

    def _bootstrap(self) -> dict[str, Any]:
        now = _now()
        live_viewers = random.randint(28, 96)
        supervise_online = random.randint(8, 22)

        traffic = []
        bases = {
            "order": 18,
            "video": 42,
            "exam": 28,
            "production": 22,
            "offline": 16,
            "supervise": 14,
            "live": 24,
        }
        for i in range(23, -1, -1):
            t = now - timedelta(minutes=5 * i)
            wave = math.sin(i / 4) * 0.08
            point = {"time": _format_hm(t)}
            for key, base in bases.items():
                point[key] = max(2, int(base * (1 + wave) + random.uniform(-4, 4)))
            traffic.append(point)

        snapshot = {
            "updatedAt": now.isoformat(),
            "overview": {
                "onlineUsers": random.randint(86, 240),
                "todayPV": random.randint(2200, 4800),
                "todayUV": random.randint(620, 1080),
                "gmv": random.randint(485000, 515000),
            },
            "modules": {
                "order": {
                    "gmv": random.randint(478000, 522000),
                    "orders": random.randint(18, 68),
                    "visitors": random.randint(180, 420),
                    "conversionRate": round(random.uniform(4.2, 9.6), 2),
                },
                "video": {
                    "plays": random.randint(260, 820),
                    "completes": random.randint(80, 260),
                    "avgWatchSec": random.randint(220, 680),
                    "publishCount": random.randint(18, 46),
                },
                "exam": {
                    "submits": random.randint(70, 280),
                    "accuracy": round(random.uniform(62.0, 86.0), 1),
                    "papers": random.randint(8, 22),
                    "finishRate": round(random.uniform(68.0, 92.0), 1),
                },
                "production": {
                    "drills": random.randint(48, 210),
                    "masteryRate": round(random.uniform(42.0, 76.0), 1),
                    "rules": random.randint(16, 42),
                    "applications": random.randint(30, 140),
                },
                "offline": {
                    "attendance": random.randint(36, 148),
                    "classes": random.randint(4, 14),
                    "attendRate": round(random.uniform(82.0, 96.0), 1),
                    "campuses": random.randint(3, 8),
                },
                "supervise": {
                    "online": supervise_online,
                    "sessions": random.randint(22, 96),
                    "avgRespSec": random.randint(22, 78),
                    "coverageRate": round(random.uniform(74.0, 94.0), 1),
                },
                "live": {
                    "sessions": random.randint(3, 10),
                    "viewers": live_viewers,
                    "peakOnline": live_viewers + random.randint(8, 28),
                    "interactionRate": round(random.uniform(18.0, 42.0), 1),
                },
            },
            "trafficTrend": traffic,
            "sourceShare": [
                {"name": "线下辅导", "value": 28},
                {"name": "直播课", "value": 22},
                {"name": "学习视频", "value": 20},
                {"name": "在线督导", "value": 16},
                {"name": "订单报名", "value": 14},
            ],
            "topRank": self._build_rank(None),
            "realtimeEvents": self._build_events(None, count=10),
            "regions": self._build_regions(None),
        }
        return snapshot

    def _predict_from(self, prev: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        wave = self._wave()
        drifts = {
            "order": wave + random.uniform(-0.015, 0.02),
            "video": wave * 1.1 + random.uniform(-0.02, 0.024),
            "exam": wave * 0.95 + random.uniform(-0.018, 0.022),
            "production": wave * 1.05 + random.uniform(-0.02, 0.023),
            "offline": wave * 0.7 + random.uniform(-0.012, 0.016),
            "supervise": wave * 0.85 + random.uniform(-0.016, 0.02),
            "live": wave * 0.9 + random.uniform(-0.018, 0.022),
        }

        prev_overview = prev["overview"]
        prev_modules = prev["modules"]

        overview = {
            "onlineUsers": _next_int(
                prev_overview["onlineUsers"],
                drift=wave + random.uniform(-0.02, 0.02),
                noise=8,
                low=40,
                high=360,
            ),
            "todayPV": _next_int(
                prev_overview["todayPV"],
                drift=abs(wave) * 0.4 + random.uniform(0.002, 0.01),
                noise=40,
                low=800,
                high=8000,
            ),
            "todayUV": _next_int(
                prev_overview["todayUV"],
                drift=abs(wave) * 0.3 + random.uniform(0.001, 0.008),
                noise=12,
                low=280,
                high=1280,
            ),
            "gmv": _next_int(
                prev_overview["gmv"],
                drift=drifts["order"] * 0.15,
                noise=2800,
                low=450000,
                high=550000,
            ),
        }

        order = {
            "gmv": _next_int(
                prev_modules["order"]["gmv"],
                drift=drifts["order"] * 0.15,
                noise=2600,
                low=450000,
                high=550000,
            ),
            "orders": _next_int(prev_modules["order"]["orders"], drift=drifts["order"], noise=2, low=6, high=160),
            "visitors": _next_int(
                prev_modules["order"]["visitors"], drift=drifts["order"], noise=8, low=60, high=900
            ),
            "conversionRate": _next_float(
                prev_modules["order"]["conversionRate"],
                drift=random.uniform(-0.03, 0.03),
                noise=0.12,
                low=1.2,
                high=18.0,
            ),
        }

        video = {
            "plays": _next_int(prev_modules["video"]["plays"], drift=drifts["video"], noise=12, low=80, high=1600),
            "completes": _next_int(
                prev_modules["video"]["completes"], drift=drifts["video"], noise=6, low=20, high=700
            ),
            "avgWatchSec": _next_int(
                prev_modules["video"]["avgWatchSec"],
                drift=random.uniform(-0.02, 0.02),
                noise=8,
                low=90,
                high=1200,
            ),
            "publishCount": _next_int(
                prev_modules["video"]["publishCount"],
                drift=abs(drifts["video"]) * 0.4 + random.uniform(0.0, 0.008),
                noise=1,
                low=6,
                high=80,
            ),
        }

        exam = {
            "submits": _next_int(prev_modules["exam"]["submits"], drift=drifts["exam"], noise=6, low=16, high=520),
            "accuracy": _next_float(
                prev_modules["exam"]["accuracy"],
                drift=random.uniform(-0.015, 0.015),
                noise=0.4,
                low=40.0,
                high=96.0,
                digits=1,
            ),
            "papers": _next_int(prev_modules["exam"]["papers"], drift=drifts["exam"] * 0.3, noise=0.6, low=3, high=40),
            "finishRate": _next_float(
                prev_modules["exam"]["finishRate"],
                drift=random.uniform(-0.02, 0.02),
                noise=0.5,
                low=40.0,
                high=98.0,
                digits=1,
            ),
        }

        production = {
            "drills": _next_int(
                prev_modules["production"]["drills"], drift=drifts["production"], noise=5, low=12, high=480
            ),
            "masteryRate": _next_float(
                prev_modules["production"]["masteryRate"],
                drift=random.uniform(-0.02, 0.02),
                noise=0.5,
                low=20.0,
                high=92.0,
                digits=1,
            ),
            "rules": _next_int(
                prev_modules["production"]["rules"], drift=drifts["production"] * 0.25, noise=0.6, low=6, high=80
            ),
            "applications": _next_int(
                prev_modules["production"]["applications"],
                drift=drifts["production"],
                noise=4,
                low=8,
                high=360,
            ),
        }

        offline = {
            "attendance": _next_int(
                prev_modules["offline"]["attendance"], drift=drifts["offline"], noise=4, low=10, high=280
            ),
            "classes": _next_int(
                prev_modules["offline"]["classes"], drift=drifts["offline"] * 0.3, noise=0.5, low=2, high=24
            ),
            "attendRate": _next_float(
                prev_modules["offline"]["attendRate"],
                drift=random.uniform(-0.01, 0.01),
                noise=0.35,
                low=60.0,
                high=99.0,
                digits=1,
            ),
            "campuses": _next_int(
                prev_modules["offline"]["campuses"], drift=0.0, noise=0.15, low=2, high=12
            ),
        }

        supervise_online = _next_int(
            prev_modules["supervise"]["online"], drift=drifts["supervise"], noise=1.2, low=3, high=48
        )
        supervise = {
            "online": supervise_online,
            "sessions": _next_int(
                prev_modules["supervise"]["sessions"], drift=drifts["supervise"], noise=3, low=8, high=220
            ),
            "avgRespSec": _next_int(
                prev_modules["supervise"]["avgRespSec"],
                drift=random.uniform(-0.03, 0.03),
                noise=2,
                low=8,
                high=180,
            ),
            "coverageRate": _next_float(
                prev_modules["supervise"]["coverageRate"],
                drift=random.uniform(-0.015, 0.015),
                noise=0.4,
                low=40.0,
                high=99.0,
                digits=1,
            ),
        }

        live_viewers = _next_int(
            prev_modules["live"]["viewers"], drift=drifts["live"], noise=4, low=8, high=220
        )
        live = {
            "sessions": _next_int(
                prev_modules["live"]["sessions"], drift=drifts["live"] * 0.25, noise=0.4, low=1, high=18
            ),
            "viewers": live_viewers,
            "peakOnline": max(
                live_viewers,
                _next_int(
                    prev_modules["live"]["peakOnline"],
                    drift=drifts["live"],
                    noise=3,
                    low=live_viewers,
                    high=260,
                ),
            ),
            "interactionRate": _next_float(
                prev_modules["live"]["interactionRate"],
                drift=random.uniform(-0.025, 0.025),
                noise=0.5,
                low=6.0,
                high=70.0,
                digits=1,
            ),
        }

        return {
            "updatedAt": now.isoformat(),
            "overview": overview,
            "modules": {
                "order": order,
                "video": video,
                "exam": exam,
                "production": production,
                "offline": offline,
                "supervise": supervise,
                "live": live,
            },
            "trafficTrend": self._predict_traffic(prev["trafficTrend"], now, drifts),
            "sourceShare": self._predict_share(prev["sourceShare"], drifts),
            "topRank": self._build_rank(prev.get("topRank")),
            "realtimeEvents": self._build_events(prev.get("realtimeEvents"), count=10),
            "regions": self._build_regions(prev.get("regions"), drifts),
        }

    def _predict_traffic(
        self,
        prev_traffic: list[dict[str, Any]],
        now: datetime,
        drifts: dict[str, float],
    ) -> list[dict[str, Any]]:
        last = prev_traffic[-1] if prev_traffic else {key: 16 for key in TRAFFIC_KEYS}
        point = {"time": _format_hm(now)}
        for key in TRAFFIC_KEYS:
            point[key] = _next_int(
                int(last.get(key, 16)),
                drift=drifts[key],
                noise=3,
                low=2,
                high=180,
            )
        traffic = list(prev_traffic[1:]) if len(prev_traffic) >= 24 else list(prev_traffic)
        traffic.append(point)
        while len(traffic) < 24:
            traffic.insert(0, deepcopy(traffic[0]))
        return traffic[-24:]

    def _predict_share(
        self,
        prev_share: list[dict[str, Any]],
        drifts: dict[str, float],
    ) -> list[dict[str, Any]]:
        weights = {
            "线下辅导": 1 + drifts["offline"] * 2,
            "直播课": 1 + drifts["live"] * 2,
            "学习视频": 1 + drifts["video"] * 2,
            "在线督导": 1 + drifts["supervise"] * 2,
            "订单报名": 1 + drifts["order"] * 2,
        }
        raw: list[tuple[str, float]] = []
        for item in prev_share:
            name = item["name"]
            value = float(item["value"]) * weights.get(name, 1.0)
            value = _clamp(value + random.uniform(-1.0, 1.0), 6, 42)
            raw.append((name, value))

        total = sum(v for _, v in raw) or 1
        normalized = [(name, v / total * 100) for name, v in raw]
        ints = [int(round(v)) for _, v in normalized]
        diff = 100 - sum(ints)
        ints[-1] += diff
        return [{"name": name, "value": max(1, ints[i])} for i, (name, _) in enumerate(normalized)]

    def _build_rank(self, prev_rank: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not prev_rank:
            items = []
            for module, name in random.sample(RANK_POOL, k=8):
                low, high = RANK_BASE[module]
                items.append({"module": module, "name": name, "value": random.randint(low, high)})
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
                        noise=max(2, item["value"] * 0.03),
                        low=4,
                        high=600,
                    ),
                }
            )

        if random.random() < 0.28:
            module, name = random.choice(RANK_POOL)
            if all(x["name"] != name for x in items):
                replace_at = random.randrange(len(items))
                items[replace_at] = {
                    "module": module,
                    "name": name,
                    "value": max(6, int(items[replace_at]["value"] * random.uniform(0.7, 1.1))),
                }

        return sorted(items, key=lambda x: x["value"], reverse=True)

    def _build_regions(
        self,
        prev_regions: list[dict[str, Any]] | None,
        drifts: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        drift_by_module = drifts or {key: 0.0 for key in TRAFFIC_KEYS}
        seed_map = {item["name"]: item for item in REGION_SEED}

        if (
            not prev_regions
            or any("lng" not in item for item in prev_regions)
            or {item["name"] for item in prev_regions} != set(seed_map)
        ):
            return [
                {
                    "name": item["name"],
                    "lng": item["lng"],
                    "lat": item["lat"],
                    "province": item["province"],
                    "module": item["module"],
                    "value": int(item["base"] * random.uniform(0.88, 1.12)),
                }
                for item in REGION_SEED
            ]

        regions: list[dict[str, Any]] = []
        for item in prev_regions:
            module = item.get("module", "order")
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
                        noise=max(3, int(item["value"]) * 0.03),
                        low=12,
                        high=480,
                    ),
                }
            )
        return sorted(regions, key=lambda x: x["value"], reverse=True)

    def _make_event(self, at: datetime) -> dict[str, Any]:
        module, template = random.choice(EVENT_TEMPLATES)
        n = random.randint(1, 48)
        return {
            "id": f"{int(at.timestamp() * 1000)}-{random.randint(100, 999)}",
            "time": _format_hms(at),
            "module": module,
            "message": template.format(n=n),
        }

    def _build_events(
        self,
        prev_events: list[dict[str, Any]] | None,
        *,
        count: int,
    ) -> list[dict[str, Any]]:
        now = _now()
        if not prev_events:
            return [self._make_event(now - timedelta(seconds=i * 5)) for i in range(count)]
        newest = self._make_event(now)
        return [newest, *prev_events][:count]


predictor = DashboardPredictor()
