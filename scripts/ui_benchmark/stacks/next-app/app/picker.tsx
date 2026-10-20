"use client";
import { useRouter } from "next/navigation";

export const SECTORS = ["Apparel", "Beauty", "Department", "Dollar", "Electronics", "Grocery", "Home", "Sporting"];

export default function Picker({ value, onPick }: { value: string; onPick?: (s: string) => void }) {
  const router = useRouter();
  return <select id="sector" value={value} onChange={e => onPick ? onPick(e.target.value) : router.push(`?sector=${e.target.value}`)}>
    {SECTORS.map(s => <option key={s}>{s}</option>)}
  </select>;
}
