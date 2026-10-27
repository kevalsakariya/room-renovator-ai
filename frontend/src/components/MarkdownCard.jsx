import React from "react";
import ReactMarkdown from "react-markdown";

const MarkdownCard = ({ text, isDarkMode }) => {
  const textColor = isDarkMode ? "#e4e4e4" : "#1f2937";
  const bgColor = isDarkMode ? "#18181b" : "#ffffff";
  const borderColor = isDarkMode ? "#27272a" : "#e5e7eb";

  return (
    <div
      style={{
        maxWidth: "760px",
        maxHeight: "480px",
        overflowY: "auto",
        background: bgColor,
        padding: "1.5rem",
        borderRadius: "12px",
        border: `1px solid ${borderColor}`,
        boxShadow: "0 8px 24px rgba(0,0,0,0.06)",
        color: textColor,
        fontSize: 14,
        lineHeight: 1.6,
        margin: "0 auto",
        textAlign: "left",
      }}
    >
      <ReactMarkdown
        children={text}
        components={{
          h1: ({ node, ...props }) => {
            void node;
            return <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12, color: isDarkMode ? "#38bdf8" : "#0284c7" }} {...props} />;
          },
          h2: ({ node, ...props }) => {
            void node;
            return <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 10, color: isDarkMode ? "#38bdf8" : "#0284c7" }} {...props} />;
          },
          h3: ({ node, ...props }) => {
            void node;
            return <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8, color: isDarkMode ? "#f1f5f9" : "#0f172a" }} {...props} />;
          },
          h4: ({ node, ...props }) => {
            void node;
            return <h4 style={{ fontSize: 15, fontWeight: 600, marginTop: 12, marginBottom: 6, color: isDarkMode ? "#38bdf8" : "#0369a1" }} {...props} />;
          },
          p: ({ node, ...props }) => {
            void node;
            return <p style={{ marginBottom: 10, color: textColor }} {...props} />;
          },
          ul: ({ node, ...props }) => {
            void node;
            return <ul style={{ paddingLeft: "1.4rem", marginBottom: 12 }} {...props} />;
          },
          li: ({ node, ...props }) => {
            void node;
            return <li style={{ marginBottom: 6 }} {...props} />;
          },
          strong: ({ node, ...props }) => {
            void node;
            return <strong style={{ fontWeight: 600, color: isDarkMode ? "#f8fafc" : "#111827" }} {...props} />;
          },
          hr: ({ node, ...props }) => {
            void node;
            return <hr style={{ borderColor, margin: "16px 0", borderTopWidth: 1 }} {...props} />;
          },
          blockquote: ({ node, ...props }) => {
            void node;
            return (
              <blockquote
                style={{
                  borderLeft: "4px solid #38bdf8",
                  padding: "8px 14px",
                  margin: "12px 0",
                  backgroundColor: isDarkMode ? "#0f172a" : "#f0f9ff",
                  borderRadius: "0 8px 8px 0",
                  color: isDarkMode ? "#bae6fd" : "#0369a1",
                  fontSize: 13,
                }}
                {...props}
              />
            );
          },
        }}
      />
    </div>
  );
};

export default MarkdownCard;

