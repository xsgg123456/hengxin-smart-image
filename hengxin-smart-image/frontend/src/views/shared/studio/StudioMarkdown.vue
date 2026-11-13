<template><div class="studio-markdown" v-html="html"></div></template>
<script setup lang="ts">
import { computed } from 'vue'
import { renderStudioMarkdown } from './studio-markdown'
const props = defineProps<{ text: string }>()
const html = computed(() => renderStudioMarkdown(props.text))
</script>
