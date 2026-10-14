import React from "react";
import ReactMarkdown from "react-markdown";

const MarkdownCard = ({ text, isDarkMode }) => {
  const textColor = isDarkMode ? "#e4e4e4" : "#111827";
  const bgColor = isDarkMode ? "#1f1f1f" : "#f9fafb";

  return (
    <div
      style={{
        maxWidth: "500px",
        maxHeight: "300px",
        overflowY: "auto",
        background: bgColor,
        padding: "1rem",
        borderRadius: "10px",
        boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
        color: textColor,
        fontSize: 14,
        lineHeight: 1.5,
        margin: "0 auto",
      }}
    >
      <ReactMarkdown
        children={text}
        components={{
          h1: ({ node, ...props }) => {
            void node;
            return <h1 style={{ fontSize: 18, marginBottom: 10 }} {...props} />;
          },
          h2: ({ node, ...props }) => {
            void node;
            return <h2 style={{ fontSize: 16, marginBottom: 8 }} {...props} />;
          },
          p: ({ node, ...props }) => {
            void node;
            return <p style={{ marginBottom: 8 }} {...props} />;
          },
          ul: ({ node, ...props }) => {
            void node;
            return <ul style={{ paddingLeft: "1.2rem", marginBottom: 10 }} {...props} />;
          },
          li: ({ node, ...props }) => {
            void node;
            return <li style={{ marginBottom: 4 }} {...props} />;
          },
          strong: ({ node, ...props }) => {
            void node;
            return <strong style={{ fontWeight: 600 }} {...props} />;
          },
        }}
      />
    </div>
  );
};

export default MarkdownCard;
