<template>
  <OverseasWorkspace
    :page="page"
    :role="previewSession.overseasRole === 'admin' ? 'operator' : previewSession.overseasRole"
    @navigate="navigate"
  />
</template>
<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import OverseasWorkspace from "./PreviewWorkspace.vue";
import { previewSession } from "./session";
const route = useRoute(),
  router = useRouter();
const page = computed(() =>
  route.path.endsWith("/tasks")
    ? "tasks"
    : route.path.endsWith("/archive")
      ? "archive"
      : "create",
);
function navigate(value: "create" | "tasks" | "archive") {
  void router.push(`/overseas/${value}`);
}
</script>
