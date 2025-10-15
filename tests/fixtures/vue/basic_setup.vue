<template>
  <div>{{ message }}</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const message = ref('Hello World')

function greet() {
  console.log(message.value)
}
</script>

<style scoped>
div {
  color: blue;
}
</style>
