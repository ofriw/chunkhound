<template>
  <div class="cross-reference-test">
    <!-- Test interpolation references -->
    <h1>{{ title }}</h1>
    <p>{{ description }}</p>
    <p>Count: {{ count }}</p>
    <p>Double: {{ doubleCount }}</p>

    <!-- Test conditional with references -->
    <div v-if="isAuthenticated">
      Welcome, {{ user.name }}!
    </div>
    <div v-else>
      Please log in
    </div>

    <!-- Test loop with references -->
    <ul>
      <li v-for="item in items" :key="item.id">
        {{ item.name }} - ${{ item.price }}
      </li>
    </ul>

    <!-- Test event handlers referencing functions -->
    <button @click="increment">Increment</button>
    <button @click="decrement">Decrement</button>
    <button @click="handleSubmit">Submit</button>
    <button @click="resetCount">Reset</button>

    <!-- Test property bindings with variables -->
    <img :src="imageUrl" :alt="imageAlt" />
    <a :href="linkUrl" :title="linkTitle">Link</a>

    <!-- Test v-model with variables -->
    <input v-model="searchQuery" placeholder="Search..." />
    <textarea v-model="notes"></textarea>

    <!-- Test complex expressions with multiple references -->
    <div v-if="user.isAdmin && permissions.includes('write')">
      Admin Panel - Count: {{ count }}
    </div>

    <!-- Test composable references -->
    <p v-if="isLoading">Loading...</p>
    <p v-if="error">Error: {{ error.message }}</p>

    <!-- Test undefined reference (should be detected) -->
    <p>{{ undefinedVariable }}</p>
    <button @click="undefinedFunction">Undefined</button>

    <!-- Test component props -->
    <ChildComponent
      :title="title"
      :count="count"
      :user="user"
      @update="handleUpdate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuth } from '@/composables/useAuth'
import { useData } from '@/composables/useData'

// Simple reactive variables
const title = ref('Cross-Reference Test')
const description = ref('Testing cross-reference analysis')
const count = ref(0)

// Computed properties
const doubleCount = computed(() => count.value * 2)

// Composable usage with destructuring
const { user, isAuthenticated, permissions } = useAuth()
const { items, isLoading, error } = useData()

// Regular variables (non-reactive)
const imageUrl = ref('/image.png')
const imageAlt = ref('Test Image')
const linkUrl = ref('https://example.com')
const linkTitle = ref('Example Link')

// v-model variables
const searchQuery = ref('')
const notes = ref('')

// Function declarations
function increment() {
  count.value++
}

function decrement() {
  count.value--
}

function resetCount() {
  count.value = 0
}

// Arrow function
const handleSubmit = () => {
  console.log('Form submitted')
  console.log('Search:', searchQuery.value)
  console.log('Notes:', notes.value)
}

// Function with parameters
const handleUpdate = (data: any) => {
  console.log('Update received:', data)
}

// Props definition
const props = defineProps<{
  initialCount?: number
  mode?: 'light' | 'dark'
}>()

// Emit definition
const emit = defineEmits<{
  (e: 'change', value: number): void
  (e: 'reset'): void
}>()
</script>

<style scoped>
.cross-reference-test {
  padding: 20px;
}

button {
  margin: 5px;
}
</style>
