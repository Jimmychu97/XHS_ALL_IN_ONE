import { Button, Form, Input, Select, Space, Switch, message } from "antd";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import {
  fetchAccounts, fetchWalleShopConfig, upsertWalleShopConfig,
} from "../../../../lib/api";
import type { PlatformAccount } from "../../../../types";

export function WalleShopConfigTab() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchAccounts("xhs").then((list) => {
      setAccounts(list);
      if (list[0]) setAccountId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (!accountId) return;
    fetchWalleShopConfig(accountId).then((cfg) => {
      form.setFieldsValue({
        ai_enabled: cfg.ai_enabled,
        auto_send: cfg.auto_send,
        model_config_id: cfg.model_config_id,
        system_prompt: cfg.system_prompt,
      });
    }).catch(() => {
      form.resetFields();
    });
  }, [accountId, form]);

  const handleSave = async () => {
    if (!accountId) return;
    const values = await form.validateFields();
    setSaving(true);
    try {
      await upsertWalleShopConfig(accountId, values);
      message.success("配置已保存");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="千帆客服"
        title="AI 配置"
        description="为每个千帆账号配置 AI 客服开关、模型和人设 Prompt"
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

      <Form
        form={form}
        layout="vertical"
        style={{ maxWidth: 600 }}
        initialValues={{ ai_enabled: false, auto_send: true, system_prompt: "" }}
      >
        <Form.Item name="ai_enabled" label="开启 AI 自动回复" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="auto_send" label="自动发送（关闭则仅生成建议，不自动发送）" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="system_prompt" label="客服人设 Prompt">
          <Input.TextArea
            rows={8}
            placeholder="例如：你是一名专业的手机验机客服，负责帮助买家完成序列号核销和验机报告解读..."
          />
        </Form.Item>
        <Form.Item>
          <Button type="primary" loading={saving} onClick={() => void handleSave()}>
            保存配置
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
}
