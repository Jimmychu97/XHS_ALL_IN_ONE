# XHS_ALL_IN_ONE — Product Overview

## Purpose
A full-stack, open-source platform for end-to-end Xiaohongshu (小红书) content operations. It closes the loop from data collection → content library → AI rewriting → image enhancement → scheduled publishing → automated pipeline — all in a single browser tab.

## Value Proposition
Replaces 5+ separate tools (scrapers, Excel, ChatGPT, Photoshop, creator dashboard) with one unified platform. The only open-source project that connects the entire XHS content production chain.

## Target Users
- XHS content creators managing multiple accounts
- Social media agencies running content pipelines at scale
- Developers building XHS automation tools (via SDK / Skills interface)

## Core Capabilities

### 1. Multi-Account Matrix
- Bind multiple PC and Creator accounts
- Three login methods: QR code, SMS verification code, Cookie import
- Fernet-encrypted cookie storage; 2-hour automatic health check with expiry notifications

### 2. Note Discovery
- Keyword search across all XHS notes with multi-dimensional filters (sort, type, date)
- URL direct lookup; watermark-free original images and video
- One-click save to content library; "already saved" indicator

### 3. Content Library
- Unified repository owned by platform user (not tied to any XHS account)
- Card / list dual views; custom tags; keyword search; batch operations
- JSON / CSV export

### 4. Draft Workshop (AI Rewriting)
- Three-column layout: draft queue + editor + AI assistant
- Deep-copy notes from library into drafts
- AI one-click rewrite: body text, title polish, tag generation
- Drag-and-drop image asset reordering; send directly to publish center

### 5. Image Workshop (AI Image Enhancement)
- Select any draft image, add reference image, enter enhancement prompt
- AI generates optimized image and replaces in-place
- Side-by-side comparison with click-to-enlarge preview

### 6. Publish Center
- Preview draft content and image assets
- Select Creator account; set visibility and publish mode (immediate / scheduled)
- Publish validation + one-click publish to XHS Creator platform

### 7. Auto-Operations Pipeline
- Configure keywords + schedule (daily / weekly / custom interval)
- Fully automated: search hot notes → AI rewrite title+body → upload assets → publish via Creator API
- True unattended operation

### 8. Additional Modules
- Data Insights: dashboard, engagement trends, top content, hot topics, comment analysis
- Competitor Monitoring: keyword / account / brand / URL monitoring with snapshot history
- Task Center: full task audit, scheduler status, duration tracking
- Notification System: real-time bell for cookie expiry and task failures
- Model Configuration: any OpenAI-compatible API (Volcengine, Alibaba Cloud Bailian, OpenAI proxies)

## SDK Layer (apis/)
Reverse-engineered XHS signing algorithms exposed as a transparent SDK:
- PC platform: QR/SMS login, note search, note detail (no-watermark), comments, user profiles, home feed, unread messages
- Creator platform: QR/SMS login, image/video upload, published works list
- Pugongying platform: KOL list, fan profiles, collaboration invitations
- Qianfan platform: distributor list, category/product info

## Skills Integration
Project exposes standardized skills consumable by agent toolchains (Clawbot, Claude Code, Codex) via [XhsSkills](https://github.com/cv-cat/XhsSkills).

## Planned Platforms
Douyin, Kuaishou, Weibo, Xianyu, Taobao (Coming Soon)
