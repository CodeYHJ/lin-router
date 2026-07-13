<script setup>
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterStore } from '../stores/router'

const route = useRoute()
const routerStore = useRouterStore()
const defaultForm = () => ({ name: '新连接组', providerType: 'relay', baseUrl: 'https://www.codeok.cc/v1', apiKey: '' })
const form = reactive(defaultForm())
const editingId = computed(() => routerStore.selectedGroupId)
const selectedModels = computed(() => routerStore.selectedGroupModels)
const providerKeyLabel = computed(() => form.providerType === 'ark' ? 'Ark API Key' : form.providerType === 'proxy' ? '上游 API Key' : 'API Key（保存连接组时不写入）')

function loadForm(group) {
  Object.assign(form, group
    ? { name: group.name, providerType: group.providerType, baseUrl: group.baseUrl, apiKey: '' }
    : defaultForm())
}

watch(editingId, () => loadForm(routerStore.selectedGroup), { immediate: true })
watch(() => route.query.new, (isNew) => { if (isNew) routerStore.selectedGroupId = '' }, { immediate: true })

async function submit() {
  if (!form.name.trim() || !form.baseUrl.trim()) return
  try {
    await routerStore.saveGroup(form, editingId.value)
  } catch (_) {
    // Store retains a Chinese-facing error for the common page-level error state.
  }
}

function createNew() {
  routerStore.selectedGroupId = ''
  loadForm(null)
}
</script>

<template>
  <section class="connections-page">
    <header class="page-heading">
      <div><p class="eyebrow">连接管理</p><h1>{{ editingId ? '编辑连接组' : '添加连接组' }}</h1><p>先保存连接组，再获取模型或手动添加模型。</p></div>
      <button class="secondary-button" type="button" @click="createNew">+ 新建连接组</button>
    </header>

    <div class="connections-layout">
      <form class="form-card" @submit.prevent="submit">
        <h2>基础配置</h2>
        <label>组名<input v-model="form.name" required placeholder="例如：我的中转站" /></label>
        <label>模式
          <select v-model="form.providerType">
            <option value="relay">中转站</option>
            <option value="ark">火山方舟</option>
            <option value="proxy">通用 OpenAI 代理</option>
          </select>
        </label>
        <label>Base URL<input v-model="form.baseUrl" required placeholder="https://example.com/v1" /></label>
        <p v-if="form.providerType === 'relay'" class="field-hint">默认第三方地址，可修改。保存连接组后，请在模型配置中填写中转站 API Key。</p>
        <label>{{ providerKeyLabel }}<input v-model="form.apiKey" type="password" :required="form.providerType !== 'relay'" placeholder="sk-xxxx" /></label>
        <p class="field-hint">客户端使用保存后生成的本地路由 Key，不是上游 API Key。</p>
        <p v-if="routerStore.error" class="form-error" role="alert">{{ routerStore.error }}</p>
        <button class="primary-button" :disabled="routerStore.saving" type="submit">{{ routerStore.saving ? '保存中…' : '保存连接组' }}</button>
      </form>

      <aside class="details-card">
        <h2>{{ routerStore.selectedGroup?.name || '连接状态' }}</h2>
        <template v-if="routerStore.selectedGroup">
          <dl><dt>模式</dt><dd>{{ routerStore.selectedGroup.providerLabel }}</dd><dt>已配置模型</dt><dd>{{ selectedModels.length }}</dd><dt>本地路由 Key</dt><dd class="mono">{{ routerStore.selectedGroup.routeKey || '保存后生成' }}</dd></dl>
          <p v-if="!selectedModels.length" class="notice">连接组已保存，下一步可获取模型或手动添加模型（模型流程将在下一批接入）。</p>
          <ul v-else class="model-list"><li v-for="model in selectedModels" :key="model.id"><span>{{ model.name }}</span><small>{{ model.upstreamModel }}</small></li></ul>
        </template>
        <p v-else class="notice">填写基础字段后保存。当前批次不会自动调用上游服务。</p>
      </aside>
    </div>
  </section>
</template>
