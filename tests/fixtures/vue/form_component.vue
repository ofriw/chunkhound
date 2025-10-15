<template>
  <div class="form-component">
    <form @submit.prevent="handleSubmit" novalidate>
      <h2>{{ formTitle }}</h2>

      <!-- Personal Information Section -->
      <fieldset>
        <legend>Personal Information</legend>

        <div class="form-group">
          <label for="firstName">
            First Name <span class="required">*</span>
          </label>
          <input
            id="firstName"
            v-model="form.firstName"
            type="text"
            :class="{ error: errors.firstName }"
            @blur="validateField('firstName')"
          />
          <span v-if="errors.firstName" class="error-message">
            {{ errors.firstName }}
          </span>
        </div>

        <div class="form-group">
          <label for="lastName">
            Last Name <span class="required">*</span>
          </label>
          <input
            id="lastName"
            v-model="form.lastName"
            type="text"
            :class="{ error: errors.lastName }"
            @blur="validateField('lastName')"
          />
          <span v-if="errors.lastName" class="error-message">
            {{ errors.lastName }}
          </span>
        </div>

        <div class="form-group">
          <label for="email">
            Email <span class="required">*</span>
          </label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            :class="{ error: errors.email }"
            @blur="validateField('email')"
          />
          <span v-if="errors.email" class="error-message">
            {{ errors.email }}
          </span>
        </div>

        <div class="form-group">
          <label for="phone">Phone Number</label>
          <input
            id="phone"
            v-model="form.phone"
            type="tel"
            :class="{ error: errors.phone }"
            @blur="validateField('phone')"
          />
          <span v-if="errors.phone" class="error-message">
            {{ errors.phone }}
          </span>
        </div>
      </fieldset>

      <!-- Address Section -->
      <fieldset>
        <legend>Address</legend>

        <div class="form-group">
          <label for="street">Street Address</label>
          <input
            id="street"
            v-model="form.address.street"
            type="text"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="city">City</label>
            <input
              id="city"
              v-model="form.address.city"
              type="text"
            />
          </div>

          <div class="form-group">
            <label for="state">State</label>
            <select id="state" v-model="form.address.state">
              <option value="">Select State</option>
              <option v-for="state in states" :key="state.code" :value="state.code">
                {{ state.name }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label for="zip">ZIP Code</label>
            <input
              id="zip"
              v-model="form.address.zip"
              type="text"
              :class="{ error: errors.zip }"
              @blur="validateField('zip')"
            />
            <span v-if="errors.zip" class="error-message">
              {{ errors.zip }}
            </span>
          </div>
        </div>
      </fieldset>

      <!-- Account Settings -->
      <fieldset>
        <legend>Account Settings</legend>

        <div class="form-group">
          <label for="username">
            Username <span class="required">*</span>
          </label>
          <input
            id="username"
            v-model.trim="form.username"
            type="text"
            :class="{ error: errors.username }"
            @blur="validateField('username')"
          />
          <span v-if="errors.username" class="error-message">
            {{ errors.username }}
          </span>
          <span v-if="checkingUsername" class="info-message">
            Checking availability...
          </span>
        </div>

        <div class="form-group">
          <label for="password">
            Password <span class="required">*</span>
          </label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            :class="{ error: errors.password }"
            @blur="validateField('password')"
          />
          <span v-if="errors.password" class="error-message">
            {{ errors.password }}
          </span>
          <div class="password-strength">
            <div
              class="strength-bar"
              :class="passwordStrengthClass"
              :style="{ width: passwordStrengthWidth }"
            ></div>
          </div>
          <span class="info-message">
            Strength: {{ passwordStrengthLabel }}
          </span>
        </div>

        <div class="form-group">
          <label for="confirmPassword">
            Confirm Password <span class="required">*</span>
          </label>
          <input
            id="confirmPassword"
            v-model="form.confirmPassword"
            type="password"
            :class="{ error: errors.confirmPassword }"
            @blur="validateField('confirmPassword')"
          />
          <span v-if="errors.confirmPassword" class="error-message">
            {{ errors.confirmPassword }}
          </span>
        </div>
      </fieldset>

      <!-- Preferences -->
      <fieldset>
        <legend>Preferences</legend>

        <div class="form-group">
          <label>Newsletter</label>
          <div class="checkbox-group">
            <label>
              <input
                v-model="form.preferences.newsletter"
                type="checkbox"
              />
              Subscribe to newsletter
            </label>
          </div>
        </div>

        <div class="form-group">
          <label>Notifications</label>
          <div class="checkbox-group">
            <label v-for="option in notificationOptions" :key="option.value">
              <input
                v-model="form.preferences.notifications"
                type="checkbox"
                :value="option.value"
              />
              {{ option.label }}
            </label>
          </div>
        </div>

        <div class="form-group">
          <label for="language">Preferred Language</label>
          <select id="language" v-model="form.preferences.language">
            <option v-for="lang in languages" :key="lang.code" :value="lang.code">
              {{ lang.name }}
            </option>
          </select>
        </div>

        <div class="form-group">
          <label for="bio">Bio</label>
          <textarea
            id="bio"
            v-model="form.bio"
            rows="4"
            :maxlength="500"
            placeholder="Tell us about yourself..."
          ></textarea>
          <span class="char-count">
            {{ form.bio.length }} / 500 characters
          </span>
        </div>
      </fieldset>

      <!-- Terms and Conditions -->
      <div class="form-group">
        <label class="checkbox-label">
          <input
            v-model="form.agreeToTerms"
            type="checkbox"
            :class="{ error: errors.agreeToTerms }"
          />
          I agree to the
          <a href="/terms" target="_blank">Terms and Conditions</a>
          <span class="required">*</span>
        </label>
        <span v-if="errors.agreeToTerms" class="error-message">
          {{ errors.agreeToTerms }}
        </span>
      </div>

      <!-- Form Actions -->
      <div class="form-actions">
        <button
          type="submit"
          :disabled="isSubmitting || !isFormValid"
          class="btn-primary"
        >
          {{ isSubmitting ? 'Submitting...' : 'Submit' }}
        </button>
        <button
          type="button"
          @click="resetForm"
          :disabled="isSubmitting"
          class="btn-secondary"
        >
          Reset
        </button>
        <button
          type="button"
          @click="cancel"
          :disabled="isSubmitting"
          class="btn-tertiary"
        >
          Cancel
        </button>
      </div>

      <!-- Submission Status -->
      <div v-if="submitSuccess" class="success-message">
        Form submitted successfully!
      </div>
      <div v-if="submitError" class="error-message">
        {{ submitError }}
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'

interface Props {
  formTitle?: string
  initialData?: Partial<FormData>
}

interface FormData {
  firstName: string
  lastName: string
  email: string
  phone: string
  address: {
    street: string
    city: string
    state: string
    zip: string
  }
  username: string
  password: string
  confirmPassword: string
  preferences: {
    newsletter: boolean
    notifications: string[]
    language: string
  }
  bio: string
  agreeToTerms: boolean
}

const props = withDefaults(defineProps<Props>(), {
  formTitle: 'Registration Form'
})

const emit = defineEmits<{
  submit: [data: FormData]
  cancel: []
}>()

const router = useRouter()

// Form state
const form = ref<FormData>({
  firstName: '',
  lastName: '',
  email: '',
  phone: '',
  address: {
    street: '',
    city: '',
    state: '',
    zip: ''
  },
  username: '',
  password: '',
  confirmPassword: '',
  preferences: {
    newsletter: false,
    notifications: [],
    language: 'en'
  },
  bio: '',
  agreeToTerms: false
})

// Validation errors
const errors = ref<Record<string, string>>({})

// Submission state
const isSubmitting = ref(false)
const submitSuccess = ref(false)
const submitError = ref('')
const checkingUsername = ref(false)

// Options
const states = [
  { code: 'CA', name: 'California' },
  { code: 'NY', name: 'New York' },
  { code: 'TX', name: 'Texas' },
  { code: 'FL', name: 'Florida' }
]

const notificationOptions = [
  { value: 'email', label: 'Email notifications' },
  { value: 'sms', label: 'SMS notifications' },
  { value: 'push', label: 'Push notifications' }
]

const languages = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' }
]

