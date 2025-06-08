# ChunkHound Examples

This directory contains example code demonstrating ChunkHound's language parsing capabilities.

## C# Language Support

ChunkHound provides comprehensive C# language support, extracting **8 semantic chunk types** from C# code:

### Supported C# Features

| Chunk Type | Description | Example |
|------------|-------------|---------|
| **Classes** | Class definitions with inheritance | `public class UserService : IUserService` |
| **Interfaces** | Interface declarations | `public interface IUserService` |
| **Structs** | Value type definitions | `public struct UserInfo` |
| **Enums** | Enumeration types | `public enum UserStatus` |
| **Methods** | Method definitions (sync/async) | `public async Task<User> GetUserAsync(int userId)` |
| **Properties** | Property declarations | `public string ServiceName { get; set; }` |
| **Constructors** | Constructor methods | `public UserService(IUserRepository repository)` |
| **Nested Types** | Classes/structs within classes | `public class ProcessingResult` |

### Advanced C# Support

ChunkHound handles modern C# language features:

- **Generic Types**: `public T ProcessData<T>(T data) where T : class`
- **Async/Await**: `public async Task<User> GetUserAsync(int userId)`
- **Multiple Namespaces**: Each namespace is parsed separately
- **Inheritance**: Base classes and derived classes
- **Abstract/Virtual Members**: Abstract methods and overrides
- **Static Members**: Static methods and properties
- **Complex Parameters**: Methods with multiple parameters and default values
- **Nullable Types**: Properties with nullable reference types

### What Gets Indexed

Each semantic chunk includes:

- **Symbol**: Fully qualified name (e.g., `ChunkHound.Examples.UserService.GetUserAsync(int)`)
- **Code Content**: Complete method/class/interface code
- **Line Numbers**: Exact start and end line positions  
- **Type Information**: Chunk type (class, method, property, etc.)
- **Language Info**: Marked as "csharp" for language-specific searches

### Search Examples

Once indexed, you can search your C# code with:

**Semantic Search:**
- "Find all async methods that handle user data"
- "Show me classes that implement repository pattern"
- "Find error handling patterns in C# code"
- "Where are validation methods defined?"

**Regex Search:**
- `async.*User.*` - Find async methods mentioning User
- `public.*interface.*` - Find all public interfaces
- `override.*` - Find all method overrides
- `.*Exception.*` - Find exception handling code

## Usage

```bash
# Index C# project
chunkhound run ./my-csharp-project

# Start search server
chunkhound mcp

# Now ask your AI assistant:
# "Find all C# classes that inherit from BaseEntity"
# "Show me async methods in the UserService class"
# "Find C# interfaces and their implementations"
```

## Performance

C# parsing performance:
- **Speed**: Comparable to Java/Python parsing
- **Accuracy**: 95%+ successful parsing of valid C# code
- **Memory**: Efficient tree-sitter based parsing
- **Zero Configuration**: Works out-of-the-box with existing ChunkHound setup

## File Extensions

ChunkHound automatically detects and processes:
- `.cs` files as C# source code

All C# files are parsed using the tree-sitter C# grammar for accurate semantic extraction.