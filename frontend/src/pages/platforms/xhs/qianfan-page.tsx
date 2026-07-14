import {
  MessageOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  ShopOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  Avatar,
  Button,
  Card,
  Col,
  Drawer,
  Empty,
  Input,
  List,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "../../../components/layout/app-shell";
import {
  fetchAccounts,
  fetchQianFanCategories,
  fetchQianFanDistributors,
  fetchQianFanDistributorDetail,
  qianFanAiChat,
  qianFanGenerateMessage,
} from "../../../lib/api";
import type { PlatformAccount } from "../../../types";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

type Distributor = {
  distributor_id: string;
  nickname: string;
  avatar: string;
  fans_count: number;
  live_first_category: string[];
  live_second_category: string[];
  recent_sales?: number;
};

type ChatMsg = { role: "user" | "assistant"; content: string };

function DistributorCard({
  item,
  onChat,
  onDetail,
}: {
  item: Distributor;
  onChat: (d: Distributor) => void;
  onDetail: (d: Distributor) => void;
}) {
  return (
    <Card
      size="small"
      hoverable
      style={{ marginBottom: 12 }}
      onClick={() => onDetail(item)}
    >
      <Row align="middle" gutter={12}>
        <Col>
          <Avatar size={48} src={item.avatar} icon={<UserOutlined />} />
        </Col>
        <Col flex={1}>
          <Text strong>{item.nickname}</Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>
            粉丝 {item.fans_count?.toLocaleString() ?? "-"}
          </Text>
          <div style={{ marginTop: 4 }}>
            {(item.live_first_category ?? []).slice(0, 3).map((c) => (
              <Tag key={c} color="blue" style={{ fontSize: 11 }}>
                {c}
              </Tag>
            ))}
          </div>
        </Col>
        <Col>
          <Button
            type="primary"
            size="small"
            icon={<MessageOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onChat(item);
            }}
          >
            AI 客服
          </Button>
        </Col>
      </Row>
    </Card>
  );
}

function AiChatPanel({
  distributor,
  onClose,
}: {
  distributor: Distributor | null;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    setInput("");
  }, [distributor?.distributor_id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || !distributor) return;
    const userMsg: ChatMsg = { role: "user", content: input.trim() };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await qianFanAiChat({
        messages: next,
        distributor_context: {
          nickname: distributor.nickname,
          fans: distributor.fans_count,
          category: (distributor.live_first_category ?? []).join("、"),
        },
      });
      setMessages([...next, { role: "assistant", content: res.reply }]);
    } catch {
      message.error("AI 回复失败");
    } finally {
      setLoading(false);
    }
  };

  const generateOpening = async (intent: string) => {
    if (!distributor) return;
    setGenerating(true);
    try {
      const res = await qianFanGenerateMessage({
        distributor_info: {
          nickname: distributor.nickname,
          fans: distributor.fans_count,
          category: (distributor.live_first_category ?? []).join("、"),
        },
        intent,
      });
      setInput(res.message);
    } catch {
      message.error("生成失败");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Drawer
      title={
        <Space>
          <RobotOutlined />
          {distributor ? `AI 客服 — ${distributor.nickname}` : "AI 客服"}
        </Space>
      }
      open={!!distributor}
      onClose={onClose}
      width={480}
      styles={{ body: { display: "flex", flexDirection: "column", padding: 16, gap: 12 } }}
    >
      {/* 快捷生成按钮 */}
      <Space wrap>
        <Text type="secondary" style={{ fontSize: 12 }}>
          快速生成：
        </Text>
        {["合作邀约", "询问档期", "报价咨询", "感谢合作"].map((intent) => (
          <Button
            key={intent}
            size="small"
            loading={generating}
            onClick={() => generateOpening(intent)}
          >
            {intent}
          </Button>
        ))}
      </Space>

      {/* 消息列表 */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          background: "rgba(255,255,255,0.03)",
          borderRadius: 8,
          padding: 12,
          minHeight: 300,
        }}
      >
        {messages.length === 0 ? (
          <Empty description="发送消息开始对话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  maxWidth: "80%",
                  background: m.role === "user" ? "#1668dc" : "rgba(255,255,255,0.08)",
                  borderRadius: 8,
                  padding: "8px 12px",
                  fontSize: 13,
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                }}
              >
                {m.content}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div style={{ textAlign: "center", padding: 8 }}>
            <Spin size="small" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* 输入框 */}
      <Space.Compact style={{ width: "100%" }}>
        <TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入消息..."
          autoSize={{ minRows: 2, maxRows: 4 }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          style={{ flex: 1 }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={() => void send()}
          loading={loading}
          style={{ height: "auto" }}
        >
          发送
        </Button>
      </Space.Compact>
    </Drawer>
  );
}

