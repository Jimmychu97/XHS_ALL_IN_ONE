import {
  CloudSyncOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import {
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Image,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";

import { http as api } from "../../../../lib/api";
import type { ArkProduct, ArkServerConfig, ArkSyncResult, Paginated } from "../../../../types";

const { Text } = Typography;

const CARD_TYPE_OPTIONS = [
  { value: 2, label: "在售" },
  { value: 3, label: "仓库中" },
  { value: 4, label: "已售罄" },
  { value: 5, label: "审核中" },
  { value: 6, label: "已下架" },
  { value: 10, label: "违规下架" },
];

const CARD_TYPE_COLOR: Record<number, string> = {
  2: "green", 3: "blue", 4: "orange", 5: "gold", 6: "default", 10: "red",
};

// ── API helpers ───────────────────────────────────────────────────────────────

async function fetchServers(): Promise<ArkServerConfig[]> {
  const res = await api.get<{ items: ArkServerConfig[] }>("/ark/servers");
  return res.data.items;
}

async function importArk(serverId: string, cookieFile: string, profileDir: string): Promise<ArkServerConfig> {
  const res = await api.post<ArkServerConfig>("/ark/servers/import-ark", {
    server_id: serverId, cookie_file: cookieFile, profile_dir: profileDir,
  });
  return res.data;
}

async function deleteServer(id: number): Promise<void> {
  await api.delete(`/ark/servers/${id}`);
}

async function syncProducts(configId: number, cardTypes: number[]): Promise<ArkSyncResult> {
  const res = await api.post<ArkSyncResult>(`/ark/servers/${configId}/sync`, { card_types: cardTypes });
  return res.data;
}

async function fetchProducts(params: {
  server_config_id?: number; card_type?: number; keyword?: string; page: number; page_size: number;
}): Promise<Paginated<ArkProduct>> {
  const res = await api.get<Paginated<ArkProduct>>("/ark/products", { params });
  return res.data;
}

async function deleteProduct(id: number): Promise<void> {
  await api.delete(`/ark/products/${id}`);
}

async function fetchProductSkus(productId: number): Promise<{ item_id: string; skus: SkuDetail[] }> {
  const res = await api.get(`/ark/products/${productId}/skus`);
  return res.data;
}

type SkuDetail = {
  sku_id: string;
  sku_name: string;
  query_type: string | null;
  service_id: string | null;
  variants: { name: string; value: string }[];
  price: number | null;
  stock: number | null;
  delivery_time: string | null;
  delivery_type: number | null;
  spec_image: string | null;
  barcode: string | null;
};

async function patchSku(
  productId: number,
  skuId: string,
  data: { query_type?: string; service_id?: string },
): Promise<void> {
  await api.patch(`/ark/products/${productId}/skus/${skuId}`, data);
}

// ── Products Tab ──────────────────────────────────────────────────────────────

export function ProductsTab() {
  const { message } = App.useApp();
  const [servers, setServers] = useState<ArkServerConfig[]>([]);
  const [selectedServer, setSelectedServer] = useState<number | undefined>();
  const [cardType, setCardType] = useState<number | undefined>(2);
  const [keyword, setKeyword] = useState("");
  const [products, setProducts] = useState<ArkProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [detailProduct, setDetailProduct] = useState<ArkProduct | null>(null);
  const [skus, setSkus] = useState<SkuDetail[]>([]);
  const [skusLoading, setSkusLoading] = useState(false);
  const [skusLoadedFor, setSkusLoadedFor] = useState<number | null>(null);
  const [editingSkuId, setEditingSkuId] = useState<string | null>(null);
  const [editingValues, setEditingValues] = useState<{ query_type: string; service_id: string }>({ query_type: "", service_id: "" });
  const [savingSkuId, setSavingSkuId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const loadProducts = async (serverId: number | undefined, p = 1) => {
    if (!serverId) return;
    setLoading(true);
    try {
      const res = await fetchProducts({
        server_config_id: serverId,
        card_type: cardType,
        keyword: keyword || undefined,
        page: p,
        page_size: 20,
      });
      setProducts(res.items);
      setTotal(res.total);
    } catch { /* silent */ } finally { setLoading(false); }
  };

  const loadServers = async () => {
    try {
      const list = await fetchServers();
      // 自动刷新 seller_name 仍等于 server_id 的账号（首次添加时未能获取真实名称）
      const refreshed = await Promise.all(
        list.map(async s => {
          if (s.seller_name === s.server_id) {
            try {
              const res = await api.post<ArkServerConfig>(`/ark/servers/${s.id}/refresh-name`);
              return res.data;
            } catch { return s; }
          }
          return s;
        })
      );
      setServers(refreshed);
      if (refreshed.length > 0 && !selectedServer) {
        setSelectedServer(refreshed[0].id);
        void loadProducts(refreshed[0].id);
      }
    } catch { /* silent */ }
  };

  useEffect(() => { void loadServers(); }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void loadProducts(selectedServer); setPage(1); }, [selectedServer, cardType]);

  const handleSync = async () => {
    if (!selectedServer) { message.warning("请先选择一个账号"); return; }
    setSyncing(true);
    try {
      const res = await syncProducts(selectedServer, [2, 3, 4, 5, 6, 10]);
      message.success(`同步完成：${res.synced} 件商品${res.errors.length ? `，${res.errors.length} 个错误` : ""}`);
      void loadProducts(selectedServer);
    } catch { /* error shown by interceptor */ } finally { setSyncing(false); }
  };

  const handleAddServer = async (values: { server_id: string; cookie_file: string; profile_dir: string }) => {
    setSubmitting(true);
    try {
      const cfg = await importArk(values.server_id, values.cookie_file, values.profile_dir);
      message.success("添加成功");
      setAddOpen(false);
      form.resetFields();
      await loadServers();
      setSelectedServer(cfg.id);
    } catch { /* error shown by interceptor */ } finally { setSubmitting(false); }
  };

  const stats = CARD_TYPE_OPTIONS.map(opt => ({
    ...opt,
    count: products.filter(p => p.card_type === opt.value).length,
  }));

  const columns: ColumnsType<ArkProduct> = [
    {
      title: "封面", dataIndex: "cover_url", width: 64,
      render: url => url
        ? <Image src={url} width={48} height={48} style={{ objectFit: "cover", borderRadius: 4 }} preview={false} />
        : <div style={{ width: 48, height: 48, background: "#262626", borderRadius: 4 }} />,
    },
    {
      title: "商品名称", dataIndex: "title", ellipsis: true,
      render: (title, row) => (
        <Button type="link" style={{ padding: 0, textAlign: "left", height: "auto" }}
          onClick={() => {
            setDetailProduct(row);
            setSkus([]);
            setSkusLoadedFor(null);
            setSkusLoading(true);
            fetchProductSkus(row.id)
              .then(res => { setSkus(res.skus); setSkusLoadedFor(row.id); })
              .catch(() => {})
              .finally(() => setSkusLoading(false));
          }}>
          {title || row.item_id}
        </Button>
      ),
    },
    {
      title: "状态", dataIndex: "card_type", width: 90,
      render: (v, row) => <Tag color={CARD_TYPE_COLOR[v] || "default"}>{row.card_type_label}</Tag>,
    },
    { title: "库存", dataIndex: "total_stock", width: 80, sorter: (a, b) => a.total_stock - b.total_stock },
    { title: "SKU", dataIndex: "sku_count", width: 60 },
    { title: "30天销量", dataIndex: "sale_qty30", width: 90, sorter: (a, b) => a.sale_qty30 - b.sale_qty30 },
    { title: "累计销量", dataIndex: "acc_sale_qty", width: 90, sorter: (a, b) => a.acc_sale_qty - b.acc_sale_qty },
    {
      title: "同步时间", dataIndex: "synced_at", width: 140,
      render: v => new Date(v).toLocaleString("zh-CN"),
    },
    {
      title: "", width: 48,
      render: (_, row) => (
        <Popconfirm title="确认删除？" onConfirm={async () => {
          await deleteProduct(row.id); void loadProducts(selectedServer);
        }}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      {/* 统计卡片 */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        {stats.map(s => (
          <Col key={s.value}>
            <Card size="small" style={{ minWidth: 100, cursor: "pointer", border: cardType === s.value ? "1px solid #1668dc" : undefined }}
              onClick={() => setCardType(cardType === s.value ? undefined : s.value)}>
              <Statistic title={s.label} value={s.count} styles={{ content: { fontSize: 20 } }} />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 工具栏 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <Select
          placeholder="选择账号"
          style={{ width: 200 }}
          value={selectedServer}
          onChange={v => setSelectedServer(v)}
          options={servers.map(s => ({ value: s.id, label: s.seller_name || s.server_id }))}
        />
        <Button icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>添加账号</Button>
        <Select
          placeholder="商品状态"
          style={{ width: 120 }}
          allowClear
          value={cardType}
          onChange={setCardType}
          options={CARD_TYPE_OPTIONS}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void loadProducts(selectedServer)}>刷新</Button>
        <Button type="primary" icon={<CloudSyncOutlined />} loading={syncing} onClick={() => void handleSync()}>
          同步商品
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={products}
        loading={loading}
        size="small"
        pagination={{
          current: page,
          pageSize: 20,
          total,
          showSizeChanger: false,
          showTotal: t => `共 ${t} 件`,
          onChange: p => { setPage(p); void loadProducts(selectedServer, p); },
        }}
      />

      {/* 商品详情 */}
      <Modal title={detailProduct?.title || "商品详情"} open={!!detailProduct}
        onCancel={() => setDetailProduct(null)} footer={null} width="80vw" style={{ maxWidth: 1000 }}>
        {detailProduct && (
          <Tabs defaultActiveKey="info" items={[
              {
                key: "info",
                label: "基本信息",
                children: (
                  <div style={{ display: "flex", gap: 16 }}>
                    {detailProduct.cover_url && (
                      <Image src={detailProduct.cover_url} width={120} height={120} style={{ objectFit: "cover", borderRadius: 8, flexShrink: 0 }} />
                    )}
                    <div style={{ flex: 1 }}>
                      <Row gutter={[8, 8]}>
                        <Col span={12}><Text type="secondary">商品 ID</Text><br /><Text copyable>{detailProduct.item_id}</Text></Col>
                        <Col span={12}><Text type="secondary">状态</Text><br /><Tag color={CARD_TYPE_COLOR[detailProduct.card_type]}>{detailProduct.card_type_label}</Tag></Col>
                        <Col span={12}><Text type="secondary">库存</Text><br /><Text strong>{detailProduct.total_stock}</Text></Col>
                        <Col span={12}><Text type="secondary">SKU 数</Text><br /><Text>{detailProduct.sku_count}</Text></Col>
                        <Col span={12}><Text type="secondary">30天销量</Text><br /><Text strong style={{ color: "#52c41a" }}>{detailProduct.sale_qty30}</Text></Col>
                        <Col span={12}><Text type="secondary">累计销量</Text><br /><Text>{detailProduct.acc_sale_qty}</Text></Col>
                        {detailProduct.price_min != null && (
                          <Col span={24}>
                            <Text type="secondary">价格</Text><br />
                            <Text strong>¥{(detailProduct.price_min / 100).toFixed(2)}</Text>
                            {detailProduct.price_max !== detailProduct.price_min && (
                              <Text> ~ ¥{((detailProduct.price_max ?? 0) / 100).toFixed(2)}</Text>
                            )}
                          </Col>
                        )}
                        <Col span={24}><Text type="secondary">同步时间</Text><br /><Text>{new Date(detailProduct.synced_at).toLocaleString("zh-CN")}</Text></Col>
                      </Row>
                    </div>
                  </div>
                ),
              },
              {
                key: "skus",
                label: `规格明细${detailProduct.sku_count > 0 ? ` (${detailProduct.sku_count})` : ""}`,
                children: (
                  <Table<SkuDetail>
                    rowKey="sku_id"
                    size="small"
                    loading={skusLoading}
                    dataSource={skus}
                    pagination={false}
                    locale={{ emptyText: skusLoading ? "加载中..." : "暂无规格数据" }}
                    columns={[
                      {
                        title: "规格",
                        dataIndex: "variants",
                        render: (variants: SkuDetail["variants"]) =>
                          variants.map(v => <Tag key={v.name}>{v.name}：{v.value}</Tag>),
                      },
                      {
                        title: "查询类型",
                        dataIndex: "query_type",
                        render: (v: string | null, row: SkuDetail) =>
                          editingSkuId === row.sku_id ? (
                            <Input
                              size="small"
                              value={editingValues.query_type}
                              onChange={e => setEditingValues(prev => ({ ...prev, query_type: e.target.value }))}
                            />
                          ) : (v || "-"),
                      },
                      {
                        title: "服务ID",
                        dataIndex: "service_id",
                        render: (v: string | null, row: SkuDetail) =>
                          editingSkuId === row.sku_id ? (
                            <Input
                              size="small"
                              value={editingValues.service_id}
                              onChange={e => setEditingValues(prev => ({ ...prev, service_id: e.target.value }))}
                            />
                          ) : (v || "-"),
                      },
                      { title: "价格", dataIndex: "price", render: (v: number | null) => v != null ? `¥${(v / 100).toFixed(2)}` : "-" },
                      { title: "库存", dataIndex: "stock", render: (v: number | null) => v ?? "-" },
                      { title: "发货时效", dataIndex: "delivery_time", render: (v: string | null) => v ? `${v}h` : "-" },
                      { title: "条形码", dataIndex: "barcode", render: (v: string | null) => v || "-" },
                      {
                        title: "",
                        width: 64,
                        render: (_: unknown, row: SkuDetail) =>
                          editingSkuId === row.sku_id ? (
                            <Button
                              type="link"
                              size="small"
                              icon={<SaveOutlined />}
                              loading={savingSkuId === row.sku_id}
                              onClick={async () => {
                                if (!detailProduct) return;
                                setSavingSkuId(row.sku_id);
                                try {
                                  await patchSku(detailProduct.id, row.sku_id, editingValues);
                                  setSkus(prev => prev.map(s =>
                                    s.sku_id === row.sku_id
                                      ? { ...s, query_type: editingValues.query_type || null, service_id: editingValues.service_id || null }
                                      : s
                                  ));
                                  setEditingSkuId(null);
                                  message.success("已保存");
                                } catch { /* interceptor shows error */ } finally {
                                  setSavingSkuId(null);
                                }
                              }}
                            >
                              保存
                            </Button>
                          ) : (
                            <Button
                              type="text"
                              size="small"
                              icon={<EditOutlined />}
                              onClick={() => {
                                setEditingSkuId(row.sku_id);
                                setEditingValues({
                                  query_type: row.query_type || "",
                                  service_id: row.service_id || "",
                                });
                              }}
                            />
                          ),
                      },
                    ]}
                  />
                ),
              },
            ]}
          />
        )}
      </Modal>

      {/* 添加账号 */}
      <Modal title="添加千帆卖家账号" open={addOpen}
        onCancel={() => { setAddOpen(false); form.resetFields(); }}
        onOk={() => form.submit()} confirmLoading={submitting} okText="导入">
        <Form form={form} layout="vertical" onFinish={handleAddServer} style={{ marginTop: 8 }}>
          <Form.Item name="server_id" label="账号标识（自定义，如店铺名）"
            rules={[{ required: true, message: "请输入账号标识" }]}>
            <Input placeholder="例如：深度验机的店" />
          </Form.Item>
          <Form.Item name="cookie_file" label="ark_cookies.json 路径（留空使用默认）">
            <Input placeholder="留空 → data/ark_cookies.json" />
          </Form.Item>
          <Form.Item name="profile_dir" label="ark_profile 目录（留空使用默认）">
            <Input placeholder="留空 → data/ark_profile" />
          </Form.Item>
        </Form>
        <Text type="secondary" style={{ fontSize: 12 }}>
          添加前请先运行 <code>python ark_capture.py</code> 完成登录。
        </Text>
      </Modal>
    </>
  );
}

export function ArkPage() {
  return (
    <App>
      <div style={{ padding: "0 0 24px" }}>
        <ProductsTab />
      </div>
    </App>
  );
}
