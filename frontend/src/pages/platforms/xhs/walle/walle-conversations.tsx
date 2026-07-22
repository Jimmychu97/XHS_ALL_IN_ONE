import { RobotOutlined, SyncOutlined, UserOutlined } from "@ant-design/icons";
import {
  Avatar, Badge, Button, Empty, List, Select, Space, Spin, Tag, Typography, message,
} from "antd";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import {
  fetchAccounts, fetchWalleConversations, fetchWalleMessages,
  updateWalleConversationStatus, walleAiSuggest, walleSync,
} from "../../../../lib/api";
import type { PlatformAccount, WalleConversation, WalleMessage } from "../../../../types";

const { Text } = Typography;

function MessageContent({ content, contentType }: { content: string; contentType: string }) {
  if (!content) return <span>[{contentType}]</span>;
  // 图片消息："[图片] https://..."
  const imgMatch = content.match(/^\[图片\]\s*(https?:\/\/\S+)/);
  if (imgMatch) {
    const proxyUrl = `/api/walle/img-proxy?url=${encodeURIComponent(imgMatch[1])}`;
    return <img src={proxyUrl} alt="图片" style={{ maxWidth: 200, maxHeight: 200, borderRadius: 4, display: "block" }} />;
  }
  return <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{content}</span>;
}

const STATUS_COLOR: Record<string, string> = { open: "blue", replied: "green", closed: "default" };
const STATUS_LABEL: Record<string, string> = { open: "待回复", replied: "已回复", closed: "已关闭" };

