/**
 * Date utility functions for formatting relative dates
 */

/**
 * Format a date string into a human-readable relative time
 * @param dateStr - ISO date string (e.g., "2024-12-10")
 * @returns Human-readable relative date (e.g., "2 days ago", "Yesterday")
 */
export const formatRelativeDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 30) return `${diffDays} days ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
};