// Computed
const passwordStrength = computed(() => {
  const password = form.value.password
  if (!password) return 0

  let strength = 0
  if (password.length >= 8) strength++
  if (password.length >= 12) strength++
  if (/[a-z]/.test(password)) strength++
  if (/[A-Z]/.test(password)) strength++
  if (/[0-9]/.test(password)) strength++
  if (/[^a-zA-Z0-9]/.test(password)) strength++

  return Math.min(strength, 5)
})

const passwordStrengthLabel = computed(() => {
  const labels = ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong', 'Very Strong']
  return labels[passwordStrength.value]
})

const passwordStrengthClass = computed(() => {
  const classes = ['very-weak', 'weak', 'fair', 'good', 'strong', 'very-strong']
  return classes[passwordStrength.value]
})

const passwordStrengthWidth = computed(() => {
  return `${(passwordStrength.value / 5) * 100}%`
})

const isFormValid = computed(() => {
  return (
    form.value.firstName &&
    form.value.lastName &&
    form.value.email &&
    form.value.username &&
    form.value.password &&
    form.value.confirmPassword &&
    form.value.agreeToTerms &&
    Object.keys(errors.value).length === 0
  )
})

// Validation functions
function validateField(fieldName: string) {
  switch (fieldName) {
    case 'firstName':
      if (!form.value.firstName) {
        errors.value.firstName = 'First name is required'
      } else if (form.value.firstName.length < 2) {
        errors.value.firstName = 'First name must be at least 2 characters'
      } else {
        delete errors.value.firstName
      }
      break

    case 'lastName':
      if (!form.value.lastName) {
        errors.value.lastName = 'Last name is required'
      } else if (form.value.lastName.length < 2) {
        errors.value.lastName = 'Last name must be at least 2 characters'
      } else {
        delete errors.value.lastName
      }
      break

    case 'email':
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!form.value.email) {
        errors.value.email = 'Email is required'
      } else if (!emailRegex.test(form.value.email)) {
        errors.value.email = 'Invalid email address'
      } else {
        delete errors.value.email
      }
      break

    case 'phone':
      if (form.value.phone) {
        const phoneRegex = /^\d{10}$/
        if (!phoneRegex.test(form.value.phone.replace(/\D/g, ''))) {
          errors.value.phone = 'Invalid phone number'
        } else {
          delete errors.value.phone
        }
      }
      break

    case 'zip':
      if (form.value.address.zip) {
        const zipRegex = /^\d{5}$/
        if (!zipRegex.test(form.value.address.zip)) {
          errors.value.zip = 'Invalid ZIP code'
        } else {
          delete errors.value.zip
        }
      }
      break

    case 'username':
      if (!form.value.username) {
        errors.value.username = 'Username is required'
      } else if (form.value.username.length < 3) {
        errors.value.username = 'Username must be at least 3 characters'
      } else if (!/^[a-zA-Z0-9_]+$/.test(form.value.username)) {
        errors.value.username = 'Username can only contain letters, numbers, and underscores'
      } else {
        delete errors.value.username
        checkUsernameAvailability()
      }
      break

    case 'password':
      if (!form.value.password) {
        errors.value.password = 'Password is required'
      } else if (form.value.password.length < 8) {
        errors.value.password = 'Password must be at least 8 characters'
      } else {
        delete errors.value.password
      }
      break

    case 'confirmPassword':
      if (!form.value.confirmPassword) {
        errors.value.confirmPassword = 'Please confirm your password'
      } else if (form.value.password !== form.value.confirmPassword) {
        errors.value.confirmPassword = 'Passwords do not match'
      } else {
        delete errors.value.confirmPassword
      }
      break
  }
}

