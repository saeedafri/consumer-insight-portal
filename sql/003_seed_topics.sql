-- ═══════════════════════════════════════════════════════════════════════════
-- CSI report modules, from the 09/21/26 and 09/28/26 questionnaires. Safe to re-run.
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO cip_topic (topic_code, topic_name, is_technical, sort_order) VALUES
  ('SHOPPING',     'Shopping and Spending',          0, 10),
  ('DEPT_STORES',  'Department Stores',              0, 20),
  ('DIAMONDS',     'Diamonds and Fine Jewelry',      0, 30),
  ('BNPL',         'Buy Now, Pay Later',             0, 40),
  ('AI_GENAI',     'AI and GenAI Shopping',          0, 50),
  ('GLP1',         'GLP-1 Impact',                   0, 60),
  ('SENTIMENT',    'Consumer Sentiment',             0, 70),
  ('MACRO',        'Macro and Gas Prices',           0, 80),
  ('DEMOGRAPHICS', 'Demographics',                   0, 90),
  ('HOLIDAY_SHOPPING', 'Holiday Shopping Tracker',   0, 100),
  ('HOLIDAY_OUTLOOK',  'Holiday Spending Outlook',   0, 110),
  ('BEAUTY',           'Beauty',                     0, 120),
  ('TARIFFS',          'Tariffs',                    0, 130),
  ('INFLATION',        'Inflation and Prices',       0, 140),
  ('TECHNICAL',    'Paradata, Quotas and Technical', 1, 99)
ON DUPLICATE KEY UPDATE
  topic_name = VALUES(topic_name),
  is_technical = VALUES(is_technical),
  sort_order = VALUES(sort_order);
