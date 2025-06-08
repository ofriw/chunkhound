using System;
using System.Collections.Generic;
using System.Linq;
using System.ComponentModel;

namespace Com.Example.Demo
{
    /// <summary>
    /// Example C# class for parser testing
    /// </summary>
    [Obsolete("This is a test class")]
    public class Sample<T> where T : IComparable<T>
    {
        private readonly string _name;
        private List<T> _items = new List<T>();

        /// <summary>
        /// Constructor with name parameter
        /// </summary>
        public Sample(string name)
        {
            _name = name ?? throw new ArgumentNullException(nameof(name));
        }

        /// <summary>
        /// Parameterless constructor
        /// </summary>
        public Sample() : this("Default")
        {
        }

        /// <summary>
        /// Name property with getter only
        /// </summary>
        public string Name => _name;

        /// <summary>
        /// Items property with full getter/setter
        /// </summary>
        public List<T> Items
        {
            get => new List<T>(_items);
            set => _items = value ?? new List<T>();
        }

        /// <summary>
        /// Auto-implemented property
        /// </summary>
        public bool IsActive { get; set; } = true;

        /// <summary>
        /// Add an item to the collection
        /// </summary>
        public void AddItem(T item)
        {
            if (item != null)
            {
                _items.Add(item);
            }
        }

        /// <summary>
        /// Get items with filtering
        /// </summary>
        public List<T> GetItems(Func<T, bool> predicate = null)
        {
            return predicate == null 
                ? new List<T>(_items) 
                : _items.Where(predicate).ToList();
        }

        /// <summary>
        /// Override ToString method
        /// </summary>
        public override string ToString()
        {
            return $"Sample({_name}, items={_items.Count})";
        }

        /// <summary>
        /// Static method example
        /// </summary>
        public static Sample<string> CreateStringSample(string name)
        {
            return new Sample<string>(name);
        }

        /// <summary>
        /// Inner class example
        /// </summary>
        private class InnerSample
        {
            private readonly string _parentName;

            public InnerSample(string parentName)
            {
                _parentName = parentName;
            }

            public void Process()
            {
                Console.WriteLine($"Processing {_parentName}");
            }
        }

        /// <summary>
        /// Nested struct example
        /// </summary>
        public struct NestedData
        {
            public int Id { get; set; }
            public string Value { get; set; }

            public NestedData(int id, string value)
            {
                Id = id;
                Value = value;
            }

            public override string ToString()
            {
                return $"NestedData(Id={Id}, Value={Value})";
            }
        }
    }

    /// <summary>
    /// Status enumeration
    /// </summary>
    public enum Status
    {
        Active,
        Inactive,
        Pending,
        Archived
    }

    /// <summary>
    /// Priority enumeration with values
    /// </summary>
    public enum Priority : int
    {
        Low = 1,
        Medium = 2,
        High = 3,
        Critical = 4
    }

    /// <summary>
    /// Processor interface example
    /// </summary>
    public interface IProcessor<T>
    {
        /// <summary>
        /// Process an item
        /// </summary>
        void Process(T item);

        /// <summary>
        /// Process multiple items
        /// </summary>
        void ProcessBatch(IEnumerable<T> items);

        /// <summary>
        /// Property in interface
        /// </summary>
        bool IsReady { get; }
    }

    /// <summary>
    /// Extended processor interface
    /// </summary>
    public interface IExtendedProcessor<T> : IProcessor<T>
    {
        /// <summary>
        /// Process with callback
        /// </summary>
        void ProcessWithCallback(T item, Action<T> callback);
    }

    /// <summary>
    /// Configuration struct
    /// </summary>
    public struct Configuration
    {
        public string ConnectionString { get; set; }
        public int Timeout { get; set; }
        public bool EnableLogging { get; set; }

        public Configuration(string connectionString, int timeout = 30, bool enableLogging = true)
        {
            ConnectionString = connectionString;
            Timeout = timeout;
            EnableLogging = enableLogging;
        }

        public void Validate()
        {
            if (string.IsNullOrEmpty(ConnectionString))
                throw new InvalidOperationException("Connection string is required");
        }
    }

    /// <summary>
    /// Abstract base class
    /// </summary>
    public abstract class BaseProcessor
    {
        protected string Name { get; set; }

        protected BaseProcessor(string name)
        {
            Name = name ?? throw new ArgumentNullException(nameof(name));
        }

        public abstract void Execute();

        public virtual void Initialize()
        {
            Console.WriteLine($"Initializing {Name}");
        }
    }

    /// <summary>
    /// Concrete implementation
    /// </summary>
    public class ConcreteProcessor : BaseProcessor, IProcessor<string>
    {
        public bool IsReady { get; private set; }

        public ConcreteProcessor(string name) : base(name)
        {
            IsReady = true;
        }

        public override void Execute()
        {
            Console.WriteLine($"Executing {Name}");
        }

        public void Process(string item)
        {
            Console.WriteLine($"Processing: {item}");
        }

        public void ProcessBatch(IEnumerable<string> items)
        {
            foreach (var item in items)
            {
                Process(item);
            }
        }
    }
}

namespace Com.Example.Demo.Extensions
{
    /// <summary>
    /// Extension methods in separate namespace
    /// </summary>
    public static class SampleExtensions
    {
        /// <summary>
        /// Extension method for Sample
        /// </summary>
        public static void PrintInfo<T>(this Sample<T> sample) where T : IComparable<T>
        {
            Console.WriteLine(sample.ToString());
        }

        /// <summary>
        /// Extension method for string
        /// </summary>
        public static bool IsValidEmail(this string email)
        {
            return !string.IsNullOrEmpty(email) && email.Contains("@");
        }
    }
}