import React, { useState, memo } from "react";
import { formatRelativeDate } from "../utils/dateUtils";
import { getVersionType } from "../utils/versionUtils";
import { CATEGORY_ICONS, DEFAULT_ICON } from "../constants/icons";

interface Change {
  category: string;
  items: string[];
}

interface VersionCardProps {
  version: string;
  date: string;
  changes: Change[];
  isBreaking?: boolean;
  className?: string;
  id?: string;
}

const VersionCard: React.FC<VersionCardProps> = ({
  version,
  date,
  changes,
  isBreaking = false,
  className = "",
  id,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const { type, color } = getVersionType(version);

  // Simple category icon lookup (performance optimized)
  const getCategoryIcon = (category: string) => {
    return CATEGORY_ICONS[category] || DEFAULT_ICON;
  };

  return (
    <div className={`version-card ${className}`} id={id}>
      {/* Version Header */}
      <div
        className="version-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="version-info">
          <div className="version-title">
            <span className={`version-badge ${color}`}>{version}</span>
            <span className={`version-type ${type}`}>{type}</span>
            {isBreaking && <span className="breaking-badge">Breaking</span>}
          </div>
          <div className="version-meta">
            <span className="version-date">{date}</span>
            <span className="version-relative">
              ({formatRelativeDate(date)})
            </span>
          </div>
        </div>
        <div className="expand-icon">{isExpanded ? "▼" : "▶"}</div>
      </div>

      {/* Changes Content */}
      {isExpanded && (
        <div className="version-content">
          {changes.map((change, index) => {
            const { icon, color: categoryColor } = getCategoryIcon(
              change.category,
            );
            return (
              <div key={index} className="change-section">
                <div className={`change-header ${categoryColor}`}>
                  <span className="change-icon">{icon}</span>
                  <span className="change-title">{change.category}</span>
                </div>
                <ul className="change-list">
                  {change.items.map((item, itemIndex) => (
                    <li key={itemIndex} className="change-item">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
};

export default memo(VersionCard);
