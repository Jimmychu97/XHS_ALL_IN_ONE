# Product Overview

## Project Identity
**Name**: XHS_ALL_IN_ONE  
**Tagline**: 小红书一站式智能运营平台  
**Type**: Full-stack web platform for automated content operations

## Value Proposition
Unified platform that bridges the gap between data collection and content publication for Xiaohongshu (Little Red Book) social media. Eliminates the need for multiple disjointed tools by providing an end-to-end workflow:

**采集 → 内容库 → AI 创作与改写 → 图片润色 → 自动发布 → 定时运营**

Target users can accomplish in one browser tab what previously required 5+ separate tools.

## Core Capabilities

### 1. Multi-Platform Account Management
- Bind multiple XHS accounts (PC端 / Creator Platform / 千帆平台)
- Three login methods: QR code scan, SMS verification, Cookie import
- Encrypted credential storage with 2-hour automated health checks
- Cookie expiration notifications

### 2. Content Discovery & Collection
- Keyword-based search across entire XHS platform
- Multi-dimensional filtering (sort, type, time, etc.)
- Detail preview drawer with watermark-free images
- One-click save to content library
- Batch URL/search/comment scraping with Excel export

### 3. Unified Content Library
- Card/list dual-view modes
- Custom tagging system
- Batch operations support
- JSON/CSV export capabilities
- View original note link

### 4. AI-Powered Content Creation
- **Draft Workshop**: Three-column editor (draft queue + editor + AI assistant)
- **Text Operations**: AI rewrite body text, polish titles, generate tags
- **Image Assets**: Drag-to-reorder, AI image enhancement
- One-click deep copy from content library to drafts

### 5. Intelligent Image Processing
- AI image generation with reference image support
- Image description generation
- Side-by-side comparison (original vs optimized)
- Click to preview enlarged images

### 6. Publishing Center
- Preview draft content and media assets
- Select Creator account for publication
- Visibility and publish mode settings (immediate/scheduled)
- Pre-publish validation
- Status tracking with retry/cancel options

### 7. Automated Operations Pipeline
- Set keywords and scheduling frequency (daily/weekly/custom interval)
- Fully automated pipeline: search → AI rewrite → upload → publish
- Unattended content production

### 8. Data Analytics
- Dashboard overview
- Interactive trend analysis
- Top content identification
- Hot topic tracking
- Comment sentiment analysis

### 9. Competitor Monitoring
- Monitor by keyword/account/brand/URL
- Automatic crawl refresh
- Snapshot history comparison

### 10. Task & Notification Center
- Full task audit trail
- Scheduler status monitoring
- Execution time tracking
- Automatic notifications for cookie expiration / task failures

## Target Users
- **Content Creators**: Individuals or teams managing XHS accounts needing streamlined content operations
- **Marketing Teams**: Agencies managing multiple client accounts requiring automation
- **E-commerce Sellers**: Store owners leveraging XHS for product promotion
- **Data Analysts**: Researchers studying XHS content trends and user behavior

## Use Case Scenarios
1. **Content Curation**: Discover trending notes → save to library → AI-rewrite for original content → publish
2. **Multi-Account Management**: Manage 10+ XHS accounts from single dashboard with health monitoring
3. **Automated Publishing**: Configure keywords → schedule frequency → let system auto-produce and publish content
4. **Competitor Analysis**: Monitor competitor accounts → receive automatic updates → analyze content strategies
5. **Customer Service** (千帆客服工作台): Real-time message capture, AI-assisted replies, knowledge base management
6. **Store Operations** (千帆卖家后台): Product inventory tracking, SKU management, order monitoring

## Platform Extensibility
Architecture designed for multi-platform expansion:
- ✅ Xiaohongshu (XHS) - Fully implemented
- 🔜 Douyin (TikTok China)
- 🔜 Kuaishou
- 🔜 Weibo
- 🔜 Xianyu
- 🔜 Taobao

## SDK Integration
Platform exposes底层SDK (underlying SDK) with transparent signature algorithm implementation:
- PC端登录 (QR code/SMS), search, note details, comments, user profiles
- Creator platform login, media upload, published works management
- 蒲公英平台 (Pugongying): KOL list, fan demographics, collaboration requests
- 千帆平台 (Qianfan): Distributor list, product categories
- 千帆客服工作台 (Customer Service): Conversation list, message history, AI reply suggestions
- 千帆卖家后台 (Seller Backend): Product management, order tracking, data dashboard

## Skills Compatibility
SDK packaged as standardized skills for integration with:
- Clawbot
- Claude Code
- OpenAI Codex
- Other AI agent toolchains

Repository: [XhsSkills](https://github.com/cv-cat/XhsSkills)
