<script setup lang="ts">
interface Props {
  title: string
  count: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  update: [value: number]
}>()

function increment() {
  emit('update', props.count + 1)
}
</script>

<template>
  <div>
    <h1>{{ title }}</h1>
    <button @click="increment">{{ count }}</button>
  </div>
</template>
