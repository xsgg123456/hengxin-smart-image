import { reactive } from "vue";
import type { BusinessIdentity, AccessScenario, OverseasRole } from "./access";
import { previewIdentity } from "./access";
import { resetOverseasPreview } from "@/views/overseas/preview-adapter";
import { resetOverseasManagement } from "@/views/overseas/admin/management-adapter";
export const previewSession = reactive<BusinessIdentity>({
  authenticated: false,
  domestic: false,
  overseas: false,
  overseasRole: "operator",
});
export function authorizePreview(scenario: AccessScenario, role: OverseasRole) {
  Object.assign(previewSession, previewIdentity(scenario, role));
}
export function logoutPreview() {
  resetOverseasPreview();
  resetOverseasManagement();
  Object.assign(previewSession, {
    authenticated: false,
    domestic: false,
    overseas: false,
  });
}
