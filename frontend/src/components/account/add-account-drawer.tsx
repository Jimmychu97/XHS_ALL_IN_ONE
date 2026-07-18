import { Alert, Button, Drawer, Input, Segmented, message } from "antd";
import { useState } from "react";
import { ChromeOutlined, LockOutlined, UserOutlined } from "@ant-design/icons";

import type { PlatformAccount } from "../../types";
import { startQianfanBrowserLogin, pollQianfanLoginStatus } from "../../lib/api";
import { CookieImportPanel } from "./cookie-import-panel";
import { PhoneLoginPanel } from "./phone-login-panel";
import { QrLoginPanel } from "./qr-login-panel";

type AddAccountDrawerProps = {
  open: boolean;
  onClose: () => void;
  onBound: () => void;
};

type AccountType = "pc" | "creator" | "qianfan";
type LoginMethod = "qr" | "phone" | "cookie" | "browser";

const accountTypeOptions = [
  { label: "PC", value: "pc" as const },
  { label: "Creator", value: "creator" as const },
  { label: "千帆", value: "qianfan" as const },
];

const pcCreatorLoginMethodOptions = [
  { label: "二维码", value: "qr" as const },
  { label: "手机验证码", value: "phone" as const },
  { label: "Cookie", value: "cookie" as const },
];

const qianfanLoginMethodOptions = [
  { label: "账号密码", value: "browser" as const },
  { label: "Cookie", value: "cookie" as const },
];

export function AddAccountDrawer({ open, onClose, onBound }: AddAccountDrawerProps) {
  const [accountType, setAccountType] = useState<AccountType>("pc");
  const [method, setMethod] = useState<LoginMethod>("qr");
  const [browserLoginStatus, setBrowserLoginStatus] = useState<string>("");
  const [isBrowserLoggingIn, setIsBrowserLoggingIn] = useState(false);
  const [browserUsername, setBrowserUsername] = useState("");
  const [browserPassword, setBrowserPassword] = useState("");

  function handleConfirmed(account: PlatformAccount) {
    const actionText = account.action === "updated" ? "已更新到账号矩阵" : "已加入账号矩阵";
    message.success(`${account.nickname || "账号"} ${actionText}`);
    onBound();
  }

  async function handleBrowserLogin() {
    if (!browserUsername || !browserPassword) {
      message.warning("请输入账号和密码");
      return;
    }

    setIsBrowserLoggingIn(true);
    setBrowserLoginStatus("正在启动浏览器...");

    try {
      await startQianfanBrowserLogin(browserUsername, browserPassword);

      const pollInterval = setInterval(async () => {
        try {
          const result = await pollQianfanLoginStatus();
          setBrowserLoginStatus(result.message);

          if (result.status === "success" || result.status === "saved") {
            clearInterval(pollInterval);
            setIsBrowserLoggingIn(false);
            message.success("千帆账号登录成功！");
            onBound();
          } else if (result.status === "error" || result.status === "timeout") {
            clearInterval(pollInterval);
            setIsBrowserLoggingIn(false);
          }
        } catch {
          // 继续轮询
        }
      }, 2000);
    } catch (e) {
      setIsBrowserLoggingIn(false);
      setBrowserLoginStatus("启动失败：" + String(e));
    }
  }

  const isQianfan = accountType === "qianfan";
  const loginMethodOptions = isQianfan ? qianfanLoginMethodOptions : pcCreatorLoginMethodOptions;

  return (
    <Drawer
      title={
        <div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
            XHS Account
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, color: "rgba(255,255,255,0.88)" }}>添加小红书账号</div>
        </div>
      }
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
      destroyOnClose
      styles={{
        header: { background: "#1f1f1f", borderBottom: "1px solid #303030" },
        body: { background: "#141414", padding: 24 },
      }}
    >
      <div style={{ marginBottom: 20 }}>
        <Segmented
          block
          value={accountType}
          options={accountTypeOptions}
          onChange={(val) => {
            const t = val as AccountType;
            setAccountType(t);
            setMethod(t === "qianfan" ? "browser" : "qr");
          }}
        />
      </div>

      <div style={{ marginBottom: 24 }}>
        <Segmented
          block
          value={method}
          options={loginMethodOptions}
          onChange={(val) => setMethod(val as LoginMethod)}
        />
      </div>

      {method === "qr" ? (
        <QrLoginPanel accountType={accountType as "pc" | "creator"} onConfirmed={handleConfirmed} />
      ) : method === "cookie" ? (
        <CookieImportPanel accountType={accountType} onImported={handleConfirmed} />
      ) : method === "browser" ? (
        <div>
          <Alert
            type="info"
            showIcon
            message="千帆账号密码登录"
            description="输入千帆平台账号密码，系统将自动打开浏览器完成登录并保存 Cookie。需要已安装 Playwright 浏览器。"
            style={{ marginBottom: 16 }}
          />
          <div style={{ marginBottom: 12 }}>
            <Input
              prefix={<UserOutlined />}
              placeholder="手机号 / 账号"
              value={browserUsername}
              onChange={(e) => setBrowserUsername(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              value={browserPassword}
              onChange={(e) => setBrowserPassword(e.target.value)}
            />
          </div>
          {browserLoginStatus && !isBrowserLoggingIn && (
            <Alert
              type={browserLoginStatus.startsWith("启动失败") ? "error" : "warning"}
              message={browserLoginStatus}
              showIcon
              style={{ marginBottom: 12 }}
            />
          )}
          <Button
            type="primary"
            block
            size="large"
            icon={<ChromeOutlined />}
            onClick={handleBrowserLogin}
            loading={isBrowserLoggingIn}
            disabled={!browserUsername || !browserPassword}
          >
            {isBrowserLoggingIn ? browserLoginStatus || "登录中..." : "打开浏览器登录"}
          </Button>
        </div>
      ) : (
        <PhoneLoginPanel accountType={accountType as "pc" | "creator"} onConfirmed={handleConfirmed} />
      )}
    </Drawer>
  );
}
