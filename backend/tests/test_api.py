"""
API 集成测试 — FastAPI TestClient 测试健康检查、提供商、转换路由。
"""

import json
import sys
from pathlib import Path

# 确保 backend 在导入路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# 确保 scripts 可被 converter 引用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthRoutes:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["message"]

    def test_health(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_demo(self):
        r = client.get("/api/demo")
        assert r.status_code in (200, 404)  # demo 文件可能不存在
        if r.status_code == 200:
            text = r.text
            assert "###" in text or "章" in text or "Demo" in text


class TestProviderRoutes:
    def test_list_providers(self):
        r = client.get("/api/providers")
        assert r.status_code == 200
        providers = r.json()
        assert isinstance(providers, list)
        assert len(providers) >= 4
        keys = [p["key"] for p in providers]
        assert "deepseek" in keys
        assert "anthropic" in keys
        assert "openai" in keys

    def test_test_provider_no_key(self):
        r = client.post("/api/providers/test", json={
            "provider": "custom",
            "api_key": "fake-key",
            "base_url": "http://localhost:99999/v1",
        })
        # 连接失败也应该是 200（返回 ok=False）
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "provider" in data

    def test_test_provider_unknown(self):
        r = client.post("/api/providers/test", json={
            "provider": "nonexistent",
            "api_key": "x",
        })
        assert r.status_code == 400

    def test_test_provider_validation(self):
        """缺少 api_key 字段应返回 422"""
        r = client.post("/api/providers/test", json={"provider": "deepseek"})
        assert r.status_code == 422


class TestConvertRoutes:
    def test_get_nonexistent_task(self):
        r = client.get("/api/convert/nonexistent-id-12345")
        assert r.status_code == 404

    def test_convert_no_files(self):
        """不上传文件应返回 422"""
        r = client.post("/api/convert")
        assert r.status_code == 422

    def test_convert_rule_mode(self):
        """规则模式转换 — 上传示例小说"""
        demo_path = Path(__file__).resolve().parent.parent.parent / "examples" / "demo_novel_3chapters.md"
        if not demo_path.exists():
            pytest.skip("demo_novel_3chapters.md not found")

        with open(demo_path, "rb") as f:
            content = f.read()

        files = {"files": ("demo.md", content, "text/plain")}
        data = {
            "script_type": "manju",
            "mode": "rule",
            "panel_mode": "simple",
            "title": "集成测试剧本",
            "episode_config": json.dumps({
                "enabled": True,
                "target_episodes": 3,
                "hook_style": "twist",
                "title_template": "第{n}集 · {subtitle}",
            }),
        }

        r = client.post("/api/convert", files=files, data=data)
        assert r.status_code == 200
        result = r.json()
        assert "task_id" in result
        task_id = result["task_id"]

        # 轮询等待任务完成
        import time
        for _ in range(30):
            status_r = client.get(f"/api/convert/{task_id}")
            assert status_r.status_code == 200
            status_data = status_r.json()
            if status_data["status"] in ("completed", "failed"):
                break
            time.sleep(0.5)

        assert status_r.status_code == 200
        final = status_r.json()
        assert final["status"] == "completed", f"Task failed: {final.get('error')}"
        assert final["script_type"] == "manju"
        assert final["total_scenes"] is not None
        assert final["total_beats"] is not None
        assert final["title"] == "集成测试剧本"
        # timing 字段
        assert final.get("timing") is not None
        assert final["download_url"] is not None

        # 下载 YAML
        dl = client.get(final["download_url"])
        assert dl.status_code == 200
        assert "script:" in dl.text

    def test_convert_invalid_script_type(self):
        """无效 script_type 应返回 422"""
        r = client.post("/api/convert", data={"script_type": "invalid"})
        assert r.status_code == 422
