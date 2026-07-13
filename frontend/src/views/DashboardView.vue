<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useRouterStore } from '../stores/router'

const router = useRouter()
const routerStore = useRouterStore()
const isEmpty = computed(() => !routerStore.groups.length)
const nextStep = computed(() => {
  if (isEmpty.value) return { title: '从添加连接组开始', text: '添加一个连接组后，你可以获取模型、测试请求，并将本机地址配置到兼容 OpenAI 的客户端。', action: '添加连接组' }
  if (!routerStore.models.length) return { title: '连接组已添加，尚未有模型', text: '选择一个连接组后获取模型或手动添加模型。', action: '管理连接组' }
  return { title: '连接与接入状态', text: '当前已保存配置；后续批次将迁移模型验证、客户端接入和运行态观测。', action: '查看连接组' }
})

function start() {
  routerStore.selectedGroupId = ''
  router.push('/connections?new=1')
}
</script>

<template>
  <section class="dashboard-page">
    <div class="eyebrow">本地 OpenAI 兼容路由器</div>
    <div class="hero-card">
      <div>
        <p class="hero-kicker">Lin Router 正在运行</p>
        <h1>{{ nextStep.title }}</h1>
        <p>{{ nextStep.text }}</p>
      </div>
      <button class="primary-button" type="button" @click="start">{{ nextStep.action }}</button>
    </div>

    <div v-if="routerStore.loading" class="status-card">正在加载连接状态…</div>
    <div v-else class="metric-grid">
      <article class="metric-card"><span>连接组</span><strong>{{ routerStore.groups.length }}</strong><small>已保存的上游连接</small></article>
      <article class="metric-card"><span>模型</span><strong>{{ routerStore.models.length }}</strong><small>当前配置模型</small></article>
      <article class="metric-card"><span>可继续配置</span><strong>{{ routerStore.readyGroupCount }}</strong><small>已有模型的连接组</small></article>
    </div>

    <article v-if="isEmpty && !routerStore.loading" class="onboarding-card">
      <h2>还没有连接组</h2>
      <p>Lin Router 本身不提供模型额度。请添加已有服务的 Base URL 与 API Key，保存后再获取或手动添加模型。</p>
      <div class="button-row">
        <button class="primary-button" type="button" @click="start">添加连接组</button>
        <RouterLink class="secondary-button" to="/connections">导入已有配置（后续批次）</RouterLink>
      </div>
    </article>
  </section>
</template>
