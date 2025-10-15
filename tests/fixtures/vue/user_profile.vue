<template>
  <div class="user-profile">
    <!-- Header Section -->
    <header class="profile-header">
      <img :src="user.avatar" :alt="`${user.name}'s avatar`" class="avatar" />
      <div class="user-info">
        <h1>{{ user.name }}</h1>
        <p class="username">@{{ user.username }}</p>
        <p class="bio">{{ user.bio }}</p>
      </div>
      <div class="profile-actions" v-if="canEdit">
        <button @click="editProfile" class="btn-primary">Edit Profile</button>
        <button @click="shareProfile" class="btn-secondary">Share</button>
      </div>
    </header>

    <!-- Stats Section -->
    <div class="profile-stats">
      <div class="stat-item">
        <span class="stat-value">{{ user.stats.posts }}</span>
        <span class="stat-label">Posts</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ user.stats.followers }}</span>
        <span class="stat-label">Followers</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ user.stats.following }}</span>
        <span class="stat-label">Following</span>
      </div>
    </div>

    <!-- Content Tabs -->
    <nav class="profile-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab', { active: currentTab === tab.id }]"
        @click="switchTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- Tab Content -->
    <div class="tab-content">
      <!-- Posts Tab -->
      <div v-if="currentTab === 'posts'" class="posts-grid">
        <div v-if="isLoadingPosts" class="loading">
          <LoadingSpinner />
        </div>
        <div v-else-if="posts.length === 0" class="empty-state">
          <p>No posts yet</p>
        </div>
        <div v-else class="grid">
          <PostCard
            v-for="post in posts"
            :key="post.id"
            :post="post"
            @like="handleLike"
            @comment="handleComment"
            @share="handleShare"
          />
        </div>
      </div>

      <!-- Followers Tab -->
      <div v-if="currentTab === 'followers'" class="followers-list">
        <UserListItem
          v-for="follower in followers"
          :key="follower.id"
          :user="follower"
          @follow="handleFollow"
          @unfollow="handleUnfollow"
        />
      </div>

      <!-- Following Tab -->
      <div v-if="currentTab === 'following'" class="following-list">
        <UserListItem
          v-for="following in followingList"
          :key="following.id"
          :user="following"
          @follow="handleFollow"
          @unfollow="handleUnfollow"
        />
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="showPagination" class="pagination">
      <button @click="previousPage" :disabled="!hasPreviousPage">Previous</button>
      <span>Page {{ currentPage }} of {{ totalPages }}</span>
      <button @click="nextPage" :disabled="!hasNextPage">Next</button>
    </div>

    <!-- Edit Profile Modal -->
    <Modal v-if="isEditModalOpen" @close="closeEditModal">
      <template #header>
        <h2>Edit Profile</h2>
      </template>
      <template #default>
        <form @submit.prevent="saveProfile">
          <input v-model="editForm.name" type="text" placeholder="Name" />
          <input v-model="editForm.username" type="text" placeholder="Username" />
          <textarea v-model="editForm.bio" placeholder="Bio"></textarea>
          <button type="submit">Save Changes</button>
        </form>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'
import PostCard from '@/components/PostCard.vue'
import UserListItem from '@/components/UserListItem.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import Modal from '@/components/Modal.vue'

interface Props {
  userId: string
}

interface User {
  id: string
  name: string
  username: string
  bio: string
  avatar: string
  stats: {
    posts: number
    followers: number
    following: number
  }
}

interface Post {
  id: string
  content: string
  likes: number
  comments: number
}

interface Tab {
  id: string
  label: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  profileUpdated: [userId: string]
  profileShared: [userId: string]
}>()

// Composables
const router = useRouter()
const { currentUser, isAuthenticated } = useAuth()
const { showToast } = useToast()

// State
const user = ref<User | null>(null)
const posts = ref<Post[]>([])
const followers = ref<User[]>([])
const followingList = ref<User[]>([])
const isLoadingPosts = ref(false)
const currentTab = ref<string>('posts')
const currentPage = ref(1)
const totalPages = ref(1)
const isEditModalOpen = ref(false)

// Edit form
const editForm = ref({
  name: '',
  username: '',
  bio: ''
})

// Tabs
const tabs: Tab[] = [
  { id: 'posts', label: 'Posts' },
  { id: 'followers', label: 'Followers' },
  { id: 'following', label: 'Following' }
]

// Computed
const canEdit = computed(() => {
  return isAuthenticated.value && currentUser.value?.id === user.value?.id
})

const hasPreviousPage = computed(() => currentPage.value > 1)
const hasNextPage = computed(() => currentPage.value < totalPages.value)

