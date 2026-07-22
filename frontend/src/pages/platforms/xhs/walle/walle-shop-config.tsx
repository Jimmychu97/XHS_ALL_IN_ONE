import { Button, Form, Input, Select, Space, Switch, App } from "antd";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import {
  fetchWalleAccounts, fetchWalleShopConfig, upsertWalleShopConfig,
} from "../../../../lib/api";
import type { PlatformAccount } from "../../../../types";

const DEFAULT_PERSONA = `你是一名专业的手机验机客服，负责帮助买家完成序列号核销和验机报告解读。
请用简洁、友好的语言回复买家，遇到不确定的问题先查知识库再回答。`;

export function WalleShopConfigTab() {
  const { message } = App.useApp();
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchWalleAccounts().then((res) => {
      setAccounts(res.items);
      if (res.items[0]) setAccountId(res.items[0].id);
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
        <Form.Item
          name="system_prompt"
          label="客服人设 Prompt"
          extra="留空则使用默认人设。此处只需填写角色定位，行为规则和工具说明由系统自动附加。"
        >
          <Input.TextArea
            rows={8}
            placeholder={DEFAULT_PERSONA}
          />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" loading={saving} onClick={() => void handleSave()}>
              保存配置
            </Button>
            <Button
              onClick={() => form.setFieldValue("system_prompt", DEFAULT_PERSONA)}
            >
              填入默认人设
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
}
