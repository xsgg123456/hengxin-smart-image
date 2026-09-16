import type { User } from "../../types/hengxin";
import { createRequest, ApiError } from "./http";
import { isMockMode } from "./client";

export { requestContainerAuthCode } from "./container-auth";

export interface DingTalkAuthConfig {
  configured: boolean;
  corpId: string;
  clientId: string;
  callbackPath: string;
}

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";
const request = createRequest(API_BASE);

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
