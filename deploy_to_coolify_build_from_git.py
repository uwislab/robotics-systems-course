"""
deploy_to_coolify.py
自动将 MkDocs 静态站点部署到 Coolify v4
流程: 直接触发 Coolify 强制重建
"""

import sys
import os
import requests
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── 从 .env 加载敏感配置 ──────────────────────────────────────────────────────
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_file):
    for _line in open(_env_file):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ─── 配置区 ────────────────────────────────────────────────────────────────────
COOLIFY_BASE  = "https://coolify.uwis.cn/api/v1"
API_KEY       = os.environ.get("COOLIFY_API_KEY", "")
PROJECT_NAME  = "Robotics_Systems_Course"
APP_NAME      = "robotics_systems_course"
GIT_REPO      = "https://github.com/uwislab/robotics-systems-course.git"
GIT_BRANCH    = "main"
DOMAIN        = "https://robotic.uwis.cn"
ENVIRONMENT   = "production"
LOCAL_DIR     = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录
DOCKER_COMPOSE_SERVICE_NAME = "web"
# ──────────────────────────────────────────────────────────────────────────────

if not API_KEY:
    print("❌ 缺少必要配置，请确保 .env 文件包含 COOLIFY_API_KEY")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def api(method, path, **kwargs):
    url = f"{COOLIFY_BASE}{path}"
    resp = requests.request(method, url, headers=HEADERS, verify=False, **kwargs)
    return resp

def step(msg):
    print(f"\n{'='*55}\n  {msg}\n{'='*55}")

def ensure_compose_domain(app_uuid, domain_url, service_name=DOCKER_COMPOSE_SERVICE_NAME):
    payload = {
        "docker_compose_domains": [
            {"name": service_name, "domain": domain_url}
        ]
    }
    resp = api("PATCH", f"/applications/{app_uuid}", json=payload)
    if resp.ok:
        print(f"✅ 已配置 docker_compose_domains: {service_name} -> {domain_url}")
    else:
        print(f"⚠️  配置 docker_compose_domains 失败 HTTP {resp.status_code}: {resp.text}")
    return resp.ok

def fetch_application_logs(app_uuid):
    try:
        resp = api("GET", f"/applications/{app_uuid}/logs")
        if not resp.ok:
            return None
        data = resp.json()
    except Exception:
        return None

    if isinstance(data, dict):
        logs = data.get("logs", "")
        return logs if isinstance(logs, str) else ""

    if isinstance(data, str):
        return data

    return ""

def print_new_log_lines(full_logs, last_logs):
    if not full_logs or full_logs == last_logs:
        return full_logs

    if last_logs and full_logs.startswith(last_logs):
        delta = full_logs[len(last_logs):]
    else:
        # If logs rotated/truncated, print tail to resync view.
        tail_lines = full_logs.splitlines()[-30:]
        delta = "\n".join(tail_lines)
        if delta:
            delta = "[log window reset]\n" + delta

    for line in delta.splitlines():
        line = line.rstrip()
        if line:
            print(f"  [deploy-log] {line}")

    return full_logs

def wait_for_site_ready(
    base_url,
    app_uuid=None,
    timeout_sec=240,
    interval_sec=8,
    min_wait_sec=40,
    stable_rounds=3,
):
    deadline = time.time() + timeout_sec
    started_at = time.time()
    checks = [
        f"{base_url}/",
        f"{base_url}/assets/stylesheets/main.484c7ddc.min.css",
        f"{base_url}/assets/javascripts/bundle.79ae519e.min.js",
    ]
    request_headers = {
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    }
    last_status = {}
    success_streak = 0
    last_logs = ""

    print(
        f"⏳ 等待站点就绪（最多 {timeout_sec} 秒，至少等待 {min_wait_sec} 秒，连续 {stable_rounds} 轮通过）..."
    )
    while time.time() < deadline:
        if app_uuid:
            logs = fetch_application_logs(app_uuid)
            if logs is not None:
                last_logs = print_new_log_lines(logs, last_logs)

        all_ok = True
        for url in checks:
            try:
                r = requests.get(
                    url,
                    timeout=10,
                    verify=False,
                    headers=request_headers,
                    params={"_health": str(int(time.time()))},
                )
                last_status[url] = r.status_code
                if r.status_code != 200:
                    all_ok = False
                    continue

                if url.endswith("/"):
                    body = (r.text or "").lower()
                    if not all(marker in body for marker in ["<html", "assets/stylesheets"]):
                        all_ok = False
                        last_status[url] = "200-but-invalid-html"
            except requests.RequestException:
                all_ok = False
                last_status[url] = "ERR"

        elapsed = int(time.time() - started_at)

        if all_ok and elapsed >= min_wait_sec:
            success_streak += 1
        else:
            success_streak = 0

        if success_streak >= stable_rounds:
            print("✅ 站点已稳定就绪，首页内容与关键静态资源可访问")
            return True

        print(
            f"  站点未稳定就绪，{interval_sec}s 后重试: "
            f"elapsed={elapsed}s, streak={success_streak}/{stable_rounds}, status={last_status}"
        )
        time.sleep(interval_sec)

    print("❌ 站点在等待窗口内仍未稳定就绪，请检查 Coolify 部署日志")
    print(f"  最后探测状态: {last_status}")
    return False

