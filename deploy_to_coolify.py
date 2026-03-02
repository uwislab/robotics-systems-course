"""
deploy_to_coolify.py
自动将 MkDocs 静态站点部署到 Coolify v4.0.0-beta.463+
流程: MkDocs 构建 → git push 到 GitHub → Coolify 强制重建
API 路径: POST /api/v1/applications/public
"""

import sys
import os
import requests
import subprocess
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── 配置区 ────────────────────────────────────────────────────────────────────
COOLIFY_BASE  = "https://coolify.uwis.cn/api/v1"
API_KEY       = "1|AORHaWcORiXNBMHrdbPF6x0422mGqf15tY4NWjGNacfcecf7"
PROJECT_NAME  = "robotic_system"
APP_NAME      = "robotic-site"
GIT_REPO      = "https://github.com/uwislab/robotics-systems-course.git"
GIT_REPO_SSH  = "git@github.com:uwislab/robotics-systems-course.git"
GIT_BRANCH    = "main"
DOMAIN        = "http://robotic.uwis.cn"
ENVIRONMENT   = "production"
INSTALL_CMD   = "pip install mkdocs mkdocs-material && mkdocs build"
PUBLISH_DIR   = "site"
LOCAL_DIR     = "/root/robotic_system"
# ──────────────────────────────────────────────────────────────────────────────

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

def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, shell=True, cwd=cwd, check=check,
                          capture_output=False, text=True)

# ─── Step 1: 构建 MkDocs 站点 ─────────────────────────────────────────────────
step("Step 1: 构建 MkDocs 静态站点")
result = subprocess.run(
    ["mkdocs", "build", "-f", "mkdocs.yml"],
    cwd=LOCAL_DIR,
)
if result.returncode != 0:
    print("❌ MkDocs 构建失败，中止部署")
    sys.exit(1)
print("✅ MkDocs 构建成功")

# ─── Step 2: 推送到 GitHub ────────────────────────────────────────────────────
step("Step 2: 推送 MkDocs 源文件到 GitHub")
os.chdir(LOCAL_DIR)

# 确保 .gitignore 不排除 site/ (Coolify 需要在 repo 里找到源文件构建)
gitignore = os.path.join(LOCAL_DIR, ".gitignore")
gitignore_content = ""
if os.path.exists(gitignore):
    with open(gitignore) as f:
        gitignore_content = f.read()
# 只保留不需要的文件排除，确保 mkdocs.yml 和 docs/ 都在
with open(gitignore, "w") as f:
    lines = [l for l in gitignore_content.splitlines() if "docs" not in l.lower()]
    f.write("\n".join(lines))

# 设置 remote
result = subprocess.run("git remote -v", shell=True, cwd=LOCAL_DIR, capture_output=True, text=True)
if "origin" not in result.stdout:
    run(f"git remote add origin {GIT_REPO_SSH}", cwd=LOCAL_DIR)
else:
    run(f"git remote set-url origin {GIT_REPO_SSH}", cwd=LOCAL_DIR)

run("git add .", cwd=LOCAL_DIR)

# 检查是否有变更
status = subprocess.run("git status --porcelain", shell=True, cwd=LOCAL_DIR,
                        capture_output=True, text=True)
if status.stdout.strip():
    run('git commit -m "chore: update course content"', cwd=LOCAL_DIR)
    print("✅ 已提交更改")
else:
    print("ℹ️  暂存区无变更（内容未修改），将强制触发 Coolify 重建")

push_result = subprocess.run(
    f"GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no' "
    f"git push -u origin master:{GIT_BRANCH} --force",
    shell=True, cwd=LOCAL_DIR
)
if push_result.returncode != 0:
    print("❌ git push 失败！")
    print("请先将 SSH 公钥添加到 GitHub：")
    print("  → https://github.com/settings/ssh/new")
    pub = subprocess.run("cat ~/.ssh/id_ed25519.pub", shell=True, capture_output=True, text=True)
    print(f"\n{pub.stdout.strip()}\n")
    sys.exit(1)
