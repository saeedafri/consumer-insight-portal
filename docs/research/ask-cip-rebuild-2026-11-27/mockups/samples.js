// Written by build_samples.py from the published files of 27 Nov 2026. Do not edit by hand: run the script again.
window.SAMPLES = [
 {
  "id": "s1",
  "level": "Easy",
  "type": "T1 Latest value",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "Did people buy beauty products recently?",
  "headline": "In the latest survey (28 Sep 2026), <em>65.5%</em> of US adults said they bought beauty products in the past three months, about the same as on 6 Jul 2026 (63.6%).",
  "cards": [
   {
    "label": "Latest survey",
    "value": "65.5%",
    "note": "28 Sep 2026",
    "tone": "main"
   },
   {
    "label": "Since 6 Jul 2026",
    "value": "About the same",
    "note": "From 63.6%",
    "tone": "same"
   },
   {
    "label": "Said no",
    "value": "34.5%",
    "note": "28 Sep 2026",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "columns",
   "title": "Bought beauty products in the past three months",
   "unit": "% of US adults, 28 Sep 2026",
   "bars": [
    {
     "label": "Yes",
     "pct": 65.5
    },
    {
     "label": "No",
     "pct": 34.5
    }
   ],
   "foot": [
    "Shares of everyone asked add up to 100%."
   ]
  },
  "evidence": {
   "wording": [
    "Have you purchased any beauty products (whether for men or women) in the past three months?"
   ],
   "source": "Coresight US Consumer Survey, 28 Sep 2026",
   "table": {
    "head": [
     "Survey date",
     "Yes",
     "No"
    ],
    "rows": [
     [
      "28 Sep 2026",
      "65.5%",
      "34.5%"
     ],
     [
      "6 Jul 2026",
      "63.6%",
      "36.4%"
     ]
    ]
   }
  },
  "alternatives": [
   "Which beauty products people bought (Coresight US Consumer Survey, last asked 28 Sep 2026)",
   "Types of beauty products bought (Coresight US Consumer Survey, last asked 28 Sep 2026)"
  ],
  "chips": [
   {
    "label": "Over time",
    "goto": "s2"
   },
   {
    "label": "By generation",
    "goto": "s3"
   },
   {
    "label": "By household income",
    "goto": "s4"
   },
   {
    "label": "Where people buy them",
    "goto": "s5"
   }
  ]
 },
 {
  "id": "s2",
  "level": "Easy",
  "type": "T2 Trend over time",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "How have beauty purchases changed over time?",
  "headline": "In the latest survey (28 Sep 2026), <em>65.5%</em> of US adults said they bought beauty products in the past three months, about the same as in September 2022 (68.9%). The share has stayed between 62.5% and 65.5% during 2026.",
  "cards": [
   {
    "label": "Latest survey",
    "value": "65.5%",
    "note": "28 Sep 2026",
    "tone": "main"
   },
   {
    "label": "Since Sep 2022",
    "value": "About the same",
    "note": "From 68.9%",
    "tone": "same"
   },
   {
    "label": "During 2026",
    "value": "Steady",
    "note": "Between 62.5% and 65.5%",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "line",
   "title": "Bought beauty products in the past three months",
   "unit": "% of US adults in each survey",
   "cadence": "quarterly",
   "grains": [
    "Quarterly",
    "Yearly"
   ],
   "ranges": [
    "Last 12 months",
    "Since 2022"
   ],
   "default_range": 1,
   "series": [
    {
     "name": "Bought beauty products",
     "points": [
      {
       "date": "2022-09-05",
       "n": 288,
       "b": 418
      },
      {
       "date": "2022-11-28",
       "n": 300,
       "b": 409
      },
      {
       "date": "2023-02-20",
       "n": 301,
       "b": 411
      },
      {
       "date": "2023-07-24",
       "n": 309,
       "b": 409
      },
      {
       "date": "2023-10-09",
       "n": 299,
       "b": 414
      },
      {
       "date": "2023-12-26",
       "n": 343,
       "b": 543
      },
      {
       "date": "2024-03-11",
       "n": 320,
       "b": 415
      },
      {
       "date": "2024-06-03",
       "n": 151,
       "b": 264
      },
      {
       "date": "2024-08-26",
       "n": 290,
       "b": 405
      },
      {
       "date": "2024-11-25",
       "n": 274,
       "b": 402
      },
      {
       "date": "2025-02-17",
       "n": 278,
       "b": 406
      },
      {
       "date": "2025-05-12",
       "n": 283,
       "b": 405
      },
      {
       "date": "2025-08-04",
       "n": 300,
       "b": 403
      },
      {
       "date": "2025-10-27",
       "n": 275,
       "b": 402
      },
      {
       "date": "2026-01-19",
       "n": 250,
       "b": 400
      },
      {
       "date": "2026-04-13",
       "n": 257,
       "b": 402
      },
      {
       "date": "2026-07-06",
       "n": 255,
       "b": 401
      },
      {
       "date": "2026-09-28",
       "n": 264,
       "b": 403
      }
     ]
    }
   ],
   "unusual": [
    {
     "date": "2024-06-03",
     "label": "Unusual low: 57.2% (Jun 2024)"
    }
   ],
   "foot": [
    "Each dot is one survey.",
    "Dashed lines join surveys more than four months apart.",
    "One reading is far from the others, so treat it with care."
   ]
  },
  "evidence": {
   "wording": [
    "Have you purchased any beauty products (whether for men or women) in the past three months?"
   ],
   "source": "Coresight US Consumer Survey, 5 Sep 2022 to 28 Sep 2026",
   "table": {
    "head": [
     "Survey date",
     "Yes",
     "No"
    ],
    "rows": [
     [
      "28 Sep 2026",
      "65.5%",
      "34.5%"
     ],
     [
      "6 Jul 2026",
      "63.6%",
      "36.4%"
     ],
     [
      "13 Apr 2026",
      "63.9%",
      "36.1%"
     ],
     [
      "19 Jan 2026",
      "62.5%",
      "37.5%"
     ],
     [
      "27 Oct 2025",
      "68.4%",
      "31.6%"
     ],
     [
      "4 Aug 2025",
      "74.4%",
      "25.6%"
     ],
     [
      "12 May 2025",
      "69.9%",
      "30.1%"
     ],
     [
      "17 Feb 2025",
      "68.5%",
      "31.5%"
     ],
     [
      "25 Nov 2024",
      "68.2%",
      "31.8%"
     ],
     [
      "26 Aug 2024",
      "71.6%",
      "28.4%"
     ],
     [
      "3 Jun 2024",
      "57.2%",
      "42.8%"
     ],
     [
      "11 Mar 2024",
      "77.1%",
      "22.9%"
     ],
     [
      "26 Dec 2023",
      "63.2%",
      "36.8%"
     ],
     [
      "9 Oct 2023",
      "72.2%",
      "27.8%"
     ],
     [
      "24 Jul 2023",
      "75.6%",
      "24.4%"
     ],
     [
      "20 Feb 2023",
      "73.2%",
      "26.8%"
     ],
     [
      "28 Nov 2022",
      "73.3%",
      "26.7%"
     ],
     [
      "5 Sep 2022",
      "68.9%",
      "31.1%"
     ]
    ]
   }
  },
  "alternatives": [],
  "chips": [
   {
    "label": "By generation",
    "goto": "s3"
   },
   {
    "label": "By household income",
    "goto": "s4"
   },
   {
    "label": "Where people buy them",
    "goto": "s5"
   },
   {
    "label": "How much people spend",
    "goto": "s6"
   },
   {
    "label": "Sep 2022 vs latest"
   }
  ]
 },
 {
  "id": "s3",
  "level": "Easy",
  "type": "T3 Compare groups",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "Which generation buys the most beauty products?",
  "headline": "In the latest survey (28 Sep 2026), Gen Z, Millennials and Gen X were about equally likely to have bought beauty products in the past three months (<em>70.5% to 72.4%</em>); Boomers were the least likely (51.2%).",
  "cards": [
   {
    "label": "Highest",
    "value": "72.4%",
    "tone": "main",
    "note": "Gen X; about the same as Gen Z and Millennials"
   },
   {
    "label": "Lowest",
    "value": "51.2%",
    "note": "Boomers",
    "tone": ""
   },
   {
    "label": "Difference",
    "value": "21.2 pts",
    "note": "A real gap",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "columns",
   "title": "Bought beauty products in the past three months, by generation",
   "unit": "% of each generation, US, 28 Sep 2026",
   "ranges": [
    "Latest survey"
   ],
   "bars": [
    {
     "label": "Gen Z",
     "pct": 70.5,
     "small": false
    },
    {
     "label": "Millennials",
     "pct": 72.1,
     "small": false
    },
    {
     "label": "Gen X",
     "pct": 72.4,
     "small": false
    },
    {
     "label": "Boomers",
     "pct": 51.2,
     "small": false
    }
   ],
   "foot": [
    "Generations whose gap to the highest could be chance are named together."
   ]
  },
  "evidence": {
   "wording": [
    "Have you purchased any beauty products (whether for men or women) in the past three months?"
   ],
   "source": "Coresight US Consumer Survey, 28 Sep 2026",
   "table": {
    "head": [
     "Generation",
     "Yes"
    ],
    "rows": [
     [
      "Gen Z",
      "70.5%"
     ],
     [
      "Millennials",
      "72.1%"
     ],
     [
      "Gen X",
      "72.4%"
     ],
     [
      "Boomers",
      "51.2%"
     ]
    ]
   }
  },
  "alternatives": [],
  "chips": [
   {
    "label": "By household income",
    "goto": "s4"
   },
   {
    "label": "By gender"
   },
   {
    "label": "By age group"
   },
   {
    "label": "Over time by generation"
   }
  ]
 },
 {
  "id": "s4",
  "level": "Hard",
  "type": "T14 Follow-up (by income)",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "previous": "s3",
  "question": "And by household income?",
  "read_as": "Beauty purchases by household income, latest survey (28 Sep 2026)",
  "headline": "In the latest survey (28 Sep 2026), US adults in households earning $50k-$99k and $100k+ were about equally likely to have bought beauty products in the past three months (<em>72.5% to 76.8%</em>); US adults in households earning under $50k were the least likely (57.1%).",
  "cards": [
   {
    "label": "Highest",
    "value": "76.8%",
    "tone": "main",
    "note": "Household income $100k+; about the same as $50k-$99k"
   },
   {
    "label": "Lowest",
    "value": "57.1%",
    "note": "Household income Under $50k",
    "tone": ""
   },
   {
    "label": "Difference",
    "value": "19.7 pts",
    "note": "A real gap",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "columns",
   "title": "Bought beauty products in the past three months, by household income",
   "unit": "% of each income group, US, 28 Sep 2026",
   "ranges": [
    "Latest survey"
   ],
   "bars": [
    {
     "label": "Under $50k",
     "pct": 57.1,
     "small": false
    },
    {
     "label": "$50k-$99k",
     "pct": 72.5,
     "small": false
    },
    {
     "label": "$100k+",
     "pct": 76.8,
     "small": false
    }
   ],
   "foot": [
    "People who preferred not to give their income are left out."
   ]
  },
  "evidence": {
   "wording": [
    "Have you purchased any beauty products (whether for men or women) in the past three months?"
   ],
   "source": "Coresight US Consumer Survey, 28 Sep 2026",
   "table": {
    "head": [
     "Household income",
     "Yes"
    ],
    "rows": [
     [
      "Under $50k",
      "57.1%"
     ],
     [
      "$50k-$99k",
      "72.5%"
     ],
     [
      "$100k+",
      "76.8%"
     ]
    ]
   }
  },
  "alternatives": [],
  "chips": [
   {
    "label": "By generation",
    "goto": "s3"
   },
   {
    "label": "By gender"
   },
   {
    "label": "How much people spend",
    "goto": "s6"
   }
  ]
 },
 {
  "id": "s5",
  "level": "Hard",
  "type": "T4 Ranked answers (long list)",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "Where do people buy beauty products?",
  "headline": "Walmart was the most common place: <em>42.8%</em> of US adults bought beauty products there in the past three months, in the latest survey (28 Sep 2026), ahead of Amazon.com (32.2%) and Bath & Body Works (16.7%).",
  "cards": [
   {
    "label": "Top answer",
    "value": "42.8%",
    "note": "Walmart",
    "tone": "main"
   },
   {
    "label": "Second",
    "value": "32.2%",
    "note": "Amazon.com",
    "tone": ""
   },
   {
    "label": "Gap between them",
    "value": "10.6 pts",
    "note": "A real gap",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "both-bars",
   "title": "Where people bought beauty products in the past three months (top 10)",
   "unit": "% of US adults, 28 Sep 2026",
   "bars": [
    {
     "label": "Walmart",
     "pct": 42.8
    },
    {
     "label": "Amazon.com",
     "pct": 32.2
    },
    {
     "label": "Bath & Body Works",
     "pct": 16.7
    },
    {
     "label": "Walgreens",
     "pct": 14.0
    },
    {
     "label": "Sephora (excluding at Kohl's)",
     "pct": 12.5
    },
    {
     "label": "Dollar store retailer",
     "pct": 12.5
    },
    {
     "label": "CVS",
     "pct": 12.1
    },
    {
     "label": "Target (excluding Ulta at Target)",
     "pct": 11.0
    },
    {
     "label": "TikTok",
     "pct": 11.0
    },
    {
     "label": "Supermarket/grocery store",
     "pct": 11.0
    }
   ],
   "foot": [
    "People could choose more than one, so shares add up to more than 100%.",
    "Mock-up only: the same list drawn as vertical bars (the meeting's choice) and horizontal bars (easier to read for long names). The manager picks one."
   ]
  },
  "evidence": {
   "wording": [
    "Which, if any, of the following retailers or platforms have you purchased beauty products from in the past three months (whether in-store or online)?"
   ],
   "source": "Coresight US Consumer Survey, 28 Sep 2026",
   "table": {
    "head": [
     "Retailer or platform",
     "Share"
    ],
    "rows": [
     [
      "Walmart",
      "42.8%"
     ],
     [
      "Amazon.com",
      "32.2%"
     ],
     [
      "Bath & Body Works",
      "16.7%"
     ],
     [
      "Walgreens",
      "14.0%"
     ],
     [
      "Sephora (excluding at Kohl's)",
      "12.5%"
     ],
     [
      "Dollar store retailer",
      "12.5%"
     ],
     [
      "CVS",
      "12.1%"
     ],
     [
      "Target (excluding Ulta at Target)",
      "11.0%"
     ],
     [
      "TikTok",
      "11.0%"
     ],
     [
      "Supermarket/grocery store",
      "11.0%"
     ],
     [
      "Ulta (excluding Ulta at Target)",
      "10.2%"
     ],
     [
      "Ulta at Target",
      "9.8%"
     ],
     [
      "YouTube",
      "9.8%"
     ],
     [
      "Instagram",
      "8.7%"
     ],
     [
      "Macy's",
      "8.7%"
     ],
     [
      "Warehouse club (Costco, Sam's Club, BJ's)",
      "8.7%"
     ],
     [
      "A brand's own website",
      "7.2%"
     ],
     [
      "Sephora at Kohl's",
      "6.8%"
     ],
     [
      "Sally Beauty",
      "6.4%"
     ],
     [
      "Nordstrom",
      "5.7%"
     ],
     [
      "Kohl's (excluding Sephora at Kohl's)",
      "4.5%"
     ],
     [
      "Salon",
      "3.8%"
     ],
     [
      "An influencer's livestream (video shopping online)",
      "3.4%"
     ],
     [
      "A brand's livestream (video shopping online)",
      "2.7%"
     ],
     [
      "Bluemercury",
      "1.9%"
     ],
     [
      "Subscription beauty box company",
      "0.4%"
     ]
    ]
   }
  },
  "alternatives": [
   "How people feel about each place they bought beauty products (Coresight US Consumer Survey, last asked 28 Sep 2026)"
  ],
  "chips": [
   {
    "label": "Walmart over time"
   },
   {
    "label": "By generation"
   },
   {
    "label": "How much people spend",
    "goto": "s6"
   }
  ]
 },
 {
  "id": "s6",
  "level": "Hard",
  "type": "T8 Amounts in ranges",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "How much do people spend on beauty products?",
  "headline": "In the latest survey (28 Sep 2026), the middle answer among US adults was <em>$51 - $75</em> spent on beauty products in the past three months; the average was about $84 (worked out from the ranges people chose).",
  "cards": [
   {
    "label": "Middle answer",
    "value": "$51 - $75",
    "note": "Half spent less, half more",
    "tone": "main"
   },
   {
    "label": "Average (estimate)",
    "value": "$84",
    "note": "From the ranges people chose",
    "tone": ""
   },
   {
    "label": "Most chosen range",
    "value": "19.3%",
    "note": "$26 - $50",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "columns",
   "title": "Spent on beauty products in the past three months",
   "unit": "% of US adults, 28 Sep 2026",
   "bars": [
    {
     "label": "Less than $10",
     "pct": 6.8
    },
    {
     "label": "$10 - $25",
     "pct": 15.5
    },
    {
     "label": "$26 - $50",
     "pct": 19.3
    },
    {
     "label": "$51 - $75",
     "pct": 18.6
    },
    {
     "label": "$76 - $99",
     "pct": 11.4
    },
    {
     "label": "$100 - $199",
     "pct": 15.5
    },
    {
     "label": "$200 - $299",
     "pct": 5.3
    },
    {
     "label": "$300 or more",
     "pct": 4.2
    }
   ],
   "foot": [
    "Spending was asked in ranges, so the average is an estimate; the top range counts at its lower end.",
    "Ranges are shown in their own order, never ranked."
   ]
  },
  "evidence": {
   "wording": [
    "How much did you spend on beauty products in the past three months?"
   ],
   "source": "Coresight US Consumer Survey, 28 Sep 2026",
   "table": {
    "head": [
     "Amount",
     "Share"
    ],
    "rows": [
     [
      "Less than $10",
      "6.8%"
     ],
     [
      "$10 - $25",
      "15.5%"
     ],
     [
      "$26 - $50",
      "19.3%"
     ],
     [
      "$51 - $75",
      "18.6%"
     ],
     [
      "$76 - $99",
      "11.4%"
     ],
     [
      "$100 - $199",
      "15.5%"
     ],
     [
      "$200 - $299",
      "5.3%"
     ],
     [
      "$300 or more",
      "4.2%"
     ],
     [
      "Don't know/cannot remember",
      "3.4%"
     ]
    ]
   }
  },
  "alternatives": [],
  "chips": [
   {
    "label": "By household income"
   },
   {
    "label": "Over time"
   },
   {
    "label": "By generation"
   }
  ]
 },
 {
  "id": "s7",
  "level": "Hard",
  "type": "T2 + T11 Monthly trend of a scale",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "Do people think tariffs are hurting them?",
  "headline": "In the latest survey (23 Nov 2026), <em>50.7%</em> of US adults said tariffs have a negative impact on them personally, about the same as in September 2025 (53.0%). During 2026 the share has gone up and down between 43.7% and 60.3%; 20.3% now say tariffs help them.",
  "cards": [
   {
    "label": "Latest survey",
    "value": "50.7%",
    "note": "Negative impact, 23 Nov 2026",
    "tone": "main"
   },
   {
    "label": "Since Sep 2025",
    "value": "About the same",
    "note": "From 53.0%",
    "tone": "same"
   },
   {
    "label": "During 2026",
    "value": "Up and down",
    "note": "Between 43.7% and 60.3%",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "line",
   "title": "Say tariffs have a negative or positive impact on them personally",
   "unit": "% of US adults in each survey",
   "cadence": "monthly",
   "grains": [
    "Monthly",
    "Quarterly",
    "Yearly"
   ],
   "ranges": [
    "Last 12 months",
    "Since 2025"
   ],
   "default_range": 0,
   "series": [
    {
     "name": "Negative impact",
     "points": [
      {
       "date": "2025-09-01",
       "n": 214,
       "b": 404
      },
      {
       "date": "2025-09-29",
       "n": 174,
       "b": 405
      },
      {
       "date": "2025-10-27",
       "n": 212,
       "b": 402
      },
      {
       "date": "2025-11-24",
       "n": 201,
       "b": 401
      },
      {
       "date": "2025-12-22",
       "n": 207,
       "b": 401
      },
      {
       "date": "2026-01-19",
       "n": 185,
       "b": 400
      },
      {
       "date": "2026-02-16",
       "n": 188,
       "b": 402
      },
      {
       "date": "2026-03-16",
       "n": 224,
       "b": 402
      },
      {
       "date": "2026-04-13",
       "n": 207,
       "b": 402
      },
      {
       "date": "2026-05-11",
       "n": 225,
       "b": 401
      },
      {
       "date": "2026-06-08",
       "n": 210,
       "b": 404
      },
      {
       "date": "2026-07-06",
       "n": 193,
       "b": 401
      },
      {
       "date": "2026-08-03",
       "n": 195,
       "b": 401
      },
      {
       "date": "2026-08-31",
       "n": 242,
       "b": 401
      },
      {
       "date": "2026-09-28",
       "n": 176,
       "b": 403
      },
      {
       "date": "2026-11-23",
       "n": 205,
       "b": 404
      }
     ]
    },
    {
     "name": "Positive impact",
     "points": [
      {
       "date": "2025-09-01",
       "n": 56,
       "b": 404
      },
      {
       "date": "2025-09-29",
       "n": 86,
       "b": 405
      },
      {
       "date": "2025-10-27",
       "n": 52,
       "b": 402
      },
      {
       "date": "2025-11-24",
       "n": 56,
       "b": 401
      },
      {
       "date": "2025-12-22",
       "n": 61,
       "b": 401
      },
      {
       "date": "2026-01-19",
       "n": 57,
       "b": 400
      },
      {
       "date": "2026-02-16",
       "n": 65,
       "b": 402
      },
      {
       "date": "2026-03-16",
       "n": 67,
       "b": 402
      },
      {
       "date": "2026-04-13",
       "n": 60,
       "b": 402
      },
      {
       "date": "2026-05-11",
       "n": 41,
       "b": 401
      },
      {
       "date": "2026-06-08",
       "n": 60,
       "b": 404
      },
      {
       "date": "2026-07-06",
       "n": 66,
       "b": 401
      },
      {
       "date": "2026-08-03",
       "n": 50,
       "b": 401
      },
      {
       "date": "2026-08-31",
       "n": 38,
       "b": 401
      },
      {
       "date": "2026-09-28",
       "n": 70,
       "b": 403
      },
      {
       "date": "2026-11-23",
       "n": 82,
       "b": 404
      }
     ]
    }
   ],
   "unusual": [],
   "foot": [
    "Negative: very or somewhat negative. Positive: very or somewhat positive.",
    "Quarterly and yearly views add up everyone asked in that period's surveys."
   ]
  },
  "evidence": {
   "wording": [
    "What impact, if any, do you think tariffs have on you personally?"
   ],
   "source": "Coresight US Consumer Survey, 1 Sep 2025 to 23 Nov 2026",
   "table": {
    "head": [
     "Survey date",
     "Negative",
     "Positive"
    ],
    "rows": [
     [
      "23 Nov 2026",
      "50.7%",
      "20.3%"
     ],
     [
      "28 Sep 2026",
      "43.7%",
      "17.4%"
     ],
     [
      "31 Aug 2026",
      "60.3%",
      "9.5%"
     ],
     [
      "3 Aug 2026",
      "48.6%",
      "12.5%"
     ],
     [
      "6 Jul 2026",
      "48.1%",
      "16.5%"
     ],
     [
      "8 Jun 2026",
      "52.0%",
      "14.9%"
     ],
     [
      "11 May 2026",
      "56.1%",
      "10.2%"
     ],
     [
      "13 Apr 2026",
      "51.5%",
      "14.9%"
     ],
     [
      "16 Mar 2026",
      "55.7%",
      "16.7%"
     ],
     [
      "16 Feb 2026",
      "46.8%",
      "16.2%"
     ],
     [
      "19 Jan 2026",
      "46.2%",
      "14.2%"
     ],
     [
      "22 Dec 2025",
      "51.6%",
      "15.2%"
     ],
     [
      "24 Nov 2025",
      "50.1%",
      "14.0%"
     ],
     [
      "27 Oct 2025",
      "52.7%",
      "12.9%"
     ],
     [
      "29 Sep 2025",
      "43.0%",
      "21.2%"
     ],
     [
      "1 Sep 2025",
      "53.0%",
      "13.9%"
     ]
    ]
   }
  },
  "alternatives": [
   "Impact of tariffs on the US economy (Coresight US Consumer Survey, last asked 23 Nov 2026)"
  ],
  "chips": [
   {
    "label": "By household income"
   },
   {
    "label": "By generation"
   },
   {
    "label": "Did people change how they shop?",
    "goto": "s13"
   },
   {
    "label": "Impact on the economy"
   }
  ]
 },
 {
  "id": "s8",
  "level": "Complex",
  "type": "T13 Both markets: ask back",
  "market": "both",
  "question": "What do consumers expect for the economy over the next year?",
  "ask_back": {
   "text": "Both the US and China surveys ask this. Which results do you want?",
   "choices": [
    {
     "label": "US results (latest 23 Nov 2026)",
     "market": "US"
    },
    {
     "label": "China results (latest 9 Nov 2026)",
     "market": "CN"
    }
   ]
  },
  "answers": {
   "US": {
    "survey": "Coresight US Consumer Survey",
    "headline": "More US adults expect the economy to get worse over the next 12 months (<em>38.4%</em>) than better (27.5%), in the latest survey (23 Nov 2026).",
    "cards": [
     {
      "label": "Expect worse",
      "value": "38.4%",
      "note": "Much or somewhat worse",
      "tone": "main"
     },
     {
      "label": "Expect better",
      "value": "27.5%",
      "note": "Much or somewhat better",
      "tone": ""
     },
     {
      "label": "Net",
      "value": "-10.9 pts",
      "note": "Better minus worse",
      "tone": ""
     }
    ],
    "chart": {
     "kind": "columns",
     "title": "Expectations for the economy over the next 12 months",
     "unit": "% of US adults, 23 Nov 2026",
     "bars": [
      {
       "label": "Much better",
       "pct": 7.9,
       "side": "pos"
      },
      {
       "label": "Somewhat better",
       "pct": 19.6,
       "side": "pos"
      },
      {
       "label": "About the same",
       "pct": 26.0,
       "side": ""
      },
      {
       "label": "Somewhat worse",
       "pct": 22.8,
       "side": "neg"
      },
      {
       "label": "Much worse",
       "pct": 15.6,
       "side": "neg"
      },
      {
       "label": "Don't know / not sure",
       "pct": 8.2,
       "side": ""
      }
     ],
     "foot": [
      "Answers in the survey's own order; the better side and the worse side are shaded."
     ]
    },
    "evidence": {
     "wording": [
      "And thinking about the economy overall over the next 12 months, do you think things will be better or worse?"
     ],
     "source": "Coresight US Consumer Survey, 23 Nov 2026",
     "table": {
      "head": [
       "Answer",
       "Share"
      ],
      "rows": [
       [
        "Much better",
        "7.9%"
       ],
       [
        "Somewhat better",
        "19.6%"
       ],
       [
        "About the same",
        "26.0%"
       ],
       [
        "Somewhat worse",
        "22.8%"
       ],
       [
        "Much worse",
        "15.6%"
       ],
       [
        "Don't know / not sure",
        "8.2%"
       ]
      ]
     }
    },
    "chips": [
     {
      "label": "Over time"
     },
     {
      "label": "By generation"
     },
     {
      "label": "Same in China",
      "market": "CN"
     }
    ]
   },
   "CN": {
    "survey": "Coresight China Consumer Survey",
    "headline": "In the latest China survey (9 Nov 2026), <em>56.0%</em> of adults in China expected the economy to be positive over the next 12 months; 13.6% expected it to be negative.",
    "cards": [
     {
      "label": "Positive",
      "value": "56.0%",
      "note": "9 Nov 2026",
      "tone": "main"
     },
     {
      "label": "Negative",
      "value": "13.6%",
      "note": "9 Nov 2026",
      "tone": ""
     },
     {
      "label": "Net",
      "value": "+42.4 pts",
      "note": "Positive minus negative",
      "tone": ""
     }
    ],
    "chart": {
     "kind": "columns",
     "title": "Expectations for the economy over the next 12 months",
     "unit": "% of adults in China, 9 Nov 2026",
     "bars": [
      {
       "label": "Positive",
       "pct": 56.0,
       "side": "pos"
      },
      {
       "label": "Same as now",
       "pct": 26.5,
       "side": ""
      },
      {
       "label": "Negative",
       "pct": 13.6,
       "side": "neg"
      },
      {
       "label": "Don't know",
       "pct": 3.8,
       "side": ""
      }
     ],
     "foot": [
      "Answers in the survey's own order. The two surveys word the question and its answers differently, so their figures are never added together."
     ]
    },
    "evidence": {
     "wording": [
      "What are your expectations for the economy over the next 12 months?"
     ],
     "source": "Coresight China Consumer Survey, 9 Nov 2026",
     "table": {
      "head": [
       "Answer",
       "Share"
      ],
      "rows": [
       [
        "Positive",
        "56.0%"
       ],
       [
        "Same as now",
        "26.5%"
       ],
       [
        "Negative",
        "13.6%"
       ],
       [
        "Don't know",
        "3.8%"
       ]
      ]
     }
    },
    "chips": [
     {
      "label": "By age group",
      "goto": "s9"
     },
     {
      "label": "By city tier"
     },
     {
      "label": "Same in the US",
      "market": "US"
     }
    ]
   }
  }
 },
 {
  "id": "s9",
  "level": "Complex",
  "type": "T12 China, by age group",
  "market": "CN",
  "survey": "Coresight China Consumer Survey",
  "question": "Which generation in China is most positive about the economy?",
  "headline": "The China survey records age groups, not generations. In the latest China survey (9 Nov 2026), adults in China aged 18-25, 26-41 and 42-57 were about equally likely to expect the economy to be positive over the next 12 months (<em>47.5% to 59.0%</em>); the differences could be chance.",
  "cards": [
   {
    "label": "Highest",
    "value": "59.0%",
    "tone": "main",
    "note": "Aged 26-41; about the same as 18-25 and 42-57"
   },
   {
    "label": "Lowest",
    "value": "47.5%",
    "note": "Aged 42-57",
    "tone": ""
   },
   {
    "label": "Difference",
    "value": "11.5 pts",
    "note": "Could be chance",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "columns",
   "title": "Expect the economy to be positive over the next 12 months, by age group",
   "unit": "% of each age group, China, 9 Nov 2026",
   "ranges": [
    "Latest survey",
    "Last 12 months"
   ],
   "bars": [
    {
     "label": "18-25",
     "pct": 53.0,
     "small": false
    },
    {
     "label": "26-41",
     "pct": 59.0,
     "small": false
    },
    {
     "label": "42-57",
     "pct": 47.5,
     "small": false
    },
    {
     "label": "57-76",
     "pct": 50.0,
     "small": true
    }
   ],
   "foot": [
    "The China survey records age groups, not generations.",
    "Fewer than 50 people answered in a hatched group: read with caution. Groups with fewer than 50 people are not compared."
   ]
  },
  "evidence": {
   "wording": [
    "What are your expectations for the economy over the next 12 months?"
   ],
   "source": "Coresight China Consumer Survey, 9 Nov 2026",
   "table": {
    "head": [
     "Age group",
     "Positive"
    ],
    "rows": [
     [
      "18-25",
      "53.0%"
     ],
     [
      "26-41",
      "59.0%"
     ],
     [
      "42-57",
      "47.5%"
     ],
     [
      "57-76",
      "50.0%"
     ]
    ]
   }
  },
  "alternatives": [],
  "chips": [
   {
    "label": "By city tier"
   },
   {
    "label": "By monthly income"
   },
   {
    "label": "Over time by age group"
   },
   {
    "label": "Same in the US",
    "goto": "s8"
   }
  ]
 },
 {
  "id": "s10",
  "level": "Hard",
  "type": "T15 Why question",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "Why did beauty purchases drop at the start of 2026?",
  "headline": "The surveys record what people did and said, not why. On 19 Jan 2026, <em>62.5%</em> of US adults said they bought beauty products in the past three months; the surveys before and after were 68.4% (27 Oct 2025) and 63.9% (13 Apr 2026). The fall from October could be chance, and it was the same question, asked the same way.",
  "cards": [
   {
    "label": "That reading",
    "value": "62.5%",
    "note": "19 Jan 2026",
    "tone": "main"
   },
   {
    "label": "Survey before",
    "value": "68.4%",
    "note": "27 Oct 2025",
    "tone": ""
   },
   {
    "label": "Survey after",
    "value": "63.9%",
    "note": "13 Apr 2026",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "line",
   "title": "Bought beauty products in the past three months",
   "unit": "% of US adults in each survey",
   "cadence": "quarterly",
   "grains": [
    "Quarterly"
   ],
   "ranges": [
    "Around the reading"
   ],
   "default_range": 0,
   "focus": "2026-01-19",
   "series": [
    {
     "name": "Bought beauty products",
     "points": [
      {
       "date": "2025-08-04",
       "n": 300,
       "b": 403
      },
      {
       "date": "2025-10-27",
       "n": 275,
       "b": 402
      },
      {
       "date": "2026-01-19",
       "n": 250,
       "b": 400
      },
      {
       "date": "2026-04-13",
       "n": 257,
       "b": 402
      },
      {
       "date": "2026-07-06",
       "n": 255,
       "b": 401
      }
     ]
    }
   ],
   "foot": [
    "The asked reading is circled. Each dot is one survey."
   ]
  },
  "evidence": {
   "wording": [
    "Have you purchased any beauty products (whether for men or women) in the past three months?"
   ],
   "source": "Coresight US Consumer Survey, 4 Aug 2025 to 6 Jul 2026",
   "table": {
    "head": [
     "Survey date",
     "Yes",
     "No"
    ],
    "rows": [
     [
      "6 Jul 2026",
      "63.6%",
      "36.4%"
     ],
     [
      "13 Apr 2026",
      "63.9%",
      "36.1%"
     ],
     [
      "19 Jan 2026",
      "62.5%",
      "37.5%"
     ],
     [
      "27 Oct 2025",
      "68.4%",
      "31.6%"
     ],
     [
      "4 Aug 2025",
      "74.4%",
      "25.6%"
     ]
    ]
   }
  },
  "alternatives": [],
  "chips": [
   {
    "label": "Compare Jan 2026 with the surveys either side"
   },
   {
    "label": "Why people buy beauty products (the reasons they gave)"
   },
   {
    "label": "Over time",
    "goto": "s2"
   }
  ]
 },
 {
  "id": "s11",
  "level": "Hard",
  "type": "T17 No survey asks this",
  "market": "US",
  "question": "How many Americans own an electric car?",
  "no_answer": {
   "text": "None of our surveys asks whether people own an electric car. These are the closest questions we have:",
   "closest": [
    "Categories people planned to buy during the Presidents' Day weekend, which include automobiles (Coresight US Consumer Survey, 12 Jan 2026)",
    "Holiday purchases in the last seven days (Coresight US Consumer Survey, 23 Nov 2026)",
    "What impact tariffs have on you personally (Coresight US Consumer Survey, 23 Nov 2026)"
   ]
  }
 },
 {
  "id": "s12",
  "level": "Hard",
  "type": "T5 Two periods compared",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "Are more people using AI tools like ChatGPT and Gemini than a year ago?",
  "headline": "Among US adults who have heard of at least one AI tool, use of Gemini rose from 34.6% (3 Nov 2025) to <em>45.2%</em> (2 Nov 2026); ChatGPT, Copilot, Perplexity, Grok and Deep Seek were about the same a year apart (ChatGPT 57.8% then, 63.3% now).",
  "cards": [
   {
    "label": "Gemini, 2 Nov 2026",
    "value": "45.2%",
    "note": "Of those who have heard of an AI tool",
    "tone": "main"
   },
   {
    "label": "Gemini, 3 Nov 2025",
    "value": "34.6%",
    "note": "A year earlier",
    "tone": ""
   },
   {
    "label": "Change",
    "value": "+10.6 pts",
    "note": "A real rise",
    "tone": "up"
   }
  ],
  "chart": {
   "kind": "paired",
   "title": "AI tools people have used",
   "unit": "% of US adults who have heard of at least one AI tool",
   "periods": [
    "3 Nov 2025",
    "2 Nov 2026"
   ],
   "bars": [
    {
     "label": "ChatGPT",
     "old": 57.8,
     "pct": 63.3
    },
    {
     "label": "Gemini",
     "old": 34.6,
     "pct": 45.2
    },
    {
     "label": "Copilot",
     "old": 18.6,
     "pct": 17.6
    },
    {
     "label": "Perplexity",
     "old": 8.1,
     "pct": 7.3
    },
    {
     "label": "Grok",
     "old": 7.6,
     "pct": 7.0
    },
    {
     "label": "Deep Seek",
     "old": 6.1,
     "pct": 6.2
    }
   ],
   "foot": [
    "People could choose more than one.",
    "Asked only of people who have heard of at least one of the tools listed."
   ]
  },
  "evidence": {
   "wording": [
    "Which of the following have you actually used?",
    "Asked of people who had heard of at least one tool in “Which of the following have you heard of?”"
   ],
   "source": "Coresight US Consumer Survey, 3 Nov 2025 and 2 Nov 2026",
   "table": {
    "head": [
     "Tool",
     "3 Nov 2025",
     "2 Nov 2026"
    ],
    "rows": [
     [
      "ChatGPT",
      "57.8%",
      "63.3%"
     ],
     [
      "Gemini",
      "34.6%",
      "45.2%"
     ],
     [
      "Copilot",
      "18.6%",
      "17.6%"
     ],
     [
      "Perplexity",
      "8.1%",
      "7.3%"
     ],
     [
      "Grok",
      "7.6%",
      "7.0%"
     ],
     [
      "Deep Seek",
      "6.1%",
      "6.2%"
     ]
    ]
   }
  },
  "alternatives": [
   "AI tools people have heard of (Coresight US Consumer Survey, last asked 2 Nov 2026)",
   "AI tools people used to help them shop (Coresight US Consumer Survey, last asked 3 Aug 2026)"
  ],
  "chips": [
   {
    "label": "Over time"
   },
   {
    "label": "By generation"
   },
   {
    "label": "AI used for shopping"
   }
  ]
 },
 {
  "id": "s13",
  "level": "Complex",
  "type": "T6 One group within another question",
  "market": "US",
  "survey": "Coresight US Consumer Survey",
  "question": "Among people who say tariffs hurt them, how many have changed how they shop?",
  "headline": "Among US adults who say tariffs have a negative impact on them, <em>53.2%</em> said they had changed their shopping to avoid the effects of tariffs in the latest survey (23 Nov 2026), compared with 42.6% of all US adults and 31.7% of everyone else, a real difference.",
  "cards": [
   {
    "label": "Say tariffs hurt them",
    "value": "53.2%",
    "note": "Changed how they shop",
    "tone": "main"
   },
   {
    "label": "All US adults",
    "value": "42.6%",
    "note": "Changed how they shop",
    "tone": ""
   },
   {
    "label": "Difference",
    "value": "21.5 pts",
    "note": "A real difference vs everyone else",
    "tone": ""
   }
  ],
  "chart": {
   "kind": "columns",
   "title": "Changed their shopping to avoid the effects of tariffs",
   "unit": "% of each group, US, 23 Nov 2026",
   "bars": [
    {
     "label": "Say tariffs hurt them",
     "pct": 53.2
    },
    {
     "label": "Everyone else",
     "pct": 31.7
    },
    {
     "label": "All US adults",
     "pct": 42.6
    }
   ],
   "foot": [
    "Counted person by person from the same survey's answers."
   ]
  },
  "evidence": {
   "wording": [
    "Have you changed your shopping behavior to avoid the effects of tariffs?",
    "Say tariffs hurt them: people who answered “very negative” or “somewhat negative” to “What impact, if any, do you think tariffs have on you personally?”"
   ],
   "source": "Coresight US Consumer Survey, 23 Nov 2026",
   "table": {
    "head": [
     "Group",
     "Changed how they shop"
    ],
    "rows": [
     [
      "Say tariffs hurt them",
      "53.2%"
     ],
     [
      "Everyone else",
      "31.7%"
     ],
     [
      "All US adults",
      "42.6%"
     ]
    ]
   }
  },
  "alternatives": [
   "How people changed their shopping to avoid tariffs (Coresight US Consumer Survey, last asked 23 Nov 2026)"
  ],
  "chips": [
   {
    "label": "How they changed it"
   },
   {
    "label": "Over time"
   },
   {
    "label": "Tariffs hurting people over time",
    "goto": "s7"
   }
  ]
 }
];
window.OPEN_QUESTIONS = [
 [
  "Show the word “unweighted” on answers?",
  "No. Say “Census-weighted figures” only when the weighted switch is on."
 ],
 [
  "Keep the number of people asked in the Excel export?",
  "No."
 ],
 [
  "Long ranked lists (retailers, products): vertical or horizontal bars?",
  "Vertical, as decided; the retailer mock-up shows both so you can choose."
 ],
 [
  "A weekly view for questions asked every week?",
  "No: monthly, quarterly and yearly only."
 ],
 [
  "A side-by-side option when both markets ask a question?",
  "No: two buttons, US results and China results."
 ],
 [
  "Does a country named in the question override the market selector?",
  "Yes: “Chinese consumers” answers from China whatever the selector says."
 ],
 [
  "Neutral or green/red arrows on changes?",
  "Neutral ink arrows: up is not always good (“worried about tariffs” up)."
 ],
 [
  "When two survey questions fit about equally: ask back first, or answer the best match and offer the other?",
  "Answer the best match and offer the others under “Not what you meant?” (today's behaviour)."
 ],
 [
  "How to warn about small samples without showing the number of people?",
  "“Fewer than 50 people answered here: read with caution.” Under 30, the figure is kept out of the headline and cards."
 ],
 [
  "A market ask-back and a question ask-back in the same answer?",
  "Ask the market only, then answer the best match and offer the others."
 ],
 [
  "The selected market does not ask the question at all (China selected, a US-only question)?",
  "Answer from the market that asks it and say so at the top of the answer."
 ]
];
