// The top line of every question screen (Question explorer, Cross-tab matrix, Trends): where you are (Overview ›
// section › Q3) and the previous / next question buttons with "3 of 58" between them. Each screen says where a
// question opens (`open`), the same way it does for the question list beside it (components/QuestionNav.tsx).
import { Link } from "react-router";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Question } from "../api";
import { QuestionCode } from "./bits";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export default function QuestionHeader({ waveId, question, questions, open }:
  { waveId: number | string; question: Question; questions: Question[]; open: (q: Question) => void }) {
  const at = questions.findIndex(x => x.id === question.id);
  const previous = at > 0 ? questions[at - 1] : null;
  const next = at >= 0 && at < questions.length - 1 ? questions[at + 1] : null;
  const step = (to: Question | null, label: string, edge: string, icon: React.ReactNode) =>
    <Tooltip>
      <TooltipTrigger render={
        <Button variant="outline" size="icon-xs" disabled={!to} onClick={() => to && open(to)} aria-label={`${label} question`}>{icon}</Button>} />
      <TooltipContent side="top">{to ? `${label}: ${to.number} (${to.short || to.text})` : edge}</TooltipContent>
    </Tooltip>;
  return <div className="qcrumbs" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
    <div className="breadcrumb">
      <Link to={`/w/${waveId}`}>Overview</Link>
      <span className="sep">›</span>
      <span>{question.section}</span>
      <span className="sep">›</span>
      <QuestionCode q={question} />
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      {step(previous, "Previous", "First question", <ChevronLeft size={14} />)}
      <span style={{ fontSize: 11.5, color: "var(--ink-2)", fontWeight: 600 }}>{at + 1} of {questions.length}</span>
      {step(next, "Next", "Last question", <ChevronRight size={14} />)}
    </div>
  </div>;
}
