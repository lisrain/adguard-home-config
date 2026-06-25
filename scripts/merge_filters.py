#!/usr/bin/env python3
"""
AdGuard Home 过滤规则合并脚本
从上游源下载、处理并合并过滤规则
"""

import json
import os
import platform
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
UPSTREAM_DIR = PROJECT_DIR / "upstream"
OUTPUT_DIR = PROJECT_DIR / "output"

# 上游规则源
SOURCES = {
    "awavenue": "https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/AWAvenue-Ads-Rule.txt",
    "github_hosts": "https://raw.githubusercontent.com/ineo6/hosts/refs/heads/master/hosts",
    "smahosts": "https://raw.githubusercontent.com/2Gardon/SM-Ad-FuckU-hosts/refs/heads/master/SMAdHosts",
    "fcm_hosts": "https://raw.githubusercontent.com/cagedbird043/fcm-hosts-next/refs/heads/main/fcm_ipv4.hosts",
    # "adblockdnslite": "https://raw.githubusercontent.com/217heidai/adblockfilters/main/rules/adblockdnslite.txt",
}

AWAVENUE_REPO = "TG-Twilight/AWAvenue-Ads-Rule"
AWAVENUE_FILE = "AWAvenue-Ads-Rule.txt"


def download_file(url: str, output_path: Path) -> bool:
    """下载文件 - Windows用PowerShell，Linux用urllib"""
    try:
        if platform.system() == "Windows":
            ps_cmd = f'Invoke-WebRequest -Uri "{url}" -OutFile "{output_path}" -UseBasicParsing'
            subprocess.run(
                ["powershell", "-Command", ps_cmd],
                check=True,
                capture_output=True,
            )
        else:
            urllib.request.urlretrieve(url, str(output_path))
        return True
    except Exception as e:
        print(f"  下载失败: {url}")
        print(f"  错误: {e}")
        return False


def extract_domain(line: str) -> str:
    """提取规则中的域名用于去重比对"""
    line = line.strip()

    # 放行规则不参与去重
    if line.startswith("@@"):
        return None

    # Hosts 格式: 0.0.0.0 domain.com 或 127.0.0.1 domain.com
    if line.startswith("0.0.0.0 ") or line.startswith("127.0.0.1 "):
        parts = line.split()
        if len(parts) >= 2:
            return parts[1].lower()

    # Adblock 格式: ||domain.com^ 或 ||domain.com^$important
    if line.startswith("||") and "^" in line:
        domain = line[2:line.index("^")].lower()
        return domain

    return None


def fetch_recently_removed_domains() -> set:
    """通过 GitHub API 获取 AWAvenue 最新 commit 中被移除的域名"""
    try:
        commits_url = f"https://api.github.com/repos/{AWAVENUE_REPO}/commits?per_page=1"
        token = os.environ.get("GITHUB_TOKEN", "")
        auth_header = {"Accept": "application/vnd.github.v3+json"}
        if token:
            auth_header["Authorization"] = f"token {token}"

        if platform.system() == "Windows":
            headers_str = " ".join(f'"{k}"="{v}"' for k, v in auth_header.items())
            ps_cmd = f'(Invoke-WebRequest -Uri "{commits_url}" -UseBasicParsing -Headers @{{{headers_str}}}).Content'
            result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
            commits = json.loads(result.stdout) if result.returncode == 0 else []
        else:
            req = urllib.request.Request(commits_url, headers=auth_header)
            with urllib.request.urlopen(req, timeout=15) as resp:
                commits = json.loads(resp.read().decode())

        if not commits:
            return set()

        sha = commits[0]["sha"]
        commit_url = f"https://api.github.com/repos/{AWAVENUE_REPO}/commits/{sha}"
        if platform.system() == "Windows":
            ps_cmd = f'(Invoke-WebRequest -Uri "{commit_url}" -UseBasicParsing -Headers @{{{headers_str}}}).Content'
            result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
            commit_data = json.loads(result.stdout) if result.returncode == 0 else {}
        else:
            req = urllib.request.Request(commit_url, headers=auth_header)
            with urllib.request.urlopen(req, timeout=15) as resp:
                commit_data = json.loads(resp.read().decode())

        removed_domains = set()
        for file_info in commit_data.get("files", []):
            if file_info["filename"] != AWAVENUE_FILE:
                continue
            patch = file_info.get("patch", "")
            for line in patch.split("\n"):
                if line.startswith("-") and not line.startswith("---"):
                    domain = extract_domain(line[1:])
                    if domain:
                        removed_domains.add(domain)

        return removed_domains
    except Exception as e:
        print(f"  [WARN] Failed to fetch AWAvenue commit diff: {e}")
        return set()


