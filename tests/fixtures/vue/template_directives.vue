<template>
  <div class="container">
    <!-- Conditional rendering -->
    <div v-if="isLoggedIn">
      Welcome back, {{ userName }}!
    </div>
    <div v-else-if="isLoading">
      Loading...
    </div>
    <div v-else>
      Please log in
    </div>

    <!-- List rendering -->
    <ul>
      <li v-for="item in items" :key="item.id">
        {{ item.name }} - {{ item.price }}
      </li>
    </ul>

    <!-- Component usage -->
    <UserProfile
      :user="currentUser"
      :show-avatar="true"
      @update="handleUserUpdate"
      @delete="handleUserDelete"
    />

    <!-- Self-closing component -->
    <BaseButton @click="handleClick" />

    <!-- Event handlers -->
    <button @click="increment">Count: {{ count }}</button>
    <form @submit.prevent="handleSubmit">
      <input v-model="formData.email" type="email" />
      <input v-model.trim="formData.name" type="text" />
    </form>

    <!-- Property bindings -->
    <img :src="imageUrl" :alt="imageAlt" />
    <a :href="linkUrl">Link</a>

    <!-- v-model (two-way binding) -->
    <input v-model="message" />
    <textarea v-model="description"></textarea>

    <!-- Conditional with complex expression -->
    <div v-if="user.isAdmin && user.permissions.includes('write')">
      Admin Panel
    </div>

    <!-- Loop with index -->
    <div v-for="(item, index) in products" :key="index">
      {{ index + 1 }}. {{ item.title }}
    </div>

    <!-- Slot usage -->
    <Modal>
      <template v-slot:header>
        <h1>Modal Title</h1>
      </template>
      <template #default>
        <p>Modal content</p>
      </template>
      <template #footer>
        <button @click="closeModal">Close</button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const isLoggedIn = ref(false)
const isLoading = ref(false)
const userName = ref('John Doe')
const items = ref([
  { id: 1, name: 'Item 1', price: 10 },
  { id: 2, name: 'Item 2', price: 20 }
])
const currentUser = ref({ name: 'Jane', email: 'jane@example.com' })
const count = ref(0)
const message = ref('')
const description = ref('')
const formData = ref({ email: '', name: '' })
const imageUrl = ref('/image.jpg')
const imageAlt = ref('Image')
const linkUrl = ref('https://example.com')
const products = ref([{ title: 'Product 1' }, { title: 'Product 2' }])

const increment = () => {
  count.value++
}

const handleClick = () => {
  console.log('Clicked')
}

const handleSubmit = () => {
  console.log('Form submitted')
}

const handleUserUpdate = (user: any) => {
  console.log('User updated', user)
}

const handleUserDelete = () => {
  console.log('User deleted')
}

const closeModal = () => {
  console.log('Modal closed')
}

const user = computed(() => ({
  isAdmin: true,
  permissions: ['read', 'write']
}))
</script>

<style scoped>
.container {
  padding: 20px;
}
</style>
