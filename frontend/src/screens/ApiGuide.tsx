// The API guide (/app/api-guide): how anyone signed in uses the portal from their own programs (the API) and from
// Claude or another AI assistant (the MCP connector), with the rules a key follows. The same content as docs/API.md;
// tests/test_docs.py fails if a route or tool is missing from either. Linked from the Account page's "API keys and
// Claude" card (components/ApiKeys.tsx) and from What's new.
import { Link } from "react-router";
import { Card } from "../components/bits";

const RULES: [string, string][] = [
  ["API keys and MCP", "Only when \"API keys and MCP\" is on your menu: the super admin turns it on per role, client or person on the Access page. Without it the Account page has no keys card and every key you made is refused (403) until it is turned back on."],
  ["Your role, client and menus", "A key reads only what your left menu shows. The super admin chooses menus per role, per client and per person on the Access page; a person's choice beats their client's, which beats their role's."],
  ["Changes apply within a minute", "When a menu is taken away (a trial ends), your screens, your keys and the MCP connector lose it within a minute (most answers at once); no sign-out or refresh needed."],
  ["Surveys", "Only the surveys your organisation may see."],
  ["Rate limit", "The same per-minute limit as your sign-in; over it, the answer is 429 with Retry-After: 60."],
  ["Admin pages", "Never through a key while sign-in is the demo; otherwise only for admins, as in the portal."],
];
// [method and address, what it returns, needs on your menu]: the routes of docs/API.md section 3
const ROUTES: [string, string, string][] = [
  ["GET /api/v1/me", "You: email, role, client, features, permissions", "—"],
  ["GET /api/v1/waves", "Every wave you may open, newest first", "—"],
  ["GET /api/v1/waves/{survey_id}/book", "A whole wave: questions, answers and topic dashboards (the always-on Overview's data)", "—"],
  ["GET /api/v1/waves/{survey_id}/results", "Finished rows for questions × cuts, ?q=XM3,XM1&dim=total,generation", "Question explorer"],
  ["GET /api/v1/waves/{survey_id}/crosstab", "One question by two cuts, ?q=XM3&by=generation,gender&weeks=4", "Cross-tab matrix"],
  ["GET /api/v1/waves/{survey_id}/report", "The weekly US Consumer Survey Insights report of a tracker wave", "Weekly report"],
  ["GET /api/v1/waves/{survey_id}/logic", "When each question was shown, and the screen-out rules", "Survey preview"],
  ["GET /api/v1/questions/{family}/{study_type}/{qcode}", "One question across every wave and cut", "Trends, Compare waves or Audiences"],
  ["GET /api/v1/dashboards/{code}", "A topic dashboard for its latest wave", "Topic dashboards"],
  ["GET /api/v1/dashboards/{code}/{survey_id}", "A topic dashboard for one wave", "Topic dashboards"],
  ["GET /api/v1/search", "Questions by words, code, answer or survey, ?q=tariffs&limit=40", "Search questions"],
  ["GET /api/v1/sectors", "The sector databank: purchase rate, retailers, brands, categories", "Sector databank"],
  ["GET /api/v1/retailers", "Retailer comparison: each retailer's reach, its shoppers' gender, generation and income, and sentiment, over pooled weeks", "Retailer comparison"],
  ["GET /api/v1/expectations", "Retail events, expected vs actual", "Expected vs actual"],
  ["GET /api/v1/reports", "The waves that have a weekly report", "—"],
  ["GET /api/v1/schedule", "The launch plan against what Forsta fielded", "Launch schedule"],
  ["GET /api/v1/fieldwork", "Each survey's funnel and why respondents dropped out", "Fieldwork"],
  ["GET /api/v1/methodology", "How the figures are made", "—"],
  ["GET /api/v1/public/facts", "The home page's counts and dates (no key needed)", "—"],
  ["POST /api/v1/ask", "A question in plain words, {\"question\": \"…\"}: the answer in sentences, a chart, every figure and its base, the source and other matching questions; shares, counts, top answers, trends by wave, 2 weeks, 4 weeks, month, quarter or year, comparisons and cuts, from the surveys only", "Ask CIP"],
  ["POST /api/v1/export/{kind}", "A screen's table as CSV, Excel or PowerPoint", "Export"],
  ["GET /api/v1/keys", "Your keys (name, first characters, date)", "— (portal sign-in)"],
  ["POST /api/v1/keys", "Make a key, {\"name\": \"…\"}", "— (portal sign-in)"],
  ["DELETE /api/v1/keys/{shown}", "Revoke one of your keys", "— (portal sign-in)"],
];
// [method and address, what it does, needs on your menu]: docs/API.md "Your team's items" (api/team.py)
const TEAM: [string, string, string][] = [
  ["GET /api/v1/team/summary", "Your boards, saved views, alerts and audiences in one answer", "—"],
  ["GET /api/v1/team/views", "Saved views shared with your team", "Saved views"],
  ["POST /api/v1/team/views", "Save a view for your team", "Saved views"],
  ["DELETE /api/v1/team/views/{view_id}", "Remove a saved view you made", "Saved views"],
  ["GET /api/v1/alerts", "Your team's alerts", "Alerts"],
  ["POST /api/v1/alerts", "Watch an answer for a significant change", "Alerts"],
  ["DELETE /api/v1/alerts/{alert_id}", "Remove an alert you made", "Alerts"],
  ["GET /api/v1/audiences", "Your team's saved audiences", "Audiences"],
  ["POST /api/v1/audiences", "Save an audience (who answered what)", "Audiences"],
  ["DELETE /api/v1/audiences/{audience_id}", "Remove an audience you made", "Audiences"],
  ["POST /api/v1/waves/{survey_id}/audience", "One question for an audience against everyone", "Audiences"],
  ["POST /api/v1/waves/{survey_id}/audience/profile", "What sets an audience apart in a wave", "Audiences"],
  ["GET /api/v1/boards", "Your team's boards", "Boards"],
  ["POST /api/v1/boards", "Make a board", "Boards"],
  ["GET /api/v1/boards/{board_id}", "A board with its pinned tables and comments", "Boards"],
  ["DELETE /api/v1/boards/{board_id}", "Remove a board you made", "Boards"],
  ["GET /api/v1/boards/{board_id}/deck", "The board as one branded PowerPoint", "Boards"],
  ["POST /api/v1/boards/{board_id}/items", "Pin a screen's table to a board", "Boards"],
  ["DELETE /api/v1/boards/items/{item_id}", "Unpin a table", "Boards"],
  ["POST /api/v1/boards/items/{item_id}/comments", "Comment on a pinned table", "Boards"],
  ["DELETE /api/v1/boards/comments/{comment_id}", "Remove a comment you made", "Boards"],
];
// [tool, what it does, needs on your menu]: the tools of docs/API.md section 4 (api/mcp.py TOOLS)
const TOOLS: [string, string, string][] = [
  ["search_questions", "Find questions by topic, words, brand or code; plain English works", "Search questions"],
  ["list_waves", "Survey waves, newest first, optionally of one family (e.g. CSI-US)", "—"],
  ["question_results", "One question in one wave: each answer's % for Total, gender and generation, the prior week and last year, and significance", "Question explorer"],
  ["question_trend", "One question over the last waves of its family", "Trends"],
  ["crosstab", "One question by two demographic cuts", "Cross-tab matrix"],
];

