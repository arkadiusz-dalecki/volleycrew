import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";

export function ConfirmDialog({
  title,
  busy = false,
  onDismiss,
  children,
}: {
  title: string;
  busy?: boolean;
  onDismiss: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const element = dialog.current!;
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    element.showModal();
    return () => {
      if (element.open) element.close();
      const target = previous?.isConnected
        ? previous
        : document.getElementById("main");
      target?.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="confirm-dialog"
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onDismiss();
      }}
    >
      <h2 id={titleId}>{title}</h2>
      <div className="confirm-dialog-body">{children}</div>
    </dialog>
  );
}
