package com.example.demo;

import java.util.ArrayList;
import java.util.List;
import static java.util.Collections.sort;

/**
 * Example Java class for parser testing
 */
@SuppressWarnings("unused")
public class Sample<T extends Comparable<T>> {
    
    private final String name;
    private List<T> items = new ArrayList<>();
    
    public Sample(String name) {
        this.name = name;
    }
    
    /**
     * Add an item to the collection
     */
    public void addItem(T item) {
        items.add(item);
    }
    
    public List<T> getItems() {
        return new ArrayList<>(items);
    }
    
    @Override
    public String toString() {
        return "Sample(" + name + ", items=" + items.size() + ")";
    }
    
    // Inner class example
    private class InnerSample {
        void process() {
            System.out.println("Processing " + name);
        }
    }
    
    // Enum example
    public enum Status {
        ACTIVE, INACTIVE, PENDING;
        
        public boolean isActive() {
            return this == ACTIVE;
        }
    }
    
    // Interface example
    public interface Processor<T> {
        void process(T item);
    }
}