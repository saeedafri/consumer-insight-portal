// The topic dashboards' names, in their own file so the left menu (components/Shell.tsx) and the tracker page
// (screens/Trackers.tsx) can list them without loading the page. The codes and what each shows: config/dashboards.yml;
// which weeks carry each: the waves list (Wave.dashboards). Trackers run every few weeks; sector dashboards ride the
// sector modules and also feed the Sector databank.
export const TRACKERS: [string, string][] = [
  ["tariffs_inflation", "Tariffs & inflation"], ["financial_health", "Financial health"], ["genai", "GenAI & AI shopping"],
  ["glp1", "GLP-1 impact"], ["mideast_gas", "Gas prices & geopolitics"], ["holiday_tracker", "Holiday shopping"],
  ["holiday_outlook", "Holiday outlook"], ["social_commerce", "Social commerce"],
];
export const SECTOR_DASHBOARDS: [string, string][] = [
  ["apparel", "Apparel"], ["beauty", "Beauty"], ["dept_stores", "Department stores"], ["drugstore", "Drugstore / pharmacy"],
  ["ecommerce", "eCommerce"], ["footwear", "Footwear"], ["home_furnishings", "Home furnishings"], ["home_improvement", "Home improvement / DIY"],
  ["luxury", "Luxury"], ["mass_warehouse", "Mass merchants / warehouse clubs"], ["off_price", "Off-price / dollar stores"],
];
