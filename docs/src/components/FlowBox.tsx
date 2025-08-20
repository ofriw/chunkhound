import React from "react";

interface FlowBoxProps {
  title?: string;
  contents: string[];
  colorScheme?: "primary" | "accent" | "info" | "warning" | "default";
  className?: string;
  monospace?: boolean;
}

const FlowBox: React.FC<FlowBoxProps> = ({
  title,
  contents,
  colorScheme = "default",
  className = "",
  monospace = false,
}) => {
  return (
    <div className={`flow-box ${className}`}>
      {title && (
        <div className={`flow-box-header ${colorScheme}-header`}>{title}</div>
      )}
      <div className={`flow-box-content ${monospace ? "monospace" : ""}`}>
        {contents.map((content, index) => (
          <div key={index} className="flow-box-line">
            {content}
          </div>
        ))}
      </div>

      <style jsx>{`
        .flow-box {
          border: 2px solid var(--color-code-border);
          border-radius: 6px;
          min-width: 250px;
          text-align: center;
          font-size: 14px;
          overflow: hidden;
        }

        .flow-box-header {
          font-weight: 600;
          font-size: 14px;
          padding: 10px 20px;
        }

        .flow-box-content {
          background: var(--color-code-bg);
          padding: 15px 20px;
          color: var(--color-text);
          margin-top: 0px;
        }

        .flow-box-content.monospace {
          font-family: "Monaco", "Menlo", monospace;
          color: var(--color-text-secondary);
        }

        .flow-box-line {
          padding: 5px 0;
          font-size: 13px;
        }

        .flow-box-line:not(:last-child) {
          border-bottom: 1px solid var(--color-border);
        }

        /* Title color schemes */
        .primary-header {
          background: var(--color-primary-muted);
          color: var(--color-primary);
        }

        .accent-header {
          background: var(--color-accent-muted);
          color: var(--color-accent);
        }

        .info-header {
          background: var(--color-info-bg);
          color: var(--color-info);
        }

        .warning-header {
          background: var(--color-warning-bg);
          color: var(--color-warning);
        }

        .default-header {
          background: var(--color-bg-tertiary);
          color: var(--color-text);
        }
      `}</style>
    </div>
  );
};

export default FlowBox;
