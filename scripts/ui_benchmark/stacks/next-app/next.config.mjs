// NEXT_OUTPUT=export → static files (served by FastAPI); otherwise a standalone Node server (SSR).
export default { basePath: "/app", output: process.env.NEXT_OUTPUT === "export" ? "export" : "standalone" };
