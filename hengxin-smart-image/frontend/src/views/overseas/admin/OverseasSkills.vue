<template><OverseasSkillCatalog :skills="catalog" @refresh="refresh" /></template>
<script setup lang="ts">
import { ref } from 'vue'
import type { Skill } from '@/api/overseas/management'
import { skills } from './management-adapter'
import OverseasSkillCatalog from './OverseasSkillCatalog.vue'
const catalog = ref<Skill[]>([])
function refresh() { catalog.value = skills.map(skill => ({ ...skill })) }
refresh()
</script>
