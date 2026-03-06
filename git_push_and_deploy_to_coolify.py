"""
deploy_to_coolify.py
自动将 MkDocs 静态站点部署到 Coolify v4
流程: MkDocs 构建 → git push 到 GitHub → Coolify 强制重建
"""

import sys
import os
import re
import shlex
import shutil
import tempfile
import requests
import time
import subprocess
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
PROJECT_NAME  = "robotic_system"
APP_NAME      = "robotic-site"
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GIT_REPO      = "https://github.com/uwislab/robotics-systems-course.git"
GIT_REPO_AUTH = f"https://{GITHUB_TOKEN}@github.com/uwislab/robotics-systems-course.git"
GIT_BRANCH    = "main"
DOMAIN        = "https://robotic.uwis.cn"
ENVIRONMENT   = "production"
LOCAL_DIR     = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录
# ──────────────────────────────────────────────────────────────────────────────

if not API_KEY or not GITHUB_TOKEN:
    print("❌ 缺少必要配置，请确保 .env 文件包含 COOLIFY_API_KEY 和 GITHUB_TOKEN")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

CC_PATTERN = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?: .+"
)

def api(method, path, **kwargs):
    url = f"{COOLIFY_BASE}{path}"
    resp = requests.request(method, url, headers=HEADERS, verify=False, **kwargs)
    return resp

def step(msg):
    print(f"\n{'='*55}\n  {msg}\n{'='*55}")

def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, shell=True, cwd=cwd, check=check,
                          capture_output=False, text=True)

def run_capture(cmd, cwd=None, check=False):
    return subprocess.run(cmd, shell=True, cwd=cwd, check=check,
                          capture_output=True, text=True)

def detect_copilot_cli():
    env_bin = os.environ.get("COPILOT_CLI", "").strip()
    if env_bin and os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
        return env_bin

    which_bin = shutil.which("copilot")
    if which_bin:
        return which_bin

    vscode_bin = os.path.expanduser(
        "~/.vscode-server/data/User/globalStorage/github.copilot-chat/copilotCli/copilot"
    )
    if os.path.isfile(vscode_bin) and os.access(vscode_bin, os.X_OK):
        return vscode_bin

    return None

