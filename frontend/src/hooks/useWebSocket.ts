"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface WebSocketState {
  lastMessage: unknown;
  sendMessage: (msg: unknown) => void;
  connected: boolean;
}

export function useWebSocket(url: string): WebSocketState {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<unknown>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();
  const reconnectDelay = useRef(1000);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;
    try {
      const socket = new WebSocket(url);
      ws.current = socket;

      socket.onopen = () => {
        setConnected(true);
        reconnectDelay.current = 1000;
      };
      socket.onmessage = (event) => {
        try {
          setLastMessage(JSON.parse(event.data));
        } catch {
          setLastMessage(event.data);
        }
      };
      socket.onclose = () => {
        setConnected(false);
        ws.current = null;
        reconnectTimeout.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
          connect();
        }, reconnectDelay.current);
      };
      socket.onerror = () => {
        socket.close();
      };
    } catch {
      setConnected(false);
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      ws.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((msg: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  }, []);

  return { lastMessage, sendMessage, connected };
}
