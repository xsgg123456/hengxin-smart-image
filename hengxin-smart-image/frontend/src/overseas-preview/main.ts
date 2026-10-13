import { createApp, h, watch } from "vue";
import { createPinia } from "pinia";
import { router } from "@/router";
import language from "@/locales";
import { useMenuStore } from "@/store/modules/menu";
import { useSettingStore } from "@/store/modules/setting";
import { useWorktabStore } from "@/store/modules/worktab";
import { initializeTheme } from "@/hooks/core/useTheme";
import { useSettingsHandlers } from "@/components/core/layouts/art-settings-panel/composables/useSettingsHandlers";
import { setupRippleDirective } from "@/directives/business/ripple";
import type { AppRouteRecord } from "@/types/router";
import PreviewApp from "./PreviewApp.vue";
import { permittedPath } from "./access";
import { previewSession } from "./session";
import "@styles/core/tailwind.css";
import "@styles/index.scss";
import "@/views/hengxin/prototype.css";

// 独立 Pinia，不安装一期持久化插件，不执行一期 bootstrap、鉴权守卫或 API。
const app = createApp(PreviewApp);
app.use(createPinia()).use(language);
setupRippleDirective(app);
const settings = useSettingStore();
settings.showFastEnter = false;
settings.showSettingGuide = false;
settings.showFestivalText = false;
initializeTheme();
useSettingsHandlers().domOperations.setRootAttribute(
  "data-box-mode",
  settings.boxBorderMode ? "border-mode" : "shadow-mode",
);

for (const route of router.getRoutes())
  if (route.name) router.removeRoute(route.name);
const entries = [
  ["create", "提交图需", "ri:add-box-line"],
  ["tasks", "工作流任务", "ri:flow-chart"],
  ["archive", "成品库", "ri:folder-check-line"],
] as const;
const menus: AppRouteRecord[] = entries.map(([key, title, icon]) => ({
  path: `/overseas/${key}`,
  name: `overseas-${key}`,
  component: () => import("./WorkspacePage.vue"),
  meta: { title, icon },
}));
const managementEntries = [
  ['usage', '调用统计', 'ri:bar-chart-line'],
  ['monitor', '执行监控', 'ri:pulse-line'],
  ['users', '用户与角色', 'ri:group-line'],
  ['skills', 'Skill 管理', 'ri:code-box-line'],
  ['settings', '系统配置', 'ri:settings-3-line'],
] as const;
const managementMenu: AppRouteRecord = {
  path: '/overseas/management', name: 'overseas-management',
  meta: { title: '管理中心', icon: 'ri:settings-3-line' },
  children: managementEntries.map(([key, title, icon]) => ({
    path: `/overseas/management/${key}`, name: `overseas-management-${key}`,
    component: () => import('@/views/overseas/admin/OverseasManagement.vue'),
    meta: { title, icon },
  })),
};
watch(() => [previewSession.overseasRole, previewSession.overseas], () => {
  useMenuStore().setMenuList(previewSession.overseas && previewSession.overseasRole === 'admin'
    ? [...menus, managementMenu] : menus);
}, { immediate: true, flush: 'sync' });
for (const [key, title] of managementEntries) router.addRoute({
  path: `/overseas/management/${key}`, name: `overseas-management-${key}`,
  component: () => import('@/views/overseas/admin/OverseasManagement.vue'),
  props: { page: key }, meta: { title },
});
const emptyPage = { render: () => h("div") };
for (const path of ["/auth/login", "/business", "/domestic"])
  router.addRoute({ path, component: emptyPage });
for (const [key, title] of entries)
  router.addRoute({
    path: `/overseas/${key}`,
    name: `overseas-${key}`,
    component: () => import("./WorkspacePage.vue"),
    meta: { title },
  });
router.addRoute({ path: "/:pathMatch(.*)*", redirect: "/business" });
router.beforeEach((to) => {
  const permitted = permittedPath(previewSession, to.path);
  if (permitted !== to.path) return permitted;
  if (to.path === "/domestic") {
    // 国内预览仍由一期原有入口加载，海外状态不传递给一期。
    window.location.assign("/?role=operator#/api-image-edits/create");
    return false;
  }
  return true;
});
router.afterEach((to) => {
  document.title = `${to.meta.title || "选择业务"} · 恒鑫智图`;
  if (to.path.startsWith("/overseas/"))
    useWorktabStore().openTab({
      title: String(to.meta.title),
      path: to.path,
      name: String(to.name),
      keepAlive: false,
    });
});
app.use(router);
void router.isReady().then(() => app.mount("#app"));
