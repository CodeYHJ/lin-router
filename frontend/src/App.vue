<script setup>
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import AppShell from './layouts/AppShell.vue'
import { useRouterStore } from './stores/router'

const routerStore = useRouterStore()
onMounted(() => routerStore.load())
</script>

<template>
  <AppShell>
    <RouterView />
  </AppShell>
</template>
