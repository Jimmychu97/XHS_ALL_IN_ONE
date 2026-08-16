# XHS_ALL_IN_ONE — Product Overview

## Purpose

XHS_ALL_IN_ONE is an all-in-one intelligent operations platform for 小红书 (Xiaohongshu/RedNote). It closes the full loop from content discovery → AI rewriting → image enhancement → scheduled publishing → automated operations, replacing 5+ separate tools with a single browser tab.

## Value Proposition

- **No manual copy-paste**: AI rewriting happens inside the editor, not in a separate ChatGPT tab
- **Full pipeline automation**: keyword search → AI rewrite → upload → publish, fully unattended
- **Multi-account matrix**: manage PC + Creator + 千帆 + 客服 + 卖家 accounts in one place
- **Encrypted credential storage**: Fernet-encrypted cookies and API keys, 2-hour health checks

## Key Features

### Content Operations
- Keyword search across XHS with multi-dimensional filters (sort, type, time)
- One-click save to content library with watermark-free images/videos
- Unified content library: card/list views, custom tags, batch ops, JSON/CSV export
- Draft workshop: 3-column editor (queue + editor + AI assistant), drag-sort assets
- AI rewrite: title, body, tags — all in one click via OpenAI-compatible APIs
- AI image enhancement with reference images, side-by-side comparison

### Publishing
- Immediate and scheduled publishing to XHS Creator platform
- Publish validation, status tracking, retry/cancel
- Auto-operations: configure keywords + frequency → fully automated pipeline

### Platform SDKs (Reverse-Engineered)
| Platform | Capabilities |
|---|---|
| XHS PC | QR/SMS login, search, note detail, comments, user profile, feed |
| XHS Creator | QR/SMS login, upload image/video posts, list published works |
| 蒲公英 | KOL list, fan profile, collaboration invite |
| 千帆分销 | Distributor list, product/category info |
| 千帆客服工作台 (Walle) | Conversation list, message history, realtime data, AI reply suggestions |
| 千帆卖家后台 (Ark) | Product management, SKU details, orders, realtime GMV metrics |

### Web Platform Modules
- Account Matrix — multi-account binding, health monitoring, expiry notifications
- Note Discovery — search, URL lookup, filters, one-click save
- Data Scraping — batch URL/search/comment crawl, Excel export, local asset download
- Content Library — dual-view, tags, batch ops, export
- Draft Workshop — AI rewrite, image polish, drag-sort
- Image Workshop — AI image generation, description, asset management
- Publish Center — image post publishing, scheduling, status tracking
- Auto Operations — scheduled tasks, full pipeline automation
- Data Insights — dashboard, engagement trends, top content, topic analysis
- Competitor Monitoring — keyword/account/brand/URL monitoring, snapshot history
- Task Center — full task audit, scheduler status, timing tracking
- Notification System — cookie expiry / task failure alerts, real-time bell
- Model Config — any OpenAI-compatible API (Volcengine, Alibaba Cloud, OpenAI proxy)

## Target Users

- 小红书 content creators and operators managing multiple accounts
- E-commerce sellers on 千帆 platform needing product/order management
- Marketing teams running competitor monitoring and content pipelines
- Developers building XHS automation tools (Skills/Agent integration via XhsSkills)

## Constraints

- For learning/research only — commercial use prohibited
- Python 3.10+ and Node.js 20+ required
- XHS cookies have limited validity; platform enforces 2-hour health checks
- Ark/Walle SDKs require Playwright browser sessions for signing