def filter_removed_domains(input_path: Path, output_path: Path, excluded_domains: set) -> int:
    """从合并结果中排除 AWAvenue 最新移除的域名"""
    lines = input_path.read_text(encoding="utf-8").splitlines()
    filtered = []
    log_lines = []
    removed_count = 0

    for line in lines:
        domain = extract_domain(line)
        if domain and domain in excluded_domains:
            log_lines.append(f"[EXCLUDED] {line.strip()}")
            log_lines.append(f"  -> removed from AWAvenue in latest commit")
            removed_count += 1
        else:
            filtered.append(line)

    output_path.write_text("\n".join(filtered), encoding="utf-8")

    log_path = output_path.parent / "dedup-log.txt"
    with open(log_path, "a", encoding="utf-8") as f:
        if log_lines:
            content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write("\n".join(log_lines) + "\n")

    return removed_count


def _load_allowlist_patterns(custom_dir: Path) -> list:
    """从 custom/user-rules.txt 中加载 @@||...^$important 放行规则，编译为正则列表"""
    rules_file = custom_dir / "user-rules.txt"
    if not rules_file.exists():
        return []

    patterns = []
    for line in rules_file.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^\s*@@\|\|(.+?)\^\$important', line)
        if not m:
            continue
        raw_domain = m.group(1)
        # 将 Adblock 通配模式转为正则：* → 匹配除空格外的任意字符
        regex_str = re.escape(raw_domain).replace(r'\*', r'[^ ]*')
        patterns.append((raw_domain, re.compile(f'^{regex_str}$')))
    return patterns


def _comment_out_whitelisted(path: Path, patterns: list) -> int:
    """在 hosts 文件中将匹配放行规则的 0.0.0.0 条目注释掉"""
    if not patterns:
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    count = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r'^0\.0\.0\.0\s+(\S+)', stripped)
        if not m:
            continue
        host_domain = m.group(1)
        for raw_pattern, regex in patterns:
            if regex.search(host_domain):
                lines[i] = f"# {line}"
                count += 1
                break

    if count:
        path.write_text("\n".join(lines), encoding="utf-8")
    return count


def process_smahosts(smahosts_path: Path, github_hosts_path: Path, fcm_hosts_path: Path,
                     output_path: Path, custom_dir: Path = None):
    """处理 SMAdHosts: 删除旧 FCM 和 GitHub 规则，追加新规则，并注释 user-rules 中放行的域名"""
    lines = smahosts_path.read_text(encoding="utf-8").splitlines()

    # 删除第14-23行 (FCM, 索引13-22) 和 第26-59行 (GitHub加速旧规则, 索引25-58)
    before = lines[:13]
    after = lines[23:25]
    after = after + lines[59:]

    # 读取 GitHub hosts 数据
    github_lines = github_hosts_path.read_text(encoding="utf-8").splitlines()
    github_entries = [line for line in github_lines if line and not line.startswith("#")]

    # 读取 fcm_hosts 数据，原样合入
    fcm_lines = fcm_hosts_path.read_text(encoding="utf-8").splitlines()
    fcm_entries = [line for line in fcm_lines if line.strip()]

    # 组合
    result = before + after
    result.append("")
    result.append("#FCM推送 (source: fcm-hosts-next)")
    result.extend(fcm_entries)
    result.append("")
    result.append("#Github加速 (source: github-hosts)")
    result.extend(github_entries)

    output_path.write_text("\n".join(result), encoding="utf-8")

    # 根据 user-rules.txt 的 @@|| 放行规则，注释掉 hosts 中对应的拦截条目
    if custom_dir:
        patterns = _load_allowlist_patterns(custom_dir)
        if patterns:
            commented = _comment_out_whitelisted(output_path, patterns)
            if commented:
                print(f"  Commented out {commented} entries matching @@|| allowlist")

    return len(lines), len(result)


