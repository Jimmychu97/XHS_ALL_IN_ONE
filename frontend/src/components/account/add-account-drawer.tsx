import { Alert, Button, Drawer, Input, Segmented, message } from "antd";
import { useState } from "react";
import { ImportOutlined } from "@ant-design/icons";

import type { PlatformAccount } from "../../types";
import { importWalleEvaAccount } from "../../lib/api";
import { CookieImportPanel } from "./cookie-import-panel";
import { PhoneLoginPanel } from "./phone-login-panel";
import { QrLoginPanel } from "./qr-login-panel";

type AddAccountDrawerProps = {
  open: boolean;
  onClose: () => void;
  onBound: () => void;
};

type AccountType = "pc" | "creator" | "qianfan" | "walle";
type LoginMethod = "qr" | "phone" | "cookie" | "eva";

const accountTypeOptions = [
  { label: "PC", value: "pc" as const },
  { label: "Creator", value: "creator" as const },
  { label: "千帆", value: "qianfan" as const },
  { label: "千帆客服", value: "walle" as const },
];

const pcCreatorLoginMethodOptions = [
  { label: "二维码", value: "qr" as const },
  { label: "手机验证码", value: "phone" as const },
  { label: "Cookie", value: "cookie" as const },
];

const qianfanLoginMethodOptions = [
  { label: "Cookie", value: "cookie" as const },
];

const walleLoginMethodOptions = [
  { label: "导入凭证文件", value: "eva" as const },
];

export function AddAccountDrawer({ open, onClose, onBound }: AddAccountDrawerProps) {
  const [accountType, setAccountType] = useState<AccountType>("pc");
  const [method, setMethod] = useState<LoginMethod>("qr");
  const [evaPath, setEvaPath] = useState(String.raw`F:\eva\eva_cookies.json`);
  const [importing, setImporting] = useState(false);

  function handleConfirmed(account: PlatformAccount) {
    const actionText = account.action === "updated" ? "已更新到账号矩阵" : "已加入账号矩阵";
    message.success(`${account.nickname || "账号"} ${actionText}`);
    onBound();
  }

  async function handleImportEva() {
    setImporting(true);
    try {
      const account = await importWalleEvaAccount(evaPath);
      handleConfirmed(account as PlatformAccount & { action?: string });
    } catch {
      message.error("导入失败，请确认 cookie_watcher.py 已运行且文件存在");
    } finally {
      setImporting(false);
    }
  }

  const isWalle = accountType === "walle";
  const isQianfan = accountType === "qianfan";
  const loginMethodOptions = isWalle
    ? walleLoginMethodOptions
    : isQianfan
    ? qianfanLoginMethodOptions
    : pcCreatorLoginMethodOptions;

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
            setMethod(t === "walle" ? "eva" : t === "qianfan" ? "cookie" : "qr");
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

      {method === "eva" ? (
        <div>
          <Alert
            type="info"
            showIcon
            message="千帆客服工作台凭证导入"
            description={
              <span>
                请先运行保活脚本：<br />
                <code>python F:\eva\cookie_watcher.py</code><br />
                脚本会自动将凭证写入 eva_cookies.json，然后点击下方按钮导入。
              </span>
            }
            style={{ marginBottom: 16 }}
          />
          <Input
            value={evaPath}
            onChange={(e) => setEvaPath(e.target.value)}
            placeholder={String.raw`F:\eva\eva_cookies.json`}
            style={{ marginBottom: 12 }}
          />
          <Button
            type="primary"
            block
            icon={<ImportOutlined />}
            loading={importing}
            onClick={handleImportEva}
          >
            {importing ? "导入中..." : "读取凭证并绑定账号"}
          </Button>
        </div>
      ) : method === "qr" ? (
        <QrLoginPanel accountType={accountType as "pc" | "creator"} onConfirmed={handleConfirmed} />
      ) : method === "cookie" ? (
        <CookieImportPanel accountType={accountType as "pc" | "creator" | "qianfan"} onImported={handleConfirmed} />
      ) : (
        <PhoneLoginPanel accountType={accountType as "pc" | "creator"} onConfirmed={handleConfirmed} />
      )}
    </Drawer>
  );
}
