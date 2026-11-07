// The Forsta admin screens' sections (screens/Forsta.tsx), in their own file so the left menu (components/Shell.tsx)
// can list them without loading the screen's code.
export const SECTIONS: [string, string, string][] = [   // [address, menu name, what the page says it is]
  ["reports", "Team reports", "The research team's saved reports in Forsta, run by Forsta itself, with the Excel, PDF and PowerPoint files Forsta exports."],
  ["check", "Forsta vs CIP", "Forsta's own cross-tab of every question, compared cell by cell with CIP's figures: proof that CIP counted every qualified respondent's answers exactly as Forsta does."],
  ["crosstab", "Cross-tab setup", "The banners the team built in Forsta (the columns of their cross-tabs), and the company's cross-tab defaults."],
  ["samples", "Sample & devices", "Each survey's funnel by sample source, operating system, browser and mobile device."],
  ["warnings", "Warnings & checks", "What Forsta flagged: blocked sessions, server errors and exceptions for every survey, and each survey's launch checks."],
  ["files", "Survey files", "The files each survey keeps in Forsta: the questionnaire, logs, data maps and assets."],
  ["deletion", "Archive & deletion", "When Forsta deletes each archived survey, what is scheduled, and the company's retention rule."],
  ["account", "Forsta account", "Forsta's categories, every API endpoint Forsta offers, and the surveys in Forsta that CIP has not loaded."],
];
