<?php
/**
 * Comprehensive PHP test file for ChunkHound parser testing.
 *
 * Tests all PHP language features:
 * - Namespaces
 * - Classes (abstract, final, regular)
 * - Interfaces
 * - Traits
 * - Methods (public, private, protected, static, abstract, final)
 * - Functions (standalone)
 * - Type hints (scalar, nullable, union, return types)
 * - PHPDoc comments
 * - Line and block comments
 */

namespace App\Services\User;

use App\Models\User;
use App\Repositories\UserRepository;
use App\Exceptions\UserNotFoundException;

/**
 * Abstract base service class.
 *
 * Demonstrates abstract classes and methods.
 */
abstract class AbstractUserService
{
    /**
     * Process user data.
     *
     * @param User $user
     * @return void
     */
    abstract protected function process(User $user): void;

    /**
     * Get repository instance.
     */
    abstract protected function getRepository(): UserRepository;
}

/**
 * Final immutable value object.
 */
final class UserId
{
    private int $value;

    public function __construct(int $value)
    {
        $this->value = $value;
    }

    public function getValue(): int
    {
        return $this->value;
    }
}

/**
 * User service for handling user operations.
 *
 * Demonstrates regular class with various method types.
 */
class UserService extends AbstractUserService
{
    private UserRepository $repository;
    private static ?UserService $instance = null;

    /**
     * Constructor with dependency injection.
     */
    public function __construct(UserRepository $repository)
    {
        $this->repository = $repository;
    }

    /**
     * Get user by ID with type hints.
     *
     * @param int $id User ID
     * @param bool $useCache Whether to use cache
     * @return User|null User object or null if not found
     */
    public function getUserById(int $id, bool $useCache = true): ?User
    {
        if ($useCache) {
            // Check cache first
            return $this->repository->findCached($id);
        }

        return $this->repository->find($id);
    }

    /**
     * Create a new user with validation.
     */
    public function createUser(string $name, string $email, ?string $phone = null): User
    {
        $user = new User();
        $user->name = $name;
        $user->email = $email;
        $user->phone = $phone;

        return $this->repository->save($user);
    }

    /**
     * Static factory method.
     */
    public static function getInstance(UserRepository $repository): self
    {
        if (self::$instance === null) {
            self::$instance = new self($repository);
        }

        return self::$instance;
    }

    /**
     * Implementation of abstract method.
     */
    protected function process(User $user): void
    {
        // Process user logic
    }

    /**
     * Implementation of abstract method.
     */
    protected function getRepository(): UserRepository
    {
        return $this->repository;
    }

    /**
     * Private helper method.
     */
    private function validateEmail(string $email): bool
    {
        return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;
    }
}

/**
 * User repository interface.
 */
interface UserRepositoryInterface
{
    /**
     * Find user by ID.
     */
    public function find(int $id): ?User;

    /**
     * Save user to database.
     */
    public function save(User $user): User;

    /**
     * Delete user by ID.
     */
    public function delete(int $id): bool;
}

/**
 * Trait for adding timestamp functionality.
 */
trait Timestampable
{
    protected ?int $createdAt = null;
    protected ?int $updatedAt = null;

    /**
     * Set created timestamp.
     */
    public function setCreatedAt(int $timestamp): void
    {
        $this->createdAt = $timestamp;
    }

    /**
     * Update the updated_at timestamp.
     */
    public function touch(): void
    {
        $this->updatedAt = time();
    }
}

// Standalone helper function
/**
 * Sanitize text input.
 *
 * @param string $text Input text
 * @return string Sanitized text
 */
function sanitizeText(string $text): string
{
    return htmlspecialchars($text, ENT_QUOTES, 'UTF-8');
}

/**
 * Format user name.
 */
function formatUserName(string $firstName, string $lastName): string
{
    return trim("$firstName $lastName");
}

/* Block comment for testing */

// Single line comment for testing