async function checkUsernameAvailability() {
  checkingUsername.value = true
  try {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500))
    // For demo, assume username is available
  } finally {
    checkingUsername.value = false
  }
}

function validateForm() {
  errors.value = {}

  validateField('firstName')
  validateField('lastName')
  validateField('email')
  validateField('phone')
  validateField('zip')
  validateField('username')
  validateField('password')
  validateField('confirmPassword')

  if (!form.value.agreeToTerms) {
    errors.value.agreeToTerms = 'You must agree to the terms and conditions'
  }

  return Object.keys(errors.value).length === 0
}

async function handleSubmit() {
  if (!validateForm()) {
    submitError.value = 'Please fix the errors in the form'
    return
  }

  isSubmitting.value = true
  submitSuccess.value = false
  submitError.value = ''

  try {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1500))

    submitSuccess.value = true
    emit('submit', form.value)

    // Redirect after successful submission
    setTimeout(() => {
      router.push('/dashboard')
    }, 2000)
  } catch (error) {
    submitError.value = 'An error occurred while submitting the form. Please try again.'
  } finally {
    isSubmitting.value = false
  }
}

function resetForm() {
  form.value = {
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    address: {
      street: '',
      city: '',
      state: '',
      zip: ''
    },
    username: '',
    password: '',
    confirmPassword: '',
    preferences: {
      newsletter: false,
      notifications: [],
      language: 'en'
    },
    bio: '',
    agreeToTerms: false
  }
  errors.value = {}
  submitSuccess.value = false
  submitError.value = ''
}