print("✅ 内容已推送到 GitHub")

# ─── Step 3: 查找 Coolify 项目 ───────────────────────────────────────────────
step("Step 3: 查找 Coolify 项目和应用")
resp = api("GET", "/projects")
resp.raise_for_status()
projects = resp.json()
project = next((p for p in projects if p["name"] == PROJECT_NAME), None)

if project:
    PROJECT_UUID = project["uuid"]
    print(f"✅ 已有项目: {PROJECT_NAME}  uuid={PROJECT_UUID}")
else:
    resp = api("POST", "/projects", json={"name": PROJECT_NAME, "description": "机器人系统课程静态站点"})
    resp.raise_for_status()
    PROJECT_UUID = resp.json()["uuid"]
    print(f"✅ 已创建项目: {PROJECT_NAME}  uuid={PROJECT_UUID}")

# ─── Step 4: 获取 Server UUID ─────────────────────────────────────────────────
resp = api("GET", "/servers")
resp.raise_for_status()
server = next((s for s in resp.json() if s.get("is_usable")), None)
if not server:
    print("❌ 没有可用 Server")
    sys.exit(1)
SERVER_UUID = server["uuid"]
print(f"✅ Server: {server['name']}  uuid={SERVER_UUID}")

# ─── Step 5: 查找或创建应用 ──────────────────────────────────────────────────
step("Step 5: 查找已有应用 / 创建新应用")
resp = api("GET", "/applications")
resp.raise_for_status()
apps = resp.json()
git_suffix = GIT_REPO.split("github.com/")[-1]
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

    # ─── Step 6: 强制重建并部署 ───────────────────────────────────────────────
    step("Step 6: 强制重建并部署（force=true）")
    resp = api("GET", f"/applications/{APP_UUID}/start?force=true")
    data = resp.json()
    print(f"✅ 部署已触发: {data.get('message', data)}")
    print(f"\n🌐 站点地址: {DOMAIN}")
    print("⏳ 请等待约 1~2 分钟后访问查看课程内容")
