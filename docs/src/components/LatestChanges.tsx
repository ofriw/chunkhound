import React from "react";

interface LatestChangesProps {
  className?: string;
}

const LatestChanges: React.FC<LatestChangesProps> = ({ className = "" }) => {
  return (
    <div className={`latest-changes ${className}`}>
      <div className="latest-changes-header">
        <h2>Latest Updates</h2>
        <p>Stay up to date with ChunkHound's latest features and improvements.</p>
      </div>

      <div className="latest-changes-grid">
        <div className="change-card">
          <div className="change-card-header">
            <h3>Recent Improvements</h3>
            <span className="rocket-icon">🚀</span>
          </div>
          <div className="change-card-content">
            <div className="change-summary">
              Multi-hop semantic search, automatic file watching, and enhanced MCP server reliability.
            </div>
            <ul className="change-highlights">
              <li className="highlight-item">
                Enhanced parsing with universal language support
              </li>
              <li className="highlight-item">
                Improved MCP server coordination and watchdog
              </li>
              <li className="highlight-item">
                Simplified configuration for easier setup
              </li>
            </ul>
          </div>
        </div>
        
        <div className="change-card">
          <div className="change-card-header">
            <h3>Performance Boost</h3>
            <span className="rocket-icon">⚡</span>
          </div>
          <div className="change-card-content">
            <div className="change-summary">
              Significant performance improvements and reliability enhancements.
            </div>
            <ul className="change-highlights">
              <li className="highlight-item">
                Enhanced database portability with relative paths
              </li>
              <li className="highlight-item">
                Better file change processing and debouncing
              </li>
              <li className="highlight-item">
                Improved MCP server initialization
              </li>
            </ul>
          </div>
        </div>

        <div className="change-card">
          <div className="change-card-header">
            <h3>Enhanced Features</h3>
            <span className="rocket-icon">✨</span>
          </div>
          <div className="change-card-content">
            <div className="change-summary">
              New transport options and improved development experience.
            </div>
            <ul className="change-highlights">
              <li className="highlight-item">
                MCP HTTP transport alongside stdio support
              </li>
              <li className="highlight-item">
                Unified configuration across CLI and MCP
              </li>
              <li className="highlight-item">
                Better cross-platform file path handling
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div className="view-all-link">
        <a href="./changelog" className="btn-secondary">
          View Full Changelog →
        </a>
      </div>
    </div>
  );
};

export default LatestChanges;