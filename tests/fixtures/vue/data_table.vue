<template>
  <div class="data-table">
    <!-- Header with Search and Filters -->
    <div class="table-header">
      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search..."
          @input="handleSearch"
        />
        <button @click="clearSearch" v-if="searchQuery">Clear</button>
      </div>

      <div class="filters">
        <select v-model="statusFilter" @change="applyFilters">
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="pending">Pending</option>
        </select>

        <select v-model="categoryFilter" @change="applyFilters">
          <option value="">All Categories</option>
          <option v-for="category in categories" :key="category" :value="category">
            {{ category }}
          </option>
        </select>
      </div>

      <div class="actions">
        <button @click="exportData" :disabled="isExporting">
          {{ isExporting ? 'Exporting...' : 'Export' }}
        </button>
        <button @click="refreshData" :disabled="isLoading">
          {{ isLoading ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-container">
      <table v-if="!isLoading && filteredData.length > 0">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                v-model="selectAll"
                @change="toggleSelectAll"
              />
            </th>
            <th
              v-for="column in columns"
              :key="column.key"
              :class="{ sortable: column.sortable }"
              @click="column.sortable && sort(column.key)"
            >
              {{ column.label }}
              <span v-if="column.sortable && sortBy === column.key" class="sort-indicator">
                {{ sortOrder === 'asc' ? '↑' : '↓' }}
              </span>
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in paginatedData"
            :key="row.id"
            :class="{ selected: selectedRows.includes(row.id), odd: index % 2 === 1 }"
          >
            <td>
              <input
                type="checkbox"
                :value="row.id"
                v-model="selectedRows"
              />
            </td>
            <td v-for="column in columns" :key="column.key">
              <span v-if="column.format">
                {{ column.format(row[column.key]) }}
              </span>
              <span v-else>
                {{ row[column.key] }}
              </span>
            </td>
            <td class="actions-cell">
              <button @click="viewRow(row)" class="btn-view">View</button>
              <button @click="editRow(row)" class="btn-edit">Edit</button>
              <button @click="deleteRow(row)" class="btn-delete">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="isLoading" class="loading-state">
        <LoadingSpinner />
        <p>Loading data...</p>
      </div>

      <div v-if="!isLoading && filteredData.length === 0" class="empty-state">
        <p v-if="searchQuery || statusFilter || categoryFilter">
          No results found. Try adjusting your filters.
        </p>
        <p v-else>
          No data available.
        </p>
      </div>
    </div>

    <!-- Pagination -->
    <div class="pagination" v-if="totalPages > 1">
      <button @click="goToFirstPage" :disabled="currentPage === 1">
        First
      </button>
      <button @click="previousPage" :disabled="currentPage === 1">
        Previous
      </button>

      <span class="page-info">
        Page {{ currentPage }} of {{ totalPages }}
      </span>

      <button @click="nextPage" :disabled="currentPage === totalPages">
        Next
      </button>
      <button @click="goToLastPage" :disabled="currentPage === totalPages">
        Last
      </button>

      <select v-model="pageSize" @change="changePageSize">
        <option :value="10">10 per page</option>
        <option :value="25">25 per page</option>
        <option :value="50">50 per page</option>
        <option :value="100">100 per page</option>
      </select>
    </div>

    <!-- Bulk Actions -->
    <div class="bulk-actions" v-if="selectedRows.length > 0">
      <span>{{ selectedRows.length }} item(s) selected</span>
      <button @click="bulkDelete">Delete Selected</button>
      <button @click="bulkExport">Export Selected</button>
      <button @click="clearSelection">Clear Selection</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'

interface Column {
  key: string
  label: string
  sortable?: boolean
  format?: (value: any) => string
}

interface DataRow {
  id: string | number
  [key: string]: any
}

interface Props {
  data?: DataRow[]
  columns: Column[]
  initialPageSize?: number
}

const props = withDefaults(defineProps<Props>(), {
  data: () => [],
  initialPageSize: 25
})

const emit = defineEmits<{
  view: [row: DataRow]
  edit: [row: DataRow]
  delete: [row: DataRow]
  bulkDelete: [ids: (string | number)[]]
  refresh: []
  export: [rows: DataRow[]]
}>()

// State
const searchQuery = ref('')
const statusFilter = ref('')
const categoryFilter = ref('')
const sortBy = ref<string>('')
const sortOrder = ref<'asc' | 'desc'>('asc')
const currentPage = ref(1)
const pageSize = ref(props.initialPageSize)
const selectedRows = ref<(string | number)[]>([])
const selectAll = ref(false)
const isLoading = ref(false)
const isExporting = ref(false)
const tableData = ref<DataRow[]>(props.data)

// Categories for filter dropdown
const categories = computed(() => {
  const cats = new Set<string>()
  tableData.value.forEach(row => {
    if (row.category) {
      cats.add(row.category)
    }
  })
  return Array.from(cats).sort()
})

// Filter and sort data
const filteredData = computed(() => {
  let result = [...tableData.value]

  // Apply search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(row => {
      return props.columns.some(column => {
        const value = String(row[column.key] || '').toLowerCase()
        return value.includes(query)
      })
    })
  }

  // Apply status filter
  if (statusFilter.value) {
    result = result.filter(row => row.status === statusFilter.value)
  }

  // Apply category filter
  if (categoryFilter.value) {
    result = result.filter(row => row.category === categoryFilter.value)
  }

  // Apply sorting
  if (sortBy.value) {
    result.sort((a, b) => {
      const aVal = a[sortBy.value]
      const bVal = b[sortBy.value]

      let comparison = 0
      if (aVal < bVal) comparison = -1
      if (aVal > bVal) comparison = 1

      return sortOrder.value === 'asc' ? comparison : -comparison
    })
  }

  return result
})

