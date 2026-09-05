import React from "react";

export function PageContext({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="page-context"
      style={{
        marginTop: "48px",
        paddingTop: "24px",
        borderTop: "1px solid var(--border-subtle, #e0e5ec)",
        color: "var(--text-secondary, #687488)",
        fontSize: "12px",
        lineHeight: "1.6",
        maxWidth: "800px"
      }}
    >
      {children}
    </div>
  );
}
