# XHS_ALL_IN_ONE — Product Overview

## Purpose
A full-stack, open-source platform for end-to-end Xiaohongshu (小红书) content operations. It closes the loop from data collection → content library → AI rewriting → image enhancement → scheduled publishing → automated pipeline — all in a single browser tab.

## Value Proposition
Replaces 5+ separate tools (scrapers, note apps, ChatGPT tab, image editors, creator dashboard) with one unified platform. The key differentiator is the fully automated pipeline: keyword search → AI rewrite → upload → publish, with zero manual intervention.

## Target Users
- Individual content creators managing XHS accounts
- Marketing teams running multi-account XHS operations
- Developers building XHS automation toolchains (via SDK / Skills interface)

## Core Feature Areas

### 1. Account Matrix
- Bind multiple PC and Creator accounts
- Three login methods: QR code, SMS verification code, Cookie import
- Fernet-encrypted cookie storage
- Automatic 2-hour health check with expiry notifications

### 2. Note Discovery
- Keyword search across all XHS notes
- Multi-dimensional filters: sort, type, time range
- Watermark-free original image/video retrieval
- One-click save to content library

### 3. Content Library
- Unified repository for all collected notes (per platform user, not per XHS account)
- Card / list dual view
- Custom tags, keyword search, batch operations
- Export to JSON / CSV

### 4. Draft Workshop (草稿工坊)
- Three-column layout: draft queue + editor + AI assistant
- AI one-click rewrite: body text, title polish, tag generation
- Drag-and-drop image asset reordering
- Send directly to publish center

### 5. Image Workshop (图片工坊)
- AI image generation with reference image support
- Image description generation
- AI and regular image asset management

### 6. Publish Center
- Preview draft content and image assets
- Select Creator account, set visibility and publish mode (immediate / scheduled)
- Publish validation + one-click publish to XHS Creator platform

### 7. Auto Operations (自动运营)
- Configurable keyword + schedule (daily / weekly / custom interval)
- Fully automated pipeline: search → AI rewrite → upload → publish
- Unattended operation

### 8. Data Insights
- Dashboard overview, engagement trends, top content, hot topics, comment analysis

### 9. Competitor Monitoring
- Keyword / account / brand / URL monitoring
- Auto-crawl refresh, snapshot history

### 10. Task Center & Notifications
- Full task audit log, scheduler status, duration tracking
- Real-time bell notifications for cookie expiry and task failures

### 11. Model Configuration
- Supports any OpenAI-compatible API endpoint
- Pre-tested with: Volcengine (火山引擎), Alibaba Cloud Bailian (阿里云百炼), OpenAI proxies

## SDK / Skills Layer
The `apis/` directory is a standalone reverse-engineered XHS SDK. It is also published as [XhsSkills](https://github.com/cv-cat/XhsSkills) for direct integration with agent toolchains (Clawbot, Claude Code, Codex, etc.).

## Platform Roadmap
| Platform | Status |
|---|---|
| 小红书 (XHS) | ✅ Live |
| 抖音 / 快手 / 微博 / 闲鱼 / 淘宝 | Coming Soon |

## Constraints
- For learning and research only — commercial use is prohibited (MIT license with explicit restriction in README)
- Requires Python 3.10+ and Node.js 20+