def merge_and_dedup(files: list, output_path: Path) -> tuple:
    """合并并去重（兼容 hosts 和 adblock 语法，放行规则不去重）"""
    all_lines = []
    for i, f in enumerate(files):
        content = f.read_text(encoding="utf-8")
        all_lines.extend(content.splitlines())
        if i < len(files) - 1:
            all_lines.extend([""] * 4)

    # 去重：基于域名去重，空行和放行规则保留
    seen_domains = {}
    deduped = []
    log_lines = []

    for line in all_lines:
        if line == "":
            deduped.append(line)
            continue

        domain = extract_domain(line)
        if domain:
            if domain not in seen_domains:
                seen_domains[domain] = line
                deduped.append(line)
            else:
                first = seen_domains[domain]
                log_lines.append(f"[SKIP] {line}")
                log_lines.append(f"  -> same as: {first}")
        else:
            deduped.append(line)

    output_path.write_text("\n".join(deduped), encoding="utf-8")

    # Write dedup log
    log_path = output_path.parent / "dedup-log.txt"
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    return len(all_lines), len(deduped), len(log_lines)


def main():
    UPSTREAM_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=== Downloading upstream sources ===")

    files = {}
    for name, url in SOURCES.items():
        output_path = UPSTREAM_DIR / f"{name}.txt"
        print(f"  {name}...", end=" ")
        if download_file(url, output_path):
            print("OK")
            files[name] = output_path
        else:
            print("FAILED")

    print("\n=== Processing SMAdHosts ===")

    if "smahosts" in files and "github_hosts" in files and "fcm_hosts" in files:
        cleaned_path = UPSTREAM_DIR / "smahosts-clean.txt"
        custom_dir = PROJECT_DIR / "custom"
        original_count, cleaned_count = process_smahosts(
            files["smahosts"], files["github_hosts"], files["fcm_hosts"],
            cleaned_path, custom_dir
        )
        print(f"  SMAdHosts: {original_count} -> {cleaned_count} lines")
        files["smahosts_cleaned"] = cleaned_path

    print("\n=== Merging and deduplicating ===")

    merge_files = []
    if "awavenue" in files:
        merge_files.append(files["awavenue"])
    if "smahosts_cleaned" in files:
        merge_files.append(files["smahosts_cleaned"])

    # Add custom rules
    custom_dir = PROJECT_DIR / "custom"
    if custom_dir.exists():
        for f in sorted(custom_dir.glob("*.txt")):
            merge_files.append(f)

    if merge_files:
        deduped_output = OUTPUT_DIR / "filters.txt"

        total, unique, skipped = merge_and_dedup(merge_files, deduped_output)

        print(f"  Total: {total}")
        print(f"  Unique: {unique}")
        print(f"  Skipped: {skipped}")

        print("\n=== Checking AWAvenue removed domains ===")
        removed_domains = fetch_recently_removed_domains()
        if removed_domains:
            print(f"  Found {len(removed_domains)} removed domains in latest commit")
            excluded_count = filter_removed_domains(deduped_output, deduped_output, removed_domains)
            print(f"  Excluded {excluded_count} domains from output")
        else:
            print("  No removed domains detected (or API unavailable)")

        print(f"\n=== Done ===")
        print(f"  filters.txt: {deduped_output}")
        print(f"  dedup-log.txt: {OUTPUT_DIR / 'dedup-log.txt'}")
    else:
        print("  No sources available")


if __name__ == "__main__":
    main()