else:
    # ─── Step 6: 创建应用 ─────────────────────────────────────────────────────
    step("Step 6: 创建静态站点应用并立即部署")
    payload = {
        "project_uuid":           PROJECT_UUID,
        "server_uuid":            SERVER_UUID,
        "environment_name":       ENVIRONMENT,
        "git_repository":         GIT_REPO,
        "git_branch":             GIT_BRANCH,
        "build_pack":             "static",
        "name":                   APP_NAME,
        "domains":                DOMAIN,
        "is_static":              True,
        "is_auto_deploy_enabled": True,
        "instant_deploy":         True,
        "install_command":        INSTALL_CMD,
        "publish_directory":      PUBLISH_DIR,
        "ports_exposes":          "80",
    }
    resp = api("POST", "/applications/public", json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        APP_UUID = data.get("uuid")
        print(f"✅ 应用创建成功！  uuid={APP_UUID}")
        print(f"🌐 站点地址: {data.get('domains', DOMAIN)}")
        print("⏳ 请等待约 1~2 分钟后访问查看课程内容")
    else:
        print(f"❌ 创建失败 HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── 配置区 ────────────────────────────────────────────────────────────────────
COOLIFY_BASE  = "https://coolify.uwis.cn/api/v1"
API_KEY       = "1|AORHaWcORiXNBMHrdbPF6x0422mGqf15tY4NWjGNacfcecf7"
PROJECT_NAME  = "robotic_system"
APP_NAME      = "robotic-site"
GIT_REPO      = "https://github.com/uwislab/robotics-systems-course.git"
GIT_BRANCH    = "main"
DOMAIN        = "http://robotic.uwis.cn"
ENVIRONMENT   = "production"
INSTALL_CMD   = "pip install mkdocs mkdocs-material && mkdocs build"
PUBLISH_DIR   = "site"
# ──────────────────────────────────────────────────────────────────────────────

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

# ─── Step 1: 构建 MkDocs 站点 ─────────────────────────────────────────────────
step("Step 1: 构建 MkDocs 静态站点")
result = subprocess.run(
    ["mkdocs", "build", "-f", "mkdocs.yml"],
    cwd="/root/robotic_system",
)
if result.returncode != 0:
    print("❌ MkDocs 构建失败，中止部署")
    sys.exit(1)
print("✅ MkDocs 构建成功")

# ─── Step 2: 获取或创建 Coolify 项目 ─────────────────────────────────────────
step("Step 2: 查找/创建 Coolify 项目")
resp = api("GET", "/projects")
resp.raise_for_status()
projects = resp.json()
project = next((p for p in projects if p["name"] == PROJECT_NAME), None)

if project:
    PROJECT_UUID = project["uuid"]
    print(f"✅ 已有项目: {PROJECT_NAME}  uuid={PROJECT_UUID}")
else:
    resp = api("POST", "/projects", json={"name": PROJECT_NAME, "description": "机器人系统课程静态站点"})
    resp.raise_for_status()
    PROJECT_UUID = resp.json()["uuid"]
    print(f"✅ 已创建项目: {PROJECT_NAME}  uuid={PROJECT_UUID}")

# ─── Step 3: 获取 Server UUID ─────────────────────────────────────────────────
step("Step 3: 获取 Server UUID")
resp = api("GET", "/servers")
resp.raise_for_status()
servers = resp.json()
server = next((s for s in servers if s.get("is_usable")), None)
if not server:
    print("❌ 没有可用 Server，请在 Coolify 面板确认服务器状态")
    sys.exit(1)
SERVER_UUID = server["uuid"]
print(f"✅ Server: {server['name']}  uuid={SERVER_UUID}")

# ─── Step 4: 查找已存在的应用（避免重复创建）────────────────────────────────
step("Step 4: 查找已有应用（避免重复创建）")
resp = api("GET", "/applications")
resp.raise_for_status()
apps = resp.json()
# Coolify 存储的 git_repository 会去掉 https://github.com/ 等前缀，用 endswith 或 name 匹配
git_suffix = GIT_REPO.split("github.com/")[-1]  # e.g. uwislab/robotics-systems-course.git
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

    # ─── Step 5: 触发重新部署 ─────────────────────────────────────────────────
    step("Step 5: 触发重新部署")
    resp = api("GET", f"/applications/{APP_UUID}/start")
    data = resp.json()
    print(f"✅ 部署已触发: {data.get('message', data)}")
    print(f"\n🌐 站点地址: {DOMAIN}")
else:
    print("ℹ️  未找到已有应用，将创建新应用")

    # ─── Step 5: 创建静态站点应用并立即部署 ──────────────────────────────────
    step("Step 5: 创建静态站点应用并立即部署")
    payload = {
        "project_uuid":           PROJECT_UUID,
        "server_uuid":            SERVER_UUID,
        "environment_name":       ENVIRONMENT,
        "git_repository":         GIT_REPO,
        "git_branch":             GIT_BRANCH,
        "build_pack":             "static",
        "name":                   APP_NAME,
        "domains":                DOMAIN,
        "is_static":              True,
        "is_auto_deploy_enabled": True,
        "instant_deploy":         True,
        "install_command":        INSTALL_CMD,
        "publish_directory":      PUBLISH_DIR,
        "ports_exposes":          "80",
    }
    resp = api("POST", "/applications/public", json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        APP_UUID = data.get("uuid")
        print(f"✅ 应用创建成功！  uuid={APP_UUID}")
        print(f"🌐 站点地址: {data.get('domains', DOMAIN)}")
    else:
        print(f"❌ 创建失败 HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)
