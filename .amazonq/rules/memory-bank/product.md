# XHS_ALL_IN_ONE — Product Overview

## Purpose
XHS_ALL_IN_ONE is an all-in-one intelligent operations platform for Xiaohongshu (小红书 / RedNote). It closes the full loop from content discovery → content library → AI rewriting → image enhancement → scheduled publishing → automated operations — all in a single browser tab.

**For learning and research purposes only. Commercial use is prohibited.**

## Core Value Proposition
Replaces 5+ separate tools (scrapers, content managers, AI platforms, image editors, publisher tools) with a single unified platform. Key differentiator: the entire pipeline is automated end-to-end with no manual copy-paste between tools.

## Target Users
- XHS content creators managing multiple accounts
- Social media operations teams running content pipelines
- Researchers studying XHS platform mechanics
- Developers building XHS automation toolchains

## Key Features

### Content Discovery & Collection
- Keyword search across all XHS notes with multi-dimensional filters (sort, type, time)
- One-click save to content library with watermark-free original images
- Batch URL / search / comment scraping with Excel export
- Local asset download for all media

### Content Library
- Unified repository for all collected notes, isolated per platform user
- Card/list dual view, custom tags, keyword search, batch operations
- JSON/CSV export

### AI Draft Workshop (草稿工坊)
- Three-panel layout: draft queue + editor + AI assistant
- One-click AI rewrite of body text, title polish, tag generation
- Drag-and-drop image asset reordering
- AI image enhancement with reference images, side-by-side comparison

### Publishing Center
- Select Creator account, set visibility and publish mode (immediate / scheduled)
- Pre-publish validation, status tracking, retry/cancel

### Automated Operations (自动运营)
- Configure keywords + schedule frequency (daily / weekly / custom interval)
- Fully automated pipeline: search → AI rewrite → upload assets → publish via Creator API
- True unattended operation

### Account Matrix
- Multi PC/Creator account binding (QR code, SMS, Cookie import)
- Fernet-encrypted cookie storage
- 2-hour automatic health check with expiry notifications

### Additional Modules
- Data Insights: dashboard, engagement trends, top content, hot topics, comment analysis
- Competitor Monitoring: keyword/account/brand/URL monitoring with snapshot history
- Task Center: full audit log, scheduler status, duration tracking
- Notification System: in-app bell notifications for cookie expiry / task failures
- Model Configuration: any OpenAI-compatible API (Volcengine, Alibaba Cloud Bailian, etc.)

### Platform SDKs (底层 SDK)
- XHS PC API: login, search, note details (watermark-free), comments, user profiles
- Creator Platform API: login, upload image sets / videos, published works list
- Pugongying (蒲公英): KOL list, fan profiles, collaboration invites
- Qianfan (千帆) Distributor: distributor list, product info
- Qianfan Customer Service Workbench (WalleEvaAPI): conversation list, message history, real-time data, AI suggested replies
- Qianfan Seller Backend (ArkAPI): seller info, GMV metrics, product management, order management

## Planned Platform Extensions
- Douyin, Kuaishou, Weibo, Xianyu, Taobao (Coming Soon)

## Skills Integration
Supports skills-based capability integration; can be used as a backend capability repository or integrated into agent toolchains (Clawbot, Claude Code, Codex) via [XhsSkills](https://github.com/cv-cat/XhsSkills).