def generate_commit_message(cwd):
    fallback = "chore: update course content"

    # Only use staged diff so message matches what is actually committed.
    diff_res = run_capture("git diff --cached --no-color", cwd=cwd)
    diff_text = (diff_res.stdout or "").strip()
    if not diff_text:
        return fallback

    # Keep prompt size bounded to avoid oversized command input.
    diff_excerpt = diff_text[:8000]

    # Uses new Copilot CLI prompt mode for non-interactive generation.
    prompt = (
        "Generate ONE Conventional Commit title from this staged git diff. "
        "Output only one line in format type(scope): subject, max 72 chars, no quotes, no code block.\\n\\n"
        f"{diff_excerpt}"
    )

    copilot_bin = detect_copilot_cli()
    if not copilot_bin:
        print("⚠️  未找到 Copilot CLI，使用默认提交信息")
        return fallback

    copilot_res = subprocess.run(
        [copilot_bin, "-p", prompt, "--silent", "--allow-all-tools"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )

    if copilot_res.returncode != 0:
        print("⚠️  Copilot CLI 不可用或调用失败，使用默认提交信息")
        return fallback

    lines = [line.strip() for line in (copilot_res.stdout or "").splitlines() if line.strip()]
    if not lines:
        print("⚠️  Copilot 未返回提交信息，使用默认提交信息")
        return fallback

    commit_msg = lines[0].strip("` ")
    if not CC_PATTERN.match(commit_msg):
        print("⚠️  Copilot 返回格式不符合 Conventional Commits，使用默认提交信息")
        return fallback

    return commit_msg

def edit_commit_message_tui(initial_message):
    editor_env = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    editor_cmd = shlex.split(editor_env) if editor_env else None
    if not editor_cmd:
        for candidate in ("nano", "vim", "vi"):
            if shutil.which(candidate):
                editor_cmd = [candidate]
                break

    if not editor_cmd:
        print("⚠️  未找到可用终端编辑器，请设置 EDITOR 或安装 nano/vim")
        return None

    fd, path = tempfile.mkstemp(prefix="commit-msg-", suffix=".txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(initial_message.strip() + "\n")

        res = subprocess.run(editor_cmd + [path], check=False)
        if res.returncode != 0:
            print("⚠️  编辑器非正常退出，保留原提交信息")
            return None

        with open(path, "r", encoding="utf-8") as f:
            lines = [
                line.strip() for line in f
                if line.strip() and not line.lstrip().startswith("#")
            ]

        if not lines:
            print("⚠️  未输入有效提交信息，保留原提交信息")
            return None

        return lines[0]
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

def review_commit_message(initial_message):
    commit_message = initial_message.strip() or "chore: update course content"

    # Keep non-interactive runs deterministic (CI/cron) and avoid waiting for input.
    if not sys.stdin.isatty():
        print(f"📝 commit message: {commit_message}")
        print("⚠️  非交互终端，跳过人工确认，继续提交")
        return commit_message, True

    while True:
        print("\n--- Commit Message Review ---")
        print(f"当前提交信息: {commit_message}")
        if not CC_PATTERN.match(commit_message):
            print("⚠️  当前提交信息不符合 Conventional Commits")

        choice = input("请选择 [Y]确认提交 / [E]编辑 / [N]中断: ").strip().lower()
        if choice in ("", "y", "yes"):
            if CC_PATTERN.match(commit_message):
                return commit_message, True

            force = input("提交信息不规范，是否仍继续提交？[y/N]: ").strip().lower()
            if force in ("y", "yes"):
                return commit_message, True
            continue

        if choice in ("e", "edit"):
            print("🖊️  即将打开终端编辑器（支持粘贴与光标移动）")
            edited = edit_commit_message_tui(commit_message)
            if edited is None:
                fallback_edit = input("可改为单行输入（留空保留原值）: ").strip()
                if fallback_edit:
                    commit_message = fallback_edit
                else:
                    print("⚠️  未修改，保留原提交信息")
            else:
                commit_message = edited
            continue

        if choice in ("n", "no", "q", "quit", "abort"):
            return commit_message, False

        print("⚠️  无效输入，请输入 Y / E / N")

def wait_for_site_ready(base_url, timeout_sec=180, interval_sec=8):
    deadline = time.time() + timeout_sec
    checks = [
        f"{base_url}/",
        f"{base_url}/assets/stylesheets/main.484c7ddc.min.css",
        f"{base_url}/assets/javascripts/bundle.79ae519e.min.js",
    ]
    last_status = {}

    print(f"⏳ 等待站点就绪（最多 {timeout_sec} 秒）...")
    while time.time() < deadline:
        all_ok = True
        for url in checks:
            try:
                r = requests.get(url, timeout=10, verify=False)
                last_status[url] = r.status_code
                if r.status_code != 200:
                    all_ok = False
            except requests.RequestException:
                all_ok = False
                last_status[url] = "ERR"

        if all_ok:
            print("✅ 站点已就绪，首页与关键静态资源可访问")
            return True

        print(f"  站点未就绪，{interval_sec}s 后重试: {last_status}")
        time.sleep(interval_sec)

    print("❌ 站点在等待窗口内仍未就绪，请检查 Coolify 部署日志")
    print(f"  最后探测状态: {last_status}")
    return False

# ─── Step 1: 确认本地源文件完整 ──────────────────────────────────────────────
step("Step 1: 检查源文件")
for required in ["mkdocs.yml", "docs", "nginx.conf"]:
    if not os.path.exists(os.path.join(LOCAL_DIR, required)):
        print(f"❌ 缺少必要文件: {required}")
        sys.exit(1)
print("✅ 源文件检查通过（MkDocs 将在 Coolify 容器内构建）")

# ─── Step 2: 推送到 GitHub ────────────────────────────────────────────────────
step("Step 2: 推送 MkDocs 源文件到 GitHub")
os.chdir(LOCAL_DIR)

# 设置 SSH remote（push 需要 SSH 认证）
result = subprocess.run("git remote -v", shell=True, cwd=LOCAL_DIR,
                        capture_output=True, text=True)
if "origin" not in result.stdout:
    run(f"git remote add origin {GIT_REPO_AUTH}", cwd=LOCAL_DIR)
else:
    run(f"git remote set-url origin {GIT_REPO_AUTH}", cwd=LOCAL_DIR)

run("git add .", cwd=LOCAL_DIR)

# 检查是否有变更
status = subprocess.run("git status --porcelain", shell=True, cwd=LOCAL_DIR,
                        capture_output=True, text=True)
if status.stdout.strip():
    generated_message = generate_commit_message(LOCAL_DIR)
    commit_message, should_commit = review_commit_message(generated_message)
    if not should_commit:
        print("⏹️  已中断提交，后续 push 与部署已取消")
        sys.exit(0)

    run(f"git commit -m {shlex.quote(commit_message)}", cwd=LOCAL_DIR)
    print(f"📝 commit message: {commit_message}")
    print("✅ 已提交更改")
else:
    print("ℹ️  暂存区无变更，将强制触发 Coolify 重建")

push_result = subprocess.run(
    f"git push -u origin {GIT_BRANCH} --force",
    shell=True, cwd=LOCAL_DIR
)
if push_result.returncode != 0:
    print("❌ git push 失败！请检查 GITHUB_TOKEN 是否有效。")
    sys.exit(1)
print("✅ 内容已推送到 GitHub")

# ─── Step 3: 查找 Coolify 项目 ───────────────────────────────────────────────
step("Step 3: 查找/创建 Coolify 项目")
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

# ─── Step 4: 获取 Server UUID ─────────────────────────────────────────────────
step("Step 4: 获取可用 Server")
resp = api("GET", "/servers")
resp.raise_for_status()
server = next((s for s in resp.json() if s.get("is_usable")), None)
if not server:
    print("❌ 没有可用 Server，请在 Coolify 面板确认服务器状态")
    sys.exit(1)
SERVER_UUID = server["uuid"]
print(f"✅ Server: {server['name']}  uuid={SERVER_UUID}")

# ─── Step 5: 查找或创建应用 ──────────────────────────────────────────────────
step("Step 5: 查找已有应用 / 创建新应用")
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

    step("Step 6: 强制重建并部署（force_rebuild=true）")
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

    if not wait_for_site_ready(DOMAIN):
        sys.exit(1)

    print(f"\n🌐 站点地址: {DOMAIN}")
    print("🎉 你现在可以直接访问查看课程内容")

else:
    step("Step 6: 创建静态站点应用并立即部署")
    payload = {
        "project_uuid":           PROJECT_UUID,
        "server_uuid":            SERVER_UUID,
        "environment_name":       ENVIRONMENT,
        "git_repository":         GIT_REPO,
        "git_branch":             GIT_BRANCH,
        "build_pack":             "dockercompose",
        "name":                   APP_NAME,
        "domains":                DOMAIN,
        "is_auto_deploy_enabled": True,
        "instant_deploy":         True,
        "ports_exposes":          "80",
    }
    resp = api("POST", "/applications/public", json=payload)
    if resp.status_code in (200, 201):
        data = resp.json()
        APP_UUID = data.get("uuid")
        if not wait_for_site_ready(DOMAIN):
            sys.exit(1)
        print(f"✅ 应用创建成功！  uuid={APP_UUID}")
        print(f"🌐 站点地址: {data.get('domains', DOMAIN)}")
        print("🎉 你现在可以直接访问查看课程内容")
    else:
        print(f"❌ 创建失败 HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)
