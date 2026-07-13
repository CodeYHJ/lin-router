<script setup>
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import ConnectionTree from '../components/ConnectionTree.vue'
import { useRouterStore } from '../stores/router'

const route = useRoute()
const routerStore = useRouterStore()
const apiBaseUrl = computed(() => `${window.location.origin}/v1`)

async function copyBaseUrl() {
  try {
    await navigator.clipboard.writeText(apiBaseUrl.value)
  } catch (_) {
    // Clipboard may be denied for non-secure localhost contexts; the URL remains visible.
  }
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/dashboard">Lin Router <span>v0.6 开发预览</span></RouterLink>
      <button class="server-address" type="button" :title="'复制 ' + apiBaseUrl" @click="copyBaseUrl">
        <i class="status-dot" aria-hidden="true" />{{ apiBaseUrl }}
      </button>
      <nav class="topnav" aria-label="主导航">
        <RouterLink to="/dashboard" :class="{ active: route.name === 'dashboard' }">首页</RouterLink>
        <RouterLink to="/connections" :class="{ active: route.name === 'connections' }">连接组</RouterLink>
      </nav>
    </header>

    <aside class="sidebar">
      <div class="sidebar-heading"><span>连接组</span><span>{{ routerStore.groups.length }}</span></div>
      <ConnectionTree />
    </aside>

    <main class="page-main">
      <p v-if="routerStore.error" class="global-error" role="alert">{{ routerStore.error }}</p>
      <RouterView />
    </main>
  </div>
</template>