function cancel() {
  emit('cancel')
  router.back()
}

// Watch username for debounced validation
watch(() => form.value.username, () => {
  if (form.value.username && form.value.username.length >= 3) {
    validateField('username')
  }
})

// Initialize with props data if provided
if (props.initialData) {
  form.value = { ...form.value, ...props.initialData }
}
</script>

<style scoped>
.form-component {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

form {
  background: white;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

h2 {
  margin-bottom: 30px;
  color: #333;
}

fieldset {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 20px;
  margin-bottom: 20px;
}

legend {
  font-weight: 600;
  color: #555;
  padding: 0 10px;
}

.form-group {
  margin-bottom: 20px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 15px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
}

input,
select,
textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

input.error,
select.error,
textarea.error {
  border-color: #dc3545;
}

.required {
  color: #dc3545;
}

.error-message {
  display: block;
  color: #dc3545;
  font-size: 0.875rem;
  margin-top: 5px;
}

.info-message {
  display: block;
  color: #6c757d;
  font-size: 0.875rem;
  margin-top: 5px;
}

.success-message {
  padding: 15px;
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
  border-radius: 4px;
  margin-top: 20px;
}

.password-strength {
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  margin-top: 5px;
  overflow: hidden;
}

.strength-bar {
  height: 100%;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.strength-bar.very-weak {
  background: #dc3545;
}

.strength-bar.weak {
  background: #fd7e14;
}

.strength-bar.fair {
  background: #ffc107;
}

.strength-bar.good {
  background: #28a745;
}

.strength-bar.strong,
.strength-bar.very-strong {
  background: #20c997;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  font-weight: normal;
}

.checkbox-group input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  font-weight: normal;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

.char-count {
  display: block;
  text-align: right;
  font-size: 0.875rem;
  color: #6c757d;
  margin-top: 5px;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 30px;
}

.btn-primary,
.btn-secondary,
.btn-tertiary {
  padding: 12px 24px;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-primary:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #545b62;
}

.btn-tertiary {
  background: white;
  color: #6c757d;
  border: 1px solid #6c757d;
}

.btn-tertiary:hover:not(:disabled) {
  background: #f8f9fa;
}
</style>
