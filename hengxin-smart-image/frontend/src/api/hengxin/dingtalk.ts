import type { User } from "../../types/hengxin";
import { createRequest, ApiError } from "./http";
import { isMockMode } from "./client";

export interface DingTalkAuthConfig {
  configured: boolean;
  corpId: string;
  clientId: string;
  callbackPath: string;
}

interface DingTalkCodeResponse {
  code?: string;
}
interface DingTalkAuthCodeOptions {
  clientId: string;
  corpId: string;
  success: (response: DingTalkCodeResponse) => void;
  fail: (error?: unknown) => void;
}
interface DingTalkClient {
  requestAuthCode(options: DingTalkAuthCodeOptions): void;
}
declare global {
  interface Window {
    dd?: DingTalkClient;
  }
}

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";
const request = createRequest(API_BASE);
const SDK_URL =
  "https://g.alicdn.com/dingding/dingtalk-jsapi/2.15.15/dingtalk.open.js";
let sdkPromise: Promise<void> | undefined;

function validConfig(value: unknown): value is DingTalkAuthConfig {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.configured === "boolean" &&
    typeof item.corpId === "string" &&
    typeof item.clientId === "string" &&
    typeof item.callbackPath === "string"
  );
}

export function getDingTalkConfig(): Promise<DingTalkAuthConfig> {
  if (isMockMode)
    return Promise.resolve({
      configured: false,
      corpId: "",
      clientId: "",
      callbackPath: "",
    });
  return request("/auth/dingtalk/config", validConfig);
}

export function startBrowserAuthorization(returnPath: string): void {
  const url = `${API_BASE.replace(/\/$/, "")}/auth/dingtalk/authorize?redirect=${encodeURIComponent(returnPath)}`;
  window.location.assign(url);
}

async function loadSdk(): Promise<void> {
  if (window.dd) return;
  sdkPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SDK_URL;
    script.async = true;
    script.onload = () =>
      window.dd ? resolve() : reject(new Error("钉钉 JSAPI 未初始化"));
    script.onerror = () => reject(new Error("钉钉 JSAPI 加载失败"));
    document.head.appendChild(script);
  });
  await sdkPromise;
}

export async function requestContainerAuthCode(
  config: DingTalkAuthConfig,
): Promise<string> {
  await loadSdk();
  return new Promise((resolve, reject) => {
    window.dd?.requestAuthCode({
      clientId: config.clientId,
      corpId: config.corpId,
      success: (response) =>
        typeof response.code === "string" && response.code
          ? resolve(response.code)
          : reject(new Error("钉钉未返回授权码")),
      fail: (error) =>
        reject(error instanceof Error ? error : new Error("钉钉免登授权失败")),
    });
  });
}

export function loginByContainer(code: string): Promise<User> {
  return request(
    "/auth/dingtalk/container",
    (value: unknown): value is User => {
      if (!value || typeof value !== "object" || Array.isArray(value))
        return false;
      const item = value as Record<string, unknown>;
      return (
        typeof item.id === "string" &&
        typeof item.name === "string" &&
        (item.role === null || typeof item.role === "string") &&
        ["pending", "active", "disabled"].includes(String(item.status))
      );
    },
    "POST",
    { code },
  );
}

export function dingtalkErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "钉钉认证失败，请稍后重试";
}
