-- ═══════════════════════════════════════════════════════════════════════════
-- CIP — seed report modules. Derived from the 09/21/26 questionnaire.
-- Safe to re-run.
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO cip_question_group (group_code, group_name, is_system, display_order) VALUES
  ('SHOPPING',     'Shopping and Spending',                 0, 10),
  ('DEPT_STORES',  'Department Stores',                     0, 20),
  ('DIAMONDS',     'Diamonds and Fine Jewelry',             0, 30),
  ('BNPL',         'Buy Now, Pay Later',                    0, 40),
  ('AI_GENAI',     'AI and GenAI Shopping',                 0, 50),
  ('GLP1',         'GLP-1 Impact',                          0, 60),
  ('SENTIMENT',    'Consumer Sentiment',                    0, 70),
  ('MACRO',        'Macro and Gas Prices',                  0, 80),
  ('DEMOGRAPHICS', 'Demographics',                          0, 90),
  ('PARADATA',     'Paradata, Quotas and Technical',        1, 99)
ON DUPLICATE KEY UPDATE
  group_name    = VALUES(group_name),
  is_system     = VALUES(is_system),
  display_order = VALUES(display_order);