export function WalleConversationsTab() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [convs, setConvs] = useState<WalleConversation[]>([]);
  const [selected, setSelected] = useState<WalleConversation | null>(null);
  const [messages, setMessages] = useState<WalleMessage[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState("");

  useEffect(() => {
    fetchAccounts("xhs").then((list) => {
      setAccounts(list);
      const first = list[0];
      if (first) setAccountId(first.id);
    });
  }, []);

  useEffect(() => {
    if (!accountId) return;
    fetchWalleConversations({ platform_account_id: accountId, page_size: 50 })
      .then((res) => setConvs(res.items))
      .catch(() => {});
  }, [accountId]);

  const handleSync = async () => {
    if (!accountId) return;
    setSyncing(true);
    try {
      const res = await walleSync(accountId);
      if (res.success) {
        message.success(`同步完成：${res.conversations} 个会话，${res.messages} 条消息`);
        const res2 = await fetchWalleConversations({ platform_account_id: accountId, page_size: 50 });
        setConvs(res2.items);
      } else {
        message.error(res.msg || "同步失败");
      }
    } finally {
      setSyncing(false);
    }
  };

  const handleSelectConv = async (conv: WalleConversation) => {
    setSelected(conv);
    setSuggestion("");
    setLoadingMsgs(true);
    try {
      const res = await fetchWalleMessages(conv.id, { page_size: 100 });
      setMessages(res.items);
    } finally {
      setLoadingMsgs(false);
    }
  };

  const handleAiSuggest = async () => {
    if (!selected) return;
    setSuggesting(true);
    try {
      const res = await walleAiSuggest(selected.id);
      if (res.success) setSuggestion(res.suggestion);
      else message.error("获取 AI 建议失败");
    } finally {
      setSuggesting(false);
    }
  };

  const handleStatusChange = async (status: string) => {
    if (!selected) return;
    await updateWalleConversationStatus(selected.id, status);
    setSelected({ ...selected, status });
    setConvs((prev) => prev.map((c) => c.id === selected.id ? { ...c, status } : c));
  };

  return (
    <div>
      <PageHeader
        eyebrow="千帆客服"
        title="会话管理"
        description="查看买家会话，获取 AI 建议回复"
        action={
          <Space>
            <Select
              placeholder="选择账号"
              value={accountId}
              onChange={setAccountId}
              style={{ width: 180 }}
              options={accounts.map((a) => ({ label: a.nickname || a.external_user_id, value: a.id }))}
            />
            <Button icon={<SyncOutlined />} loading={syncing} onClick={() => void handleSync()}>
              同步消息
            </Button>
          </Space>
        }
      />

      <div style={{ display: "flex", gap: 16, height: "calc(100vh - 200px)" }}>
        {/* 左侧会话列表 */}
        <div style={{ width: 300, flexShrink: 0, border: "1px solid #303030", borderRadius: 8, overflow: "auto" }}>
          {convs.length === 0 ? (
            <Empty description="暂无会话，点击同步消息" style={{ marginTop: 60 }} />
          ) : (
            <List
              dataSource={convs}
              renderItem={(conv) => (
                <List.Item
                  key={conv.id}
                  onClick={() => void handleSelectConv(conv)}
                  style={{
                    padding: "12px 16px",
                    cursor: "pointer",
                    background: selected?.id === conv.id ? "rgba(22,104,220,0.1)" : "transparent",
                    borderBottom: "1px solid #262626",
                  }}
                >
                  <List.Item.Meta
                    avatar={<Avatar icon={<UserOutlined />} size={36} />}
                    title={
                      <Space size={4}>
                        <Text style={{ fontSize: 13 }}>{conv.customer_name || conv.customer_id || "买家"}</Text>
                        {conv.unread_count > 0 && <Badge count={conv.unread_count} size="small" />}
                      </Space>
                    }
                    description={
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                          {conv.last_msg_content || "暂无消息"}
                        </Text>
                        <div style={{ marginTop: 2 }}>
                          <Tag color={STATUS_COLOR[conv.status] ?? "default"} style={{ fontSize: 11 }}>
                            {STATUS_LABEL[conv.status] ?? conv.status}
                          </Tag>
                        </div>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </div>

        {/* 右侧消息区 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", border: "1px solid #303030", borderRadius: 8, overflow: "hidden" }}>
          {!selected ? (
            <Empty description="选择左侧会话查看消息" style={{ margin: "auto" }} />
          ) : (
            <>
              {/* 顶部操作栏 */}
              <div style={{ padding: "10px 16px", borderBottom: "1px solid #303030", display: "flex", alignItems: "center", gap: 12 }}>
                <Text strong>{selected.customer_name || "买家"}</Text>
                <Select
                  size="small"
                  value={selected.status}
                  onChange={(v) => void handleStatusChange(v)}
                  options={[
                    { label: "待回复", value: "open" },
                    { label: "已回复", value: "replied" },
                    { label: "已关闭", value: "closed" },
                  ]}
                  style={{ width: 100 }}
                />
                <Button
                  size="small"
                  icon={<RobotOutlined />}
                  loading={suggesting}
                  onClick={() => void handleAiSuggest()}
                >
                  AI 建议
                </Button>
              </div>

              {/* 消息列表 */}
              <div style={{ flex: 1, overflowY: "auto", padding: 16 }}>
                {loadingMsgs ? (
                  <Spin style={{ display: "block", margin: "40px auto" }} />
                ) : messages.length === 0 ? (
                  <Empty description="暂无消息记录" />
                ) : (
                  messages.map((m) => (
                    <div
                      key={m.id}
                      style={{
                        display: "flex",
                        justifyContent: m.sender_type === "customer" ? "flex-start" : "flex-end",
                        marginBottom: 12,
                      }}
                    >
                      {m.sender_type === "customer" && (
                        <Avatar icon={<UserOutlined />} size={28} style={{ marginRight: 8, flexShrink: 0 }} />
                      )}
                      <div
                        style={{
                          maxWidth: "70%",
                          background: m.sender_type === "customer" ? "rgba(255,255,255,0.08)" : "#1668dc",
                          borderRadius: 8,
                          padding: "8px 12px",
                          fontSize: 13,
                          lineHeight: 1.6,
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                        }}
                      >
                        <MessageContent content={m.content} contentType={m.content_type} />
                        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginTop: 4, textAlign: "right" }}>
                          {m.msg_time ? new Date(m.msg_time).toLocaleTimeString("zh-CN") : ""}
                        </div>
                      </div>
                      {m.sender_type !== "customer" && (
                        <Avatar icon={<RobotOutlined />} size={28} style={{ marginLeft: 8, flexShrink: 0, background: "#1668dc" }} />
                      )}
                    </div>
                  ))
                )}
              </div>

              {/* AI 建议区 */}
              {suggestion && (
                <div style={{ padding: "12px 16px", borderTop: "1px solid #303030", background: "rgba(22,104,220,0.06)" }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>AI 建议回复：</Text>
                  <div style={{ marginTop: 4, fontSize: 13, whiteSpace: "pre-wrap" }}>{suggestion}</div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
