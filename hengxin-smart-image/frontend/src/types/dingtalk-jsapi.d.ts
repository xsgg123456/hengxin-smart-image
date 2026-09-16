declare module "dingtalk-jsapi" {
  interface AuthCodeOptions {
    corpId: string;
    clientId: string;
    onSuccess?: (result: { code?: string }) => void;
    onFail?: (error?: unknown) => void;
  }

  function requestAuthCode(
    options: AuthCodeOptions,
  ): Promise<{ code?: string }> | void;

  export { requestAuthCode };
  const dd: { requestAuthCode: typeof requestAuthCode };
  export default dd;
}
