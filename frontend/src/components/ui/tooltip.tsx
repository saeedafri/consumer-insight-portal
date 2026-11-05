// Help that works by hover, keyboard and touch: a real tooltip element tied to its trigger (aria-describedby), shown
// while the trigger is hovered or focused (a tap focuses it), hidden again with Escape. Styles: styles.css .tip.
import { Children, cloneElement, Fragment, isValidElement, useId, useState } from "react";
import type { ReactElement, ReactNode } from "react";

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <Fragment>{children}</Fragment>;
}

export function TooltipTrigger(_: { render?: ReactElement; children?: ReactNode; className?: string }) {
  return null;   // read by Tooltip
}

export function TooltipContent(_: { children?: ReactNode; side?: string; className?: string }) {
  return null;   // read by Tooltip
}

const FOCUSABLE = /^(a|button|input|select|textarea|label)$/;

export function Tooltip({ children }: { children: ReactNode }) {
  const id = useId();
  const [quiet, setQuiet] = useState(false);
  const parts = Children.toArray(children).filter(isValidElement) as ReactElement<{ render?: ReactElement; children?: ReactNode; side?: string }>[];
  const trigger = parts.find(p => p.type === TooltipTrigger), content = parts.find(p => p.type === TooltipContent);
  const target = trigger?.props.render ?? trigger?.props.children;
  if (!content) return <>{target}</>;
  // components (Button) and native controls take focus already; a plain chip is made focusable so a tap or Tab shows it
  const focusable = isValidElement(target) && (typeof target.type !== "string" || FOCUSABLE.test(target.type));
  const shown = isValidElement<{ tabIndex?: number }>(target)
    ? cloneElement(target as ReactElement<Record<string, unknown>>, { "aria-describedby": id, ...(focusable ? {} : { tabIndex: 0 }) })
    : <span tabIndex={0} aria-describedby={id}>{target}</span>;
  return <span className={`tip-wrap${quiet ? " quiet" : ""}`} onKeyDown={e => { if (e.key === "Escape") setQuiet(true); }}
               onMouseLeave={() => setQuiet(false)} onBlur={() => setQuiet(false)}>
    {shown}
    <span role="tooltip" id={id} className={`tip ${content.props.side === "bottom" ? "bottom" : "top"}`}>{content.props.children}</span>
  </span>;
}