export function QianFanPage() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [categories, setCategories] = useState<{ first_category: string; second_category: string[] }[]>([]);
  const [choice, setChoice] = useState("-1");
  const [page, setPage] = useState(1);
  const [distributors, setDistributors] = useState<Distributor[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [chatTarget, setChatTarget] = useState<Distributor | null>(null);
  const [detailTarget, setDetailTarget] = useState<Distributor | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchAccounts("xhs").then((list) => {
      setAccounts(list);
      const pc = list.find((a) => a.sub_type === "pc");
      if (pc) setAccountId(pc.id);
    });
  }, []);

  useEffect(() => {
    if (!accountId) return;
    fetchQianFanCategories(accountId)
      .then((res) => setCategories(res.items ?? []))
      .catch(() => {});
  }, [accountId]);

  const loadDistributors = async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const res = await fetchQianFanDistributors(accountId, choice, page);
      setDistributors(res.items ?? []);
      setTotal(res.total ?? 0);
    } catch {
      message.error("获取分销商列表失败");
    } finally {
      setLoading(false);
    }
  };

  const openDetail = async (d: Distributor) => {
    if (!accountId) return;
    setDetailTarget(d);
    setDetailLoading(true);
    try {
      const res = await fetchQianFanDistributorDetail(accountId, d.distributor_id);
      setDetail(res);
    } catch {
      message.error("获取详情失败");
    } finally {
      setDetailLoading(false);
    }
  };

  const categoryOptions = [
    { label: "全部品类", value: "-1" },
    ...categories.map((c, i) => ({ label: c.first_category, value: String(i) })),
  ];

  return (
    <div>
      <PageHeader
        eyebrow="千帆平台"
        title="千帆分销商"
        description="浏览分销商列表，使用 AI 客服一键生成合作消息"
        action={
          <Space>
            <Select
              placeholder="选择账号"
              value={accountId}
              onChange={setAccountId}
              style={{ width: 160 }}
              options={accounts.map((a) => ({ label: a.nickname || a.external_user_id, value: a.id }))}
            />
            <Select
              value={choice}
              onChange={(v) => { setChoice(v); setPage(1); }}
              style={{ width: 160 }}
              options={categoryOptions}
            />
            <Button
              type="primary"
              icon={<SearchOutlined />}
              onClick={() => void loadDistributors()}
              loading={loading}
            >
              搜索
            </Button>
          </Space>
        }
      />

      <Spin spinning={loading}>
        {distributors.length === 0 ? (
          <Empty
            image={<ShopOutlined style={{ fontSize: 48, color: "rgba(255,255,255,0.2)" }} />}
            description="选择账号和品类后点击搜索"
          />
        ) : (
          <List
            dataSource={distributors}
            pagination={{ current: page, total, pageSize: 20, onChange: (p) => { setPage(p); void loadDistributors(); } }}
            renderItem={(item) => (
              <DistributorCard
                key={item.distributor_id}
                item={item}
                onChat={setChatTarget}
                onDetail={openDetail}
              />
            )}
          />
        )}
      </Spin>

      {/* 详情抽屉 */}
      <Drawer
        title={detailTarget?.nickname ?? "分销商详情"}
        open={!!detailTarget}
        onClose={() => { setDetailTarget(null); setDetail(null); }}
        width={480}
      >
        {detailLoading ? (
          <Spin />
        ) : detail ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Card size="small" title="基本信息">
              <Paragraph>
                <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(detail.detail, null, 2)}
                </pre>
              </Paragraph>
            </Card>
            <Card size="small" title="合作品类">
              <Paragraph>
                <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(detail.cooperation, null, 2)}
                </pre>
              </Paragraph>
            </Card>
            <Button
              type="primary"
              icon={<MessageOutlined />}
              block
              onClick={() => {
                if (detailTarget) { setChatTarget(detailTarget); setDetailTarget(null); }
              }}
            >
              开启 AI 客服对话
            </Button>
          </Space>
        ) : null}
      </Drawer>

      {/* AI 客服对话 */}
      <AiChatPanel distributor={chatTarget} onClose={() => setChatTarget(null)} />
    </div>
  );
}
