"""API 级端到端冒烟：登录 → 上传 → SSE 检测流(S2) → 角色裁剪 → S5 复核中断/恢复 → 会话回放。
用法（backend 目录，服务已启动）：uv run python scripts/smoke_api.py
"""
import asyncio
import os
import json
import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

BASE = os.environ.get("QC_BASE", "http://127.0.0.1:8000")
TINY_JPEG = base64_bytes = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1c\x1c\x1c \x1e\x1d #\" \x1c%,\"$(#!,/\x31.  \x1f/3\x1e-/)&1A;A>@FHKJG?;CEGaLGGJHFkY^dm`kfjRgJfifhsadpQnz\x83\x8ay\x82ko\xc1\\\x7fw\x89\x80\x8e\x90\x8c\x86\x8b\x8e\x9f\x97\x95\x8f\x9c\xaa\x9e\xa6\xaa\xb0\xa6\xb1\xa2\xad\xa9\xb2\xff\xc9\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xcc\x00\x06\x00\x10\x10\x05\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9"
)


def sse_summary(events: list[dict]) -> None:
    tokens = "".join(e["data"].get("delta", "") for e in events if e["event"] == "token")
    print("  事件序列:", " → ".join(f"{e['event']}" for e in events if e["event"] != "token"))
    print("  打字机文本:", tokens.replace("\n", " ")[:120], "…")


async def collect_stream(client: httpx.AsyncClient, url: str, payload: dict, token: str) -> list[dict]:
    events = []
    async with client.stream("POST", url, json=payload, headers={"Authorization": f"Bearer {token}"}) as resp:
        assert resp.status_code == 200, await resp.aread()
        current: dict = {}
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                current = {"event": line[6:].strip(), "data": ""}
            elif line.startswith("data:") and current:
                raw = line[5:].strip()
                try:
                    current["data"] = json.loads(raw)
                except json.JSONDecodeError:
                    current["data"] = raw
                events.append(current)
                if current["event"] in ("done", "error"):
                    break
    return events


