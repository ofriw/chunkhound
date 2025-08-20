import React from "react";
import FlowBox from "./FlowBox";

const SemanticSearchFlow = () => {
  return (
    <div className="semantic-flow-container">
      <div className="flow-step">
        <FlowBox 
          title="Query"
          contents={['"database timeout"']}
          colorScheme="primary"
        />
      </div>

      <div className="flow-arrow">↓</div>

      <div className="flow-step">
        <FlowBox 
          title="Embedding"
          contents={['[0.2, -0.1, 0.8, ...]']}
          colorScheme="warning"
          monospace={true}
        />
      </div>

      <div className="flow-arrow">↓</div>

      <FlowBox 
        title="Search"
        contents={['Find nearest neighbors in vector space']}
        colorScheme="info"
      />

      <div className="flow-arrow">↓</div>

      <FlowBox 
        title="Results"
        contents={[
          'SQL connection timeout',
          'DB retry logic', 
          'Connection pool config'
        ]}
        colorScheme="accent"
      />

      <style jsx>{`
        .semantic-flow-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 5px;
          margin: 30px 0;
          font-family:
            Inter,
            -apple-system,
            BlinkMacSystemFont,
            sans-serif;
          padding-left: 0;
        }

        .flow-step {
          display: flex;
          justify-content: center;
          margin-top: 0px;
        }


        .flow-arrow {
          font-size: 24px;
          color: var(--color-text-tertiary);
          font-weight: bold;
          margin-top: 0px;
        }


        .step-with-annotation {
          position: relative;
          display: flex;
          justify-content: center;
        }

        .step-indicator {
          position: absolute;
          left: -280px;
          top: 50%;
          transform: translateY(-50%);
          width: 250px;
        }

        .step-number {
          position: absolute;
          left: 0;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: var(--color-bg-secondary);
          border: 1px solid var(--color-border);
          text-align: center;
          line-height: 20px;
          font-size: 10px;
          font-weight: 600;
          color: var(--color-text-tertiary);
        }

        .step-text {
          position: absolute;
          left: 30px;
          font-size: 11px;
          color: var(--color-text-tertiary);
          line-height: 1.2;
          white-space: nowrap;
        }
      `}</style>
    </div>
  );
};

export default SemanticSearchFlow;
