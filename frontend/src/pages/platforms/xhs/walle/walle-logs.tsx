import { ClearOutlined, PauseCircleOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { Badge, Button, Space, Tag, Typography } from "antd";
import { useEffect, useRef, useState } from "react";
import { getAccessToken } from "../../../../lib/api";

const { Text } = Typography;

interface LogEntry {
  ts: string;
  level: "info" | "success" | "warning" | "error";
  text: string;
  app_cid?: string;
  sender_type?: string;
  ping?: boolean;
}

const LEVEL_COLOR: Record<string, string> = {
  info: "blue",
  success: "green",
  warning: "orange",
  error: "red",
};

export function WalleLogsTab() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [connected, setConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);

  pausedRef.current = paused;

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    const es = new EventSource(`/api/walle/logs/stream?token=${encodeURIComponent(token)}`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const entry: LogEntry = JSON.parse(e.data);
        if (entry.ping) return;
        if (!pausedRef.current) {
          setLogs((prev) => [...prev.slice(-499), entry]);
        }
      } catch {}
    };
    return () => { es.close(); setConnected(false); };
  }, []);

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, paused]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 120px)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <Space>
          <Badge status={connected ? "processing" : "error"} text={connected ? "已连接" : "未连接"} />
          <Text type="secondary" style={{ fontSize: 12 }}>{logs.length} 条</Text>
        </Space>
        <Space>
          <Button
            size="small"
            icon={paused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
            onClick={() => setPaused((p) => !p)}
          >
            {paused ? "继续" : "暂停"}
          </Button>
          <Button size="small" icon={<ClearOutlined />} onClick={() => setLogs([])}>
            清空
          </Button>
        </Space>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          background: "#0d0d0d",
          borderRadius: 6,
          padding: "8px 12px",
          fontFamily: "monospace",
          fontSize: 12,
          lineHeight: "22px",
        }}
      >
        {logs.length === 0 && (
          <Text type="secondary" style={{ fontSize: 12 }}>等待日志...</Text>
        )}
        {logs.map((log, i) => (
          <div key={i} style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
            <Text style={{ color: "#555", flexShrink: 0 }}>{log.ts}</Text>
            <Tag color={LEVEL_COLOR[log.level] ?? "default"} style={{ margin: 0, flexShrink: 0 }}>
              {log.level}
            </Tag>
            <Text style={{ color: "#d4d4d4", wordBreak: "break-all" }}>{log.text}</Text>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
