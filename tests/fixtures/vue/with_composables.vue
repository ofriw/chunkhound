<script setup lang="ts">
import { ref, computed } from 'vue'
import { useUser } from '@/composables/useUser'
import { useCounter } from '@/composables/useCounter'

const { user, login, logout } = useUser()
const { count, increment, decrement } = useCounter()

const isAuthenticated = computed(() => user.value !== null)

function handleLogin() {
  login('user@example.com', 'password')
}

function handleLogout() {
  logout()
}

function handleIncrement() {
  increment()
}

function handleDecrement() {
  decrement()
}

defineExpose({
  handleIncrement,
  handleDecrement,
  handleLogin,
  handleLogout
})
</script>

<template>
  <div class="user-component">
    <p v-if="isAuthenticated">User: {{ user.name }}</p>
    <p v-else>Not logged in</p>
    <p>Count: {{ count }}</p>
    <button @click="handleLogin" v-if="!isAuthenticated">Login</button>
    <button @click="handleLogout" v-if="isAuthenticated">Logout</button>
    <button @click="handleIncrement">+</button>
    <button @click="handleDecrement">-</button>
  </div>
</template>
