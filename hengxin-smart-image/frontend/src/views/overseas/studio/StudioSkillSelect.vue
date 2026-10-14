<template>
  <ElSelect v-model="value" clearable filterable fit-input-width :disabled="disabled" placeholder="选择 Skill（可选）" aria-label="选择 Skill" popper-class="studio-skill-options">
    <ElOption v-for="item in skills" :key="item.id" :value="item.id" :label="item.displayName">
      <strong>{{ item.displayName }}</strong>
      <p>{{ item.description || '暂无描述' }}</p>
    </ElOption>
  </ElSelect>
  <ElButton v-if="selected" text size="small" @click="detailsOpen = true">查看 Skill 说明</ElButton>
  <ElDialog v-model="detailsOpen" :title="selected?.displayName" width="min(640px,94vw)" append-to-body>
    <p class="studio-skill-description">{{ selected?.description || '暂无描述' }}</p>
  </ElDialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Studio } from '@/api/overseas/studio'
const props = defineProps<{ skills: Studio['skills']; disabled: boolean }>()
const value = defineModel<string>({ required: true })
const selected = computed(() => props.skills.find(item => item.id === value.value))
const detailsOpen = ref(false)
</script>
