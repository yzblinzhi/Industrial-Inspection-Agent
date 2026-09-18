"""建库 + 种子数据（幂等）：
1. alembic upgrade head 建 6 张表；
2. 写入 3 个角色账号、5 个工件及结构化标准（对应评测场景 S1-S5）。
用法（backend 目录）：uv run python scripts/init_db.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    print("[init_db] alembic upgrade head 完成")


SEED_USERS = [
    {"username": "admin", "password": "Admin@123", "role": "admin", "display_name": "系统管理员"},
    {"username": "engineer", "password": "Engineer@123", "role": "process_engineer", "display_name": "王工艺员"},
    {"username": "operator", "password": "Operator@123", "role": "operator", "display_name": "张操作工"},
]

_STD = lambda **kw: kw  # noqa: E731

SEED_WORKPIECES = [
    {
        "workpiece_no": "FL-PN18-A", "name": "法兰盘A", "material": "Q235",
        "coating_spec": "环氧底漆+聚氨酯面漆",
        "standards": [
            _STD(defect_type="sagging", max_area_cm2=5.0, max_count=2, confidence_threshold=0.6),
            _STD(defect_type="orange_peel", max_area_cm2=3.0, confidence_threshold=0.6),
            _STD(defect_type="color_deviation", confidence_threshold=0.6, extra_rules={"max_delta_e": 1.5}),
            _STD(defect_type="particle", max_area_cm2=0.5, max_count=3, confidence_threshold=0.6),
        ],
    },
    {
        "workpiece_no": "CL-ZH02-B", "name": "立柱B", "material": "45钢",
        "coating_spec": "环氧富锌底漆+丙烯酸面漆",
        "standards": [
            _STD(defect_type="sagging", max_area_cm2=5.0, confidence_threshold=0.6),
            _STD(defect_type="orange_peel", max_area_cm2=3.0, confidence_threshold=0.6),
            _STD(defect_type="particle", max_area_cm2=0.5, max_count=3, confidence_threshold=0.6),
        ],
    },
    {
        "workpiece_no": "PN-MB03-C", "name": "面板C", "material": "SPCC",
        "coating_spec": "粉末喷涂",
        "standards": [
            _STD(defect_type="color_deviation", confidence_threshold=0.6, extra_rules={"max_delta_e": 1.5}),
            _STD(defect_type="sagging", max_area_cm2=5.0, confidence_threshold=0.6),
        ],
    },
    {
        "workpiece_no": "DR-MB07-D", "name": "门板D", "material": "冷轧板",
        "coating_spec": "聚氨酯面漆",
        "standards": [
            _STD(defect_type="sagging", max_area_cm2=5.0, confidence_threshold=0.6),
            _STD(defect_type="orange_peel", max_area_cm2=2.5, confidence_threshold=0.6),
            _STD(defect_type="particle", max_area_cm2=0.5, confidence_threshold=0.6),
            _STD(defect_type="color_deviation", confidence_threshold=0.6, extra_rules={"max_delta_e": 1.5}),
        ],
    },
    {
        "workpiece_no": "PL-XT05-E", "name": "平板E", "material": "铝板",
        "coating_spec": "氟碳面漆",
        "standards": [
            _STD(defect_type="sagging", max_area_cm2=5.0, confidence_threshold=0.6),
            _STD(defect_type="particle", max_area_cm2=0.5, confidence_threshold=0.6),
        ],
    },
]


async def seed() -> None:
    from app.core.db import SessionLocal
    from app.core.security import hash_password
    from app.models import QualityStandard, User, Workpiece

    async with SessionLocal() as session:
        for u in SEED_USERS:
            exists = (
                await session.execute(select(User).where(User.username == u["username"]))
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    User(
                        username=u["username"],
                        password_hash=hash_password(u["password"]),
                        role=u["role"],
                        display_name=u["display_name"],
                    )
                )
                print(f"[init_db] 创建用户 {u['username']}({u['role']})")
        await session.flush()

        for wp in SEED_WORKPIECES:
            exists = (
                await session.execute(
                    select(Workpiece).where(Workpiece.workpiece_no == wp["workpiece_no"])
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            w = Workpiece(
                workpiece_no=wp["workpiece_no"],
                name=wp["name"],
                material=wp["material"],
                coating_spec=wp["coating_spec"],
            )
            session.add(w)
            await session.flush()
            for std in wp["standards"]:
                session.add(QualityStandard(workpiece_id=w.id, **std))
            print(f"[init_db] 创建工件 {wp['workpiece_no']}（{len(wp['standards'])} 条标准）")
        await session.commit()


if __name__ == "__main__":
    run_migrations()
    asyncio.run(seed())
    print("[init_db] 全部完成")
