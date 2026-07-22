import { Button, Form, Input, Typography, App } from "antd";
import { useEffect, useState } from "react";
import { fetchWalleEvaConfig, saveWalleEvaConfig } from "../../../../lib/api";

const { Text } = Typography;

export function WalleEvaConfigTab() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();

  useEffect(() => {
    fetchWalleEvaConfig().then((r) => form.setFieldsValue({ eva_dir: r.eva_dir }));
  }, [form]);

  const onSave = async (values: { eva_dir: string }) => {
    setLoading(true);
    try {
      await saveWalleEvaConfig(values.eva_dir);
      message.success("保存成功，重启服务后生效");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 520 }}>
      <div style={{ marginBottom: 20 }}>
        <Text strong>EVA 安装目录</Text>
        <br />
        <Text type="secondary" style={{ fontSize: 12 }}>
          千帆客服工作台（EVA）的安装路径，例如 <code>D:/eva</code>。
          保存后重启服务，<code>cookie_watcher.py</code> 将从该目录启动。
        </Text>
      </div>
      <Form form={form} onFinish={onSave} layout="vertical">
        <Form.Item name="eva_dir" label="EVA 目录">
          <Input placeholder="例如 D:/eva 或 F:/eva" allowClear />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading}>
            保存
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
}
