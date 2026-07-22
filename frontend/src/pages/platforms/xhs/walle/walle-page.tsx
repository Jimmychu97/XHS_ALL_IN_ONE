import { CustomerServiceOutlined, FileTextOutlined, KeyOutlined, ReadOutlined, SettingOutlined, ShoppingOutlined, TeamOutlined } from "@ant-design/icons";
import { Layout, Menu } from "antd";
import type { MenuProps } from "antd";
import { useState } from "react";
import { WalleAccountsTab } from "./walle-accounts";
import { WalleConversationsTab } from "./walle-conversations";
import { WalleKnowledgeTab } from "./walle-knowledge";
import { WalleKeywordsTab } from "./walle-keywords";
import { WalleLogsTab } from "./walle-logs";
import { WalleOrdersTab } from "./walle-orders";
import { WalleShopConfigTab } from "./walle-shop-config";

const { Sider, Content } = Layout;

type TabKey = "accounts" | "conversations" | "knowledge" | "keywords" | "orders" | "logs" | "shop-config";

const menuItems: MenuProps["items"] = [
  { key: "accounts",      icon: <TeamOutlined />,           label: "账号管理" },
  { key: "conversations", icon: <CustomerServiceOutlined />, label: "会话管理" },
  { key: "knowledge",     icon: <ReadOutlined />,            label: "知识库" },
  { key: "keywords",      icon: <KeyOutlined />,             label: "转人工关键词" },
  { key: "orders",        icon: <ShoppingOutlined />,        label: "核销记录" },
  { key: "logs",          icon: <FileTextOutlined />,        label: "实时日志" },
  { key: "shop-config",   icon: <SettingOutlined />,         label: "AI 配置" },
];

export function WallePage() {
  const [tab, setTab] = useState<TabKey>("accounts");

  return (
    <Layout style={{ minHeight: "calc(100vh - 48px)", background: "transparent" }}>
      <Sider
        width={180}
        theme="dark"
        style={{ borderRight: "1px solid #303030", background: "#141414" }}
      >
        <div style={{ padding: "16px 16px 8px", color: "rgba(255,255,255,.45)", fontSize: 11, letterSpacing: 1, textTransform: "uppercase" }}>
          千帆客服
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[tab]}
          onClick={({ key }) => setTab(key as TabKey)}
          items={menuItems}
          style={{ borderRight: 0, background: "transparent" }}
        />
      </Sider>
      <Content style={{ padding: 24, overflow: "auto" }}>
        {tab === "accounts"      && <WalleAccountsTab />}
        {tab === "conversations" && <WalleConversationsTab />}
        {tab === "knowledge"     && <WalleKnowledgeTab />}
        {tab === "keywords"      && <WalleKeywordsTab />}
        {tab === "orders"        && <WalleOrdersTab />}
        {tab === "logs"          && <WalleLogsTab />}
        {tab === "shop-config"   && <WalleShopConfigTab />}
      </Content>
    </Layout>
  );
}