const Table = ({ head, rows, code }: { head: string[]; rows: string[][]; code?: boolean }) =>
  <div className="table-wrap"><table className="data">
    <thead><tr>{head.map(h => <th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.map(r => <tr key={r[0]}>{r.map((c, i) => i === 0 ? <th key={i} scope="row">{code ? <code>{c}</code> : c}</th> : <td key={i}>{c}</td>)}</tr>)}</tbody>
  </table></div>;

export default function ApiGuide() {
  const portal = location.origin;
  return <div className="stack" style={{ maxWidth: 1000 }}>
    <div className="page-head"><div><h1>API and Claude</h1>
      <p className="lede">Read the portal's data from your own programs (the API) and from Claude or any AI assistant that supports MCP connectors. Both act as you: they see exactly what your menus show, no more, at the moment of each request.</p></div></div>
    <Card title="1. Make a key">
      <ol className="guide-steps">
        <li>Open <Link to="/account">Account</Link> → <b>API keys and MCP</b>.</li>
        <li>Type a name for the key (the tool it is for, such as "My Claude") and press <b>Make a key</b>.</li>
        <li>Copy the key now: it starts with <code>cip_</code> and is shown once. CIP keeps only its fingerprint.</li>
      </ol>
      <p className="muted small">Up to 10 keys; revoke any of them on the same card and it stops at once. A key cannot make or revoke keys: that needs your signed-in portal session.</p>
    </Card>
    <Card title="2. What a key may read: the same rules everywhere"><Table head={["Rule", "What it means for a key"]} rows={RULES} /></Card>
    <Card title="3. The API" sub={`Send the key as Authorization: Bearer cip_… to ${portal}/api/v1/…; the machine-readable description is at /api/v1/openapi.json.`}>
      <pre className="guide-code">{`curl -H "Authorization: Bearer cip_…" "${portal}/api/v1/waves"
curl -H "Authorization: Bearer cip_…" "${portal}/api/v1/search?q=holiday%20shopping"
curl -H "Authorization: Bearer cip_…" "${portal}/api/v1/waves/532/results?q=q4&dim=total,generation"`}</pre>
      <Table head={["Method and address", "What it returns", "Needs on your menu"]} rows={ROUTES} code />
      <h3 className="details-head">Your team's items</h3>
      <p className="small">The same boards, saved views, alerts and audiences as on the screens; you can remove only what you made.</p>
      <Table head={["Method and address", "What it does", "Needs on your menu"]} rows={TEAM} code />
      <p className="muted small">Question codes may be written in any case (XM3 or xm3). Answers are JSON. Errors are {"{\"detail\": \"…\", \"status\": n}"}: 401 no or revoked key, 403 not on your menu or a survey you may not see, 404 not found, 429 too many requests, 503 busy (retry after Retry-After seconds).</p>
    </Card>
    <Card title="4. The MCP connector (Claude and other AI assistants)" sub={`Address ${portal}/mcp (MCP streamable HTTP, protocol 2025-06-18), with the same Authorization header.`}>
      <pre className="guide-code">{`claude mcp add --transport http cip ${portal}/mcp --header "Authorization: Bearer cip_…"`}</pre>
      <p className="small">Claude Desktop or claude.ai: Settings → Connectors → Add custom connector, address {portal}/mcp, header Authorization: Bearer cip_….</p>
      <Table head={["Tool", "What it does", "Needs on your menu"]} rows={TOOLS} code />
      <p className="muted small">A tool your menus do not include answers with an error the assistant can read. Figures are unweighted percentages of qualified respondents unless a tool says otherwise; cite the survey, wave date and base (n).</p>
    </Card>
  </div>;
}
