// The four views of one question are siblings, not actions: one tab strip under the question, shared by every view.
import { Link, useLocation } from "react-router";
import { allowed, useMe } from "../api";

// [path, label, the /me feature it needs (config/access.yml)]
const VIEWS = [["questions", "Chart", "explorer"], ["crosstab", "Cross-tab", "crosstab"], ["trends", "Trends", "trends"], ["compare", "Compare waves", "trends"]] as const;

export default function QuestionTabs({ id, q }: { id: number; q: string }) {
  const me = useMe().data;
  const here = useLocation().pathname.split("/")[3];
  return <nav className="qtabs" aria-label="Views of this question">
    {VIEWS.filter(([, , feature]) => allowed(me, feature)).map(([path, label]) =>
      <Link key={path} to={`/w/${id}/${path}/${encodeURIComponent(q)}`} aria-current={here === path ? "page" : undefined}>{label}</Link>)}
  </nav>;
}
