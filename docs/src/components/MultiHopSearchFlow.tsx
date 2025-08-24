import React from "react";
import FlowBox from "./FlowBox";

const MultiHopSearchFlow = () => {
  return (
    <div className="multi-hop-flow-container">
      <div className="flow-step">
        <FlowBox
          title="Your Query"
          contents={['"authentication system"']}
          colorScheme="primary"
        />
      </div>

      <div className="flow-arrow">↓</div>
      <div className="stage-label">Retrieve more candidates</div>

      <FlowBox
        title="Expanded Initial Search"
        contents={["Get 3× the normal number of results", "All top-ranked matches for better reranking"]}
        colorScheme="info"
      />

      <div className="flow-arrow">↓</div>

      <FlowBox
        title="Starting Points"
        contents={["validateUser()", "loginHandler()", "checkAuth()", "hashPassword()", "createSession()"]}
        colorScheme="default"
      />

      <div className="flow-arrow">↓</div>
      <div className="stage-label">Follow the breadcrumbs</div>

      <div className="expansion-loop">
        <FlowBox
          title="Explore Connections"
          contents={["What's similar to validateUser()? → Token generation", "What's similar to hashPassword()? → Crypto utilities", "What's similar to createSession()? → Session storage"]}
          colorScheme="accent"
        />

        <div className="flow-arrow">↓</div>

        <FlowBox
          title="Ripple Effect"
          contents={["Each discovery leads to more discoveries", "Building semantic chains across the codebase", "Maintaining focus on original query"]}
          colorScheme="info"
        />

        <div className="flow-arrow">↓</div>

        <FlowBox
          title="Quality Control"
          contents={["Rerank everything against your original query", "Keep the relevant, discard the distant"]}
          colorScheme="warning"
        />
      </div>

      <div className="flow-arrow">↓</div>
      <div className="loop-indicator">↻ Continue exploring until diminishing returns...</div>

      <div className="flow-arrow">↓</div>
      <div className="stage-label">Complete picture emerges</div>

      <FlowBox
        title="Semantic Chain Discovered"
        contents={[
          "Core authentication logic",
          "Password security & hashing", 
          "Token & session management",
          "Authorization & permissions",
          "Security monitoring & logging"
        ]}
        colorScheme="accent"
      />

      <style jsx>{`
        .multi-hop-flow-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
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
          font-size: 13px;
          color: var(--color-text-secondary);
          font-weight: 500;
          font-style: italic;
          margin: 4px 0;
        }

        .loop-indicator {
          font-size: 13px;
          color: var(--color-accent);
          font-weight: 500;
          font-style: italic;
          margin: 8px 0;
          text-align: center;
        }

        .expansion-loop {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          padding: 20px;
          border: 2px dashed var(--color-accent-muted);
          border-radius: 12px;
          background: var(--color-bg-secondary);
          margin: 8px 0;
        }

        .flow-arrow {
          font-size: 24px;
          color: var(--color-text-tertiary);
          font-weight: bold;
          margin: 4px 0;
        }
      `}</style>
    </div>
  );
};

export default MultiHopSearchFlow;
