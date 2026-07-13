import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { linRouterApi } from '../api/lin-router'
import { toConnectionGroup, toConnectionModel, toGroupPayload } from '../adapters/connection'

export const useRouterStore = defineStore('router', () => {
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  const groups = ref([])
  const models = ref([])
  const selectedGroupId = ref('')

  const selectedGroup = computed(() => groups.value.find((group) => group.id === selectedGroupId.value) || null)
  const selectedGroupModels = computed(() => models.value.filter((model) => model.groupId === selectedGroupId.value))
  const readyGroupCount = computed(() => groups.value.filter((group) => group.modelCount > 0).length)

  function applyState(payload = {}) {
    const modelItems = (payload.models || []).map(toConnectionModel)
    models.value = modelItems
    groups.value = (payload.groups || []).map((raw) => {
      const group = toConnectionGroup(raw)
      return { ...group, modelCount: modelItems.filter((model) => model.groupId === group.id).length }
    })
    if (selectedGroupId.value && !groups.value.some((group) => group.id === selectedGroupId.value)) {
      selectedGroupId.value = ''
    }
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const payload = await linRouterApi.getState()
      applyState(payload)
    } catch (cause) {
      error.value = cause.message || '加载连接状态失败'
      throw cause
    } finally {
      loading.value = false
    }
  }

  async function saveGroup(form, id = '') {
    saving.value = true
    error.value = ''
    try {
      const existing = id ? selectedGroup.value?.raw : {}
      const payload = toGroupPayload(form, existing)
      const result = id ? await linRouterApi.saveGroup(id, payload) : await linRouterApi.createGroup(payload)
      await load()
      selectedGroupId.value = id || result?.group?.id || ''
      return result
    } catch (cause) {
      error.value = cause.message || '保存连接组失败'
      throw cause
    } finally {
      saving.value = false
    }
  }

  return {
    loading, saving, error, groups, models, selectedGroupId,
    selectedGroup, selectedGroupModels, readyGroupCount,
    load, saveGroup,
  }
})
