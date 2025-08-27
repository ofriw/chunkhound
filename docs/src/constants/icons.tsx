import React from "react";

/**
 * Category icons for changelog entries
 * Extracted to prevent recreation on every render
 */

export interface CategoryIcon {
  icon: React.ReactElement;
  color: string;
}

export const CATEGORY_ICONS: Record<string, CategoryIcon> = {
  Added: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle
          cx="8"
          cy="8"
          r="6"
          stroke="var(--color-success)"
          strokeWidth="2"
        />
        <path
          d="M8 5v6M5 8h6"
          stroke="var(--color-success)"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    ),
    color: "success",
  },
  Changed: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M 2 5 L 13 5"
          stroke="var(--color-primary)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M 10 2 L 13 5 L 10 8"
          stroke="var(--color-primary)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
        <path
          d="M 14 11 L 3 11"
          stroke="var(--color-primary)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M 6 8 L 3 11 L 6 14"
          stroke="var(--color-primary)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    ),
    color: "primary",
  },
  Fixed: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle
          cx="8"
          cy="8"
          r="6"
          stroke="var(--color-fixed)"
          strokeWidth="2"
        />
        <path
          d="M5 8l2 2 4-4"
          stroke="var(--color-fixed)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    color: "fixed",
  },
  Enhanced: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M8 3l3 5H5l3-5z"
          stroke="var(--color-enhanced)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M8 3v10"
          stroke="var(--color-enhanced)"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    ),
    color: "enhanced",
  },
  Removed: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle
          cx="8"
          cy="8"
          r="6"
          stroke="var(--color-neutral)"
          strokeWidth="2"
        />
        <path
          d="M5 8h6"
          stroke="var(--color-neutral)"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    ),
    color: "neutral",
  },
  Security: {
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M8 2l4 2v4c0 3-2 5-4 6-2-1-4-3-4-6V4l4-2z"
          stroke="var(--color-error)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    color: "error",
  },
};

export const DEFAULT_ICON: CategoryIcon = {
  icon: <span>•</span>,
  color: "default",
};