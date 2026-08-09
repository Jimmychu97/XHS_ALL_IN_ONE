import { Alert, Button, Drawer, Segmented, message } from "antd";
import { useState } from "react";

import type { PlatformAccount } from "../../types";
import { QrLoginPanel } from "./qr-login-panel";
import { PhoneLoginPanel } from "./phone-login-panel";
import { CookieImportPanel } from "./cookie-import-panel";

type AddAccountDrawerProps = {
  open: boolean;
  onClose: () => void;
  onBound: () => void;
};

type LoginMethod = "qr" | "phone" | "cookie";

const loginMethodOptions = [
  { label: "二维码", value: "qr" as const },
  { label: "手机验证码", value: "phone" as const },
  { label: "Cookie", value: "cookie" as const },
];

export function AddAccountDrawer({ open, onClose, onBound }: AddAccountDrawerProps) {
  const [method, setMethod] = useState<LoginMethod>("qr");

  function handleConfirmed(account: PlatformAccount) {
    const actionText = account.action === "updated" ? "已更新到账号矩阵" : "已加入账号矩阵";
    message.success(`${account.nickname || "账号"} ${actionText}`);
    onBound();
  }

  return (
    <Drawer
      title={
        <div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 4, textTransform: "uppercase", letterSpacing: 1 }}>
            XHS Account
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, color: "rgba(255,255,255,0.88)" }}>添加小红书 PC 账号</div>
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
      <Alert
        type="info"
        showIcon
        message="账号矩阵仅支持 PC 账号"
        description="用于搜索、抓取笔记和账号健康检查。其他账号类型请在对应功能模块内绑定。"
        style={{ marginBottom: 20 }}
      />

      <div style={{ marginBottom: 24 }}>
        <Segmented
          block
          value={method}
          options={loginMethodOptions}
          onChange={(val) => setMethod(val as LoginMethod)}
        />
      </div>

      {method === "qr" ? (
        <QrLoginPanel accountType="pc" onConfirmed={handleConfirmed} />
      ) : method === "cookie" ? (
        <CookieImportPanel accountType="pc" onImported={handleConfirmed} />
      ) : (
        <PhoneLoginPanel accountType="pc" onConfirmed={handleConfirmed} />
      )}
    </Drawer>
  );
}
