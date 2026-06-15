#!/usr/bin/env python3
"""
AdGuard Home 过滤规则合并脚本
从上游源下载、处理并合并过滤规则
"""

import os
import platform
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
    "awavenue": "https://github.boki.moe/https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/AWAvenue-Ads-Rule.txt",
    "github_hosts": "https://v4.gh-proxy.org/https://raw.githubusercontent.com/maxiaof/github-hosts/refs/heads/master/hosts",
    "smahosts": "https://v4.gh-proxy.org/https://raw.githubusercontent.com/2Gardon/SM-Ad-FuckU-hosts/refs/heads/master/SMAdHosts",
}


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


def process_smahosts(smahosts_path: Path, github_hosts_path: Path, output_path: Path):
    """处理 SMAdHosts: 删除旧 GitHub 规则，追加新规则"""
    lines = smahosts_path.read_text(encoding="utf-8").splitlines()

    # 删除第26-59行 (索引25-58)
    before = lines[:25]
    after = lines[59:]

    # 读取 GitHub hosts 数据
    github_lines = github_hosts_path.read_text(encoding="utf-8").splitlines()
    github_entries = [line for line in github_lines if line and not line.startswith("#")]

    # 组合
    result = before + after
    result.append("")
    result.append("#Github加速 (source: github-hosts)")
    result.extend(github_entries)

    output_path.write_text("\n".join(result), encoding="utf-8")

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

    if "smahosts" in files and "github_hosts" in files:
        cleaned_path = UPSTREAM_DIR / "smahosts-clean.txt"
        original_count, cleaned_count = process_smahosts(
            files["smahosts"], files["github_hosts"], cleaned_path
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
        print(f"\n=== Done ===")
        print(f"  filters.txt: {deduped_output}")
        print(f"  dedup-log.txt: {OUTPUT_DIR / 'dedup-log.txt'}")
    else:
        print("  No sources available")


if __name__ == "__main__":
    main()
