export interface ContainerAuthConfig {
  configured: boolean;
  corpId: string;
  clientId: string;
  callbackPath: string;
}

export interface ContainerAuthCodeResult {
  code?: string;
}

export interface ContainerAuthCodeOptions {
  corpId: string;
  clientId: string;
  onSuccess: (response: ContainerAuthCodeResult) => void;
  onFail: (error?: unknown) => void;
}

export type ContainerAuthCodeInvoker = (
  options: ContainerAuthCodeOptions,
) => void | Promise<unknown>;

interface DingTalkJsapiModule {
  default?: DingTalkJsapiModule;
  requestAuthCode?: ContainerAuthCodeInvoker;
  runtime?: { permission?: { requestAuthCode?: ContainerAuthCodeInvoker } };
}

function resolveAuthCodeRequest(
  module: DingTalkJsapiModule,
): ContainerAuthCodeInvoker | undefined {
  const dd = module.default ?? module;
  return (
    dd.requestAuthCode ??
    dd.runtime?.permission?.requestAuthCode ??
    module.requestAuthCode
  );
}

async function invokeDingTalkAuthCode(
  options: ContainerAuthCodeOptions,
): Promise<void> {
  const module = (await import("dingtalk-jsapi")) as DingTalkJsapiModule;
  const request = resolveAuthCodeRequest(module);
  if (typeof request !== "function") {
    throw new Error("钉钉 JSAPI 未初始化");
  }
  const pending = request({
    corpId: options.corpId,
    clientId: options.clientId,
    onSuccess: options.onSuccess,
    onFail: options.onFail,
  });
  if (pending && typeof (pending as Promise<unknown>).then === "function") {
    const result = (await pending) as ContainerAuthCodeResult | undefined;
    if (typeof result?.code === "string" && result.code) {
      options.onSuccess({ code: result.code });
    }
  }
}

export async function requestContainerAuthCode(
  config: ContainerAuthConfig,
  invoke: ContainerAuthCodeInvoker = invokeDingTalkAuthCode,
): Promise<string> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const succeed = (code: string) => {
      if (settled) return;
      settled = true;
      resolve(code);
    };
    const fail = (error: unknown) => {
      if (settled) return;
      settled = true;
      reject(
        error instanceof Error ? error : new Error("钉钉免登授权失败"),
      );
    };
    try {
      const pending = invoke({
        corpId: config.corpId,
        clientId: config.clientId,
        onSuccess: (response) => {
          typeof response.code === "string" && response.code
            ? succeed(response.code)
            : fail(new Error("钉钉未返回授权码"));
        },
        onFail: fail,
      });
      void Promise.resolve(pending).catch(fail);
    } catch (error) {
      fail(error);
    }
  });
}
