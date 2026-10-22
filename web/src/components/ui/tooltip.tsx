// Hover help as the portal always showed it: the browser's own title on the element, no extra layer.
import { Children, cloneElement, Fragment, isValidElement } from "react";
import type { ReactElement, ReactNode } from "react";

const text = (node: ReactNode): string => Children.toArray(node).map(n => (typeof n === "string" || typeof n === "number" ? String(n)
  : isValidElement<{ children?: ReactNode }>(n) ? text(n.props.children) : "")).join("");

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <Fragment>{children}</Fragment>;
}

export function TooltipTrigger(_: { render?: ReactElement; children?: ReactNode; className?: string }) {
  return null;   // read by Tooltip
}

export function TooltipContent(_: { children?: ReactNode; side?: string; className?: string }) {
  return null;   // read by Tooltip
}

export function Tooltip({ children }: { children: ReactNode }) {
  const parts = Children.toArray(children).filter(isValidElement) as ReactElement<{ render?: ReactElement; children?: ReactNode }>[];
  const trigger = parts.find(p => p.type === TooltipTrigger), content = parts.find(p => p.type === TooltipContent);
  const title = content ? text(content.props.children) : undefined;
  const target = trigger?.props.render ?? trigger?.props.children;
  return isValidElement<{ title?: string }>(target) ? cloneElement(target, { title }) : <span title={title}>{target}</span>;
}
