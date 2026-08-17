# XHS_ALL_IN_ONE 服务器部署指南（方案A：Windows Server 整机部署）

> 适用：把整个系统（后端 + 前端 + 千帆客服工作台 + Ark 保活）搬到一台 Windows Server 上。
> 前置要求：**Windows Server 2019/2022（带 GUI）**，因为千帆客服工作台是 Electron Windows 应用，且 Ark 首次登录需要浏览器。

---

## 0. 架构约束（为什么推荐整机 Windows）

| 组件 | 依赖 | 说明 |
|---|---|---|
| 千帆客服工作台（Walle） | Windows + Electron + CDP 端口 9222 | 只能 Windows 运行，必须常开 |
| cookie_watcher.py | 连接本机 9222 → 推送后端 | 随工作台一起跑 |
| ark_capture.py | Playwright 浏览器，首次需有头登录 | 登录一次后 daemon 保活 |
| 后端 + 前端 | Python / Node | Windows 可直接跑 |

---

## 1. 服务器准备

- **系统**：Windows Server 2019 / 2022（带桌面体验），保持 RDP 会话可交互（登录浏览器用）
- **软件**：
  - Python 3.11（勾选 Add to PATH）
  - Node.js 20 LTS
  - Git
- **防火墙**：放行 `8000`（或经 nginx 反代 443）；`9222` / `9223` **仅限本机**

## 2. 安装千帆客服工作台（关键步骤）

1. 安装工作台到 `F:\eva`（保持与本项目默认路径一致）
2. 打补丁开启调试端口 9222：
   ```bash
   asar extract F:\eva\resources\app.asar F:\eva\resources\app-unpacked
   # 编辑 F:\eva\resources\app-unpacked\main\window\main.cjs 的 initCommandLine()
   #   添加：app.commandLine.appendSwitch('remote-debugging-port', '9222')
   asar pack F:\eva\resources\app-unpacked F:\eva\resources\app.asar
   ```
3. 打开工作台并**登录账号**，保持常开
4. 设置**开机自启**：`shell:startup` 放快捷方式，或任务计划程序 → 登录时启动

## 3. 部署代码

```bash
cd C:\srv
git clone https://github.com/cv-cat/XHS_ALL_IN_ONE.git
cd XHS_ALL_IN_ONE

pip install -r requirements.txt
npm install
cd frontend && npm install && cd ..
playwright install chromium        # Ark 需要
```

## 4. 配置（换机器必做）

1. 复制 `config/default.yaml` 为 `config/production.yaml`（或直接改 default.yaml）
2. **必须更换密钥**（旧密钥已暴露，换机器后不要沿用）：
   ```yaml
   security:
     secret_key: "<随机长字符串>"
     fernet_key: "<随机 Fernet key>"
   ```
3. 数据库：
   - **SQLite**：把旧机的 `data/spider_xhs.db` 拷到新机 `data/` 下
   - **MySQL**（可选）：`DATABASE_TYPE=mysql` + `DATABASE_URL`，先 `alembic upgrade head`
4. 确认 `walle.eva_dir` 指向 `F:/eva`

## 5. 登录初始化（一次性，RDP 操作）

```bash
python main.py --with-frontend
```

1. 浏览器打开 `http://localhost:5173` → 注册/登录平台账号
2. **绑定 XHS 账号**（PC / Creator）：扫码或短信登录（换机器后 XHS 可能风控，建议重新登录）
3. **Ark 首次登录**：
   ```bash
   python ark_capture.py        # 有头模式，浏览器里登录 ark，Ctrl+C 保存 cookie
   ```
   之后 `main.py` 会自动拉起 `ark_capture.py --daemon` 保活
4. 确认客服工作台在线（`eva_cookies.json` 有更新）

## 6. 常驻运行（开机自启）

- **方式一（推荐）**：任务计划程序 → 创建任务 → 触发器"启动时" → 操作 `python main.py --with-frontend`（工作目录设为项目根）
- **方式二**：NSSM 注册为 Windows 服务：
  ```bash
  nssm install SpiderXHS "C:\Python311\python.exe" "C:\srv\XHS_ALL_IN_ONE\main.py" "--with-frontend"
  nssm set SpiderXHS AppDirectory "C:\srv\XHS_ALL_IN_ONE"
  nssm start SpiderXHS
  ```

> ✅ `main.py` 已内置**进程守护**：cookie_watcher / ark_capture 崩溃自动重启（退避 5s→60s），无需额外工具。

## 7. 安全加固

- **8000 不直接暴露公网**：用 nginx / Caddy 反代 + HTTPS
  ```nginx
  server {
      listen 443 ssl;
      server_name your-domain.com;
      location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }
  }
  ```
- **防火墙**：9222 / 9223 / 5173 只允许本机；3306 只允许内网
- 换密钥后**重新扫码登录**各 XHS 账号（IP/UA 变化，旧会话可能失效）

## 8. 监控与备份（已内置）

- **凭证心跳检查**：每小时检查 backend_token / eva_cookies / edith_auth / ark_cookies 新鲜度，异常写入站内通知
- **backend_token 自愈**：临期/无效自动重签，无需人工
- **数据库每日备份**：`data/backup/spider_xhs_YYYYMMDD_HHMMSS.db`，保留 7 天
- **日志轮转**：`data/logs/backend.log` 按天轮转，保留 14 天
- **外部监控**：uptimerobot / 阿里云监控定时打 `GET /api/health`

## 9. 常见坑

| 坑 | 解决 |
|---|---|
| 工作台没开 → Walle 推送断流 | 开机自启工作台；凭证检查会发通知 |
| 换机器后 XHS 风控 | 重新扫码登录，别硬用旧 cookie |
| Ark 同步无数据 | 先有头登录一次（Ctrl+C 保存 cookie） |
| 服务器时区不对 | 设置上海时区（代码用 `shanghai_now()`） |
| SQLite 并发量大 | 切 MySQL（docker-compose 已备好 mysql 配置） |

## 10. 上线前检查清单

- [ ] 防火墙：9222/9223/5173 仅本机，8000 或 443 对外
- [ ] `secret_key` / `fernet_key` 已更换
- [ ] 数据库已迁移（SQLite 拷贝或 MySQL）
- [ ] 平台账号已重新扫码绑定
- [ ] Ark 已登录一次并保存 cookie
- [ ] 客服工作台常开 + 开机自启
- [ ] `python main.py --with-frontend` 重启后各模块日志正常
- [ ] 外部监控已接入 `/api/health`
- [ ] 第一次每日备份已生成（`data/backup/`）
