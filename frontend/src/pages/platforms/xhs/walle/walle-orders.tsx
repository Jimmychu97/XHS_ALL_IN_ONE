import { Select, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import { PageHeader } from "../../../../components/layout/app-shell";
import { fetchAccounts, fetchWalleOrders } from "../../../../lib/api";
import type { PlatformAccount, WalleOrder } from "../../../../types";

const STATUS_MAP: Record<number, { label: string; color: string }> = {
  0: { label: "待核销", color: "blue" },
  1: { label: "成功",   color: "green" },
  2: { label: "失败",   color: "red" },
  3: { label: "已过期", color: "default" },
};

export function WalleOrdersTab() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [orders, setOrders] = useState<WalleOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchAccounts("xhs").then((list) => {
      setAccounts(list);
      if (list[0]) setAccountId(list[0].id);
    });
  }, []);

  useEffect(() => {
    if (!accountId) return;
    load(1);
  }, [accountId]);

  const load = async (p: number) => {
    if (!accountId) return;
    setLoading(true);
    try {
      const res = await fetchWalleOrders(accountId, { page: p, page_size: 20 });
      setOrders(res.items);
      setTotal(res.total);
      setPage(p);
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<WalleOrder> = [
    { title: "会话 ID", dataIndex: "app_cid", ellipsis: true, width: 200 },
    { title: "序列号/IMEI", dataIndex: "sn_imei", width: 160 },
    { title: "卡券号", dataIndex: "coupon_code", width: 140 },
    { title: "商品", dataIndex: "goods_name", ellipsis: true },
    { title: "规格", dataIndex: "spec", width: 100 },
    { title: "订单号", dataIndex: "order_sn", width: 140 },
    {
      title: "状态", dataIndex: "status", width: 90,
      render: (v: number) => {
        const s = STATUS_MAP[v] ?? { label: String(v), color: "default" };
        return <Tag color={s.color}>{s.label}</Tag>;
      },
    },
    {
      title: "时间", dataIndex: "created_at", width: 160,
      render: (v: string) => new Date(v).toLocaleString("zh-CN"),
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="千帆客服"
        title="核销记录"
        description="查看序列号/IMEI + 卡券核销流程记录"
        action={
          <Select
            placeholder="选择账号"
            value={accountId}
            onChange={(v) => { setAccountId(v); }}
            style={{ width: 180 }}
            options={accounts.map((a) => ({ label: a.nickname || a.external_user_id, value: a.id }))}
          />
        }
      />
      <Table
        rowKey="id"
        columns={columns}
        dataSource={orders}
        loading={loading}
        size="small"
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: (p) => void load(p),
        }}
      />
    </div>
  );
}
