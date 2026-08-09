import { Avatar, Button, Card, Col, Empty, Modal, Row, Space, Tag, Typography } from "antd";
import { App } from "antd";
import { DeleteOutlined, ReloadOutlined, UserOutlined, WarningOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import { deleteAccount, fetchWalleAccounts, http } from "../../../../lib/api";
import type { PlatformAccount } from "../../../../types";

const { Text } = Typography;

async function autoImport(): Promise<{ ok: boolean; reason?: string; login_url?: string } & Partial<PlatformAccount>> {
  const res = await http.post<{ ok: boolean; reason?: string; login_url?: string } & Partial<PlatformAccount>>(
    "/walle/accounts/auto-import"
  );
  return res.data;
}

export function WalleAccountsTab() {
  const { message } = App.useApp();
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [noCredential, setNoCredential] = useState(false);

  async function load(silent = false) {
    if (!silent) setLoading(true);
    try {
      // 先静默自动导入
      const result = await autoImport();
      if (!result.ok && result.reason === "no_cookie") {
        setNoCredential(true);
      } else {
        setNoCredential(false);
      }
      // 再拉账号列表
      const res = await fetchWalleAccounts();
      setAccounts(res.items);
    } finally {
      setLoading(false);
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
        description="自动读取 cookie_watcher.py 保存的凭证，无需手动操作"
        action={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>刷新</Button>
          </Space>
        }
      />

      {noCredential && (
        <Card
          style={{ marginBottom: 24, borderColor: "#faad14", background: "#2a1f00" }}
          size="small"
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <WarningOutlined style={{ color: "#faad14", fontSize: 20 }} />
            <div style={{ flex: 1 }}>
              <Text strong style={{ color: "#faad14" }}>未检测到千帆客服凭证</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>
                请确认 cookie_watcher.py 已运行，或手动打开工作台登录后刷新
              </Text>
            </div>
            <Button
              size="small"
              onClick={() => window.open("https://walle.xiaohongshu.com", "_blank")}
            >
              打开工作台
            </Button>
          </div>
        </Card>
      )}

      {accounts.length === 0 && !loading ? (
        <Empty
          image={<UserOutlined style={{ fontSize: 48, color: "rgba(255,255,255,0.25)" }} />}
          imageStyle={{ height: 64 }}
          description={<Text style={{ color: "rgba(255,255,255,0.45)" }}>暂无绑定账号</Text>}
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
