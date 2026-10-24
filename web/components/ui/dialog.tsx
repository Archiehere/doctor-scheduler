"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Modal built on the native <dialog> element: focus trapping and Esc come for free. */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className="m-auto w-[min(440px,calc(100vw-32px))] rounded-lg border border-line bg-surface p-0 text-ink shadow-pop"
      aria-labelledby="dialog-title"
    >
      <div className="px-6 pt-6">
        <h2 id="dialog-title" className="text-base font-semibold">
          {title}
        </h2>
        {description && <div className="mt-1.5 text-sm text-ink-muted">{description}</div>}
      </div>
      {children && <div className="px-6 pt-4">{children}</div>}
      {footer && (
        <div className="mt-6 flex justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>
      )}
    </dialog>
  );
}
