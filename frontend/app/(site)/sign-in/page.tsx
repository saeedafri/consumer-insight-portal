import { Breadcrumbs } from "../seo";

export const metadata = {
  title: "Sign in",
  description: "Sign in to the Coresight Consumer Insight Portal with your work account.",
  alternates: { canonical: "/sign-in/" },
};

export default function SignIn() {
  return <section className="signin-box">
    <Breadcrumbs items={[["Home", "/"], ["Sign in", "/sign-in/"]]} />
    <h1>Sign in</h1>
    <p>Use your Coresight or client work account.</p>
    <a className="btn primary" href="/auth/login?next=/app/">Continue with your work account</a>
    <p className="small">No account yet? Ask your Coresight contact for access.</p>
  </section>;
}