async def login(client, username, password):
    r = await client.post(f"{BASE}/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def main() -> None:
    async with httpx.AsyncClient(timeout=120) as c:
        print("== 1) 三角色登录 ==")
        op, eng, adm = await login(c, "operator", "Operator@123"), \
            await login(c, "engineer", "Engineer@123"), await login(c, "admin", "Admin@123")
        print("  ✅ operator / engineer / admin 登录成功")

        print("== 2) 操作工上传图片 (S2 立柱) ==")
        r = await c.post(f"{BASE}/api/v1/upload/image",
                         files={"file": ("S2.jpg", TINY_JPEG, "image/jpeg")},
                         headers={"Authorization": f"Bearer {op}"})
        assert r.status_code == 200, r.text
        image_key = r.json()["image_key"]
        print(f"  ✅ image_key = {image_key}")

        print("== 3) 操作工发起检测 (SSE 全流程) ==")
        events = await collect_stream(c, f"{BASE}/api/v1/chat/stream",
                                      {"message": "检测立柱 CL-ZH02-B，批次 B2026-09-01", "image_key": image_key}, op)
        sse_summary(events)
        done = next(e for e in events if e["event"] == "done")
        session_id, insp_id = done["data"]["session_id"], done["data"]["inspection_id"]
        status = done["data"]["status"]
        print(f"  ✅ 终态 status={status} inspection_id={insp_id} session={session_id[:8]}…")
        assert status == "fail", "S2 应判定不合格"
        cv_ev = next(e for e in events if e["event"] == "cv_result")
        assert cv_ev["data"]["detections"][0]["defect_type"] == "sagging"

        print("== 4) 角色字段裁剪对比（同一检测记录） ==")
        r_op = await c.get(f"{BASE}/api/v1/inspections/{insp_id}", headers={"Authorization": f"Bearer {op}"})
        r_eng = await c.get(f"{BASE}/api/v1/inspections/{insp_id}", headers={"Authorization": f"Bearer {eng}"})
        op_keys, eng_keys = set(r_op.json().keys()), set(r_eng.json().keys())
        print(f"  操作工可见字段: {sorted(op_keys)}")
        print("  ✅ 操作工无量化字段:", not ({"cv_result", "analysis_report", "standard_gaps"} & op_keys))
        print("  ✅ 工艺员有全量字段:", {"cv_result", "analysis_report", "standard_gaps"} <= eng_keys)

        print("== 5) 会话回放（含图片与检测关联） ==")
        r = await c.get(f"{BASE}/api/v1/conversations/{session_id}/messages", headers={"Authorization": f"Bearer {op}"})
        body = r.json()
        msgs = body["messages"]
        user_msgs = [m for m in msgs if m["role"] == "user"]
        print(f"  ✅ 回放 {len(msgs)} 条消息，最后一条角色={msgs[-1]['role']}")
        assert msgs[-1]["role"] == "assistant"
        assert body.get("last_inspection_id") == insp_id, "回放应恢复最近检测 id"
        assert user_msgs and user_msgs[0].get("image"), "回放的用户消息应带签名图片 URL"
        assert user_msgs[0].get("inspection_id") == insp_id, "回放的用户消息应关联检测记录"

        print("== 6) S5 低置信度 → 保守不合格 + 操作工申请复核 + 工艺员处置 ==")
        r = await c.post(f"{BASE}/api/v1/upload/image",
                         files={"file": ("S5.jpg", TINY_JPEG, "image/jpeg")},
                         headers={"Authorization": f"Bearer {op}"})
        image_key5 = r.json()["image_key"]
        events5 = await collect_stream(c, f"{BASE}/api/v1/chat/stream",
                                       {"message": "检测平板 PL-XT05-E", "image_key": image_key5}, op)
        done5 = next(e for e in events5 if e["event"] in ("done", "error"))
        insp5 = done5["data"].get("inspection_id")
        print(f"  ✅ 低置信度保守判定: status={done5['data'].get('status')} 记录#{insp5}")
        assert done5["data"].get("status") == "fail", "S5 低置信度应按不合格处理"

        # 操作工申请复核（REST）→ 创建复核工单
        r = await c.post(f"{BASE}/api/v1/inspections/{insp5}/request-review",
                         json={"comment": "不认可该结果，申请复核"},
                         headers={"Authorization": f"Bearer {op}"})
        req_id = r.json().get("request_id")
        print(f"  ✅ 操作工申请复核: HTTP {r.status_code} -> 工单#{req_id} 状态 {r.json().get('status')}")
        assert r.status_code == 200 and r.json()["status"] == "pending"

        # 复核工作台待处理队列可见（工艺员）
        r = await c.get(f"{BASE}/api/v1/reviews/workbench", params={"box": "pending"},
                        headers={"Authorization": f"Bearer {eng}"})
        ids = [x["inspection_id"] for x in r.json()]
        print(f"  ✅ 复核工作台待处理队列包含记录#{insp5}: {insp5 in ids}")
        assert insp5 in ids

        # 操作工无权处置
        r = await c.post(f"{BASE}/api/v1/reviews/{req_id}/decide",
                         json={"decision": "confirm_fail", "comment": "试一下"},
                         headers={"Authorization": f"Bearer {op}"})
        print(f"  ✅ 操作工处置被拒: HTTP {r.status_code}")
        assert r.status_code == 403

        # 工艺员"驳回重检"（不强制）→ 工单被驳回，操作工侧感叹号
        r = await c.post(f"{BASE}/api/v1/reviews/{req_id}/decide",
                         json={"decision": "reject", "comment": "图像存疑，退回重检", "force": False},
                         headers={"Authorization": f"Bearer {eng}"})
        print(f"  ✅ 工艺员驳回重检: HTTP {r.status_code} -> 工单 {r.json().get('status')}")
        assert r.status_code == 200 and r.json()["status"] == "rejected"

        r = await c.get(f"{BASE}/api/v1/reviews/rejected-count", headers={"Authorization": f"Bearer {op}"})
        print(f"  ✅ 操作工被驳回感叹号: count={r.json().get('count')}")
        assert r.json()["count"] >= 1

        # 操作工申请驳回重申（备注必填）
        r = await c.post(f"{BASE}/api/v1/reviews/{req_id}/reapply",
                         json={"comment": "已核对工件与批次，申请重新复核"},
                         headers={"Authorization": f"Bearer {op}"})
        print(f"  ✅ 操作工申请驳回重申: HTTP {r.status_code} -> 工单 {r.json().get('status')}")
        assert r.status_code == 200 and r.json()["status"] == "reapply"

        # 工艺员对重申单处置：不得再驳回
        r = await c.post(f"{BASE}/api/v1/reviews/{req_id}/decide",
                         json={"decision": "reject", "comment": "再驳一次"},
                         headers={"Authorization": f"Bearer {eng}"})
        print(f"  ✅ 重审单驳回被拒: HTTP {r.status_code}")
        assert r.status_code == 400

        # 工艺员最终确认不合格
        r = await c.post(f"{BASE}/api/v1/reviews/{req_id}/decide",
                         json={"decision": "confirm_fail", "comment": "确认为光照问题，维持不合格"},
                         headers={"Authorization": f"Bearer {eng}"})
        print(f"  ✅ 工艺员最终处置: HTTP {r.status_code} -> 系统状态 {r.json().get('inspection_status')}")
        assert r.status_code == 200 and r.json()["inspection_status"] == "fail"

        # 全部复核里该工单应为已复核
        r = await c.get(f"{BASE}/api/v1/reviews/my", params={"box": "all"},
                        headers={"Authorization": f"Bearer {op}"})
        mine = next((x for x in r.json() if x["id"] == req_id), None)
        print(f"  ✅ 全部复核中工单状态: {mine.get('review_status')} | 处理人 {mine.get('reviewer')}")
        assert mine and mine["review_status"] == "done"

        print("== 7) 检测数据库（去重视图） ==")
        # 同一工件+同批次连测两次（保证全新库上 count=2），再验证与其它批次互相独立
        for i in (1, 2):
            r = await c.post(f"{BASE}/api/v1/upload/image",
                             files={"file": (f"S2db{i}.jpg", TINY_JPEG, "image/jpeg")},
                             headers={"Authorization": f"Bearer {op}"})
            await collect_stream(c, f"{BASE}/api/v1/chat/stream",
                                 {"message": "检测立柱 CL-ZH02-B，批次 B-DBTEST", "image_key": r.json()["image_key"]}, op)

        r = await c.get(f"{BASE}/api/v1/inspections/database",
                        params={"workpiece_no": "CL-ZH02-B"}, headers={"Authorization": f"Bearer {eng}"})
        items = r.json()["items"]
        btest = next((x for x in items if x["batch_no"] == "B-DBTEST"), None)
        b1 = next((x for x in items if x["batch_no"] == "B2026-09-01"), None)
        latest_id = btest["inspection_id"] if btest else None
        print(f"  ✅ 同批次两次检测合并为一条: 存在={btest is not None}, 次数={btest['check_count'] if btest else 0}")
        assert btest and btest["check_count"] >= 2, "同批次多次检测应合并且计数>=2"
        print(f"  ✅ 不同批次独立成条: B2026-09-01 存在={b1 is not None}（与 B-DBTEST 互不合并）")
        assert b1 is not None and b1["inspection_id"] != latest_id

        # latest-wins：再测一次确认结论取最新那条的 id
        r = await c.post(f"{BASE}/api/v1/upload/image",
                         files={"file": ("S2db3.jpg", TINY_JPEG, "image/jpeg")},
                         headers={"Authorization": f"Bearer {op}"})
        ev3 = await collect_stream(c, f"{BASE}/api/v1/chat/stream",
                                   {"message": "检测立柱 CL-ZH02-B，批次 B-DBTEST", "image_key": r.json()["image_key"]}, op)
        done3 = next(e for e in ev3 if e["event"] in ("done", "error"))["data"]
        r = await c.get(f"{BASE}/api/v1/inspections/database",
                        params={"workpiece_no": "CL-ZH02-B"}, headers={"Authorization": f"Bearer {eng}"})
        btest2 = next((x for x in r.json()["items"] if x["batch_no"] == "B-DBTEST"), None)
        print(f"  ✅ latest-wins: 第三次检测 id={done3.get('inspection_id')} == 库中展示 id={btest2['inspection_id']}, 次数={btest2['check_count']}")
        assert btest2["inspection_id"] == done3.get("inspection_id") and btest2["check_count"] >= 3

        # 操作工字段裁剪
        r = await c.get(f"{BASE}/api/v1/inspections/database",
                        params={"workpiece_no": "CL-ZH02-B"}, headers={"Authorization": f"Bearer {op}"})
        op_item = next((x for x in r.json()["items"] if x["batch_no"] == "B-DBTEST"), None)
        print(f"  ✅ 操作工数据库视角无量化字段: {'cv_result' not in op_item and 'analysis_report' not in op_item}")
        assert "cv_result" not in op_item and "analysis_report" not in op_item

        print("== 8) 审计日志(管理员) ==")
        r = await c.get(f"{BASE}/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {adm}"})
        actions = [x["action"] for x in r.json()]
        print(f"  ✅ 审计动作: {actions[:6]}")

    print("\n===== API 冒烟全部通过 =====")


if __name__ == "__main__":
    import base64
    asyncio.run(main())
