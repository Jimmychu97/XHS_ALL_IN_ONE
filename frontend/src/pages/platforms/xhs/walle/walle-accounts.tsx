import { Alert, Avatar, Button, Card, Col, Empty, message, Modal, Row, Space, Tag, Typography } from "antd";
import { DeleteOutlined, ImportOutlined, ReloadOutlined, UserOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import { deleteAccount, fetchWalleAccounts, importWalleEvaAccount } from "../../../../lib/api";
import type { PlatformAccount } from "../../../../types";

const { Text } = Typography;

export function WalleAccountsTab() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await fetchWalleAccounts();
      setAccounts(res.items);
    } finally {
      setLoading(false);
    }
  }

  async function handleImport() {
    setImporting(true);
    try {
      await importWalleEvaAccount();
      message.success("千帆客服工作台账号已绑定");
      void load();
    } catch {
      message.error("导入失败，请确认 cookie_watcher.py 已运行且 F:\\eva\\eva_cookies.json 存在");
    } finally {
      setImporting(false);
    }
  }

  function handleDelete(account: PlatformAccount) {
    Modal.confirm({
      title: "删除账号",
      content: `删除「${account.nickname || account.id}」？`,
      okText: "确认删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: async () => {
        await deleteAccount(account.id);
        setAccounts((prev) => prev.filter((a) => a.id !== account.id));
      },
    });
  }

  useEffect(() => { void load(); }, []);

  return (
    <div>
      <PageHeader
        eyebrow="千帆客服"
        title="账号管理"
        description="绑定千帆客服工作台账号，需先运行 cookie_watcher.py 保活脚本"
        action={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
            <Button type="primary" icon={<ImportOutlined />} loading={importing} onClick={handleImport}>
              导入凭证
            </Button>
          </Space>
        }
      />

      <Alert
        type="info"
        showIcon
        message="使用前请先启动保活脚本"
        description={<code>python F:\eva\cookie_watcher.py</code>}
        style={{ marginBottom: 24 }}
      />

      {accounts.length === 0 && !loading ? (
        <Empty
          image={<UserOutlined style={{ fontSize: 48, color: "rgba(255,255,255,0.25)" }} />}
          imageStyle={{ height: 64 }}
          description={<Text style={{ color: "rgba(255,255,255,0.45)" }}>暂无绑定账号，点击「导入凭证」读取 eva_cookies.json</Text>}
        />
      ) : (
        <Row gutter={[16, 16]}>
          {accounts.map((account) => (
            <Col xs={24} sm={12} md={8} key={account.id}>
              <Card
                size="small"
                style={{ background: "#1a1a1a", borderColor: "#303030", borderLeft: "3px solid #fa8c16" }}
                styles={{ body: { padding: 20 } }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                  <Avatar size={40} icon={<UserOutlined />} style={{ background: "#3d1a00" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text strong ellipsis style={{ display: "block", color: "rgba(255,255,255,0.88)" }}>
                      {account.nickname || "千帆客服工作台"}
                    </Text>
                    <Text style={{ fontSize: 12, color: "rgba(255,255,255,0.35)" }}>
                      ID: {account.external_user_id || "-"}
                    </Text>
                  </div>
                  <Tag color={account.status === "active" ? "green" : "red"}>
                    {account.status === "active" ? "正常" : "过期"}
                  </Tag>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 12, borderTop: "1px solid #303030" }}>
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(account)}>
                    删除
                  </Button>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
