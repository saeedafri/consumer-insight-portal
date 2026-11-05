// The portal's segmented control (styles.css .seg: a group of buttons, the chosen one aria-pressed) behind Tabs.
import { createContext, useContext } from "react";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

const Chosen = createContext<{ value: string; pick: (value: string) => void }>({ value: "", pick: () => {} });

export function Tabs({ value, onValueChange, children }: { value: string; onValueChange: (value: string) => void; children: ReactNode; className?: string }) {
  return <Chosen.Provider value={{ value, pick: onValueChange }}>{children}</Chosen.Provider>;
}

export function TabsList({ className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div role="group" className={`seg ${className}`.trim()} {...rest} />;
}

export function TabsTrigger({ value, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { value: string }) {
  const chosen = useContext(Chosen);
  return <button type="button" aria-pressed={chosen.value === value} onClick={() => chosen.pick(value)} {...rest} />;
}
