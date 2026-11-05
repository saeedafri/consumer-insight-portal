// The portal's own buttons (styles.css .btn, .btn.primary, .btn-chip) behind the Button name the screens use.
import type { ButtonHTMLAttributes } from "react";

type Look = { variant?: "default" | "outline" | "secondary" | "ghost" | "link" | "destructive"; size?: "default" | "sm" | "xs" | "lg" | "icon" | "icon-xs"; className?: string };

export function buttonVariants({ variant = "default", size, className = "" }: Look = {}): string {
  const base = size?.startsWith("icon") ? `icon-btn${size === "icon-xs" ? " icon-xs" : ""}`
    : size === "xs" || variant === "ghost" ? "btn-chip" : variant === "default" ? "btn primary" : "btn";
  return `${base} ${className}`.trim();
}

export function Button({ variant = "default", size, className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & Look) {
  return <button className={buttonVariants({ variant, size, className })} {...rest} />;
}
