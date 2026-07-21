# AdGuard Home Filter Lists

整合上游过滤规则源，自动去重合并，生成可用的过滤器列表。

## 规则源

| 名称 | 说明 | 仓库 |
|------|------|------|
| AWAvenueAds | 秋风广告规则 | [TG-Twilight/AWAvenue-Ads-Rule](https://github.com/TG-Twilight/AWAvenue-Ads-Rule) |
| Github Hosts | GitHub加速 | [ineo6/hosts](https://github.com/ineo6/hosts) |
| FCM Hosts | FCM推送规则 | [cagedbird043/fcm-hosts-next](https://github.com/cagedbird043/fcm-hosts-next) |
| ~~AdBlock DNS Lite~~ | ~~去重合并广告过滤规则~~（暂未启用） | [217heidai/adblockfilters](https://github.com/217heidai/adblockfilters) |
| Adguard-Home-For-Magisk-Mod | user-rules部分规则参考 | [liuzq2002/Adguard-Home-For-Magisk-Mod](https://github.com/liuzq2002/Adguard-Home-For-Magisk-Mod) |

## 产物位置

| 文件 | 说明 |
|------|------|
| `output/filters.txt` | 最终合并去重后的规则文件，可导入 AdGuard Home |
| `output/dedup-log.txt` | 去重日志，记录被合并的重复规则 |

## 直达链接

| 链接 | 说明 |
|------|------|
| [filters.txt](https://raw.githubusercontent.com/lisrain/adguard-home-config/refs/heads/master/output/filters.txt) | GitHub 直连 |
| [filters.txt (镜像)](https://v4.gh-proxy.org/https://raw.githubusercontent.com/lisrain/adguard-home-config/refs/heads/master/output/filters.txt) | 国内镜像 |

## 导入 AdGuard Home

1. 下载 `output/filters.txt`
2. AdGuard Home 后台 -> 过滤器 -> 添加自定义规则列表
3. 填入规则文件的 URL 或本地路径

## 自定义规则

在 `custom/` 目录下放置 `.txt` 文件，会自动合并到最终产物中。

## GitHub Actions

- 定时任务：每天北京时间 03:00 和 15:00 自动执行
- 产物提交到仓库 `output/` 目录
- 也会上传到 Actions Artifacts

## 智能去重

- 支持 Hosts 格式 (`0.0.0.0 domain.com`) 和 Adblock 格式 (`||domain.com^`)
- 同一域名不同格式视为重复，保留第一条
- 放行规则 (`@@||domain.com^`) 不参与去重，全部保留

## 目录结构

```
├── scripts/
│   └── merge_filters.py        # 合并去重脚本
├── custom/                     # 自定义规则源（手动维护）
├── upstream/                   # 下载的上游文件（git忽略）
├── output/                     # 生成的规则文件
└── .github/workflows/
    └── build.yml
```

## 致谢

感谢以下仓库提供规则数据：

- [TG-Twilight/AWAvenue-Ads-Rule](https://github.com/TG-Twilight/AWAvenue-Ads-Rule) - 秋风广告规则
- [ineo6/hosts](https://github.com/ineo6/hosts) - GitHub 加速 hosts
- [cagedbird043/fcm-hosts-next](https://github.com/cagedbird043/fcm-hosts-next) - FCM 推送 hosts
- [217heidai/adblockfilters](https://github.com/217heidai/adblockfilters) - 去重合并广告过滤规则
- [liuzq2002/Adguard-Home-For-Magisk-Mod](https://github.com/liuzq2002/Adguard-Home-For-Magisk-Mod) - user-rules 部分规则参考
- ~~[maxiaof/github-hosts](https://github.com/maxiaof/github-hosts)~~ - 前 GitHub 加速 hosts 上游

## License

本仓库脚本代码采用 [MIT 许可证](LICENSE)。

上游过滤规则数据的许可证如下：

| 规则源 | 许可证 |
|--------|--------|
| AWAvenue-Ads-Rule | GPL-3.0 |
| adblockfilters | GPL-3.0 |
| ineo6/hosts | MIT |
| fcm-hosts-next | MIT |
