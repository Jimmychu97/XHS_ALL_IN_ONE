# XHS_ALL_IN_ONE — Product Overview

## Purpose
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
