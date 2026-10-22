// The portal's text field (styles.css .field) behind the Input name the screens use.
import type { InputHTMLAttributes } from "react";

export function Input({ className = "", ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`field ${className}`.trim()} {...rest} />;
}
