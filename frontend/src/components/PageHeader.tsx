import { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: ReactNode;
  backLink?: ReactNode;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  children,
  backLink,
}: PageHeaderProps) {
  return (
    <section className="flex items-start justify-between gap-7">
      <div>
        {backLink && <div className="mb-2">{backLink}</div>}
        {eyebrow && (
          <p className="m-0 text-slate-500 text-25 font-bold uppercase tracking-widest">
            {eyebrow}
          </p>
        )}
        <h1 className="m-0 my-1 text-slate-900 text-500 tracking-tight">
          {title}
        </h1>
        {description && (
          <p className="m-0 max-w-2xl text-slate-600 text-100">
            {description}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}
