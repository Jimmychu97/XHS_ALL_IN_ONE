import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Input, Popconfirm, Select, Space, Tag, message } from "antd";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import { createWalleKeyword, deleteWalleKeyword, fetchAccounts, fetchWalleKeywords } from "../../../../lib/api";
import type { PlatformAccount, WalleKeyword } from "../../../../types";

export function WalleKeywordsTab() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [keywords, setKeywords] = useState<WalleKeyword[]>([]);
  const [input, setInput] = useState("");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    fetchAccounts("xhs").then((list) => {
      setAccounts(list);
      if (list[0]) setAccountId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (!accountId) return;
    fetchWalleKeywords(accountId).then((res) => setKeywords(res.items));
  }, [accountId]);

  const handleAdd = async () => {
    const kw = input.trim();
    if (!kw || !accountId) return;
    setAdding(true);
    try {
      const item = await createWalleKeyword(accountId, kw);
      setKeywords((prev) => [...prev, item]);
      setInput("");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteWalleKeyword(id);
    setKeywords((prev) => prev.filter((k) => k.id !== id));
    message.success("已删除");
  };

  return (
    <div>
      <PageHeader
        eyebrow="千帆客服"
        title="转人工关键词"
        description="买家消息命中关键词时自动转接人工客服，截断 AI 链路"
        action={
          <Select
            placeholder="选择账号"
            value={accountId}
            onChange={setAccountId}
            style={{ width: 180 }}
            options={accounts.map((a) => ({ label: a.nickname || a.external_user_id, value: a.id }))}
          />
        }
      />

      <Space.Compact style={{ marginBottom: 24 }}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入关键词，如：人工、退款、投诉"
          style={{ width: 300 }}
          onPressEnter={() => void handleAdd()}
        />
        <Button type="primary" icon={<PlusOutlined />} loading={adding} onClick={() => void handleAdd()}>
          添加
        </Button>
      </Space.Compact>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {keywords.map((kw) => (
          <Tag
            key={kw.id}
            closable
            onClose={(e) => { e.preventDefault(); void handleDelete(kw.id); }}
            style={{ fontSize: 14, padding: "4px 10px" }}
          >
            {kw.keyword}
          </Tag>
        ))}
        {keywords.length === 0 && (
          <span style={{ color: "rgba(255,255,255,0.35)", fontSize: 13 }}>暂无关键词，添加后生效</span>
        )}
      </div>
    </div>
  );
}