// Pagination
const totalPages = computed(() => {
  return Math.ceil(filteredData.value.length / pageSize.value)
})

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredData.value.slice(start, end)
})

// Methods
function handleSearch() {
  currentPage.value = 1
  selectAll.value = false
  selectedRows.value = []
}

function clearSearch() {
  searchQuery.value = ''
  handleSearch()
}

function applyFilters() {
  currentPage.value = 1
  selectAll.value = false
  selectedRows.value = []
}

function sort(columnKey: string) {
  if (sortBy.value === columnKey) {
    // Toggle sort order
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    // New column, default to ascending
    sortBy.value = columnKey
    sortOrder.value = 'asc'
  }
}

function toggleSelectAll() {
  if (selectAll.value) {
    // Select all rows on current page
    selectedRows.value = paginatedData.value.map(row => row.id)
  } else {
    // Deselect all
    selectedRows.value = []
  }
}

function viewRow(row: DataRow) {
  emit('view', row)
}

function editRow(row: DataRow) {
  emit('edit', row)
}

async function deleteRow(row: DataRow) {
  if (confirm(`Are you sure you want to delete this item?`)) {
    emit('delete', row)
    // Remove from local data
    const index = tableData.value.findIndex(r => r.id === row.id)
    if (index !== -1) {
      tableData.value.splice(index, 1)
    }
  }
}

async function bulkDelete() {
  if (confirm(`Are you sure you want to delete ${selectedRows.value.length} item(s)?`)) {
    emit('bulkDelete', selectedRows.value)
    // Remove from local data
    tableData.value = tableData.value.filter(
      row => !selectedRows.value.includes(row.id)
    )
    selectedRows.value = []
    selectAll.value = false
  }
}

async function bulkExport() {
  const rowsToExport = tableData.value.filter(
    row => selectedRows.value.includes(row.id)
  )
  emit('export', rowsToExport)
}

function clearSelection() {
  selectedRows.value = []
  selectAll.value = false
}

async function exportData() {
  isExporting.value = true
  try {
    emit('export', filteredData.value)
    // Simulate export delay
    await new Promise(resolve => setTimeout(resolve, 1000))
  } finally {
    isExporting.value = false
  }
}

async function refreshData() {
  isLoading.value = true
  try {
    emit('refresh')
    // Simulate refresh delay
    await new Promise(resolve => setTimeout(resolve, 500))
  } finally {
    isLoading.value = false
  }
}

function previousPage() {
  if (currentPage.value > 1) {
    currentPage.value--
    selectAll.value = false
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    selectAll.value = false
  }
}

function goToFirstPage() {
  currentPage.value = 1
  selectAll.value = false
}

function goToLastPage() {
  currentPage.value = totalPages.value
  selectAll.value = false
}

function changePageSize() {
  currentPage.value = 1
  selectAll.value = false
  selectedRows.value = []
}

// Watch for data changes
watch(() => props.data, (newData) => {
  tableData.value = newData
  selectedRows.value = []
  selectAll.value = false
})

// Check if all items on current page are selected
watch(selectedRows, () => {
  const allSelected = paginatedData.value.every(
    row => selectedRows.value.includes(row.id)
  )
  selectAll.value = allSelected && paginatedData.value.length > 0
})

// Lifecycle
onMounted(() => {
  if (props.data.length === 0) {
    refreshData()
  }
})
</script>

<style scoped>
.data-table {
  width: 100%;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  gap: 20px;
  flex-wrap: wrap;
}

.search-box {
  display: flex;
  gap: 10px;
  flex: 1;
  min-width: 250px;
}

.search-box input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.filters {
  display: flex;
  gap: 10px;
}

.filters select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.actions {
  display: flex;
  gap: 10px;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

thead {
  background: #f8f9fa;
}

th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #dee2e6;
}

th.sortable {
  cursor: pointer;
  user-select: none;
}

th.sortable:hover {
  background: #e9ecef;
}

.sort-indicator {
  margin-left: 5px;
}

td {
  padding: 12px;
  border-bottom: 1px solid #dee2e6;
}

tr.odd {
  background: #f8f9fa;
}

tr.selected {
  background: #e7f3ff;
}

.actions-cell {
  display: flex;
  gap: 5px;
}

.btn-view,
.btn-edit,
.btn-delete {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
}

.btn-view {
  background: #17a2b8;
  color: white;
}

.btn-edit {
  background: #ffc107;
  color: #333;
}

.btn-delete {
  background: #dc3545;
  color: white;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #6c757d;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
}

.pagination button {
  padding: 6px 12px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination select {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.page-info {
  padding: 0 10px;
  font-weight: 500;
}

.bulk-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 15px;
  background: #e7f3ff;
  border-radius: 4px;
  margin-top: 20px;
}

.bulk-actions button {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background: #007bff;
  color: white;
}
</style>
