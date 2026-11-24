import type { ReactNode } from "react";
import { Icon } from "./Icon";

/** Estado vacío diseñado: explica QUÉ falta y CÓMO conseguirlo (nunca se rellena con datos inventados). */
export function EmptyState({ title, children, icon = "inbox", action }: {
  title: string; children?: ReactNode; icon?: string; action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon"><Icon name={icon} /></div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div style={{ marginTop: 10 }}>{action}</div>}
    </div>
  );
}
