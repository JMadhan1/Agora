"use client";

import { useState, useEffect } from "react";
import clsx from "clsx";

interface ToastProps {
  message: string;
  type?: "success" | "error" | "info";
  duration?: number;
  onClose?: () => void;
}

export function Toast({ message, type = "info", duration = 4000, onClose }: ToastProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => { setVisible(false); onClose?.(); }, duration);
    return () => clearTimeout(t);
  }, [duration, onClose]);

  if (!visible) return null;

  return (
    <div className={clsx(
      "fixed top-4 right-4 z-50 px-4 py-3 rounded-lg border shadow-xl text-sm font-medium max-w-sm",
      type === "success" && "bg-green-900 border-green-700 text-green-200",
      type === "error" && "bg-red-900 border-red-700 text-red-200",
      type === "info" && "bg-slate-800 border-slate-600 text-slate-200",
    )}>
      {message}
    </div>
  );
}
