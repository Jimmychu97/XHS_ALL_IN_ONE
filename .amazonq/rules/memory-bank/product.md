# XHS_ALL_IN_ONE — Product Overview

## Purpose
<<<<<<< HEAD
A full-stack, open-source platform for end-to-end Xiaohongshu (小红书) content operations: scraping → content library → AI rewriting → image enhancement → scheduled publishing → fully automated pipeline. Replaces 5+ separate tools with a single browser tab.

## Target Users
- XHS content creators and operators managing multiple accounts
- Social media agencies running multi-account matrix strategies
- E-commerce sellers using XHS for product promotion
- Developers building XHS automation toolchains

## Core Value Proposition
- **Full pipeline closure**: search → save → AI rewrite → publish, all in one platform
- **Multi-account matrix**: bind multiple PC/Creator accounts, unified health monitoring
- **No manual copy-paste**: AI rewriting happens inside the editor, not in a separate chat window
- **True automation**: keyword + schedule → system runs the entire pipeline unattended

## Key Features

### Content Discovery & Library
- Keyword search across all XHS notes with multi-dimensional filters (sort, type, time)
- One-click save to content library with watermark-free original images/videos
- Card/list dual view, custom tags, batch operations, JSON/CSV export

### Draft Workshop (AI-Powered)
- Three-column layout: draft queue + editor + AI assistant
- AI rewrite body text, polish title, generate hashtags
- Drag-and-drop image asset ordering
- AI image enhancement with reference images

### Publishing Center
- Select Creator account, set visibility and publish mode (immediate / scheduled)
- Pre-publish validation, status tracking, retry/cancel

### Automated Operations
- Configure keywords + schedule frequency (daily/weekly/custom interval)
- Full unattended pipeline: search hot notes → AI rewrite → upload assets → publish via Creator API

### Account Matrix
- Bind multiple PC/Creator accounts via QR code, SMS, or Cookie import
- Fernet-encrypted cookie storage, 2-hour automatic health check, expiry notifications

### Analytics & Monitoring
- Dashboard: interaction trends, top content, hot topics, comment analysis
- Competitor monitoring: keyword/account/brand/URL tracking with snapshot history

### Qianfan Customer Service Workbench
- Full SDK for `walle.xiaohongshu.com` (Electron app) via CDP remote debugging
- Real-time message capture, multi-store routing, AI suggested replies
- Web management UI: conversations, knowledge base, transfer keywords, redemption records

## Platform Scope
- **Live**: Xiaohongshu (XHS) — PC端, Creator Platform, 蒲公英, 千帆, 千帆客服
- **Planned**: Douyin, Kuaishou, Weibo, Xianyu, Taobao

## Constraints
- For learning/research only — commercial use prohibited
- Requires XHS accounts to remain logged in for cookie-based auth
- AI features require external OpenAI-compatible API configuration
=======
A full-stack, all-in-one operations platform for Xiaohongshu (小红书 / XHS). It closes the loop from content discovery → AI rewriting → image enhancement → scheduled publishing → automated pipeline, replacing 5+ separate tools with a single browser tab.

## Value Proposition
- **Collect**: Keyword search + one-click save to content library; assets auto-downloaded locally
- **Manage**: Unified content library with card/list views, custom tags, bulk ops, JSON/CSV export
- **AI Rewrite**: In-editor one-click rewrite of body, title, and hashtags via any OpenAI-compatible API
- **Image Polish**: AI image enhancement with reference images, side-by-side comparison
- **Publish**: Select account → set visibility/schedule → one-click publish to XHS Creator platform
- **Automate**: Keyword + frequency config → fully unattended pipeline: search → AI rewrite → upload → publish
- **Multi-account**: Account matrix with encrypted cookie storage, 2-hour health checks, expiry notifications
- **Customer Service**: Qianfan (千帆) customer service workbench SDK with AI-suggested replies and agent loop

## Key Features

### Bottom-layer SDK (reverse-engineered signing)
- XHS PC: QR/SMS login, note search, note detail (watermark-free), comments, user profiles, home feed
- XHS Creator: QR/SMS login, upload image sets / videos, published works list
- Pugongying (蒲公英): KOL list, fan profiles, collaboration invites
- Qianfan (千帆): distributor list, product info, customer service workbench (Walle/Eva)

### Web Operations Platform
| Module | Highlights |
|---|---|
| Account Matrix | Multi PC/Creator accounts, Fernet-encrypted cookies, 2h health check |
| Note Discovery | Keyword search, URL lookup, multi-filter, one-click save |
| Data Scraping | Bulk URL/search/comment scraping, Excel export, local asset download |
| Content Library | Dual view, custom tags, bulk ops, JSON/CSV export |
| Draft Workshop | 3-column editor, AI rewrite, drag-sort assets, AI image polish |
| Image Workshop | AI image generation (with reference), asset management |
| Publish Center | Image-set publish, scheduled publish, status tracking, retry/cancel |
| Auto Operations | Cron tasks (daily/weekly/custom), full unattended pipeline |
| Data Insights | Dashboard, engagement trends, top content, topic analysis |
| Competitor Monitor | Keyword/account/brand/URL monitoring, snapshot history |
| Task Center | Full task audit, scheduler status, duration tracking |
| Notifications | Cookie expiry / task failure alerts, real-time bell |
| Model Config | Any OpenAI-compatible API (Volcengine, Alibaba Cloud, OpenAI proxy) |
| Walle CS Workbench | Session list, message history, knowledge base, AI agent loop, SSE log stream |

## Target Users
- XHS content creators and operators managing multiple accounts
- E-commerce brands running XHS marketing pipelines
- Agencies needing multi-account, multi-content automated operations
- Developers building on top of XHS SDK capabilities via Skills integration

## Planned Platforms
Douyin, Kuaishou, Weibo, Xianyu, Taobao (Coming Soon)

## Constraints
- For learning/research only — commercial use prohibited
- Python 3.10+, Node.js 20+ required
- XHS cookies are time-limited; platform enforces 2h health checks
>>>>>>> 565ca0d81789bed899163a193de2ada985367970