const showPagination = computed(() => {
  return currentTab.value === 'posts' && posts.value.length > 0
})

// Methods
async function fetchUserProfile() {
  try {
    // Simulated API call
    const response = await fetch(`/api/users/${props.userId}`)
    user.value = await response.json()
  } catch (error) {
    console.error('Failed to fetch user profile:', error)
    showToast('Failed to load profile', 'error')
  }
}

async function fetchPosts(page: number = 1) {
  isLoadingPosts.value = true
  try {
    const response = await fetch(`/api/users/${props.userId}/posts?page=${page}`)
    const data = await response.json()
    posts.value = data.posts
    totalPages.value = data.totalPages
  } catch (error) {
    console.error('Failed to fetch posts:', error)
    showToast('Failed to load posts', 'error')
  } finally {
    isLoadingPosts.value = false
  }
}

async function fetchFollowers() {
  try {
    const response = await fetch(`/api/users/${props.userId}/followers`)
    followers.value = await response.json()
  } catch (error) {
    console.error('Failed to fetch followers:', error)
  }
}

async function fetchFollowing() {
  try {
    const response = await fetch(`/api/users/${props.userId}/following`)
    followingList.value = await response.json()
  } catch (error) {
    console.error('Failed to fetch following:', error)
  }
}

function switchTab(tabId: string) {
  currentTab.value = tabId

  if (tabId === 'posts' && posts.value.length === 0) {
    fetchPosts()
  } else if (tabId === 'followers' && followers.value.length === 0) {
    fetchFollowers()
  } else if (tabId === 'following' && followingList.value.length === 0) {
    fetchFollowing()
  }
}

function editProfile() {
  if (!user.value) return

  editForm.value = {
    name: user.value.name,
    username: user.value.username,
    bio: user.value.bio
  }

  isEditModalOpen.value = true
}

async function saveProfile() {
  try {
    const response = await fetch(`/api/users/${props.userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm.value)
    })

    if (response.ok) {
      const updatedUser = await response.json()
      user.value = updatedUser
      isEditModalOpen.value = false
      showToast('Profile updated successfully', 'success')
      emit('profileUpdated', props.userId)
    }
  } catch (error) {
    console.error('Failed to save profile:', error)
    showToast('Failed to update profile', 'error')
  }
}

function closeEditModal() {
  isEditModalOpen.value = false
}

function shareProfile() {
  const url = `${window.location.origin}/profile/${props.userId}`
  navigator.clipboard.writeText(url)
  showToast('Profile link copied to clipboard', 'success')
  emit('profileShared', props.userId)
}

function handleLike(postId: string) {
  console.log('Liked post:', postId)
}

function handleComment(postId: string) {
  console.log('Comment on post:', postId)
}

function handleShare(postId: string) {
  console.log('Share post:', postId)
}

function handleFollow(userId: string) {
  console.log('Follow user:', userId)
}

function handleUnfollow(userId: string) {
  console.log('Unfollow user:', userId)
}

function previousPage() {
  if (hasPreviousPage.value) {
    currentPage.value--
    fetchPosts(currentPage.value)
  }
}

function nextPage() {
  if (hasNextPage.value) {
    currentPage.value++
    fetchPosts(currentPage.value)
  }
}

// Lifecycle
onMounted(() => {
  fetchUserProfile()
  fetchPosts()
})

// Watchers
watch(() => props.userId, () => {
  currentPage.value = 1
  fetchUserProfile()
  fetchPosts()
})
</script>

<style scoped>
.user-profile {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.profile-header {
  display: flex;
  gap: 20px;
  margin-bottom: 30px;
}

.avatar {
  width: 150px;
  height: 150px;
  border-radius: 50%;
  object-fit: cover;
}

.user-info {
  flex: 1;
}

.username {
  color: #666;
  font-size: 1.1rem;
}

.bio {
  margin-top: 10px;
  color: #333;
}

.profile-actions {
  display: flex;
  gap: 10px;
}

.profile-stats {
  display: flex;
  gap: 40px;
  margin-bottom: 30px;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
}

.stat-label {
  color: #666;
  font-size: 0.9rem;
}

.profile-tabs {
  display: flex;
  gap: 10px;
  border-bottom: 2px solid #eee;
  margin-bottom: 20px;
}

.tab {
  padding: 10px 20px;
  background: none;
  border: none;
  cursor: pointer;
  position: relative;
}

.tab.active {
  font-weight: bold;
}

.tab.active::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background: #007bff;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  margin-top: 30px;
}

.btn-primary,
.btn-secondary {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}
</style>
