<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useRouterStore } from '../stores/router'

const router = useRouter()
const routerStore = useRouterStore()
const selectedId = computed(() => routerStore.selectedGroupId)

function selectGroup(id) {
  routerStore.selectedGroupId = id
  router.push('/connections')
}
</script>

<template>
  <div class="connection-tree">
    <button
      v-for="group in routerStore.groups"
      :key="group.id"
      type="button"
      class="tree-group"
      :class="{ selected: selectedId === group.id }"
      @click="selectGroup(group.id)"
    >
      <span class="tree-indicator" :class="group.modelCount ? 'ready' : 'pending'" />
      <span class="tree-name">{{ group.name }}</span>
      <span class="tree-count">{{ group.modelCount }}</span>
    </button>
    <p v-if="!routerStore.loading && !routerStore.groups.length" class="tree-empty">暂无连接组<br>从首页开始添加。</p>
  </div>
</template>
