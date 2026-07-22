import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import {
  Button, Form, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tag, message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import {
  createWalleKnowledge, deleteWalleKnowledge, fetchAccounts,
  fetchWalleKnowledge, updateWalleKnowledge,
} from "../../../../lib/api";
import type { PlatformAccount, WalleKnowledge } from "../../../../types";

const PRESET_TAGS = ["物流", "售后", "售前", "支付", "商品规格", "优惠券", "退换货", "发货时间"];

export function WalleKnowledgeTab() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [items, setItems] = useState<WalleKnowledge[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<WalleKnowledge | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchAccounts("xhs").then((list) => {
      setAccounts(list);
      if (list[0]) setAccountId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (!accountId) return;
    load();
  }, [accountId]);

  const load = async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const res = await fetchWalleKnowledge(accountId, { page_size: 200 });
      setItems(res.items);
    } finally {
      setLoading(false);
    }
  };

  const openAdd = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (item: WalleKnowledge) => {
    setEditing(item);
    form.setFieldsValue({
      title: item.title,
      content: item.content,
      tags: item.tags ? item.tags.split(",").filter(Boolean) : [],
      enabled: item.enabled,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    const payload = { ...values, tags: (values.tags as string[] ?? []).join(",") };
    if (editing) {
      await updateWalleKnowledge(editing.id, payload);
      message.success("更新成功");
    } else {
      await createWalleKnowledge(accountId!, payload);
      message.success("添加成功");
    }
    setModalOpen(false);
    void load();
  };

  const handleDelete = async (id: number) => {
    await deleteWalleKnowledge(id);
    message.success("删除成功");
    void load();
  };

  const columns: ColumnsType<WalleKnowledge> = [
    { title: "标题", dataIndex: "title", width: 180, ellipsis: true },
    {
      title: "内容", dataIndex: "content", ellipsis: true,
      render: (v: string) => <span title={v}>{v.slice(0, 60)}{v.length > 60 ? "…" : ""}</span>,
    },
    {
      title: "标签", dataIndex: "tags", width: 200,
      render: (v: string) => v ? v.split(",").filter(Boolean).map((t) => <Tag key={t}>{t}</Tag>) : "-",
    },
    {
      title: "状态", dataIndex: "enabled", width: 80,
      render: (v: boolean) => <Tag color={v ? "green" : "default"}>{v ? "启用" : "禁用"}</Tag>,
    },
    {
      title: "操作", width: 120,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="确认删除？" onConfirm={() => void handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="千帆客服"
        title="知识库"
        description="管理客服话术、FAQ 和规则，AI 回复时自动检索注入"
        action={
          <Space>
            <Select
              placeholder="选择账号"
              value={accountId}
              onChange={setAccountId}
              style={{ width: 180 }}
              options={accounts.map((a) => ({ label: a.nickname || a.external_user_id, value: a.id }))}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>添加知识</Button>
          </Space>
        }
      />

      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{ pageSize: 20 }}
        size="small"
      />

      <Modal
        title={editing ? "编辑知识" : "添加知识"}
        open={modalOpen}
        onOk={() => void handleSave()}
        onCancel={() => setModalOpen(false)}
        width={600}
      >
        <Form form={form} layout="vertical" initialValues={{ enabled: true }}>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input placeholder="例如：退换货政策" />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true }]}>
            <Input.TextArea rows={5} placeholder="输入客服话术内容..." />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" placeholder="选择或输入标签" options={PRESET_TAGS.map((t) => ({ label: t, value: t }))} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