# ─── Step 1: 确认本地源文件完整 ──────────────────────────────────────────────
step("Step 1: 检查源文件")
for required in ["mkdocs.yml", "docs", "nginx.conf"]:
    if not os.path.exists(os.path.join(LOCAL_DIR, required)):
        print(f"❌ 缺少必要文件: {required}")
        sys.exit(1)
print("✅ 源文件检查通过（MkDocs 将在 Coolify 容器内构建）")

# ─── Step 2: 查找 Coolify 项目 ───────────────────────────────────────────────
step("Step 2: 查找/创建 Coolify 项目")
resp = api("GET", "/projects")
resp.raise_for_status()
projects = resp.json()
project = next((p for p in projects if p["name"] == PROJECT_NAME), None)

if project:
    PROJECT_UUID = project["uuid"]
    print(f"✅ 已有项目: {PROJECT_NAME}  uuid={PROJECT_UUID}")
else:
    resp = api("POST", "/projects",
               json={"name": PROJECT_NAME, "description": "机器人系统课程静态站点"})
    resp.raise_for_status()
    PROJECT_UUID = resp.json()["uuid"]
    print(f"✅ 已创建项目: {PROJECT_NAME}  uuid={PROJECT_UUID}")

# ─── Step 3: 获取 Server UUID ─────────────────────────────────────────────────
step("Step 3: 获取可用 Server")
resp = api("GET", "/servers")
resp.raise_for_status()
server = next((s for s in resp.json() if s.get("is_usable")), None)
if not server:
    print("❌ 没有可用 Server，请在 Coolify 面板确认服务器状态")
    sys.exit(1)
SERVER_UUID = server["uuid"]
print(f"✅ Server: {server['name']}  uuid={SERVER_UUID}")

# ─── Step 4: 查找或创建应用 ──────────────────────────────────────────────────
step("Step 4: 查找已有应用 / 创建新应用")
resp = api("GET", "/applications")
resp.raise_for_status()
apps = resp.json()

git_suffix = GIT_REPO.split("github.com/")[-1]  # uwislab/robotics-systems-course.git
app = next(
    (a for a in apps if
     a.get("git_repository") == git_suffix or
     a.get("git_repository") == GIT_REPO or
     a.get("name") == APP_NAME or
     a.get("fqdn") == DOMAIN),
    None
)

if app:
    APP_UUID = app["uuid"]
    print(f"✅ 已有应用: {app.get('name')}  uuid={APP_UUID}")

    # 确保使用 dockercompose buildpack（通过 docker-compose.yml 的 build.network: host 绕过 BuildKit 限制）
    patch = api("PATCH", f"/applications/{APP_UUID}", json={
        "build_pack":      "dockercompose",
        "install_command": "",
    })
    if patch.ok:
        print(f"✅ 应用配置已更新（build_pack=dockercompose）")

    ensure_compose_domain(APP_UUID, DOMAIN)

    step("Step 5: 强制重建并部署（force_rebuild=true）")
    # POST /start with force_rebuild=true 让 Coolify 忽略 SHA 缓存重新构建镜像
    resp = api("POST", f"/applications/{APP_UUID}/start",
               json={"force_rebuild": True})
    data = resp.json()
    print(f"  API 响应: {data}")
    if resp.ok or "queued" in str(data).lower() or "deployment" in str(data).lower():
        print(f"✅ 强制重建已触发")
    else:
        print(f"❌ 触发失败 HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)

    if not wait_for_site_ready(DOMAIN, app_uuid=APP_UUID):
        sys.exit(1)

    print(f"\n🌐 站点地址: {DOMAIN}")
    print("🎉 你现在可以直接访问查看课程内容")

else:
    step("Step 5: 创建静态站点应用并立即部署")
    payload = {
        "project_uuid":           PROJECT_UUID,
        "server_uuid":            SERVER_UUID,
        "environment_name":       ENVIRONMENT,
        "git_repository":         GIT_REPO,
        "git_branch":             GIT_BRANCH,
        "build_pack":             "dockercompose",
        "name":                   APP_NAME,
        "docker_compose_domains": [{
            "name": DOCKER_COMPOSE_SERVICE_NAME,
            "domain": DOMAIN,
        }],
        "is_auto_deploy_enabled": True,
        "instant_deploy":         True,
        "ports_exposes":          "80",
    }
    resp = api("POST", "/applications/public", json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        APP_UUID = data.get("uuid")
        if not wait_for_site_ready(DOMAIN, app_uuid=APP_UUID):
            sys.exit(1)
        print(f"✅ 应用创建成功！  uuid={APP_UUID}")
        print(f"🌐 站点地址: {data.get('domains', DOMAIN)}")
        print("🎉 你现在可以直接访问查看课程内容")
    else:
        print(f"❌ 创建失败 HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)
