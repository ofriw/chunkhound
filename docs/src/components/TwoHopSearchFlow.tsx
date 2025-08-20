import React from "react";
import FlowBox from "./FlowBox";

const TwoHopSearchFlow = () => {
  return (
    <div className="two-hop-flow-container">
      <div className="flow-step">
        <FlowBox
          title="Query"
          contents={['"user authentication"']}
          colorScheme="primary"
        />
      </div>

      <div className="flow-arrow">↓</div>
      <div className="stage-label">Stage 1: Get immediate candidates</div>

      <div className="flow-step">
        <FlowBox
          title="Embedding"
          contents={["[0.2, -0.1, 0.8, ...]"]}
          colorScheme="warning"
          monospace={true}
        />
      </div>

      <div className="flow-arrow">↓</div>

      <FlowBox
        title="Search"
        contents={["Find nearest neighbors in vector space"]}
        colorScheme="info"
      />

      <div className="flow-arrow">↓</div>

      <FlowBox
        title="Initial Results"
        contents={["validateUser()", "checkAuth()", "loginHandler()"]}
        colorScheme="default"
      />

      <div className="flow-arrow">↓</div>
      <div className="stage-label">Stage 2: Semantic expansion</div>

      <FlowBox
        title="Find Neighbors"
        contents={["For each top result, find semantically similar chunks"]}
        colorScheme="info"
      />

      <div className="flow-arrow">↓</div>

      <FlowBox
        title="Expanded Set"
        contents={[
          "validateUser()",
          "checkAuth()",
          "loginHandler()",
          "hashPassword()",
          "generateToken()",
          "createSession()",
          "getUserProfile()",
        ]}
        colorScheme="default"
      />

      <div className="flow-arrow">↓</div>
      <div className="stage-label">Stage 3: Rerank against original query</div>

      <FlowBox
        title="Rerank"
        contents={["Sort by relevance to original query"]}
        colorScheme="warning"
      />

      <div className="flow-arrow">↓</div>

      <FlowBox
        title="Final Results"
        contents={[
          "validateUser()",
          "hashPassword()",
          "checkAuth()",
          "createSession()",
        ]}
        colorScheme="accent"
      />

      <style jsx>{`
        .two-hop-flow-container {
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

        .stage-label {
          font-size: 12px;
          color: var(--color-text-tertiary);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin: 5px 0;
        }

        .flow-arrow {
          font-size: 24px;
          color: var(--color-text-tertiary);
          font-weight: bold;
          margin-top: 0px;
        }
      `}</style>
    </div>
  );
};

export default TwoHopSearchFlow;
