#!/usr/bin/env python3
"""
AdGuard Home 过滤规则合并脚本
从上游源下载、处理并合并过滤规则
"""

import os
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
UPSTREAM_DIR = PROJECT_DIR / "upstream"
OUTPUT_DIR = PROJECT_DIR / "output"

# 上游规则源
SOURCES = {
    "awavenue": "https://raw.githubusercontent.com/TG-Twilight/AWAvenue-Ads-Rule/main/AWAvenue-Ads-Rule.txt",
    "github_hosts": "https://raw.githubusercontent.com/maxiaof/github-hosts/refs/heads/master/hosts",
    "smahosts": "https://raw.githubusercontent.com/2Gardon/SM-Ad-FuckU-hosts/refs/heads/master/SMAdHosts",
}


def download_file(url: str, output_path: Path) -> bool:
    """下载文件"""
    try:
        urllib.request.urlretrieve(url, str(output_path))
        return True
    except Exception as e:
        print(f"  下载失败: {url}")
        print(f"  错误: {e}")
        return False


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
    result.append("#Github加速 (来源: github-hosts)")
    result.extend(github_entries)

    output_path.write_text("\n".join(result), encoding="utf-8")

    return len(lines), len(result)


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


def merge_and_dedup(files: list, output_path: Path) -> tuple:
    """合并并去重（兼容 hosts 和 adblock 语法，放行规则不去重）"""
    all_lines = []
    for i, f in enumerate(files):
        content = f.read_text(encoding="utf-8")
        all_lines.extend(content.splitlines())
        if i < len(files) - 1:
            all_lines.extend([""] * 4)

    # 去重：基于域名去重，空行和放行规则保留
    seen_domains = {}  # domain -> first occurrence line
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
    # 创建目录
    UPSTREAM_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=== 下载上游规则源 ===")

    files = {}
    for name, url in SOURCES.items():
        output_path = UPSTREAM_DIR / f"{name}.txt"
        print(f"下载 {name}...")
        if download_file(url, output_path):
            print(f"  成功: {output_path.name}")
            files[name] = output_path
        else:
            print(f"  跳过: {name}")

    print("\n=== 处理 SMAdHosts ===")

    if "smahosts" in files and "github_hosts" in files:
        cleaned_path = UPSTREAM_DIR / "smahosts-clean.txt"
        original_count, cleaned_count = process_smahosts(
            files["smahosts"], files["github_hosts"], cleaned_path
        )
        print(f"SMAdHosts: {original_count} 行 -> {cleaned_count} 行")
        print("  删除旧 GitHub 加速规则，追加新 Github Hosts 数据")
        files["smahosts_cleaned"] = cleaned_path

    print("\n=== 合并所有规则 ===")

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

        removed = total - unique
        print(f"原始规则数: {total}")
        print(f"去重后规则数: {unique}")
        print(f"移除重复: {removed}")
        print(f"详细日志: {OUTPUT_DIR / 'dedup-log.txt'}")
        print(f"\n=== 合并完成 ===")
        print(f"输出文件: {deduped_output}")
    else:
        print("没有可用的规则源")


if __name__ == "__main__":
    main()
