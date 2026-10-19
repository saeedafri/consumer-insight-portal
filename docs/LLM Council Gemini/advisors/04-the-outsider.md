# Advisor 4: The Outsider
## Enterprise Customer Perspective, Cognitive Friction & The Curse of Knowledge

**Perspective:** Naive client viewpoint, accessibility, UX cognitive load, and elimination of industry jargon.

---

I have never worked at Coresight, I have never written survey questionnaires, and I have no loyalty to your internal code. Looking at this project from the outside, the biggest risk to client adoption is that **you are suffering from an extreme case of the curse of knowledge**.

You have built a platform designed by survey statisticians, for survey statisticians. Look at the terminology all over your schemas, views, and screens:  
* `stub_key`, `bipolar grid`, `item_code q1r1`, `DP7r3`, `seg_letter A..N1`, `is_exclusive`, `net_group TOP2/BOT2`, `answer_base_n vs seg_base_n`.

If you put a VP of Merchandising at Target or a Brand Director at Nike in front of this UI, they will have no idea what they are looking at. They do not care about questionnaire column routing, bipolar grids, or whether a variable is marked "virtual."

When paying corporate clients log in, they want answers to three basic things:
1. **Search that speaks plain English:** They want to type *"Target vs Walmart beauty"* and instantly see a clean dashboard, not navigate through `DEPT_STORES` topics and pick question codes like `DP7`.
2. **Instant Executive Visualizations:** Clean, interactive trend lines that explain the key takeaway in plain language (*"Amazon gained +3.2% share in apparel this quarter"*).
3. **One-Click Presentation Exports:** A single button that exports a high-resolution PNG or a fully styled PowerPoint slide ready to drop into an executive meeting.

If your new React application just reproduces the complexity of your Streamlit screens with faster buttons, it will still fail with clients. Hide the survey plumbing. Build a consumer-grade experience on top of your enterprise-grade data.
