export type Business = "domestic" | "overseas";
export type OverseasRole = "operator" | "designer" | "admin";
export type AccessScenario = "both" | "domestic" | "overseas" | "none";
export interface BusinessIdentity {
  authenticated: boolean;
  domestic: boolean;
  overseas: boolean;
  overseasRole: OverseasRole;
}
export function previewIdentity(
  scenario: AccessScenario,
  role: OverseasRole,
): BusinessIdentity {
  return {
    authenticated: true,
    domestic: scenario === "both" || scenario === "domestic",
    overseas: scenario === "both" || scenario === "overseas",
    overseasRole: role,
  };
}
export function mayEnter(
  identity: BusinessIdentity,
  business: Business,
): boolean {
  return identity.authenticated && identity[business];
}
export function permittedPath(
  identity: BusinessIdentity,
  path: string,
): string {
  if (!identity.authenticated) return "/auth/login";
  if (path.startsWith("/overseas/") && !mayEnter(identity, "overseas"))
    return "/business";
  if (path === "/domestic" && !mayEnter(identity, "domestic"))
    return "/business";
  if (path.startsWith("/overseas/management/") && identity.overseasRole !== "admin")
    return "/overseas/tasks";
  return path;
}
