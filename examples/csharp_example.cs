using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace ChunkHound.Examples
{
    /// <summary>
    /// Example C# code demonstrating ChunkHound's parsing capabilities.
    /// This file shows the 8 semantic chunk types that ChunkHound extracts:
    /// Classes, Interfaces, Structs, Enums, Methods, Properties, Constructors
    /// </summary>
    public class UserService : IUserService
    {
        private readonly IUserRepository _repository;
        private readonly ILogger<UserService> _logger;

        // Constructor - extracted as semantic chunk
        public UserService(IUserRepository repository, ILogger<UserService> logger)
        {
            _repository = repository ?? throw new ArgumentNullException(nameof(repository));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        // Property - extracted as semantic chunk
        public string ServiceName { get; private set; } = "UserService";

        // Async method - extracted as semantic chunk
        public async Task<User> GetUserAsync(int userId)
        {
            _logger.LogInformation("Retrieving user with ID: {UserId}", userId);
            
            try
            {
                var user = await _repository.GetByIdAsync(userId);
                return user ?? throw new UserNotFoundException($"User {userId} not found");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving user {UserId}", userId);
                throw;
            }
        }

        // Generic method - extracted as semantic chunk
        public T ProcessData<T>(T data) where T : class, new()
        {
            if (data == null)
                return new T();
            
            return data;
        }
    }

    // Interface - extracted as semantic chunk
    public interface IUserService
    {
        Task<User> GetUserAsync(int userId);
        string ServiceName { get; }
    }

    // Struct - extracted as semantic chunk  
    public struct UserInfo
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public DateTime CreatedAt { get; set; }

        // Constructor in struct - extracted as semantic chunk
        public UserInfo(int id, string name)
        {
            Id = id;
            Name = name;
            CreatedAt = DateTime.UtcNow;
        }
    }

    // Enum - extracted as semantic chunk
    public enum UserStatus
    {
        Active,
        Inactive,
        Suspended,
        Deleted
    }

    // Nested class example
    public class DataProcessor
    {
        // Nested class - extracted as semantic chunk
        public class ProcessingResult
        {
            public bool Success { get; set; }
            public string Message { get; set; }
            public DateTime ProcessedAt { get; set; }
        }

        // Method with complex parameters - extracted as semantic chunk
        public async Task<ProcessingResult> ProcessUserDataAsync(
            List<UserInfo> users, 
            Dictionary<string, object> options = null)
        {
            await Task.Delay(100); // Simulate processing
            
            return new ProcessingResult
            {
                Success = true,
                Message = $"Processed {users?.Count ?? 0} users",
                ProcessedAt = DateTime.UtcNow
            };
        }
    }
}

// Multiple namespaces supported
namespace ChunkHound.Examples.Models
{
    // Class with inheritance - extracted as semantic chunk
    public abstract class BaseEntity
    {
        public int Id { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime? UpdatedAt { get; set; }

        // Abstract method - extracted as semantic chunk
        public abstract void Validate();
    }

    // Derived class - extracted as semantic chunk
    public class User : BaseEntity
    {
        public string Username { get; set; }
        public string Email { get; set; }
        public UserStatus Status { get; set; }

        // Override method - extracted as semantic chunk
        public override void Validate()
        {
            if (string.IsNullOrWhiteSpace(Username))
                throw new ValidationException("Username is required");
            
            if (string.IsNullOrWhiteSpace(Email))
                throw new ValidationException("Email is required");
        }

        // Static method - extracted as semantic chunk
        public static User CreateNew(string username, string email)
        {
            return new User
            {
                Username = username,
                Email = email,
                Status = UserStatus.Active,
                CreatedAt = DateTime.UtcNow
            };
        }
    }
}